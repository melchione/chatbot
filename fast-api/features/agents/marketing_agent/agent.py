from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from features.agents.models import Models

from features.agents.marketing_agent.prompt import get_description, get_instruction

root_agent = Agent(
    name="marketing_agent",
    model=LiteLlm(model=Models.CLAUDE_SONNET),
    description=get_description(),
    instruction=get_instruction(),
)
