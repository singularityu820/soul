"""Main FastAPI application."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .dependencies import pipeline
from .routes import audio, chat, diary, eeg, emotion, health, info, video, websockets, image, volcano_image_routes, volcano_image_emotion_routes

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
# 注册图片生成路由
app.include_router(image.router) #讯飞
app.include_router(volcano_image_routes.router)
app.include_router(volcano_image_emotion_routes.router)

# 挂载静态文件服务 - 放在路由注册之后
app.mount("/static", StaticFiles(directory="."), name="static")
app.mount("/generated_images", StaticFiles(directory="generated_images"), name="generated_images")
# 挂载根目录，提供HTML文件访问
app.mount("/", StaticFiles(directory="../", html=True), name="frontend")
