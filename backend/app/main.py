"""Main FastAPI application."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .dependencies import pipeline
from .routes import audio, chat, diary, eeg, emotion, health, info, video, websockets

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan manager."""
    try:
        await pipeline.start()
        yield
    finally:
        await pipeline.stop()


app = FastAPI(title="Soul Emotion Agent", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router, tags=["health"])
app.include_router(info.router, tags=["info"])
app.include_router(emotion.router, tags=["emotion"])
app.include_router(chat.router, tags=["chat"])
app.include_router(audio.router, tags=["audio"])
app.include_router(video.router, tags=["video"])
app.include_router(eeg.router, tags=["eeg"])
app.include_router(diary.router, prefix="/api/diary", tags=["diary"])
app.include_router(websockets.router, tags=["websockets"])
