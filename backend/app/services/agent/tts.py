from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import AsyncIterator, Dict, List, Optional

import httpx

from ...config import TTSProvider, TTSServiceConfig

_DETECTION_TIMEOUT = 0.35


@dataclass(slots=True)
class TTSDetectionResult:
    provider: TTSProvider
    reason: str


@dataclass(slots=True)
class SynthesizedSpeech:
    provider: TTSProvider
    voice: str
    locale: str
    audio_reference: str
    segments: Optional[List[str]] = None


class BaseTTSClient:
    provider: TTSProvider

    async def synthesize(self, text: str, voice: str, locale: str) -> SynthesizedSpeech:
        raise NotImplementedError


class SandboxTTSClient(BaseTTSClient):
    def __init__(self, provider: TTSProvider = TTSProvider.SANDBOX) -> None:
        self.provider = provider

    async def synthesize(self, text: str, voice: str, locale: str) -> SynthesizedSpeech:
        snippet = text[:60]
        reference = f"sandbox://{self.provider.value}/{voice}?preview={snippet}"
        return SynthesizedSpeech(
            provider=self.provider,
            voice=voice,
            locale=locale,
            audio_reference=reference,
            segments=[reference],
        )


class RemoteTTSClient(BaseTTSClient):
    def __init__(
        self,
        provider: TTSProvider,
        endpoint: str,
        api_key: Optional[str],
        timeout: float,
    ) -> None:
        self.provider = provider
        self.endpoint = endpoint
        self.api_key = api_key
        self.timeout = timeout

    async def synthesize(self, text: str, voice: str, locale: str) -> SynthesizedSpeech:
        if not self.api_key:
            return SynthesizedSpeech(
                provider=self.provider,
                voice=voice,
                locale=locale,
                audio_reference=f"missing-key://{self.provider.value}",
                segments=[f"missing-key://{self.provider.value}"],
            )
        payload = {
            "input": text,
            "voice": voice,
            "locale": locale,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.endpoint, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                reference = data.get("audio_url") or data.get("audio_reference")
                if reference:
                    return SynthesizedSpeech(
                        provider=self.provider,
                        voice=voice,
                        locale=locale,
                        audio_reference=reference,
                        segments=[reference],
                    )
        except httpx.HTTPError:
            return SynthesizedSpeech(
                provider=self.provider,
                voice=voice,
                locale=locale,
                audio_reference=f"error://{self.provider.value}",
                segments=[f"error://{self.provider.value}"],
            )
        return SynthesizedSpeech(
            provider=self.provider,
            voice=voice,
            locale=locale,
            audio_reference=f"empty://{self.provider.value}",
            segments=[f"empty://{self.provider.value}"],
        )


@dataclass(slots=True)
class _TTSChunk:
    text: str
    voice: str
    locale: str
    emotion: str


class SoVITSTTSClient(BaseTTSClient):
    def __init__(self, config: TTSServiceConfig, timeout: float) -> None:
        self.provider = TTSProvider.SOVITS
        self._config = config
        self._timeout = timeout
        self._endpoint = (config.sovits_endpoint or os.getenv("SOVITS_ENDPOINT", "")).rstrip("/")
        if not self._endpoint:
            raise ValueError("GPT-SoVITs endpoint is not configured.")
        self._public_base = (
            config.sovits_public_base
            or os.getenv("SOVITS_PUBLIC_BASE", "")
            or self._endpoint
        ).rstrip("/")
        self._app_key = config.sovits_app_key or os.getenv("SOVITS_APP_KEY", "")
        self._download_url = config.sovits_download_url or os.getenv("SOVITS_DOWNLOAD_URL", "")
        self._lock = asyncio.Lock()

    async def synthesize(self, text: str, voice: str, locale: str) -> SynthesizedSpeech:
        stripped = text.strip()
        if not stripped:
            return SynthesizedSpeech(
                provider=self.provider,
                voice=voice,
                locale=locale,
                audio_reference="",
                segments=None,
            )

        chunks = self._build_chunks(stripped, voice, locale)
        urls: List[str] = []
        
        import logging
        logger = logging.getLogger(__name__)
        
        async with self._lock:
            for chunk in chunks:
                try:
                    url = await self._request_chunk(chunk)
                    urls.append(url)
                except Exception as e:
                    logger.error(f"Failed to synthesize chunk: {e}", exc_info=True)
                    # 返回错误信息而不是中断整个流程
                    return SynthesizedSpeech(
                        provider=self.provider,
                        voice=voice,
                        locale=locale,
                        audio_reference=f"error://{self.provider.value}/{str(e)}",
                        segments=None,
                    )

        audio_reference = urls[0] if urls else ""
        return SynthesizedSpeech(
            provider=self.provider,
            voice=voice,
            locale=locale,
            audio_reference=audio_reference,
            segments=urls or None,
        )
    
    async def synthesize_stream(self, text: str, voice: str, locale: str) -> AsyncIterator[str]:
        """
        流式合成 TTS 音频
        
        每生成一个音频片段就立即 yield 出来，而不是等待所有片段生成完毕。
        这样可以减少首音延迟，用户能更快听到响应。
        
        Args:
            text: 要合成的文本
            voice: 语音模型
            locale: 语言/地区
            
        Yields:
            音频 URL，按生成顺序逐个返回
        """
        import logging
        logger = logging.getLogger(__name__)
        
        stripped = text.strip()
        if not stripped:
            return
        
        chunks = self._build_chunks(stripped, voice, locale)
        logger.info(f"TTS stream: synthesizing {len(chunks)} chunks")
        
        async with self._lock:
            for i, chunk in enumerate(chunks):
                try:
                    logger.info(f"TTS stream: generating chunk {i+1}/{len(chunks)}")
                    url = await self._request_chunk(chunk)
                    yield url
                except Exception as e:
                    logger.error(f"TTS stream: failed to synthesize chunk {i+1}: {e}", exc_info=True)
                    # 继续处理下一个片段，不中断整个流
                    continue

    def _build_chunks(self, text: str, voice: str, locale: str) -> List[_TTSChunk]:
        cfg = self._config
        min_chars = max(1, cfg.sovits_min_chunk_chars)
        punctuation = set(cfg.sovits_split_punctuation)
        voice_prefix = cfg.sovits_voice_token_prefix.lower()
        lang_prefix = cfg.sovits_lang_token_prefix.lower()
        emotion_prefix = cfg.sovits_emotion_token_prefix.lower()

        current_voice = voice
        current_locale = locale
        current_emotion = cfg.sovits_emotion
        pending: List[str] = []
        chunks: List[_TTSChunk] = []

        def flush(force: bool = False) -> None:
            nonlocal pending
            content = "".join(pending).strip()
            if not content:
                pending = []
                return
            if force or len(content) >= min_chars:
                chunks.append(
                    _TTSChunk(
                        text=content,
                        voice=current_voice,
                        locale=current_locale,
                        emotion=current_emotion,
                    )
                )
                pending = []

        idx = 0
        length = len(text)
        while idx < length:
            char = text[idx]
            if char == "<":
                token_end = text.find(">", idx)
                if token_end != -1:
                    raw_token = text[idx : token_end + 1]
                    lower_token = raw_token.lower()
                    if lower_token.startswith(voice_prefix):
                        flush(force=True)
                        current_voice = raw_token[len(cfg.sovits_voice_token_prefix) : -1].strip() or voice
                        idx = token_end + 1
                        continue
                    if lower_token.startswith(lang_prefix):
                        flush(force=True)
                        current_locale = raw_token[len(cfg.sovits_lang_token_prefix) : -1].strip() or locale
                        idx = token_end + 1
                        continue
                    if lower_token.startswith(emotion_prefix):
                        flush(force=True)
                        current_emotion = raw_token[len(cfg.sovits_emotion_token_prefix) : -1].strip() or cfg.sovits_emotion
                        idx = token_end + 1
                        continue
            pending.append(char)
            if char in punctuation and "".join(pending).strip():
                flush(force=False)
            idx += 1

        flush(force=True)
        if not chunks:
            chunks.append(
                _TTSChunk(
                    text=text,
                    voice=current_voice,
                    locale=current_locale,
                    emotion=current_emotion,
                )
            )
        return chunks

    async def _request_chunk(self, chunk: _TTSChunk) -> str:
        payload = self._build_payload(chunk)
        headers = {"accept": "application/json", "Content-Type": "application/json"}
        
        import logging
        import json
        logger = logging.getLogger(__name__)
        logger.info(f"TTS request to: {self._endpoint}/infer_single")
        logger.info(f"TTS payload summary: text='{chunk.text[:50]}...', emotion='{chunk.emotion}', model='{self._config.sovits_model_name}'")
        logger.info(f"TTS full payload: {json.dumps(payload, ensure_ascii=False, indent=2)}")
        
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(f"{self._endpoint}/infer_single", headers=headers, json=payload)
        
        logger.info(f"TTS response status: {response.status_code}")
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"TTS response data keys: {list(data.keys())}")
        logger.info(f"TTS response data: {data}")
        
        audio_url = data.get("audio_url")
        if not audio_url:
            raise ValueError(f"TTS response missing audio_url field. Response: {data}")
        return self._normalize_audio_url(audio_url)

    def _build_payload(self, chunk: _TTSChunk) -> Dict[str, object]:
        cfg = self._config
        request: Dict[str, object] = {
            "app_key": self._app_key,
            "dl_url": self._download_url,
            "version": cfg.sovits_version,
            "model_name": cfg.sovits_model_name,
            "prompt_text_lang": cfg.sovits_prompt_text_lang,
            "emotion": chunk.emotion or cfg.sovits_emotion,
            "text": chunk.text,
            "text_lang": self._resolve_text_lang(chunk.locale),
            "top_k": cfg.sovits_top_k,
            "top_p": cfg.sovits_top_p,
            "temperature": cfg.sovits_temperature,
            "text_split_method": cfg.sovits_text_split_method,
            "batch_size": cfg.sovits_batch_size,
            "batch_threshold": cfg.sovits_batch_threshold,
            "split_bucket": cfg.sovits_split_bucket,
            "speed_facter": cfg.sovits_speed_factor,
            "fragment_interval": cfg.sovits_fragment_interval,
            "media_type": cfg.sovits_media_type,
            "parallel_infer": cfg.sovits_parallel_infer,
            "repetition_penalty": cfg.sovits_repetition_penalty,
            "seed": cfg.sovits_seed,
            "sample_steps": cfg.sovits_sample_steps,
            "if_sr": cfg.sovits_if_sr,
        }
        return request

    def _resolve_text_lang(self, locale: str) -> str:
        mapping = self._config.sovits_text_lang_map or {}
        return mapping.get(locale.lower(), self._config.sovits_text_lang_default)

    def _normalize_audio_url(self, audio_url: str) -> str:
        if audio_url.startswith("http://0.0.0.0:8000"):
            return audio_url.replace("http://0.0.0.0:8000", self._public_base, 1)
        if audio_url.startswith("/"):
            return f"{self._public_base}{audio_url}"
        return audio_url
