"""Health check routes."""

from fastapi import APIRouter, Depends

from ..dependencies import get_pipeline
from ..services.emotion import EmotionPipeline

router = APIRouter()


@router.get("/health")
async def health(pipeline: EmotionPipeline = Depends(get_pipeline)) -> dict[str, str | None]:
    state = pipeline.latest_state
    return {
        "status": "ok",
        "emotion": state.label if state else None,
        "confidence": f"{state.confidence:.2f}" if state else None,
    }
