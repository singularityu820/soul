from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Optional

import httpx

from ...config import LLMProvider, LLMServiceConfig

_DETECTION_TIMEOUT = 0.35


@dataclass(slots=True)
class LLMDetectionResult:
    provider: LLMProvider
    reason: str


class BaseLLMClient:
    provider: LLMProvider

    async def generate(self, prompt: str, **kwargs: object) -> str:
        raise NotImplementedError


class SandboxLLMClient(BaseLLMClient):
    def __init__(self, provider: LLMProvider = LLMProvider.SANDBOX) -> None:
        self.provider = provider

    async def generate(self, prompt: str, **kwargs: object) -> str:
        tail = prompt[-160:].replace("\n", " ")
        return f"[{self.provider.value}] 占位回复：{tail or '...' }"


class RemoteLLMClient(BaseLLMClient):
    def __init__(
        self,
        provider: LLMProvider,
        endpoint: str,
        api_key: Optional[str],
        timeout: float,
    ) -> None:
        self.provider = provider
        self.endpoint = endpoint
        self.api_key = api_key
        self.timeout = timeout

    async def generate(self, prompt: str, **kwargs: object) -> str:
        if not self.api_key:
            return f"[{self.provider.value}] 未配置 API 密钥，使用占位回复。"
        headers: Dict[str, str] = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "model": kwargs.get("model", "default"),
            "messages": kwargs.get(
                "messages",
                [
                    {"role": "system", "content": "You are a supportive companion."},
                    {"role": "user", "content": prompt},
                ],
            ),
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.endpoint, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                content = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content")
                )
                if content:
                    return content
        except httpx.HTTPError:
            return f"[{self.provider.value}] 接口不可用，使用占位回复。"
        return f"[{self.provider.value}] 未返回内容。"


class LLMService:
    def __init__(self, config: LLMServiceConfig | None = None) -> None:
        self.config = config or LLMServiceConfig()
        self._detection: Optional[LLMDetectionResult] = None
        self._client: Optional[BaseLLMClient] = None

    @property
    def provider(self) -> LLMProvider:
        if not self._detection:
            self._detection = self._detect()
        return self._detection.provider

    def detection_reason(self) -> str:
        if not self._detection:
            self._detection = self._detect()
        return self._detection.reason

    def client(self) -> BaseLLMClient:
        if not self._client:
            detection = self._detect()
            self._detection = detection
            self._client = self._build_client(detection.provider)
        return self._client

    async def generate(self, prompt: str, **kwargs: object) -> str:
        client = self.client()
        return await client.generate(prompt, **kwargs)

    def _detect(self) -> LLMDetectionResult:
        config = self.config
        if config.preferred_provider:
            return LLMDetectionResult(
                provider=config.preferred_provider,
                reason="Preferred provider configured.",
            )

        env_choice = os.getenv("LLM_PROVIDER")
        if env_choice:
            provider = self._map_provider(env_choice)
            if provider:
                return LLMDetectionResult(
                    provider=provider,
                    reason="Detected from LLM_PROVIDER environment variable.",
                )

        if not config.allow_auto_detect:
            return LLMDetectionResult(provider=LLMProvider.SANDBOX, reason="Auto detect disabled.")

        detectors = [
            self._detect_openai,
            self._detect_modelscope,
            self._detect_zhipu,
            self._detect_vllm,
            self._detect_ollama,
        ]
        for detector in detectors:
            provider = detector()
            if provider:
                return provider

        return LLMDetectionResult(provider=LLMProvider.SANDBOX, reason="No provider matched.")

    def _build_client(self, provider: LLMProvider) -> BaseLLMClient:
        timeout = self.config.timeout_seconds
        overrides = self.config.endpoint_overrides
        if provider == LLMProvider.OPENAI:
            endpoint = overrides.get(provider, "https://api.openai.com/v1/chat/completions")
            return RemoteLLMClient(provider, endpoint, os.getenv("OPENAI_API_KEY"), timeout)
        if provider == LLMProvider.MODEL_SCOPE:
            endpoint = overrides.get(provider, "https://api-inference.modelscope.cn/v1/services/chat/completions")
            return RemoteLLMClient(provider, endpoint, os.getenv("MODELSCOPE_API_KEY"), timeout)
        if provider == LLMProvider.ZHIPU:
            endpoint = overrides.get(provider, "https://open.bigmodel.cn/api/paas/v4/chat/completions")
            return RemoteLLMClient(provider, endpoint, os.getenv("ZHIPUAI_API_KEY"), timeout)
        if provider == LLMProvider.VLLM:
            endpoint = overrides.get(provider, os.getenv("VLLM_ENDPOINT", "http://127.0.0.1:8000/v1/chat/completions"))
            return RemoteLLMClient(provider, endpoint, os.getenv("VLLM_API_KEY"), timeout)
        if provider == LLMProvider.OLLAMA:
            endpoint = overrides.get(provider, os.getenv("OLLAMA_ENDPOINT", "http://127.0.0.1:11434/v1/chat/completions"))
            return RemoteLLMClient(provider, endpoint, os.getenv("OLLAMA_API_KEY"), timeout)
        return SandboxLLMClient(provider)

    def _detect_openai(self) -> Optional[LLMDetectionResult]:
        if os.getenv("OPENAI_API_KEY"):
            return LLMDetectionResult(provider=LLMProvider.OPENAI, reason="Found OPENAI_API_KEY.")
        return None

    def _detect_modelscope(self) -> Optional[LLMDetectionResult]:
        if os.getenv("MODELSCOPE_API_KEY") or os.getenv("MODELSCOPE_ACCESS_KEY"):
            return LLMDetectionResult(provider=LLMProvider.MODEL_SCOPE, reason="Found ModelScope credentials.")
        return None

    def _detect_zhipu(self) -> Optional[LLMDetectionResult]:
        if os.getenv("ZHIPUAI_API_KEY") or os.getenv("ZHIPUAI_API_SECRET"):
            return LLMDetectionResult(provider=LLMProvider.ZHIPU, reason="Found Zhipu credentials.")
        return None

    def _detect_vllm(self) -> Optional[LLMDetectionResult]:
        endpoint = os.getenv("VLLM_ENDPOINT", "http://127.0.0.1:8000/v1/chat/completions")
        return self._probe_endpoint(endpoint, LLMProvider.VLLM)

    def _detect_ollama(self) -> Optional[LLMDetectionResult]:
        endpoint = os.getenv("OLLAMA_ENDPOINT", "http://127.0.0.1:11434/api/tags")
        return self._probe_endpoint(endpoint, LLMProvider.OLLAMA)

    def _probe_endpoint(self, endpoint: str, provider: LLMProvider) -> Optional[LLMDetectionResult]:
        try:
            url = endpoint
            if provider == LLMProvider.OLLAMA and endpoint.endswith("/api/tags"):
                url = endpoint
            with httpx.Client(timeout=_DETECTION_TIMEOUT) as client:
                response = client.get(url)
                if response.status_code < 500:
                    return LLMDetectionResult(
                        provider=provider,
                        reason=f"Endpoint responsive: {endpoint}",
                    )
        except httpx.HTTPError:
            return None
        return None

    def _map_provider(self, value: str) -> Optional[LLMProvider]:
        try:
            return LLMProvider(value.lower())
        except ValueError:
            return None
