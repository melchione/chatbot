import os
import logging
import base64  # Pour décoder les images
from typing import Any, Optional
from fastapi.middleware.cors import CORSMiddleware

import vertexai
from vertexai import agent_engines
from vertexai.generative_models import Content, Part  # Ajout pour multimodal
from google.api_core import exceptions as google_exceptions  # Ajout de l'import

# from google.generativeai.types import Content, Part, Blob # Mis en commentaire pour l'instant

from dotenv import load_dotenv

from fastapi import (
    FastAPI,
    Request,
    WebSocket,
    WebSocketDisconnect,
    HTTPException,  # Pour les erreurs HTTP si nécessaire
)
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import (
    Response,
    FileResponse,
)  # FileResponse pour servir index.html comme dans l'exemple
from fastapi.staticfiles import StaticFiles  # Pour servir des fichiers statiques
from pathlib import Path  # Pour la gestion des chemins
from contextlib import suppress

# Configuration du logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
)
logger = logging.getLogger(__name__)

# Charger les variables d'environnement
load_dotenv()

# --- Configuration Globale & Variables d'État ---
APP_NAME = "ChatbotFastAPIServer"
remote_app: Optional[Any] = None  # Référence à l'agent Vertex AI déployé

STATIC_DIR = (
    Path(__file__).parent / "static"
)  # Si vous voulez servir une UI de test simple

# --- Session Management (similaire à ADK, mais simplifié pour Vertex AI) ---
# Pour cet exemple, nous n'avons pas besoin d'un service de session complexe comme dans ADK
# car l'état est géré par l'objet `chat` de Vertex AI pour chaque connexion WebSocket.


async def initialize_vertex_ai_agent():
    """Initialise Vertex AI et récupère la référence à l'agent déployé."""
    global remote_app
    logger.info("Attempting to initialize Vertex AI and connect to the agent...")

    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("GOOGLE_CLOUD_LOCATION")
    agent_resource_id = os.getenv("AGENT_RESOURCE_ID")

    if not all([project_id, location, agent_resource_id]):
        logger.critical(
            "Missing critical environment variables for Vertex AI. Application might not work."
        )
        # Lever une exception ici pourrait être plus propre pour empêcher le démarrage
        raise RuntimeError(
            "Missing GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, or AGENT_RESOURCE_ID env vars."
        )

    try:
        vertexai.init(project=project_id, location=location)
        logger.info(
            f"Vertex AI initialized for project='{project_id}', location='{location}'."
        )

        remote_app = agent_engines.get(agent_resource_id)
        if remote_app:
            logger.info(f"Successfully connected to remote agent: {agent_resource_id}")
        else:
            logger.error(
                f"Failed to connect to remote agent (remote_app is None): {agent_resource_id}"
            )
            raise RuntimeError(f"Could not connect to agent {agent_resource_id}")
    except Exception as e:
        logger.exception(f"Fatal error during Vertex AI agent initialization: {e}")
        raise  # Relancer l'exception pour que FastAPI la gère au démarrage


# --- Application FastAPI ---
app = FastAPI(
    title=APP_NAME,
    docs_url="/docs" if os.getenv("ENVIRONMENT") != "production" else None,
    redoc_url=None,
    # on_startup est géré par @app.on_event("startup") maintenant
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,  # Si vous utilisez des cookies ou des en-têtes d'autorisation
    allow_methods=["*"],  # Ou spécifiez des méthodes comme ["GET", "POST"]
    allow_headers=["*"],  # Ou spécifiez des en-têtes autorisés
)


# --- Événements de Démarrage/Arrêt de FastAPI ---
@app.on_event("startup")
async def startup_event():
    logger.info("FastAPI server starting up...")
    try:
        await initialize_vertex_ai_agent()
        if not remote_app:
            logger.critical(
                "Vertex AI Remote App (agent) failed to initialize. WebSocket endpoint might not function."
            )
        else:
            logger.info("Vertex AI Remote App (agent) initialized successfully.")
    except Exception as e:
        logger.critical(f"Error during startup: {e}", exc_info=True)
        # Il pourrait être judicieux de ne pas démarrer l'application si l'agent ne s'initialise pas
        # Mais FastAPI continuera, donc nous loggons une erreur critique.


# --- Service de fichiers statiques --- (Ajout comme dans live_server.py)
if not STATIC_DIR.is_dir():
    logger.error(f"Static directory not found at {STATIC_DIR}. UI will not be served.")
else:
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    logger.info(f"Serving static files from {STATIC_DIR}")

    @app.get("/")
    async def read_index():
        index_path = STATIC_DIR / "index.html"
        if not index_path.is_file():
            logger.error("index.html not found in static directory.")
            return Response(content="index.html not found", status_code=404)
        logger.debug("Serving index.html")
        return FileResponse(str(index_path))


