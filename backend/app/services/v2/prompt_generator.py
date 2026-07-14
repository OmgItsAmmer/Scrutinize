import logging

from app.core.config import Settings
from app.services.v2.json_utils import parse_json_object
from app.services.v2.llm_clients.cloud import CloudLlmClient
from app.services.v2.llm_clients.local import LocalLlmClient
from app.services.v2.prompts import load_prompt

logger = logging.getLogger(__name__)

_REQUIRED_KEYS = ("gate", "rewriter", "generic", "synthesis", "decision")

AVAILABLE_TOOLS = (
    "- generate_pdf: Create a downloadable PDF document from synthesized project content. "
    "The gate agent must set requested_tool to \"generate_pdf\" when the user asks for a PDF, "
    "report, handout, document, export, downloadable write-up, slides, flowchart artifact, "
    "or any equivalent file and the topic is within the project scope. "
    "For in-scope PDF/export requests, route MUST be \"rag\" (or \"web\"/\"hybrid\" if web data "
    "is also needed) — never \"generic\"."
)


def _build_system_instruction(name: str, description: str) -> str:
    gate_template = load_prompt("rag_gate_system.txt")
    decision_template = load_prompt("decision_agent_system.txt")

    return (
        "You are an expert prompt engineer. Your task is to generate customized system prompts "
        "for five different agents in a RAG-powered chatbot pipeline named Scrutinize.\n\n"
        "Project details:\n"
        f"- Project Name: {name}\n"
        f"- Project Description (also defines in-scope topics and refusal boundaries): {description}\n\n"
        "Available application tools (the gate agent MUST document and route these):\n"
        f"{AVAILABLE_TOOLS}\n\n"
        "Agent responsibilities:\n"
        "1. 'gate': Classifies/routes the user query. It MUST inspect whether the query is within "
        "the project description scope. If out-of-scope, route to 'generic' and provide a polite "
        "decline in reply. It MUST preserve tool routing via requested_tool. "
        "In-scope PDF/export requests MUST route to 'rag' (not 'generic') with "
        "requested_tool=\"generate_pdf\" and reply=null.\n"
        "2. 'rewriter': Rewrites user queries for optimal keyword document search within project scope.\n"
        "3. 'generic': Handles greetings, small talk, and out-of-scope questions with polite scope boundaries.\n"
        "4. 'synthesis': Answers using only retrieved document sources. If information is missing, "
        "respond exactly: 'I could not find sufficient information in the provided sources.'\n"
        "5. 'decision': Evaluates whether routing and the draft answer were correct; verdict is "
        "'good' or 'retry'.\n\n"
        "CRITICAL — the generated 'gate' prompt MUST instruct the agent to return JSON only using "
        "this exact schema (adapt scope/rules to the project, but keep keys and enum values unchanged):\n"
        f"{gate_template}\n\n"
        "CRITICAL — the generated 'decision' prompt MUST instruct the agent to return JSON only using "
        "this exact schema (adapt evaluation rules to the project, but keep keys and enum values unchanged):\n"
        f"{decision_template}\n\n"
        "The gate prompt MUST mention all available application tools listed above and explain when "
        "to set requested_tool to \"generate_pdf\" versus null.\n"
        "The decision prompt MUST explain how to evaluate PDF/document/tool requests and when to "
        "retry with correct_route \"rag\".\n\n"
        "You MUST return a JSON object with exactly the keys: 'gate', 'rewriter', 'generic', "
        "'synthesis', 'decision'. Each value must be the full system prompt string for that agent."
    )


def generate_project_prompts(
    name: str,
    description: str,
    settings: Settings,
) -> dict[str, str]:
    """
    Generates customized system prompts for the five agent types:
    gate, rewriter, generic, synthesis, decision.
    Tries the local LLM 'qwen3.5:2b' first, falling back to cloud OpenAI 'gpt-4o-mini'.
    """
    system_instruction = _build_system_instruction(name, description)
    user_prompt = "Generate the JSON object containing the five system prompts."

    if settings.local_llm_base_url:
        try:
            logger.info("Attempting to generate project prompts using local LLM 'qwen3.5:2b'...")
            local_client = LocalLlmClient(settings)
            response = local_client.generate(
                model="qwen3.5:2b",
                system=system_instruction,
                user=user_prompt,
                json_mode=True,
            )
            data = parse_json_object(response.content)
            if all(k in data for k in _REQUIRED_KEYS):
                logger.info("Successfully generated project prompts using local LLM.")
                return {key: str(data[key]) for key in _REQUIRED_KEYS}
            logger.warning("Local LLM returned incomplete JSON keys: %s. Falling back...", data.keys())
        except Exception as exc:
            logger.warning("Failed to generate prompts using local LLM: %s. Falling back to cloud LLM...", exc)

    try:
        logger.info("Attempting to generate project prompts using cloud LLM 'gpt-4o-mini'...")
        cloud_client = CloudLlmClient(settings)
        response = cloud_client.generate(
            model="gpt-4o-mini",
            system=system_instruction,
            user=user_prompt,
            json_mode=True,
        )
        data = parse_json_object(response.content)
        if all(k in data for k in _REQUIRED_KEYS):
            logger.info("Successfully generated project prompts using cloud LLM.")
            return {key: str(data[key]) for key in _REQUIRED_KEYS}
        raise ValueError(f"Cloud LLM returned incomplete JSON keys: {data.keys()}")
    except Exception as exc:
        logger.error("Failed to generate prompts using cloud LLM fallback: %s", exc)
        raise RuntimeError(f"Could not generate project prompts from LLMs: {exc}") from exc
