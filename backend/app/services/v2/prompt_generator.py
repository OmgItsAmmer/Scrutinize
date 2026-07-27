import logging
from uuid import UUID
from sqlmodel import Session, select

from app.core.config import Settings
from app.services.v2.json_utils import parse_json_object
from app.services.v2.llm_clients.cloud import CloudLlmClient
from app.services.v2.llm_clients.local import LocalLlmClient
from app.services.v2.prompts import load_prompt
from app.services.v2.llm_clients import BaseLlmClient

logger = logging.getLogger(__name__)

_REQUIRED_KEYS = ("gate", "rewriter", "generic", "synthesis", "decision", "visual_svg")

AVAILABLE_TOOLS = (
    "- generate_pdf: Create a downloadable PDF document from synthesized project content. "
    "The gate agent must set requested_tool to \"generate_pdf\" when the user asks for a PDF, "
    "report, handout, document, export, downloadable write-up, slides, "
    "or any equivalent file and the topic is within the project scope. "
    "For in-scope PDF/export requests, route MUST be \"rag\" (or \"web\"/\"hybrid\" if web data "
    "is also needed) — never \"generic\".\n"
    "- generate_flowchart: Create a Mermaid flowchart diagram representing processes, architectures, or workflows. "
    "The gate agent must set requested_tool to \"generate_flowchart\" when the user asks for a flowchart, "
    "diagram, visual process, sequence diagram, Mermaid code, or any visual workflow mapping. "
    "For flowchart requests, route MUST be \"rag\" (or \"web\"/\"hybrid\") — never \"generic\".\n"
    "- web_search: Search the web for real-time technology/AI news, startup funding, or recent tech developments. "
    "The gate agent must select route as \"web\" or \"hybrid\" (or request tool \"web_search\") when the user query requires "
    "real-time/recent information not covered in local documents."
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
        "requested_tool=\"generate_pdf\" and reply=null. "
        "In-scope flowchart/diagram requests MUST route to 'rag' (not 'generic') with "
        "requested_tool=\"generate_flowchart\" and reply=null.\n"
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
        "to set requested_tool to \"generate_pdf\" or \"generate_flowchart\" versus null.\n"
        "The decision prompt MUST explain how to evaluate PDF/document/flowchart/tool requests and when to "
        "retry with correct_route \"rag\".\n\n"
        "You MUST return a JSON object with exactly the keys: 'gate', 'rewriter', 'generic', "
        "'synthesis', 'decision', 'visual_svg'. Each value must be the full system prompt string for that agent, "
        "except 'visual_svg' which must be a valid, raw, modern, beautiful, and self-contained SVG code "
        "representing the project visually based on the project name and description.\n"
        "SVG Design Guidelines:\n"
        "- Must use viewBox='0 0 200 150' to fit the card header aspect ratio.\n"
        "- First of all, read the project name and description.\n"
        "- If it is an object, company, or anything, find the main color of that thing. For example, NVIDIA's main color is green, so the background of the SVG must be green or have green as the primary background/color theme.\n"
        "- If the mentioned project name and description is about a company or a person, find their famous identity (such as their logo, face shape, or most connected community logo) and visualize it in the center or main path of the SVG.\n"
        "- If anything extra about that main topic is mentioned in the project, try to visualize it in the SVG as side elements/details surrounding the main logo or identity.\n"
        "- Do NOT draw simple shapes, plain text, or basic clip art. Create a highly creative, sophisticated, and modern digital vector artwork.\n"
        "- Use rich, vibrant gradient maps (define multi-stop <linearGradient> or <radialGradient> with high-end color transitions in a <defs> block) instead of flat, solid colors.\n"
        "- Use organic curves, flowing wave paths, and complex bezier shapes (<path d='...' />) to draw custom artwork rather than basic rectangles and circles.\n"
        "- Incorporate glowing aura and dimension effects. Define `<filter id='glow'>` in the defs containing `<feGaussianBlur>` and `<feMerge>` elements to make parts of the vector glow.\n"
        "- Use layered translucent glassmorphic plates (shapes with `fill-opacity='0.15'` up to `0.45` and subtle borders) overlapping each other to create stunning depth.\n"
        "- Forbid low-effort designs, centered single shapes, emojis, or flat cartoons. The SVG must look like a premium digital asset created by a professional designer.\n"
        "- Do not wrap the SVG string in markdown code block ticks inside the JSON value."
    )


