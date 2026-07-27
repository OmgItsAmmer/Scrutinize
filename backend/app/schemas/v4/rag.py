from typing import Literal
from pydantic import BaseModel, Field

Route = Literal["rag", "web", "hybrid", "generic"]
RequestedTool = Literal["generate_pdf", "generate_flowchart", "web_search"]


class GateResult(BaseModel):
    """Routing classification result from the RAG gate."""
    route: Route = Field(
        description="The determined query routing path (rag, web, hybrid, generic)."
    )
    reason: str = Field(
        description="A brief explanation of the routing decision."
    )
    requested_tool: RequestedTool | None = Field(
        default=None,
        description="The tool required to complete this query, or None if no specific tool is requested."
    )
    reply: str | None = Field(
        default=None,
        description="A conversational reply ONLY if route is 'generic'. Otherwise, must be None."
    )


class QueryRewriteResult(BaseModel):
    """Structured output for search query optimization."""
    rewritten_query: str = Field(
        description="The optimized/expanded query string for RAG retrieval."
    )
    explanation: str = Field(
        description="Brief reasoning for the rewrite modifications."
    )


class EvidenceAssessmentResult(BaseModel):
    """Evaluates if the retrieved chunks contain enough details to answer the query."""
    is_sufficient: bool = Field(
        description="True if the retrieved context is sufficient to answer the query, False otherwise."
    )
    reasoning: str = Field(
        description="Detailed explanation of the sufficiency assessment."
    )
    missing_information: str | None = Field(
        default=None,
        description="Specific details or content missing from the retrieval context, if any."
    )


class CitationMapping(BaseModel):
    """Validation mapping for a cited source snippet."""
    citation_id: str = Field(
        description="The cited document/source identifier (e.g. filename, UUID, index)."
    )
    supports_claim: bool = Field(
        description="Whether the retrieved content supports the corresponding claim in the draft."
    )
    snippet_evidence: str = Field(
        description="The specific snippet from the source document that acts as evidence."
    )


class CitationMapResult(BaseModel):
    """Validation result mapping for all citations in the draft answer."""
    has_valid_citations: bool = Field(
        description="True if all cited content is valid and supported by active sources."
    )
    mappings: list[CitationMapping] = Field(
        default_factory=list,
        description="List of citation support verification mappings."
    )


class GroundednessResult(BaseModel):
    """Scoring and verification metrics of synthesized answers against reference documents."""
    score: float = Field(
        description="Groundedness score between 0.0 and 1.0 (with 1.0 being perfectly grounded)."
    )
    reasoning: str = Field(
        description="Detailed explanation justifying the groundedness score."
    )
    is_grounded: bool = Field(
        description="Whether the score is at or above the safety threshold (e.g., 0.90)."
    )
