from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import AsyncIterator, Dict, Optional

import httpx
from openai import AsyncOpenAI

from ...config import LLMProvider, LLMServiceConfig

_DETECTION_TIMEOUT = 0.35

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LLMDetectionResult:
    provider: LLMProvider
    reason: str


class BaseLLMClient:
    provider: LLMProvider

    async def generate(self, prompt: str, **kwargs: object) -> str:
        raise NotImplementedError
    
    async def generate_stream(self, prompt: str, **kwargs: object) -> AsyncIterator[str]:
        """Generate response in streaming mode, yielding chunks"""
        raise NotImplementedError


class SandboxLLMClient(BaseLLMClient):
    def __init__(self, provider: LLMProvider = LLMProvider.SANDBOX) -> None:
        self.provider = provider

    async def generate(self, prompt: str, **kwargs: object) -> str:
        tail = prompt[-160:].replace("\n", " ")
        return f"[{self.provider.value}] 占位回复：{tail or '...' }"
    
    async def generate_stream(self, prompt: str, **kwargs: object) -> AsyncIterator[str]:
        """Simulate streaming by yielding parts of the response"""
        response = await self.generate(prompt, **kwargs)
        # Split into chunks for streaming simulation
        chunk_size = 5
        for i in range(0, len(response), chunk_size):
            yield response[i:i + chunk_size]


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
        self._openai_client: Optional[AsyncOpenAI] = None
    
    def _get_openai_client(self) -> AsyncOpenAI:
        """Get or create OpenAI client"""
        if self._openai_client is None:
            # Extract base_url from endpoint (remove /chat/completions suffix)
            base_url = self.endpoint
            if base_url.endswith("/chat/completions"):
                base_url = base_url[:-len("/chat/completions")]
            
            self._openai_client = AsyncOpenAI(
                api_key=self.api_key or "dummy",
                base_url=base_url,
                timeout=self.timeout,
            )
        return self._openai_client

    async def generate(self, prompt: str, **kwargs: object) -> str:
        if not self.api_key:
            return f"[{self.provider.value}] 未配置 API 密钥，使用占位回复。"
        
        try:
            client = self._get_openai_client()
            
            # Use LLM_MODEL_ID from env if available, otherwise use kwargs or default
            default_model = os.getenv("LLM_MODEL_ID", "default")
            model = kwargs.get("model", default_model)
            
            messages = kwargs.get(
                "messages",
                [
                    {"role": "system", "content": "You are a supportive companion."},
                    {"role": "user", "content": prompt},
                ],
            )
            
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                stream=False,
            )
            
            content = response.choices[0].message.content
            if content:
                return content
            
        except Exception as e:
            logger.warning(f"LLM error: {e}")
            return f"[{self.provider.value}] 接口不可用，使用占位回复。"
        
        return f"[{self.provider.value}] 未返回内容。"
    
    async def generate_stream(self, prompt: str, **kwargs: object) -> AsyncIterator[str]:
        """Generate response in streaming mode using OpenAI SDK"""
        if not self.api_key:
            yield f"[{self.provider.value}] 未配置 API 密钥，使用占位回复。"
            return
        
        try:
            client = self._get_openai_client()
            
            default_model = os.getenv("LLM_MODEL_ID", "default")
            model = kwargs.get("model", default_model)
            
            messages = kwargs.get(
                "messages",
                [
                    {"role": "system", "content": "You are a supportive companion."},
                    {"role": "user", "content": prompt},
                ],
            )
            
            # Create streaming completion
            stream = await client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                stream_options={"include_usage": True},  # Include usage stats
            )
            
            # Iterate over stream chunks
            async for chunk in stream:
                # Extract content delta from chunk
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        yield delta.content
                        
        except Exception as e:
            logger.warning(f"LLM streaming error: {e}")
            yield f"[{self.provider.value}] 流式接口不可用。"