def generate_project_prompts(
    name: str,
    description: str,
    settings: Settings,
) -> dict[str, str]:
    """
    Generates customized system prompts for the five agent types:
    gate, rewriter, generic, synthesis, decision.
    Tries cloud OpenAI 'gpt-4o' first for high-quality creative SVGs and prompts,
    falling back to the local LLM if cloud fails.
    """
    system_instruction = _build_system_instruction(name, description)
    user_prompt = (
        f"Generate the JSON object containing the five system prompts and the visual SVG.\n\n"
        f"CRITICAL: For the 'visual_svg' key, you must design custom artwork that directly represents "
        f"the project '{name}' and its description: '{description}'. "
        f"Analyze the name and description, identify the core theme/domain, and construct a beautiful, "
        f"thematic vector illustration representing that specific domain. Do not make it generic."
    )

    try:
        logger.info("Attempting to generate project prompts using cloud LLM 'gpt-4o'...")
        cloud_client = CloudLlmClient(settings)
        response = cloud_client.generate(
            model="gpt-4o",
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
        logger.warning("Failed to generate prompts using cloud LLM: %s. Trying local LLM fallback...", exc)

    if settings.local_llm_base_url:
        try:
            logger.info("Attempting to generate project prompts using local LLM fallback 'qwen3.5:2b'...")
            local_client = LocalLlmClient(settings)
            response = local_client.generate(
                model="qwen3.5:2b",
                system=system_instruction,
                user=user_prompt,
                json_mode=True,
            )
            data = parse_json_object(response.content)
            if all(k in data for k in _REQUIRED_KEYS):
                logger.info("Successfully generated project prompts using local LLM fallback.")
                return {key: str(data[key]) for key in _REQUIRED_KEYS}
            logger.warning("Local LLM fallback returned incomplete JSON keys: %s", data.keys())
        except Exception as local_exc:
            logger.error("Failed to generate prompts using local LLM fallback: %s", local_exc)

    raise RuntimeError("Could not generate project prompts from any configured LLM.")


def recreate_project_svg(
    project_id: UUID,
    session: Session,
    settings: Settings,
    llm: BaseLlmClient,
) -> None:
    """
    Fetches context (recent messages) in this project and triggers Cloud LLM to
    regenerate a new visual SVG representation, saving it to project settings.
    """
    from app.models.project import Project
    from app.models.conversation import ChatConversation, ChatMessage

    project = session.get(Project, project_id)
    if not project:
        logger.warning("Project %s not found for SVG recreation", project_id)
        return

    # Get the last 10 messages for context
    recent_messages = session.exec(
        select(ChatMessage)
        .join(ChatConversation, ChatMessage.conversation_id == ChatConversation.id)
        .where(ChatConversation.project_id == project_id)
        .where(ChatMessage.status == "completed")
        .where(ChatMessage.role.in_(["user", "assistant"]))
        .order_by(ChatMessage.created_at.desc())
        .limit(10)
    ).all()

    # Reverse to chronological order
    recent_messages.reverse()

    # Build context string
    history_text = "\n".join(f"{m.role}: {m.content}" for m in recent_messages)

    system_instruction = (
        "You are a professional designer. Your task is to generate a beautiful, modern, clean, "
        "and self-contained SVG image that visually represents a project based on its title, "
        "description, and recent chat history.\n\n"
        "Project details:\n"
        f"- Project Name: {project.name}\n"
        f"- Project Description: {project.settings.get('description', '')}\n\n"
        "Recent conversation context to inspire the design update:\n"
        f"{history_text}\n\n"
        "SVG Requirements:\n"
        "- Must be valid, raw, modern, beautiful, and clean SVG code.\n"
        "- Must use viewBox='0 0 200 150' to fit the card header aspect ratio.\n"
        "- First of all, read the project name and description.\n"
        "- If it is an object, company, or anything, find the main color of that thing. For example, NVIDIA's main color is green, so the background of the SVG must be green or have green as the primary background/color theme.\n"
        "- If the mentioned project name and description is about a company or a person, find their famous identity (such as their logo, face shape, or most connected community logo) and visualize it in the center or main path of the SVG.\n"
        "- If anything extra about that main topic is mentioned in the project, try to visualize it in the SVG as side elements/details surrounding the main logo or identity.\n"
        "- Do NOT draw simple shapes, plain text, or basic clip art. Create a highly creative, sophisticated, and modern digital vector artwork.\n"
        "- Use rich, vibrant gradient maps (define multi-stop <linearGradient> or <radialGradient> with high-end color transitions in a <defs> block) instead of flat, solid colors.\n"
        "- Use organic curves, flowing wave paths, and complex bezier shapes (<path d='...' />) to draw custom artwork rather than basic rectangles and circles.\n"
        "- Incorporate glowing aura and dimension effects. Define `<filter id='glow'>` in the defs containing `<feGaussianBlur>` and `<feMerge>` elements to make parts of the vector glow.\n"
        "- Use layered translucent glassmorphic plates (shapes with `fill-opacity='0.15'` up to `0.45` and subtle borders) overlapping each other to create stunning depth.\n"
        "- Forbid low-effort designs, centered single shapes, emojis, or flat cartoons. The SVG must look like a premium digital asset created by a professional designer.\n"
        "- Do not include markdown code block formatting (such as ```xml or ```svg).\n"
        "- Output ONLY the raw SVG code. No explanations, no JSON, no prefix, no suffix."
    )

    try:
        logger.info("Attempting to regenerate visual SVG using Cloud LLM gpt-4o...")
        cloud_client = CloudLlmClient(settings)
        response = cloud_client.generate(
            model="gpt-4o",
            system=system_instruction,
            user="Generate the new updated visual SVG representation.",
        )
        svg_code = response.content.strip()
        # Clean up code blocks if LLM accidentally wrapped it
        if "```" in svg_code:
            lines = svg_code.splitlines()
            cleaned_lines = [l for l in lines if not l.strip().startswith("```")]
            svg_code = "\n".join(cleaned_lines).strip()
    except Exception as exc:
        logger.error("Failed to regenerate SVG using Cloud LLM: %s. Falling back to provided llm...", exc)
        try:
            response = llm.generate(
                model="gpt-4o",
                system=system_instruction,
                user="Generate the new updated visual SVG representation.",
            )
            svg_code = response.content.strip()
            if "```" in svg_code:
                lines = svg_code.splitlines()
                cleaned_lines = [l for l in lines if not l.strip().startswith("```")]
                svg_code = "\n".join(cleaned_lines).strip()
        except Exception as fallback_exc:
            logger.error("Fallback LLM also failed to regenerate SVG: %s", fallback_exc)
            return

    if svg_code.startswith("<svg") and "</svg>" in svg_code:
        project_settings = dict(project.settings)
        project_settings["visual_svg"] = svg_code
        project.settings = project_settings
        session.add(project)
        session.commit()
        logger.info("Successfully updated visual SVG for project %s", project_id)
    else:
        logger.warning("Generated text does not seem to contain a valid SVG: %s", svg_code[:100])

