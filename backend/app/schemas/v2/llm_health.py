from pydantic import BaseModel, Field


class LlmHealthResponse(BaseModel):
    status: str = Field(description="ok when the gate model responds; error otherwise")
    model: str | None = Field(default=None, description="Model used for the probe")
    detail: str | None = Field(default=None, description="Error detail when status is error")
    sample_response: str | None = Field(
        default=None,
        description="Truncated model output on success",
    )
