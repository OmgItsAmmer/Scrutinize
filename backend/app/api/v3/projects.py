from datetime import UTC, datetime, timedelta
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.core.deps import get_db_session
from app.models.pipeline_log import PipelineRun, PipelineStep
from pydantic import BaseModel

router = APIRouter()

class ModelUsage(BaseModel):
    model_name: str
    total_calls: int
    total_tokens: int
    total_cost_usd: float

class DailyUsage(BaseModel):
    date: str
    total_runs: int
    total_tokens: int
    total_cost_usd: float

class ProjectUsageResponse(BaseModel):
    project_id: UUID
    total_runs: int
    total_tokens: int
    total_cost_usd: float
    by_model: list[ModelUsage]
    by_day: list[DailyUsage]

@router.get("/{project_id}/usage", response_model=ProjectUsageResponse, tags=["projects"])
async def get_project_usage(
    project_id: UUID,
    session: Session = Depends(get_db_session)
) -> ProjectUsageResponse:
    # Query all pipeline runs for the project
    runs_stmt = select(PipelineRun).where(PipelineRun.project_id == project_id)
    runs = list(session.exec(runs_stmt).all())
    
    total_runs = len(runs)
    total_tokens = sum((r.total_tokens or 0) for r in runs)
    total_cost_usd = sum((r.total_cost_usd or 0.0) for r in runs)
    
    # Aggregate step-level details grouped by model
    run_ids = [r.id for r in runs]
    by_model = []
    
    if run_ids:
        # Query steps for these runs
        steps_stmt = select(PipelineStep).where(PipelineStep.run_id.in_(run_ids))
        steps = list(session.exec(steps_stmt).all())
        
        model_stats = {}
        for step in steps:
            model = step.model_name or "unknown"
            if model not in model_stats:
                model_stats[model] = {"calls": 0, "tokens": 0, "cost": 0.0}
            
            model_stats[model]["calls"] += 1
            step_tokens = (step.prompt_tokens or 0) + (step.completion_tokens or 0)
            model_stats[model]["tokens"] += step_tokens
            model_stats[model]["cost"] += (step.cost_usd or 0.0)
            
        for model_name, stats in model_stats.items():
            by_model.append(
                ModelUsage(
                    model_name=model_name,
                    total_calls=stats["calls"],
                    total_tokens=stats["tokens"],
                    total_cost_usd=round(stats["cost"], 6),
                )
            )
            
    # Daily metrics for the last 30 days
    daily_stats = {}
    for i in range(30):
        day = (datetime.now(UTC) - timedelta(days=i)).strftime("%Y-%m-%d")
        daily_stats[day] = {"runs": 0, "tokens": 0, "cost": 0.0}
        
    for r in runs:
        day_str = r.created_at.strftime("%Y-%m-%d")
        if day_str in daily_stats:
            daily_stats[day_str]["runs"] += 1
            daily_stats[day_str]["tokens"] += (r.total_tokens or 0)
            daily_stats[day_str]["cost"] += (r.total_cost_usd or 0.0)
            
    by_day = []
    for day in sorted(daily_stats.keys()):
        stats = daily_stats[day]
        by_day.append(
            DailyUsage(
                date=day,
                total_runs=stats["runs"],
                total_tokens=stats["tokens"],
                total_cost_usd=round(stats["cost"], 6),
            )
        )
        
    return ProjectUsageResponse(
        project_id=project_id,
        total_runs=total_runs,
        total_tokens=total_tokens,
        total_cost_usd=round(total_cost_usd, 6),
        by_model=by_model,
        by_day=by_day,
    )
