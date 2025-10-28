from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

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
                    )
        except httpx.HTTPError:
            return SynthesizedSpeech(
                provider=self.provider,
                voice=voice,
                locale=locale,
                audio_reference=f"error://{self.provider.value}",
            )
        return SynthesizedSpeech(
            provider=self.provider,
            voice=voice,
            locale=locale,
            audio_reference=f"empty://{self.provider.value}",
        )


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
