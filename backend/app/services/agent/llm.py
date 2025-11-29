from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import AsyncIterator, Dict, Optional

import httpx

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
        """默认实现：调用generate方法，然后按chunk返回文本"""
        full_text = await self.generate(prompt, **kwargs)
        if not full_text:
            return
        
        buffer = []
        chunk_size = 80
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
        
        headers: Dict[str, str] = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # For Coze API, use the specific endpoint
        if self.provider == LLMProvider.COZE:
            endpoint = "https://api.coze.cn/v3/chat"
            # Coze requires bot_id in payload
            bot_id = os.getenv("COZE_BOT_ID", "7577955978616995903")
            
            # Get messages from kwargs or use default
            messages = kwargs.get("messages", [
                {"role": "user", "content": prompt},
            ])
            
            # Convert to Coze API format with content_type
            additional_messages = []
            for msg in messages:
                coze_msg = {
                    "role": msg["role"],
                    "content": msg["content"],
                    "content_type": "text"
                }
                additional_messages.append(coze_msg)
            
            payload = {
                "bot_id": bot_id,
                "user_id": kwargs.get("user_id", "default_user"),
                "additional_messages": additional_messages,
                "stream": False,
                "auto_save_history": True
            }
        else:
            # Use LLM_MODEL_ID from env if available, otherwise use kwargs or default
            default_model = os.getenv("LLM_MODEL_ID", "default")
            model = kwargs.get("model", default_model)
            
            payload = {
                "model": model,
                "messages": kwargs.get(
                    "messages",
                    [
                        {"role": "system", "content": "You are a supportive companion."},
                        {"role": "user", "content": prompt},
                    ],
                ),
            }
        
        # 添加调试信息
        if self.provider == LLMProvider.COZE:
            logger.info(f"Coze API Request - Endpoint: {endpoint}, Bot ID: {bot_id}")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                
                # Initialize content variable
                content = None
                
                # Handle Coze API response format
                if self.provider == LLMProvider.COZE:
                    # Check if API returned an error
                    if data.get("code") != 0:
                        error_msg = data.get("msg", "Unknown error")
                        logger.warning(f"Coze API error: {error_msg}")
                        return f"[{self.provider.value}] API错误: {error_msg}"
                    # Extract content from successful response
                    # For non-streaming response, we get the complete message directly
                    if "data" in data:
                        # Check if it's a non-streaming response with chat_id
                        if "chat_id" in data["data"]:
                            # This is a non-streaming response, we need to poll for the result
                            # For simplicity, we'll just return a placeholder for now
                            return f"[{self.provider.value}] 非流式响应，需要轮询获取结果，chat_id: {data['data']['chat_id']}"
                        # Check if it's a direct response with messages
                        elif "messages" in data["data"]:
                            # This is a complete response with all messages
                            messages = data["data"]["messages"]
                            if messages:
                                last_message = messages[-1]
                                if "content" in last_message:
                                    return last_message["content"]
                    # For streaming response (which we'll use primarily)
                    elif "content" in data:
                        # This is a streaming response chunk
                        return data["content"]
                else:
                    # Handle other providers (including Doubao)
                    content = (
                        data.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content")
                    )
                
                if content:
                    return content
        except httpx.HTTPError as e:
            logger.warning(f"LLM HTTP error: {e}")
            return f"[{self.provider.value}] 接口不可用，使用占位回复。"
        return f"[{self.provider.value}] 未返回内容。"
    
    async def generate_stream(self, prompt: str, **kwargs: object) -> AsyncIterator[str]:
        """实现流式响应"""
        if not self.api_key:
            yield f"[{self.provider.value}] 未配置 API 密钥，使用占位回复。"
            return
        
        headers: Dict[str, str] = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # For Coze API, use the specific endpoint
        if self.provider == LLMProvider.COZE:
            endpoint = "https://api.coze.cn/v3/chat"
            # Coze requires bot_id in payload
            bot_id = os.getenv("COZE_BOT_ID", "7577955978616995903")
            
            # Get messages from kwargs or use default
            messages = kwargs.get("messages", [
                {"role": "user", "content": prompt},
            ])
            
            # Convert to Coze API format with content_type
            additional_messages = []
            for msg in messages:
                coze_msg = {
                    "role": msg["role"],
                    "content": msg["content"],
                    "content_type": "text"
                }
                additional_messages.append(coze_msg)
            
            payload = {
                "bot_id": bot_id,
                "user_id": kwargs.get("user_id", "default_user"),
                "additional_messages": additional_messages,
                "stream": True,  # 启用流式响应
            }
        else:
            # Use LLM_MODEL_ID from env if available, otherwise use kwargs or default
            default_model = os.getenv("LLM_MODEL_ID", "default")
            model = kwargs.get("model", default_model)
            endpoint = self.endpoint
            
            payload = {
                "model": model,
                "messages": kwargs.get(
                    "messages",
                    [
                        {"role": "system", "content": "You are a supportive companion."},
                        {"role": "user", "content": prompt},
                    ],
                ),
                "stream": True,  # 启用流式响应
            }
        
        # 添加调试信息
        if self.provider == LLMProvider.COZE:
            logger.info(f"Coze API Stream Request - Endpoint: {endpoint}, Bot ID: {bot_id}")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", endpoint, headers=headers, json=payload) as response:
                    response.raise_for_status()
                    
                    # Coze stream handling
                    if self.provider == LLMProvider.COZE:
                        # Coze uses SSE format with event: conversation.message.delta
                        async for line in response.aiter_lines():
                            if line.strip():
                                # Skip event type lines
                                if line.startswith("event: "):
                                    continue
                                elif line.startswith("data: "):
                                    data_str = line[6:].strip()
                                    if data_str == "[DONE]":
                                        break
                                    try:
                                        import json
                                        data = json.loads(data_str)
                                        # Check if this is a delta event with content
                                        if isinstance(data, dict):
                                            # For event: conversation.message.delta
                                            if "content" in data and data.get("role") == "assistant" and data.get("type") == "answer":
                                                chunk = data["content"]
                                                if chunk:
                                                    yield chunk
                                            # For event: conversation.message.completed
                                            # This contains the full message, but we've already streamed all chunks
                                    except json.JSONDecodeError:
                                        logger.warning(f"Failed to parse JSON from Coze stream: {data_str}")
                                        continue
                    else:
                        # Other providers (including Doubao) stream handling
                        async for line in response.aiter_lines():
                            if line.strip():
                                if line.startswith("data: "):
                                    data_str = line[6:]  # 去掉 "data: " 前缀
                                    if data_str.strip() == "[DONE]":
                                        break
                                    try:
                                        import json
                                        data = json.loads(data_str)
                                        if "choices" in data and len(data["choices"]) > 0:
                                            delta = data["choices"][0].get("delta", {})
                                            if "content" in delta and delta["content"]:
                                                yield delta["content"]
                                    except json.JSONDecodeError:
                                        logger.warning(f"Failed to parse JSON from stream: {data_str}")
                                        continue
        except httpx.HTTPError as e:
            logger.warning(f"LLM Stream HTTP error: {e}")
            yield f"[{self.provider.value}] 流式接口不可用，使用占位回复。"
        except Exception as e:
            logger.warning(f"LLM Stream error: {e}")
            yield f"[{self.provider.value}] 流式响应出错，使用占位回复。"


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

    async def generate_stream(
        self,
        prompt: str = "",
        *,
        messages: Optional[list[dict[str, object]]] = None,
        chunk_size: int = 80,
        **kwargs: object,
    ) -> AsyncIterator[str]:
        """流式接口：直接调用客户端的generate_stream方法"""
        client = self.client()
        logger.info(f"Generating stream response with LLM provider: {client.provider.value}")
        
        gen_kwargs = dict(kwargs)
        if messages is not None:
            gen_kwargs["messages"] = messages
        
        try:
            async for chunk in client.generate_stream(prompt, **gen_kwargs):
                yield chunk
        except Exception as e:
            logger.exception(f"LLM stream generation error: {e}")
            yield f"[{client.provider.value}] 流式响应出错，使用占位回复。"

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
            self._detect_coze,
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
        if provider == LLMProvider.COZE:
            # Coze API configuration
            endpoint = overrides.get(provider, "https://api.coze.cn/v3/chat")
            api_key = os.getenv("COZE_API_KEY", "pat_iohHxuKegfTwBdPxQByEOv6LRxXbz5LBPgwN53GMvCFy7lA1rB6f7MxjxjekKLyp")
            return RemoteLLMClient(provider, endpoint, api_key, timeout)
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

    def _detect_coze(self) -> Optional[LLMDetectionResult]:
        if os.getenv("COZE_API_KEY"):
            return LLMDetectionResult(provider=LLMProvider.COZE, reason="Found Coze API key.")
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
