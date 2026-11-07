"""Persist usage counts returned by the AI provider; never infer tokens from text length."""
from sqlalchemy.orm import Session
from app.config import get_settings
from app.models import AIUsageRecord


def record_ai_usage(db: Session, *, organization_id, user_id, result, feature: str) -> bool:
    """Add one successful provider call. Returns False when provider usage is unavailable."""
    prompt = result.prompt_tokens
    completion = result.completion_tokens
    total = result.total_tokens
    if not all(isinstance(value, int) and value >= 0 for value in (prompt, completion, total)):
        return False
    settings = get_settings()
    cost = None
    if result.provider == "openai" and settings.openai_input_usd_per_million_tokens > 0 and settings.openai_output_usd_per_million_tokens > 0:
        # USD/million * tokens equals USD micros, avoiding floating-point currency storage.
        cost = round(prompt * settings.openai_input_usd_per_million_tokens + completion * settings.openai_output_usd_per_million_tokens)
    db.add(AIUsageRecord(organization_id=organization_id, user_id=user_id, provider=result.provider,
        model=result.model, feature=feature, prompt_tokens=prompt, completion_tokens=completion,
        total_tokens=total, estimated_cost_usd_micros=cost))
    db.flush()
    return True
