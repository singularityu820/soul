from __future__ import annotations

import asyncio
import base64
import io
import logging
import os
import wave
from enum import Enum
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class ASRProvider(str, Enum):
    OPENAI = "openai"
    AZURE = "azure"
    DASHSCOPE = "dashscope"
    MODELSCOPE = "modelscope"
    SANDBOX = "sandbox"


class ASRService:
    """语音识别服务,支持多种 ASR 提供商"""

    def __init__(self) -> None:
        self.provider = self._detect_provider()
        logger.info("ASR provider detected: %s", self.provider.value)

    def _detect_provider(self) -> ASRProvider:
        """自动检测可用的 ASR 提供商"""
        # 优先使用环境变量指定的提供商
        provider_env = os.getenv("ASR_PROVIDER", "").lower()
        if provider_env == "openai" and os.getenv("OPENAI_API_KEY"):
            return ASRProvider.OPENAI
        if provider_env == "azure" and os.getenv("AZURE_SPEECH_KEY"):
            return ASRProvider.AZURE
        if provider_env == "dashscope" and os.getenv("DASHSCOPE_API_KEY"):
            return ASRProvider.DASHSCOPE
        if provider_env == "modelscope" and os.getenv("MODELSCOPE_API_KEY"):
            return ASRProvider.MODELSCOPE

        # 自动检测
        if os.getenv("DASHSCOPE_API_KEY"):
            return ASRProvider.DASHSCOPE
        if os.getenv("OPENAI_API_KEY"):
            return ASRProvider.OPENAI
        if os.getenv("AZURE_SPEECH_KEY"):
            return ASRProvider.AZURE
        if os.getenv("MODELSCOPE_API_KEY"):
            return ASRProvider.MODELSCOPE

        logger.warning("No ASR provider credentials found, using sandbox mode")
        return ASRProvider.SANDBOX

    async def transcribe(
        self,
        audio_bytes: bytes,
        language: str = "zh",
        sample_rate: int = 16000,
    ) -> str:
        """
        将音频转换为文本。

        Args:
            audio_bytes: PCM 音频数据 (16-bit)
            language: 语言代码 (zh, en, ja 等)
            sample_rate: 采样率

        Returns:
            识别的文本
        """
        if self.provider == ASRProvider.OPENAI:
            text = await self._transcribe_openai(audio_bytes, language, sample_rate)
        elif self.provider == ASRProvider.AZURE:
            text = await self._transcribe_azure(audio_bytes, language, sample_rate)
        elif self.provider == ASRProvider.DASHSCOPE:
            text = await self._transcribe_dashscope(audio_bytes, language, sample_rate)
        elif self.provider == ASRProvider.MODELSCOPE:
            text = await self._transcribe_modelscope(audio_bytes, language, sample_rate)
        else:
            text = await self._transcribe_sandbox(audio_bytes, language, sample_rate)

        trimmed = text.strip() if text else ""
        if not trimmed and self.provider == ASRProvider.DASHSCOPE:
            logger.warning(
                "DashScope returned empty transcript; falling back to sandbox ASR"
            )
            trimmed = await self._transcribe_sandbox(audio_bytes, language, sample_rate)

        if trimmed:
            logger.info("ASR transcript (%s): %s", self.provider.value, trimmed)
        else:
            logger.info("ASR transcript (%s): <empty>", self.provider.value)
        return trimmed

    async def _transcribe_openai(
        self,
        audio_bytes: bytes,
        language: str,
        sample_rate: int,
    ) -> str:
        """使用 OpenAI Whisper API"""
        try:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not set")

            # 将 PCM 转换为 WAV 格式
            wav_buffer = self._pcm_to_wav(audio_bytes, sample_rate)

            # 调用 Whisper API
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    files={
                        "file": ("audio.wav", wav_buffer, "audio/wav"),
                    },
                    data={
                        "model": "whisper-1",
                        "language": language if language != "zh" else "zh-CN",
                    },
                )

            if not response.is_success:
                logger.error("OpenAI ASR failed: %s", response.text)
                return ""

            result = response.json()
            return result.get("text", "").strip()

        except Exception as e:
            logger.exception("Failed to transcribe with OpenAI: %s", e)
            return ""

    async def _transcribe_azure(
        self,
        audio_bytes: bytes,
        language: str,
        sample_rate: int,
    ) -> str:
        """使用 Azure Speech Service"""
        try:
            speech_key = os.getenv("AZURE_SPEECH_KEY")
            region = os.getenv("AZURE_SPEECH_REGION", "eastus")
            if not speech_key:
                raise ValueError("AZURE_SPEECH_KEY not set")

            # Azure 语音识别 REST API
            lang_code = "zh-CN" if language == "zh" else f"{language}-{language.upper()}"
            url = f"https://{region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1"

            wav_buffer = self._pcm_to_wav(audio_bytes, sample_rate)

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    headers={
                        "Ocp-Apim-Subscription-Key": speech_key,
                        "Content-Type": "audio/wav; codecs=audio/pcm; samplerate=16000",
                    },
                    params={"language": lang_code},
                    content=wav_buffer,
                )

            if not response.is_success:
                logger.error("Azure ASR failed: %s", response.text)
                return ""

            result = response.json()
            return result.get("DisplayText", "").strip()

        except Exception as e:
            logger.exception("Failed to transcribe with Azure: %s", e)
            return ""

    async def _transcribe_dashscope(
        self,
        audio_bytes: bytes,
        language: str,
        sample_rate: int,
    ) -> str:
        """使用阿里云 DashScope Qwen ASR Flash"""
        try:
            import dashscope
            from dashscope import MultiModalConversation

            api_key = os.getenv("DASHSCOPE_API_KEY")
            if not api_key:
                raise ValueError("DASHSCOPE_API_KEY not set")

            # 将 PCM 转换为 WAV
            wav_data = self._pcm_to_wav(audio_bytes, sample_rate)

            # 配置请求地域
            base_url = os.getenv("DASHSCOPE_API_BASE_URL")
            if not base_url:
                region = os.getenv("DASHSCOPE_REGION", "cn").lower()
                base_url = (
                    "https://dashscope-intl.aliyuncs.com/api/v1"
                    if region in {"sg", "intl", "singapore"}
                    else "https://dashscope.aliyuncs.com/api/v1"
                )
            dashscope.base_http_api_url = base_url.rstrip("/")

            # DashScope 目前要求音频以 URL 或 base64 数据的形式提供，这里采用 base64 内联
            encoded_audio = base64.b64encode(wav_data).decode("ascii")
            audio_uri = f"data:audio/wav;base64,{encoded_audio}"

            messages = [
                {"role": "system", "content": [{"text": ""}]},
                {
                    "role": "user",
                    "content": [
                        {"audio": audio_uri}
                    ],
                },
            ]

            lang_map = {
                "zh": "zh",
                "en": "en",
                "ja": "ja",
                "yue": "yue",
                "ko": "ko",
            }
            asr_lang = lang_map.get(language, "zh")

            model = os.getenv("DASHSCOPE_ASR_MODEL", "qwen3-asr-flash")

            # ITN、语言识别等开关通过环境变量控制
            enable_itn = os.getenv("DASHSCOPE_ASR_ENABLE_ITN", "true").lower() not in {"0", "false", "no"}
            enable_lid = os.getenv("DASHSCOPE_ASR_ENABLE_LID", "true").lower() not in {"0", "false", "no"}

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: MultiModalConversation.call(
                    api_key=api_key,
                    model=model,
                    messages=messages,
                    result_format="message",
                    asr_options={
                        "language": asr_lang,
                        "enable_itn": enable_itn,
                        "enable_lid": enable_lid,
                    },
                ),
            )

            if response.status_code == 200:
                output = getattr(response, "output", None)
                if not output:
                    logger.warning("DashScope ASR response missing output")
                    return ""

                choices = getattr(output, "choices", None)
                if not choices:
                    logger.warning("DashScope ASR response missing choices")
                    return ""

                message = choices[0].message if choices else None
                if not message:
                    logger.warning("DashScope ASR response missing message content")
                    return ""

                contents = getattr(message, "content", [])
                for item in contents:
                    if isinstance(item, dict) and "text" in item:
                        return item["text"].strip()

                logger.warning("DashScope ASR returned empty content array")
                return ""

            logger.error(
                "DashScope ASR failed: %s - %s",
                response.status_code,
                getattr(response, "message", ""),
            )
            return ""

        except ImportError:
            logger.error("dashscope package not installed. Run: pip install dashscope")
            return ""
        except Exception as e:
            logger.exception("Failed to transcribe with DashScope: %s", e)
            return ""

    async def _transcribe_modelscope(
        self,
        audio_bytes: bytes,
        language: str,
        sample_rate: int,
    ) -> str:
        """使用 ModelScope ASR"""
        # TODO: 实现 ModelScope ASR 集成
        logger.warning("ModelScop ASR not implemented yet")
        return ""

    async def _transcribe_sandbox(
        self,
        audio_bytes: bytes,
        language: str,
        sample_rate: int,
    ) -> str:
        """沙盒模式,返回占位文本"""
        duration = len(audio_bytes) / (sample_rate * 2)  # 16-bit = 2 bytes per sample
        logger.info("Sandbox ASR: received %.2f seconds of audio", duration)
        return f"[沙盒模式] 收到 {duration:.1f} 秒音频"

    def _pcm_to_wav(self, pcm_bytes: bytes, sample_rate: int) -> bytes:
        """将 PCM 音频转换为 WAV 格式"""
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)  # mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_bytes)
        return buffer.getvalue()