class TTSService:
    def __init__(self, config: TTSServiceConfig | None = None) -> None:
        self.config = config or TTSServiceConfig()
        self._detection: Optional[TTSDetectionResult] = None
        self._client: Optional[BaseTTSClient] = None

    @property
    def provider(self) -> TTSProvider:
        if not self._detection:
            self._detection = self._detect()
        return self._detection.provider

    def detection_reason(self) -> str:
        if not self._detection:
            self._detection = self._detect()
        return self._detection.reason

    def client(self) -> BaseTTSClient:
        if not self._client:
            detection = self._detect()
            self._detection = detection
            self._client = self._build_client(detection.provider)
        return self._client

    async def synthesize(self, text: str, voice: str, locale: str) -> SynthesizedSpeech:
        client = self.client()
        return await client.synthesize(text, voice, locale)
    
    async def synthesize_stream(self, text: str, voice: str, locale: str) -> AsyncIterator[str]:
        """
        流式合成 TTS 音频
        
        每生成一个音频片段就立即返回，用于实时语音对话场景。
        
        Args:
            text: 要合成的文本
            voice: 语音模型
            locale: 语言/地区
            
        Yields:
            音频 URL，按生成顺序逐个返回
        """
        client = self.client()
        
        # 只有 SoVITS 客户端支持流式合成
        if isinstance(client, SoVITSTTSClient):
            async for audio_url in client.synthesize_stream(text, voice, locale):
                yield audio_url
        else:
            # 其他 TTS 客户端回退到批量模式
            result = await client.synthesize(text, voice, locale)
            if result.segments:
                for segment in result.segments:
                    yield segment
            elif result.audio_reference:
                yield result.audio_reference

    def _detect(self) -> TTSDetectionResult:
        config = self.config
        if config.preferred_provider:
            return TTSDetectionResult(config.preferred_provider, "Preferred provider configured.")

        env_choice = os.getenv("TTS_PROVIDER")
        if env_choice:
            provider = self._map_provider(env_choice)
            if provider:
                return TTSDetectionResult(provider, "Detected from TTS_PROVIDER environment variable.")

        if not config.allow_auto_detect:
            return TTSDetectionResult(TTSProvider.SANDBOX, "Auto detect disabled.")

        sovits = self._detect_sovits()
        if sovits:
            return sovits

        detectors = [
            self._detect_azure,
            self._detect_edge,
            self._detect_polly,
            self._detect_ollama,
        ]
        for detector in detectors:
            result = detector()
            if result:
                return result

        return TTSDetectionResult(TTSProvider.SANDBOX, "No provider matched.")

    def _build_client(self, provider: TTSProvider) -> BaseTTSClient:
        timeout = self.config.timeout_seconds
        if provider == TTSProvider.SOVITS:
            endpoint = self._resolve_sovits_endpoint()
            if not endpoint:
                return SandboxTTSClient(TTSProvider.SANDBOX)
            # client reads endpoint from config/env internally
            return SoVITSTTSClient(self.config, timeout)
        if provider == TTSProvider.AZURE:
            endpoint = os.getenv("AZURE_TTS_ENDPOINT", "https://example.cognitiveservices.azure.com/tts")
            return RemoteTTSClient(provider, endpoint, os.getenv("AZURE_TTS_KEY"), timeout)
        if provider == TTSProvider.EDGE:
            endpoint = os.getenv("EDGE_TTS_ENDPOINT", "https://speech.platform.bing.com/synthesize")
            return RemoteTTSClient(provider, endpoint, os.getenv("EDGE_TTS_KEY"), timeout)
        if provider == TTSProvider.POLLY:
            endpoint = os.getenv("POLLY_TTS_ENDPOINT", "https://polly.us-east-1.amazonaws.com/v1/speech")
            api_key = os.getenv("AWS_ACCESS_KEY_ID")
            return RemoteTTSClient(provider, endpoint, api_key, timeout)
        if provider == TTSProvider.COQUI:
            endpoint = os.getenv("COQUI_TTS_ENDPOINT", "http://127.0.0.1:5002/api/tts")
            return RemoteTTSClient(provider, endpoint, os.getenv("COQUI_TTS_KEY"), timeout)
        if provider == TTSProvider.OLLAMA:
            endpoint = os.getenv("OLLAMA_TTS_ENDPOINT", "http://127.0.0.1:11434/api/generate")
            return RemoteTTSClient(provider, endpoint, os.getenv("OLLAMA_TTS_KEY"), timeout)
        return SandboxTTSClient(provider)

    def _detect_azure(self) -> Optional[TTSDetectionResult]:
        if os.getenv("AZURE_TTS_KEY"):
            return TTSDetectionResult(TTSProvider.AZURE, "Found Azure TTS credentials.")
        return None

    def _detect_sovits(self) -> Optional[TTSDetectionResult]:
        endpoint = self._resolve_sovits_endpoint()
        if endpoint:
            return TTSDetectionResult(TTSProvider.SOVITS, f"SOVITS endpoint: {endpoint}")
        return None

    def _resolve_sovits_endpoint(self) -> str:
        return (self.config.sovits_endpoint or os.getenv("SOVITS_ENDPOINT", "")).rstrip("/")

    def _detect_edge(self) -> Optional[TTSDetectionResult]:
        if os.getenv("EDGE_TTS_KEY"):
            return TTSDetectionResult(TTSProvider.EDGE, "Found Edge TTS credentials.")
        return None

    def _detect_polly(self) -> Optional[TTSDetectionResult]:
        if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
            return TTSDetectionResult(TTSProvider.POLLY, "Found AWS credentials.")
        return None

    def _detect_ollama(self) -> Optional[TTSDetectionResult]:
        endpoint = os.getenv("OLLAMA_TTS_ENDPOINT", "http://127.0.0.1:11434/api/generate")
        try:
            with httpx.Client(timeout=_DETECTION_TIMEOUT) as client:
                response = client.post(endpoint, json={"prompt": "ping"})
                if response.status_code < 500:
                    return TTSDetectionResult(TTSProvider.OLLAMA, f"Endpoint responsive: {endpoint}")
        except httpx.HTTPError:
            return None
        return None

    def _map_provider(self, value: str) -> Optional[TTSProvider]:
        try:
            return TTSProvider(value.lower())
        except ValueError:
            return None
