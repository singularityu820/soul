from __future__ import annotations

import asyncio
import logging
from typing import Optional

from ...schemas import AgentMessage, EmotionState, PipelineEvent
from ..agent import ConversationalAgent
from .avatar import AvatarOrchestrator
from .eeg import EEGEmotionClassifier, EEGSample, EEGStreamTool
from .face import FaceEmotionTool
from .fusion import EmotionFusionService

logger = logging.getLogger(__name__)


class EmotionPipeline:
    """Coordinates multimodal emotion inference and downstream actions."""

    def __init__(
        self,
        eeg_stream: EEGStreamTool,
        eeg_classifier: EEGEmotionClassifier,
        face_tool: FaceEmotionTool,
        fusion: EmotionFusionService,
        avatar: AvatarOrchestrator,
        agent: ConversationalAgent,
    ) -> None:
        self.eeg_stream = eeg_stream
        self.eeg_classifier = eeg_classifier
        self.face_tool = face_tool
        self.fusion = fusion
        self.avatar = avatar
        self.agent = agent

        self._listeners: set[asyncio.Queue[PipelineEvent]] = set()
        self._task: Optional[asyncio.Task[None]] = None
        self._running = asyncio.Event()
        self.latest_state: Optional[EmotionState] = None
        self.latest_message: Optional[AgentMessage] = None
        self._proactive_enabled: bool = False

    @property
    def proactive_enabled(self) -> bool:
        return self._proactive_enabled

    def enable_proactive(self) -> None:
        self._proactive_enabled = True
        logger.info("Emotion pipeline proactive mode enabled")

    def disable_proactive(self) -> None:
        self._proactive_enabled = False
        logger.info("Emotion pipeline proactive mode disabled")

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._running.set()
        self._task = asyncio.create_task(self._run_loop(), name="emotion-pipeline")
        logger.info("Emotion pipeline started")

    async def stop(self) -> None:
        self._running.clear()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            logger.info("Emotion pipeline stopped")

    def subscribe(self) -> asyncio.Queue[PipelineEvent]:
        queue: asyncio.Queue[PipelineEvent] = asyncio.Queue()
        self._listeners.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[PipelineEvent]) -> None:
        self._listeners.discard(queue)

    async def update_face_observation(
        self, label: str, confidence: float, intensity: float, faces_detected: int
    ) -> None:
        await self.face_tool.update_observation(
            label=label,
            confidence=confidence,
            intensity=intensity,
            faces_detected=faces_detected,
        )

    async def _run_loop(self) -> None:
        try:
            while self._running.is_set():
                sample: EEGSample = await self.eeg_stream.sample()
                eeg_channel = await self.eeg_classifier.classify(sample)
                face_channel = await self.face_tool.analyze()
                fused = self.fusion.fuse([eeg_channel, face_channel])
                fused_with_wave = fused.model_copy(update={"waveform": sample.waveform})

                avatar_pose = self.avatar.translate(fused_with_wave)
                agent_message = await self.agent.handle_emotion_state(
                    fused_with_wave, proactive=self._proactive_enabled
                )

                event = PipelineEvent(
                    emotion=fused_with_wave,
                    avatar=avatar_pose,
                    agent_message=agent_message,
                )

                self.latest_state = fused_with_wave
                self.latest_message = agent_message
                await self._broadcast(event)
        except asyncio.CancelledError:
            logger.debug("Emotion pipeline loop cancelled")
        except Exception:  # pragma: no cover - surface errors in logs
            logger.exception("Emotion pipeline encountered an error")

    async def _broadcast(self, event: PipelineEvent) -> None:
        for queue in list(self._listeners):
            await queue.put(event)
