from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel

from app.models.file import FileModality


class PipelineRun(SQLModel, table=True):
    __tablename__ = "pipeline_runs"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    query: str
    modality_filter: FileModality | None = None
    conversation_context: str | None = None
    start_time: datetime
    end_time: datetime | None = None
    final_route: str | None = None
    final_answer: str | None = None
    final_confidence: float | None = None
    attempts_count: int = 0
    disclaimer_appended: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PipelineStep(SQLModel, table=True):
    __tablename__ = "pipeline_steps"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    run_id: UUID = Field(foreign_key="pipeline_runs.id", index=True)
    step_type: str  # 'rewrite', 'gate', 'retrieval', 'synthesis', 'evaluation'
    attempt: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class StepRewrite(SQLModel, table=True):
    __tablename__ = "step_rewrites"

    step_id: UUID = Field(foreign_key="pipeline_steps.id", primary_key=True)
    input_query: str
    prev_feedback: str | None = None
    rewritten_query: str


class StepGate(SQLModel, table=True):
    __tablename__ = "step_gates"

    step_id: UUID = Field(foreign_key="pipeline_steps.id", primary_key=True)
    route: str
    reason: str | None = None
    reply: str | None = None


class StepRetrieval(SQLModel, table=True):
    __tablename__ = "step_retrievals"

    step_id: UUID = Field(foreign_key="pipeline_steps.id", primary_key=True)
    query: str
    rewritten_query: str


class RetrievedSource(SQLModel, table=True):
    __tablename__ = "retrieved_sources"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    step_id: UUID = Field(foreign_key="step_retrievals.step_id", index=True)
    segment_id: UUID | None = Field(default=None, foreign_key="segments.id", nullable=True)
    file_id: UUID | None = Field(default=None, foreign_key="files.id", nullable=True)
    modality: FileModality
    title: str
    content: str
    source_path: str
    start_time: float | None = None
    end_time: float | None = None
    score: float
    rank: int


class StepSynthesis(SQLModel, table=True):
    __tablename__ = "step_syntheses"

    step_id: UUID = Field(foreign_key="pipeline_steps.id", primary_key=True)
    answer: str


class StepEvaluation(SQLModel, table=True):
    __tablename__ = "step_evaluations"

    step_id: UUID = Field(foreign_key="pipeline_steps.id", primary_key=True)
    verdict: str
    confidence: float
    correct_route: str | None = None
    feedback: str | None = None
