import copy
import json
from pydantic import BaseModel, Field
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmResponse
from google.genai import types

from features.agents.models import Models
from features.agents.marketing_agent.prompt import get_description, get_instruction
from shared.orm.entities.synthetic_text import SyntheticText


class AgentOutput(BaseModel):
    markdown: str = Field(description="The markdown of the agent output")
    text_for_tts: str = Field(description="The text for tts of the agent output")


async def after_model_callback(
    callback_context: CallbackContext, llm_response: LlmResponse
):
    # --- Inspection ---
    original_text = ""
    if llm_response.content and llm_response.content.parts:
        # Assuming simple text response for this example
        if llm_response.content.parts[0].text:
            original_text = llm_response.content.parts[0].text
            print(
                f"[Callback] Inspected original response text: '{original_text[:100]}...'"
            )  # Log snippet
        elif llm_response.content.parts[0].function_call:
            print(
                f"[Callback] Inspected response: Contains function call '{llm_response.content.parts[0].function_call.name}'. No text modification."
            )
            return None  # Don't modify tool calls in this example
        else:
            print("[Callback] Inspected response: No text content found.")
            return None
    elif llm_response.error_message:
        print(
            f"[Callback] Inspected response: Contains error '{llm_response.error_message}'. No modification."
        )
        return None
    else:
        print("[Callback] Inspected response: Empty LlmResponse.")
        return None  # Nothing to modify

    try:

        json_answer = json.loads(
            original_text.replace("```json", "").replace("```", "")
        )
        text = json_answer["text_for_tts"]
        markdown = json_answer["markdown"]
        id = callback_context.invocation_id.replace("-", "")

        synthetic_text = SyntheticText(
            text=text,
        )
        await synthetic_text.save(chosen_id=id)
        modified_parts = [copy.deepcopy(part) for part in llm_response.content.parts]
        modified_parts[0].text = markdown
        new_response = LlmResponse(
            content=types.Content(role="model", parts=modified_parts),
        )
        print(f"[Callback] Returning modified response.")
        return new_response  #

    except Exception as e:
        print(f"[Callback] Error parsing JSON: {e}")
        return original_text


root_agent = LlmAgent(
    name="marketing_agent",
    model=LiteLlm(model=Models.CLAUDE_SONNET),
    description=get_description(),
    instruction=get_instruction(),
    output_schema=AgentOutput,
    after_model_callback=after_model_callback,  # Le schéma est toujours défini ici pour l'agent
)
