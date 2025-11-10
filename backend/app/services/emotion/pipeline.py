from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional, Dict, Any

from ...schemas import AgentMessage, EmotionState, PipelineEvent
from ..agent.agent import ConversationalAgent
from .avatar import AvatarOrchestrator
from .eeg import EEGEmotionClassifier, EEGSample, EEGStreamTool
from .face import FaceEmotionTool
# from ..agent.speech import SpeechEmotionTool  # <-- 已移除导入
from .fusion import EmotionFusionService

logger = logging.getLogger(__name__)


class EmotionPipeline:
    """Coordinates multimodal emotion inference and downstream actions."""

    def __init__(
        self,
        eeg_stream: EEGStreamTool,
        eeg_classifier: EEGEmotionClassifier,
        face_tool: FaceEmotionTool,
        # speech_tool: SpeechEmotionTool,  # <-- 已移除 speech_tool 参数
        fusion: EmotionFusionService,
        avatar: AvatarOrchestrator,
        agent: ConversationalAgent,
    ) -> None:
        self.eeg_stream = eeg_stream
        self.eeg_classifier = eeg_classifier
        self.face_tool = face_tool
        # self.speech_tool = speech_tool  # <-- 已移除 self.speech_tool
        self.fusion = fusion
        self.avatar = avatar
        self.agent = agent

        self._listeners: set[asyncio.Queue[PipelineEvent]] = set()
        self._task: Optional[asyncio.Task[None]] = None
        self._running = asyncio.Event()
        self.latest_state: Optional[EmotionState] = None
        self.latest_message: Optional[AgentMessage] = None
        
        # 添加融合频率控制
        self._last_fusion_time = 0
        self._fusion_interval = 60  # 融合间隔60秒

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

    async def update_face_observation_from_frame(self, emotion_result: Dict[str, Any]) -> None:
        """从视频帧情绪检测结果更新面部情绪观察数据
        
        Args:
            emotion_result: 情绪检测结果，包含情绪标签、置信度、人脸位置等信息
        """
        if not emotion_result:
            return
            
        # 提取情绪信息
        emotion_label = emotion_result.get("emotion", "neutral")
        confidence = emotion_result.get("confidence", 0.0)
        
        # 提取人脸位置信息
        face_bbox = emotion_result.get("face_bbox", {})
        face_position = [
            {
                "x": face_bbox.get("x", 0),
                "y": face_bbox.get("y", 0),
                "width": face_bbox.get("width", 100),
                "height": face_bbox.get("height", 100)
            }
        ]
        
        # 更新面部情绪观察数据
        await self.face_tool.update_observation(
            label=emotion_label,
            confidence=confidence,
            intensity=confidence,
            faces_detected=1
        )
        
        # 注释掉直接广播面部情绪事件的代码，避免频繁更新前端
        # 面部情绪数据将在融合时（每60秒）通过_run_loop方法一起广播
        # 创建面部情绪状态
        # face_emotion_state = {
        #     "label": emotion_label,
        #     "confidence": confidence,
        #     "face_position": face_position,
        #     "timestamp": emotion_result.get("timestamp", time.time())
        # }
        # 
        # # 广播面部情绪事件
        # face_event = PipelineEvent(face_emotion=face_emotion_state)
        # await self._broadcast(face_event)

    async def _run_loop(self) -> None:
        try:
            while self._running.is_set():
                sample: EEGSample = await self.eeg_stream.sample()
                eeg_channel = await self.eeg_classifier.classify(sample)
                face_channel = await self.face_tool.analyze()
                # speech_channel = await self.speech_tool.analyze()  # <-- 已移除 speech_tool 调用
                
                # 检查是否应该进行融合（控制融合频率）
                current_time = time.time()
                should_fuse = current_time - self._last_fusion_time >= self._fusion_interval
                
                if should_fuse:
                    # 仅融合EEG和面部通道
                    fused = self.fusion.fuse([eeg_channel, face_channel])
                    self._last_fusion_time = current_time
                    
                    fused_with_wave = fused.model_copy(update={"waveform": sample.waveform})

                    avatar_pose = self.avatar.translate(fused_with_wave)
                    agent_message = await self.agent.handle_emotion_state(fused_with_wave)

                    event = PipelineEvent(
                        emotion=fused_with_wave,
                        avatar=avatar_pose,
                        agent_message=agent_message,
                    )

                    self.latest_state = fused_with_wave
                    self.latest_message = agent_message
                    await self._broadcast(event)
                # 注释掉非融合期间的面部情绪广播，这样前端就不会每3秒收到更新
                # else:
                #     # 不融合时，仅广播面部情绪事件
                #     face_event = PipelineEvent(face_emotion={
                #         "label": face_channel.label,
                #         "confidence": face_channel.confidence,
                #         "timestamp": current_time
                #     })
                #     await self._broadcast(face_event)
                    
        except asyncio.CancelledError:
            logger.debug("Emotion pipeline loop cancelled")
        except Exception:  # pragma: no cover - surface errors in logs
            logger.exception("Emotion pipeline encountered an error")

    async def _broadcast(self, event: PipelineEvent) -> None:
        for queue in list(self._listeners):
            await queue.put(event)

    async def broadcast_face_emotion(self, room_id: str, face_emotion_data: Dict[str, Any]) -> None:
        """广播面部情绪数据到特定房间
        
        Args:
            room_id: 房间ID
            face_emotion_data: 面部情绪数据
        """
        # 创建面部情绪事件
        face_event = PipelineEvent(face_emotion=face_emotion_data)
        
        # 广播事件
        await self._broadcast(face_event)
        
        logger.info(f"Broadcasted face emotion to room {room_id}: {face_emotion_data.get('label')}")

    def enable_proactive(self) -> None:
        """启用主动模式，当有活跃会话时"""
        logger.info("Emotion pipeline proactive mode enabled")

    def disable_proactive(self) -> None:
        """禁用主动模式，当没有活跃会话时"""
        logger.info("Emotion pipeline disabled")