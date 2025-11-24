"""Emotion-related routes (face, agent)."""

from fastapi import APIRouter, Depends

from ..dependencies import get_agent, get_memory, get_pipeline
from ..schemas import FaceObservationIn, MemorySnapshotOut, UserMessageIn
from ..services.agent import AgentMemory, ConversationalAgent
from ..services.emotion import EmotionPipeline

router = APIRouter()


@router.post("/ingest/face")
async def ingest_face(
    payload: FaceObservationIn,
    pipeline: EmotionPipeline = Depends(get_pipeline),
) -> dict[str, str]:
    await pipeline.update_face_observation(
        label=payload.label,
        confidence=payload.confidence,
        intensity=payload.intensity,
        faces_detected=payload.faces_detected,
    )
    return {"status": "accepted"}


@router.post("/agent/user-message")
async def user_message(
    payload: UserMessageIn,
    agent: ConversationalAgent = Depends(get_agent),
) -> dict[str, str]:
    await agent.ingest_user_message(payload.text)
    return {"status": "recorded"}


@router.get("/memory/snapshot", response_model=MemorySnapshotOut)
async def memory_snapshot(memory: AgentMemory = Depends(get_memory)) -> MemorySnapshotOut:
    records = memory.snapshot()
    return MemorySnapshotOut(recent_events=records, size=memory.count())
