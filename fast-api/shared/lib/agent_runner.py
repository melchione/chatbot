import json
import base64
import asyncio
import os
from typing import Type, TypeVar, Optional, Dict, Any
from pydantic import BaseModel, ValidationError
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types


# Importer les variables de contexte
from features.agents.models import Models

T = TypeVar("T", bound=BaseModel)


async def run_agent_with_retry(
    agent: LlmAgent,
    user_input_text: str,
    output_schema: Type[T] | None = None,
    retry_count: int = 3,
    app_name: str = "agency_flow",
    fallback_model_name: Optional[str | LiteLlm] = Models.GEMINI_25_PRO,
    fallback_retry_count: Optional[int] = None,
    files: Optional[list[str]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Exécute un agent LLM, parse la sortie JSON et réessaie. Utilise un fallback si nécessaire.

    Args:
        agent: L'instance LlmAgent.
        output_schema: Classe Pydantic BaseModel pour validation.
        user_input_text: Entrée utilisateur.
        retry_count: Tentatives pour le modèle principal.
        app_name: Nom de l'application pour la session.
        fallback_model_name: Nom du modèle LLM de fallback. Si None, pas de fallback.
        fallback_retry_count: Tentatives pour le fallback. Si None, utilise retry_count.

    Returns:
        Dictionnaire du JSON validé, ou None si échec final.
    """
    user_id = "admin"
    session_id = "admin"
    original_model = agent.model
    result: Optional[Dict[str, Any]] = None

    if not user_id or not session_id:
        print("Erreur: Contexte user_id/session_id manquant.")
        return None

    session_service = InMemorySessionService()
    try:
        await session_service.create_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )
    except Exception as e:
        print(f"Avertissement: Création session échouée (peut exister): {e}")

    runner = Runner(agent=agent, app_name=app_name, session_service=session_service)
    parts = [types.Part(text=user_input_text)]
    if files:
        for file in files:
            # Séparation préfixe ↔ données
            prefix, b64_image = file.split(",", 1)
            mime_type = prefix.split(":")[1].split(";")[0]  # -> "image/png"

            # --- 3) Décodage Base64 vers bytes
            img_bytes = base64.b64decode(b64_image)

            # --- 4) Création du Part multimédia
            image_part = types.Part(
                inline_data=types.Blob(data=img_bytes, mime_type=mime_type)
            )
            parts.append(image_part)

    user_content = types.Content(role="user", parts=parts)

    phases = [("principal", agent.model, retry_count)]
    if fallback_model_name:
        effective_fallback_retry_count = (
            fallback_retry_count if fallback_retry_count is not None else retry_count
        )
        phases.append(
            (
                "fallback",
                fallback_model_name,
                effective_fallback_retry_count,
            )
        )

    try:
        for phase_name, current_model_instance, max_attempts in phases:
            print(
                f"\n--- Démarrage phase '{phase_name}' avec modèle: {getattr(current_model_instance, 'model', 'Inconnu')} ({max_attempts} tentatives) ---"
            )
            agent.model = current_model_instance

            # Recréer le runner si le modèle a changé (plus sûr)
            runner = Runner(
                agent=agent, app_name=app_name, session_service=session_service
            )

            for attempt in range(max_attempts):
                print(
                    f"--- Tentative {phase_name} {attempt + 1}/{max_attempts} pour l'agent {agent.name} ---"
                )
                final_response_content = None
                try:
                    async for event in runner.run_async(
                        user_id=user_id, session_id=session_id, new_message=user_content
                    ):
                        if (
                            event.is_final_response()
                            and event.content
                            and event.content.parts
                        ):
                            final_response_content = event.content.parts[0].text
                            print(
                                f"<<< Réponse brute (tentative {phase_name} {attempt + 1}): {final_response_content}"
                            )
                            break

                    if final_response_content:
                        try:
                            if not output_schema:
                                return final_response_content

                            final_response_content = final_response_content.replace(
                                "```json", ""
                            ).replace("```", "")

                            output_data = json.loads(final_response_content)
                            validated_output = output_schema(**output_data)
                            print(
                                f"--- Réponse structurée validée (tentative {phase_name} {attempt + 1}) ---"
                            )
                            result = validated_output.model_dump()
                            # Sortir de toutes les boucles dès qu'un succès est obtenu
                            return result
                        except (json.JSONDecodeError, ValidationError) as e:
                            print(
                                f"Erreur parsing/validation (tentative {phase_name} {attempt + 1}): {e}"
                            )
                            print(f"Réponse brute: {final_response_content}")
                        except Exception as e:
                            print(
                                f"Erreur inattendue traitement (tentative {phase_name} {attempt + 1}): {e}"
                            )
                            print(f"Réponse brute: {final_response_content}")
                    else:
                        print(
                            f"Aucune réponse finale reçue (tentative {phase_name} {attempt + 1})."
                        )

                except Exception as e:
                    print(
                        f"Erreur exécution agent (tentative {phase_name} {attempt + 1}): {e}"
                    )

                if attempt < max_attempts - 1:
                    await asyncio.sleep(
                        1
                    )  # Pause avant prochaine tentative de la phase

            # Si on arrive ici, la phase actuelle a échoué
            print(
                f"--- Échec de la phase '{phase_name}' après {max_attempts} tentatives. ---"
            )
            # Si c'était la phase principale et qu'il n'y a pas de fallback, on peut arrêter
            if phase_name == "principal" and len(phases) == 1:
                break

    finally:
        # Assurer la restauration du modèle original quoi qu'il arrive
        agent.model = original_model
        print(
            f"\n--- Fin de l'exécution. Modèle de l'agent restauré à l'original: {getattr(original_model, 'model', 'Inconnu')}. Résultat: {'Succès' if result else 'Échec'} ---"
        )

    # Si on arrive ici, toutes les phases (y compris fallback si tenté) ont échoué
    return result  # Retourne None si aucun succès