class LLMService:
    def __init__(self, config: LLMServiceConfig | None = None) -> None:
        # Ensure environment variables are loaded
        from pathlib import Path
        from dotenv import load_dotenv
        # Path from llm.py to .env: backend/app/services/agent/llm.py -> ../.env
        env_path = Path(__file__).parent.parent.parent.parent.parent / ".env"
        load_dotenv(env_path)
        
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
        logger.info(f"Generating response with LLM provider: {client.provider.value}")
        try:
            response = await client.generate(prompt, **kwargs)
            logger.debug(f"LLM generated response: {response[:50]}...")
            return response
        except Exception as e:
            logger.exception(f"LLM generation error: {e}")
            raise
    
    async def generate_stream(self, prompt: str, **kwargs: object) -> AsyncIterator[str]:
        """Generate response in streaming mode"""
        client = self.client()
        logger.info(f"Generating streaming response with LLM provider: {client.provider.value}")
        try:
            async for chunk in client.generate_stream(prompt, **kwargs):
                yield chunk
        except Exception as e:
            logger.exception(f"LLM streaming generation error: {e}")
            raise

    async def generate_stream(
        self,
        prompt: str = "",
        *,
        messages: Optional[list[dict[str, object]]] = None,
        chunk_size: int = 80,
        **kwargs: object,
    ) -> AsyncIterator[str]:
        """轻量级流式接口：在无原生流式API时按 chunk 依次返回文本"""
        gen_kwargs = dict(kwargs)
        if messages is not None:
            gen_kwargs["messages"] = messages

        full_text = await self.generate(prompt, **gen_kwargs)
        if not full_text:
            return

        buffer: list[str] = []
        break_chars = {"。", "！", "？", "!", "?", "；", ";", "\n"}

        for ch in full_text:
            buffer.append(ch)
            should_flush = ch in break_chars or len(buffer) >= chunk_size
            if should_flush:
                chunk = "".join(buffer).strip()
                buffer.clear()
                if chunk:
                    yield chunk

        if buffer:
            chunk = "".join(buffer).strip()
            if chunk:
                yield chunk

    def _detect(self) -> LLMDetectionResult:
        config = self.config
        if config.preferred_provider:
            logger.info(f"Using preferred LLM provider: {config.preferred_provider.value}")
            return LLMDetectionResult(
                provider=config.preferred_provider,
                reason="Preferred provider configured.",
            )

        env_choice = os.getenv("LLM_PROVIDER")
        if env_choice:
            provider = self._map_provider(env_choice)
            if provider:
                logger.info(f"Using LLM provider from env: {provider.value}")
                return LLMDetectionResult(
                    provider=provider,
                    reason="Detected from LLM_PROVIDER environment variable.",
                )

        # Check for generic LLM configuration (LLM_API_KEY + LLM_BASE_URL) - moved up in priority
        if os.getenv("LLM_API_KEY") and os.getenv("LLM_BASE_URL"):
            logger.info("Using generic LLM configuration (LLM_API_KEY + LLM_BASE_URL)")
            return LLMDetectionResult(
                provider=LLMProvider.OPENAI,  # Use OpenAI-compatible client
                reason="Found LLM_API_KEY and LLM_BASE_URL environment variables.",
            )

        if not config.allow_auto_detect:
            logger.warning("LLM auto-detection disabled, using sandbox mode")
            return LLMDetectionResult(provider=LLMProvider.SANDBOX, reason="Auto detect disabled.")

        detectors = [
            self._detect_openai,
            self._detect_modelscope,
            self._detect_zhipu,
            self._detect_vllm,
            self._detect_ollama,
        ]
        logger.info("Auto-detecting LLM provider...")
        for detector in detectors:
            provider = detector()
            if provider:
                logger.info(f"LLM provider detected: {provider.provider.value} - {provider.reason}")
                return provider

        logger.warning("No LLM provider detected, falling back to sandbox mode")
        return LLMDetectionResult(provider=LLMProvider.SANDBOX, reason="No provider matched.")

    def _build_client(self, provider: LLMProvider) -> BaseLLMClient:
        timeout = self.config.timeout_seconds
        overrides = self.config.endpoint_overrides
        
        # Check for generic LLM configuration first
        generic_api_key = os.getenv("LLM_API_KEY")
        generic_base_url = os.getenv("LLM_BASE_URL")
        
        if provider == LLMProvider.OPENAI:
            # Use generic config if available, otherwise use OpenAI-specific
            api_key = generic_api_key or os.getenv("OPENAI_API_KEY")
            if generic_base_url:
                # Generic base URL provided, construct chat completions endpoint
                endpoint = f"{generic_base_url.rstrip('/')}/chat/completions"
            else:
                endpoint = overrides.get(provider, "https://api.openai.com/v1/chat/completions")
            return RemoteLLMClient(provider, endpoint, api_key, timeout)
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
        # Skip VLLM detection if we're running on the same port as the backend
        # to avoid detecting the backend service itself as VLLM
        endpoint = os.getenv("VLLM_ENDPOINT", "http://127.0.0.1:8000/v1/chat/completions")
        if endpoint.startswith("http://127.0.0.1:8000") or endpoint.startswith("http://localhost:8000"):
            logger.info("Skipping VLLM detection on localhost:8000 to avoid detecting backend service")
            return None
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
