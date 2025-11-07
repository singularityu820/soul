from __future__ import annotations

import asyncio
import time
from typing import Iterable, Optional

from ..config import AgentConfig
from ..schemas import AgentMessage, ChannelEmotion, EmotionState
from .memory import AgentMemory
from .llm import LLMService
from .tts import SynthesizedSpeech, TTSService


class ConversationalAgent:
    """Heuristic conversational core with stubs for future LLM tool integration."""

    def __init__(
        self,
        memory: AgentMemory,
        config: AgentConfig | None = None,
        llm_service: Optional[LLMService] = None,
        tts_service: Optional[TTSService] = None,
    ) -> None:
        self.memory = memory
        self.config = config or AgentConfig()
        self.llm_service = llm_service or LLMService()
        self.tts_service = tts_service or TTSService()
        self._outbound_listeners: set[asyncio.Queue[AgentMessage]] = set()
        self._last_trigger_time: float = 0.0
        self._last_emotion: Optional[EmotionState] = None

    async def ingest_user_message(self, text: str) -> None:
        self.memory.add_event(text=f"User: {text}", tags=["user", "dialogue"])

    async def handle_emotion_state(self, emotion: EmotionState) -> Optional[AgentMessage]:
        now = time.time()
        self.memory.add_event(
            text=f"Emotion observed: {emotion.label} (score={emotion.mood_score:.2f})",
            tags=["emotion"],
        )
        should_speak = self._should_speak(now, emotion)
        self._last_emotion = emotion
        if not should_speak:
            return None

        message = await self._compose_message(emotion)
        await self._broadcast(message)
        self._last_trigger_time = now
        return message

    async def respond_with_context(self, emotion: Optional[EmotionState]) -> AgentMessage:
        state = emotion or self._neutral_emotion()
        return await self._compose_message(state)

    def subscribe(self) -> asyncio.Queue[AgentMessage]:
        queue: asyncio.Queue[AgentMessage] = asyncio.Queue()
        self._outbound_listeners.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[AgentMessage]) -> None:
        self._outbound_listeners.discard(queue)

    async def _broadcast(self, message: AgentMessage) -> None:
        self.memory.add_event(text=f"Agent: {message.text}", tags=["agent", "dialogue"])
        for queue in list(self._outbound_listeners):
            await queue.put(message)

    def _should_speak(self, now: float, emotion: EmotionState) -> bool:
        if not self._last_emotion:
            return True
        delta_time = now - self._last_trigger_time
        mood_delta = abs(emotion.mood_score - self._last_emotion.mood_score)
        label_changed = emotion.label != self._last_emotion.label

        if delta_time > self.config.proactive_interval_seconds:
            return True
        if delta_time > self.config.check_interval_seconds and label_changed:
            return True
        if emotion.mood_score < self.config.negative_threshold:
            return True
        if (
            emotion.mood_score > self.config.positive_threshold
            and delta_time > self.config.check_interval_seconds
        ):
            return True
        if mood_delta > 0.4 and delta_time > self.config.check_interval_seconds:
            return True
        return False

    async def _compose_message(self, emotion: EmotionState) -> AgentMessage:
        voice_style = self._voice_style_for(emotion)
        language = self._language_for(emotion)
        prompt = self._build_prompt(emotion, voice_style, language)
        text = await self._generate_with_llm(prompt, emotion)
        speech = await self._maybe_synthesize(text, voice_style, language)
        return AgentMessage(
            text=text,
            voice_style=voice_style,
            language=language,
            emotion=emotion.label,
            llm_provider=self.llm_service.provider.value,
            tts_provider=speech.provider.value if speech else None,
            audio_reference=speech.audio_reference if speech else None,
        )

    def _build_prompt(self, emotion: EmotionState, voice_style: str, language: str) -> str:
        mood_summary = (
            f"当前情绪：{emotion.label}，心境值 {emotion.mood_score:.2f}，置信度 {emotion.confidence:.2f}."
        )
        recent = self.memory.search("dialogue", limit=5)
        memory_lines = "\n".join(item.content for item in recent)
        base_instruction = (
            "你是一位贴心的聊天搭子，根据用户当前情绪给出温暖、自然的回答，"
            "语言要口语化，适当使用 emoji，让对话轻松。"
        )
        prompt_sections = [base_instruction, mood_summary]
        if memory_lines:
            prompt_sections.append("近期记忆：" + memory_lines)
        prompt_sections.append(f"语气偏向：{voice_style}")
        prompt_sections.append(f"语言：{language}")
        prompt_sections.append("请输出下一句回复。")
        return "\n".join(prompt_sections)

    async def _generate_with_llm(self, prompt: str, emotion: EmotionState) -> str:
        try:
            return await self.llm_service.generate(prompt)
        except Exception:
            return self._fallback_text(emotion)

    def _voice_style_for(self, emotion: EmotionState) -> str:
        if emotion.mood_score < self.config.negative_threshold:
            return "soft_calm"
        if emotion.mood_score > self.config.positive_threshold:
            return "bright_energy"
        return "balanced"

    def _language_for(self, emotion: EmotionState) -> str:
        # Placeholder: default to Chinese, switch to English when highly positive.
        return "en" if emotion.mood_score > 0.6 else "zh"

    def _fallback_text(self, emotion: EmotionState) -> str:
        if emotion.mood_score < self.config.negative_threshold:
            return "我注意到你有些紧张，要不要一起做几个深呼吸？"
        if emotion.mood_score > self.config.positive_threshold:
            return "听起来你现在状态很棒！要不要分享一下让你开心的事情？"
        if emotion.label == "neutral":
            return "我会陪着你，随时准备聊天。"
        if emotion.label == "calm":
            return "保持这种平稳的节奏很好，我们继续保持。"
        return f"我感受到你有点{emotion.label}，愿意和我聊聊吗？"

    async def _maybe_synthesize(
        self, text: str, voice_style: str, language: str
    ) -> Optional[SynthesizedSpeech]:
        try:
            voice = self._select_voice(voice_style, language)
            return await self.tts_service.synthesize(text, voice, language)
        except Exception:
            return None

    def _select_voice(self, voice_style: str, language: str) -> str:
        key = f"{language}:{voice_style}"
        defaults = self.tts_service.config.voice_defaults or {}
        return defaults.get(key) or defaults.get(language) or "default"

    def _neutral_emotion(self) -> EmotionState:
        return EmotionState(
            label="neutral",
            confidence=0.2,
            mood_score=0.0,
            components=[
                ChannelEmotion(
                    source="fusion",
                    label="neutral",
                    confidence=0.2,
                    mood_score=0.0,
                    metadata={},
                )
            ],
        )