# --- WebSocket Endpoint --- (Inspiré de live_server.py et adapté pour Vertex AI)
@app.websocket("/ws/create_session/{client_id}")
async def create_session(websocket: WebSocket, client_id: str):
    await websocket.accept()
    logger.info("WebSocket client connected for session creation.")

    remote_session = remote_app.create_session(user_id=client_id)
    session_id = remote_session["id"]

    await websocket.send_json({"type": "session_created", "session_id": session_id})

    # Générer un ID de session unique


# --- WebSocket Endpoint ---
@app.websocket("/ws/{client_id}/{session_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str, session_id: str):
    await websocket.accept()
    logger.info(
        f"WebSocket client connected: User ID '{client_id}' with Session ID '{session_id}'."
    )

    if not remote_app:
        logger.error(
            f"Remote app (Vertex AI agent) not initialized. Closing WebSocket for client {client_id}."
        )
        await websocket.send_json(
            {"type": "error", "message": "Chat service not available."}
        )
        await websocket.close(
            code=1011, reason="Chat service not available (agent missing)"
        )
        return

    # Envoyer un statut de connexion une fois que remote_app est confirmé
    await websocket.send_json({"type": "status", "message": "Agent service connected"})

    try:
        while True:
            client_message_json = await websocket.receive_json()
            logger.info(f"Client {client_id} sent JSON: {client_message_json}")

            message_type = client_message_json.get("type")
            message_data = client_message_json.get("data")

            query_input: Any = None

            if message_type == "text":
                if isinstance(message_data, str):
                    query_input = message_data
                else:
                    logger.warning(
                        f"Received text message with invalid data payload: {message_data}"
                    )
                    await websocket.send_json(
                        {"type": "error", "message": "Invalid text payload."}
                    )
                    continue
            elif message_type == "image":
                if isinstance(
                    message_data, str
                ):  # Assuming data is base64 string for image
                    mime_type = client_message_json.get(
                        "mime_type", "image/png"
                    )  # Default to png if not specified
                    prompt = client_message_json.get(
                        "prompt", ""
                    )  # Optional accompanying prompt

                    try:
                        image_bytes = base64.b64decode(message_data)
                        image_part = Part.from_data(
                            data=image_bytes, mime_type=mime_type
                        )
                        parts = []
                        if prompt:
                            parts.append(Part.from_text(prompt))
                        parts.append(image_part)
                        query_input = Content(parts=parts)
                        logger.info(
                            f"Prepared image content for agent (prompt: '{prompt}', mime_type: {mime_type})"
                        )
                    except Exception as e:
                        logger.error(f"Error processing image data: {e}", exc_info=True)
                        await websocket.send_json(
                            {"type": "error", "message": "Error processing image data."}
                        )
                        continue
                else:
                    logger.warning(
                        f"Received image message with invalid data payload: {message_data}"
                    )
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": "Invalid image payload (expected base64 string).",
                        }
                    )
                    continue
            else:
                logger.warning(f"Unknown message type received: {message_type}")
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": f"Unknown message type: {message_type}",
                    }
                )
                continue

            if query_input is None:
                logger.info(
                    f"No valid query_input to send to agent for client {client_id}."
                )
                await websocket.send_json(
                    {"type": "message_end"}
                )  # Send message_end to signify processing turn complete
                continue

            logger.info(
                f"Sending to agent for client {client_id} (session {session_id}): {type(query_input)}"
            )

            # Utiliser remote_app.stream_query() avec les paramètres spécifiés
            stream = remote_app.stream_query(
                user_id=client_id,  # Utiliser le client_id de l'URL comme user_id
                session_id=session_id,
                message=query_input,  # Peut être str ou Content
            )

            event_received = False
            for event in stream:  # Itérer sur les événements du stream
                event_received = True
                text_content = None
                try:
                    if (
                        isinstance(event, dict)
                        and "content" in event
                        and isinstance(event["content"], dict)
                        and "parts" in event["content"]
                        and isinstance(event["content"]["parts"], list)
                        and len(event["content"]["parts"]) > 0
                        and isinstance(event["content"]["parts"][0], dict)
                        and "text" in event["content"]["parts"][0]
                    ):
                        text_content = event["content"]["parts"][0]["text"]
                except Exception as e:
                    logger.warning(
                        f"Error accessing text in event structure: {e} - Event: {event}"
                    )

                if text_content:
                    logger.debug(
                        f"Agent response event for {client_id} (session: {session_id}): {text_content}"
                    )
                    await websocket.send_json(
                        {"type": "message_part", "text": text_content}
                    )
                else:
                    # Log l'événement brut si le texte n'a pas pu être extrait selon le chemin attendu
                    logger.debug(
                        f"Agent response event for {client_id} (session: {session_id}) (raw or no extractable text): {event}"
                    )

            if not event_received:
                logger.info(
                    f"No events received from agent for client {client_id} after stream_query with input type '{message_type}'."
                )

            await websocket.send_json({"type": "message_end"})
            logger.info(f"Finished streaming agent response to client {client_id}")

    except WebSocketDisconnect:
        logger.info(f"WebSocket client {client_id} disconnected.")
    except google_exceptions.GoogleAPIError as e:
        logger.error(
            f"Google API error during chat with {client_id}: {e}", exc_info=True
        )
        error_message = f"An error occurred with the chat service: {type(e).__name__}"
        if hasattr(e, "message"):
            error_message += f" - {e.message}"
        try:
            await websocket.send_json({"type": "error", "message": error_message})
        except Exception as send_err:
            logger.error(f"Failed to send error to client {client_id}: {send_err}")
    except Exception as e:
        logger.error(
            f"Error in WebSocket endpoint for client {client_id}: {e}", exc_info=True
        )
        try:
            await websocket.send_json(
                {"type": "error", "message": "An unexpected error occurred."}
            )
        except Exception as send_err:
            logger.error(
                f"Failed to send unexpected error to client {client_id}: {send_err}"
            )
    finally:
        logger.info(f"Closing WebSocket connection for client {client_id}.")
        # Pas besoin de `chat.close()` explicitement ici, la session est gérée par l'objet chat.
        # Si des ressources spécifiques devaient être libérées, ce serait ici.
        with suppress(Exception):
            await websocket.close()


