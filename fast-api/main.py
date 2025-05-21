import os
import logging
import base64
import uuid  # Ajout pour générer des session_id uniques
from typing import Any, Optional

from features.agents.marketing_agent.agent import root_agent  # Votre import

from fastapi.middleware.cors import CORSMiddleware

# Imports ADK
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
import google.genai as genai  # Pour genai.types

from dotenv import load_dotenv

from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    HTTPException,
)
from starlette.responses import (
    FileResponse,
)
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from contextlib import suppress

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
)
logger = logging.getLogger(__name__)

load_dotenv()

APP_NAME = "ChatbotFastAPIServerWithADK"  # Nom mis à jour
APP_NAME_ADK = "ChatbotLocalADK"  # Nom spécifique pour ADK

agent_runner: Optional[Runner] = None
session_service = DatabaseSessionService(db_url="sqlite:///database/sessions.db")


STATIC_DIR = Path(__file__).parent / "static"

# Commenter/Supprimer l'initialisation de l'agent Vertex AI distant
# async def initialize_vertex_ai_agent(): ...

app = FastAPI(
    title=APP_NAME,
    docs_url="/docs" if os.getenv("ENVIRONMENT") != "production" else None,
    redoc_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    global agent_runner
    logger.info("FastAPI server starting up for local ADK agent...")
    try:
        # Initialiser le Runner ADK
        agent_runner = Runner(
            agent=root_agent, app_name=APP_NAME_ADK, session_service=session_service
        )
        if agent_runner:
            logger.info(
                f"ADK Runner initialized successfully for agent '{root_agent.name}' and app '{APP_NAME_ADK}'."
            )
        else:
            logger.critical("ADK Runner failed to initialize.")
            # Vous pourriez vouloir empêcher le démarrage ici si le runner est crucial
    except Exception as e:
        logger.critical(f"Error during ADK Runner initialization: {e}", exc_info=True)
        # Gérer l'erreur comme il convient (par exemple, ne pas démarrer le serveur)


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
            return {"error": "index.html not found"}, 404
        logger.debug("Serving index.html")
        return FileResponse(str(index_path))


@app.websocket("/ws/create_session/{client_id}")
async def create_session_adk(websocket: WebSocket, client_id: str):
    await websocket.accept()
    logger.info(
        f"ADK WebSocket client connected for session creation: User ID '{client_id}'."
    )

    session_id = str(uuid.uuid4())  # Générer un ID de session unique

    try:
        session = await session_service.create_session(
            app_name=APP_NAME_ADK, user_id=client_id, session_id=session_id
        )
        logger.info(f"Session créée: {session}")
    except Exception as e:
        logger.warning(f"Création session échouée (peut exister): {e}")

    try:
        await websocket.send_json({"type": "session_created", "session_id": session_id})
    except Exception as e:
        logger.error(
            f"Failed to create ADK session for user '{client_id}': {e}", exc_info=True
        )
        await websocket.send_json(
            {"type": "error", "message": f"Failed to create session: {str(e)}"}
        )
        await websocket.close(code=1011, reason="Session creation failed")


@app.websocket("/ws/{client_id}/{session_id}")
async def websocket_endpoint_adk(websocket: WebSocket, client_id: str, session_id: str):
    await websocket.accept()
    logger.info(
        f"ADK WebSocket client connected: User ID '{client_id}' with Session ID '{session_id}'."
    )

    if not agent_runner:
        logger.error(
            "ADK Runner not initialized. Closing WebSocket for client {client_id}."
        )
        await websocket.send_json(
            {"type": "error", "message": "Chat service (ADK Runner) not available."}
        )
        await websocket.close(
            code=1011, reason="Chat service not available (ADK Runner missing)"
        )
        return

    await websocket.send_json(
        {"type": "status", "message": "ADK Agent service connected"}
    )

    try:
        while True:
            client_message_json = await websocket.receive_json()
            logger.info(f"Client {client_id} (ADK) sent JSON: {client_message_json}")

            message_type = client_message_json.get("type")
            message_data = client_message_json.get(
                "data"
            )  # Chaîne texte ou chaîne base64 pour image

            user_content: Optional[genai.types.Content] = None
            parts_for_content = []

            if message_type == "text":
                if isinstance(message_data, str):
                    parts_for_content.append(genai.types.Part(text=message_data))
                else:
                    logger.warning(
                        f"Received ADK text message with invalid data payload: {message_data}"
                    )
                    await websocket.send_json(
                        {"type": "error", "message": "Invalid text payload."}
                    )
                    continue

            elif message_type == "image":
                mime_type = client_message_json.get("mime_type", "image/png")
                prompt = client_message_json.get("prompt", "")

                if not isinstance(
                    message_data, str
                ):  # message_data doit être une chaîne base64
                    logger.warning(
                        f"Received ADK image message with invalid data (not string): {message_data}"
                    )
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": "Invalid image payload (expected base64 string).",
                        }
                    )
                    continue

                try:
                    if prompt:  # Texte en premier
                        parts_for_content.append(genai.types.Part(text=prompt))

                    image_bytes = base64.b64decode(message_data)
                    image_blob = genai.types.Blob(mime_type=mime_type, data=image_bytes)
                    image_part = genai.types.Part(inline_data=image_blob)
                    parts_for_content.append(image_part)

                    logger.info(
                        f"Prepared ADK image content (prompt: '{prompt}', mime_type: {mime_type})"
                    )
                except base64.binascii.Error as b64_error:
                    logger.error(
                        f"Error decoding base64 image data for ADK: {b64_error}",
                        exc_info=True,
                    )
                    await websocket.send_json(
                        {"type": "error", "message": "Invalid base64 image data."}
                    )
                    continue
                except Exception as e:
                    logger.error(f"Error processing ADK image data: {e}", exc_info=True)
                    await websocket.send_json(
                        {"type": "error", "message": "Error processing image data."}
                    )
                    continue

            else:
                logger.warning(f"Unknown ADK message type received: {message_type}")
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": f"Unknown message type: {message_type}",
                    }
                )
                continue

            if not parts_for_content:
                logger.info(
                    f"No content parts to send to ADK agent for client {client_id}."
                )
                await websocket.send_json({"type": "message_end"})
                continue

            user_content = genai.types.Content(parts=parts_for_content, role="user")
            logger.debug(
                f"Sending to ADK agent for client {client_id} (session {session_id}): {str(user_content)}"
            )

            event_received_count = 0
            async for event in agent_runner.run_async(
                user_id=client_id,
                session_id=session_id,
                new_message=user_content,
            ):
                event_received_count += 1
                logger.debug(
                    f"ADK Agent event for {client_id} (session: {session_id}): RAW EVENT: {event}"
                )

                # Adapter l'extraction du texte selon la structure des événements ADK
                text_content = None
                if event.is_final_response() and event.content and event.content.parts:
                    text_content = event.content.parts[0].text
                    logger.info(
                        f"ADK Agent FINAL response for {client_id}: {text_content}"
                    )
                    await websocket.send_json(
                        {"type": "message_part", "text": text_content, "is_final": True}
                    )
                elif (
                    event.content and event.content.parts
                ):  # Pour les parties intermédiaires
                    # Il faudra peut-être ajuster cela si les événements ADK ont une structure différente pour les message_part
                    # Pour l'instant, on suppose que les parties de contenu intermédiaires ont aussi du texte
                    intermediate_text = event.content.parts[0].text
                    if intermediate_text:
                        logger.info(
                            f"ADK Agent INTERMEDIATE response for {client_id}: {intermediate_text}"
                        )
                        await websocket.send_json(
                            {
                                "type": "message_part",
                                "text": intermediate_text,
                                "is_final": False,
                            }
                        )

            if event_received_count == 0:
                logger.info(
                    f"No events received from ADK agent for client {client_id} after run_async with input type '{message_type}'."
                )

            await websocket.send_json({"type": "message_end"})
            logger.info(f"Finished streaming ADK agent response to client {client_id}")

    except WebSocketDisconnect:
        logger.info(f"ADK WebSocket client {client_id} disconnected.")
    except Exception as e:
        logger.error(
            f"Error in ADK WebSocket endpoint for client {client_id}: {e}",
            exc_info=True,
        )
        try:
            await websocket.send_json(
                {
                    "type": "error",
                    "message": "An unexpected error occurred with ADK agent.",
                }
            )
        except Exception as send_err:
            logger.error(
                f"Failed to send unexpected ADK error to client {client_id}: {send_err}"
            )
    finally:
        logger.info(f"Closing ADK WebSocket connection for client {client_id}.")
        with suppress(Exception):  # Safely attempt to close
            await websocket.close()


