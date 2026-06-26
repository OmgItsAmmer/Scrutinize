from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.models.file import FileModality


class PipelineRun(SQLModel, table=True):
    __tablename__ = "pipeline_runs"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    original_query: str
    modality_filter: FileModality | None = None
    conversation_context: str | None = None
    start_time: datetime
    end_time: datetime | None = None
    final_route: str | None = None
    final_answer: str | None = None
    final_confidence: float | None = None
    attempts_count: int = 0
    disclaimer_appended: bool = False
    run_metadata: dict = Field(default_factory=dict, sa_column=Column(JSONB().with_variant(JSON, "sqlite")))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PipelineStep(SQLModel, table=True):
    __tablename__ = "pipeline_steps"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    run_id: UUID = Field(foreign_key="pipeline_runs.id", index=True)
    step_type: str  # 'rewrite', 'gate', 'retrieval', 'synthesis', 'evaluation'
    attempt: int
    model_name: str | None = None
    model_input: dict | list | None = Field(default=None, sa_column=Column(JSONB().with_variant(JSON, "sqlite")))
    raw_thinking: str | None = None
    model_output: str | None = None
    structured_output: dict | list | None = Field(default=None, sa_column=Column(JSONB().with_variant(JSON, "sqlite")))
    retrieved_sources: list | dict | None = Field(default=None, sa_column=Column(JSONB().with_variant(JSON, "sqlite")))
    latency_ms: int | None = None
    status: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