# --- Nouvel Endpoint HTTP pour récupérer l'historique de session ---
@app.get("/session_history/{user_id}/{session_id}")
async def get_session_history(user_id: str, session_id: str):
    logger.info(
        f"Attempting to retrieve session history for User ID: {user_id}, Session ID: {session_id}"
    )
    if not remote_app:
        logger.error(
            "Remote app (Vertex AI agent) not initialized. Cannot fetch session history."
        )
        raise HTTPException(status_code=503, detail="Chat service not available.")

    try:
        session_data = remote_app.get_session(user_id=user_id, session_id=session_id)
        if session_data and "events" in session_data:
            logger.info(
                f"Successfully retrieved {len(session_data['events'])} events for session {session_id}."
            )
            return {"events": session_data["events"]}
        elif (
            session_data
        ):  # session_data existe mais pas d'events (peu probable avec la structure donnée)
            logger.warning(
                f"Session {session_id} found but no 'events' key or events are empty."
            )
            return {"events": []}
        else:
            logger.warning(
                f"Session not found for User ID: {user_id}, Session ID: {session_id}"
            )
            # Il est important de ne pas lever une erreur 404 ici si une session non trouvée est un cas "normal"
            # pour le client qui essaie de charger l'historique. Le client peut créer une nouvelle session.
            # Renvoyer une liste vide permet au client de continuer sans erreur bloquante.
            return {"events": []}
    except google_exceptions.NotFound:
        logger.warning(
            f"Session not found via Google API for User ID: {user_id}, Session ID: {session_id}"
        )
        return {
            "events": []
        }  # Traiter comme non trouvé, le client créera une nouvelle session
    except Exception as e:
        logger.error(
            f"Error retrieving session history for User ID: {user_id}, Session ID: {session_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Error retrieving session history.")


# --- Lancement du serveur (pour exécution directe avec Uvicorn) ---
if __name__ == "__main__":
    # Assurez-vous que les variables d'environnement sont chargées si ce n'est déjà fait
    load_dotenv()

    server_host = os.getenv("SERVER_HOST", "127.0.0.1")
    raw_port = os.getenv("SERVER_PORT", "8000")
    server_port = 8000  # Valeur par défaut si la conversion échoue
    try:
        server_port = int(raw_port)
    except ValueError:
        logger.warning(
            f"Invalid SERVER_PORT: '{raw_port}'. Defaulting to {server_port}."
        )

    logger.info(
        f"Starting FastAPI server (direct run) on http://{server_host}:{server_port}"
    )
    try:
        import uvicorn

        uvicorn.run(app, host=server_host, port=server_port, log_level="info")
    except ImportError:
        logger.critical("Uvicorn not installed. Run 'pip install uvicorn[standard]'.")
    except Exception as startup_error:
        logger.critical(
            f"Failed to start Uvicorn server: {startup_error}", exc_info=True
        )