# --- Endpoint HTTP pour récupérer l'historique de session (Adaptation pour ADK) ---
@app.get("/session_history/{user_id}/{session_id}")
async def get_session_history_adk(user_id: str, session_id: str):
    logger.info(
        f"Attempting to retrieve ADK session history for User ID: {user_id}, Session ID: {session_id}"
    )
    try:
        session_data = await session_service.get_session(
            app_name=APP_NAME_ADK, user_id=user_id, session_id=session_id
        )
        if session_data and hasattr(session_data, "events") and session_data.events:
            # Convertir l'historique des messages (objets Content) en un format sérialisable JSON
            # que le client peut comprendre. Par exemple, une liste de dictionnaires.
            serializable_history = []
            for msg_content in session_data.events:
                # On peut utiliser model_dump_json ou construire un dictionnaire manuellement
                # Pour la simplicité, on va juste prendre le texte de la première partie si disponible.
                # Le client devra être adapté si une structure plus riche est nécessaire.

                # Préparer la structure pour les "parts" du contenu
                serialized_parts = []
                if msg_content.content and msg_content.content.parts:
                    for part in msg_content.content.parts:
                        part_dict = {}
                        if part.text:
                            part_dict["text"] = part.text
                        elif part.inline_data and part.inline_data.data:
                            # Assurer l'encodage Base64 pour les données binaires de l'image
                            base64_encoded_data = base64.b64encode(
                                part.inline_data.data
                            ).decode("utf-8")
                            part_dict["inlineData"] = {
                                "mimeType": part.inline_data.mime_type,
                                "data": base64_encoded_data,
                            }

                        # N'ajouter la partie que si elle n'est pas vide
                        if part_dict:
                            serialized_parts.append(part_dict)

                # Construire l'objet de contenu sérialisé
                serialized_content = {
                    "parts": serialized_parts,
                    "role": (
                        msg_content.content.role if msg_content.content else "unknown"
                    ),
                }

                serializable_history.append(
                    {
                        "author": msg_content.author,
                        "content": serialized_content,  # Utiliser le contenu sérialisé
                        "id": msg_content.id,
                        # Simplifié, ne gère pas les images dans l'historique pour l'instant
                        # Idéalement, ici on sérialiserait toute la structure de Content
                    }
                )
            logger.info(
                f"Successfully retrieved {len(serializable_history)} messages from ADK session {session_id}."
            )
            return {
                "events": serializable_history
            }  # "events" est gardé pour compatibilité client
        else:
            logger.warning(
                f"ADK Session not found or history empty for User ID: {user_id}, Session ID: {session_id}"
            )
            return {"events": []}
    # Gérer les exceptions spécifiques à InMemorySessionService si nécessaire, sinon une Exception générale suffit.
    except Exception as e:
        logger.error(
            f"Error retrieving ADK session history for User ID: {user_id}, Session ID: {session_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail="Error retrieving ADK session history."
        )


if __name__ == "__main__":
    load_dotenv()
    server_host = os.getenv("SERVER_HOST", "127.0.0.1")
    raw_port = os.getenv("SERVER_PORT", "8000")
    server_port = 8000
    try:
        server_port = int(raw_port)
    except ValueError:
        logger.warning(
            f"Invalid SERVER_PORT: '{raw_port}'. Defaulting to {server_port}."
        )

    logger.info(
        f"Starting FastAPI server (direct run with ADK) on http://{server_host}:{server_port}"
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
