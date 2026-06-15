from pydantic import BaseModel


class DependencyCheck(BaseModel):
    status: str
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    checks: dict[str, DependencyCheck]
