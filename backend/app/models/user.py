from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "users"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    email: str = Field(unique=True, index=True, max_length=255)
    password_hash: str | None = Field(default=None, nullable=True)
    is_verified: bool = Field(default=False)
    verification_otp: str | None = Field(default=None, max_length=6)
    otp_expires_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProjectMember(SQLModel, table=True):
    __tablename__ = "project_members"
    user_id: UUID = Field(foreign_key="users.id", primary_key=True, ondelete="CASCADE")
    project_id: UUID = Field(foreign_key="projects.id", primary_key=True, ondelete="CASCADE")
    role: str = Field(default="member", max_length=50)
    joined_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
