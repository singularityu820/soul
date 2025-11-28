from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import AsyncIterator, Dict, List, Optional

import httpx

from ...config import LLMProvider, LLMServiceConfig
from ...schemas import AgentMessage

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TextChatConfig:
    """独立文本聊天配置"""
    provider: LLMProvider = LLMProvider.DOUBAO
    api_key: Optional[str] = None
    model_id: str = "doubao-seed-1-6-251015"
    endpoint: str = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
    timeout: float = 60.0
    system_prompt: str = "你是一位贴心的聊天搭子，根据用户的消息给出温暖、自然的回答，语言要口语化，适当使用 emoji，让对话轻松。"


class TextChatLLMService:
    """独立文本聊天LLM服务，不依赖多模态情绪识别系统"""
    
    def __init__(self, config: Optional[TextChatConfig] = None) -> None:
        # Ensure environment variables are loaded
        from pathlib import Path
        from dotenv import load_dotenv
        env_path = Path(__file__).parent.parent.parent.parent.parent / ".env"
        load_dotenv(env_path)
        
        self.config = config or TextChatConfig()
        
        # 如果配置中没有提供API密钥，尝试从环境变量获取
        if not self.config.api_key:
            if self.config.provider == LLMProvider.DOUBAO:
                self.config.api_key = os.getenv("DOUBAO_API_KEY")
            elif self.config.provider == LLMProvider.OPENAI:
                self.config.api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
            elif self.config.provider == LLMProvider.ZHIPU:
                self.config.api_key = os.getenv("ZHIPUAI_API_KEY")
            elif self.config.provider == LLMProvider.MODEL_SCOPE:
                self.config.api_key = os.getenv("MODELSCOPE_API_KEY")
        
        # 如果配置中没有提供模型ID，尝试从环境变量获取
        if self.config.provider == LLMProvider.DOUBAO and not self.config.model_id:
            self.config.model_id = os.getenv("DOUBAO_MODEL_ID", "doubao-seed-1-6-251015")
        elif not self.config.model_id:
            self.config.model_id = os.getenv("LLM_MODEL_ID", "default")

    async def generate_response(self, user_message: str, conversation_history: Optional[List[Dict[str, str]]] = None) -> str:
        """生成回复，不依赖情绪状态"""
        if not self.config.api_key:
            return f"[{self.config.provider.value}] 未配置 API 密钥，无法生成回复。"
        
        # 构建消息列表
        messages = []
        
        # 添加系统提示
        messages.append({"role": "system", "content": self.config.system_prompt})
        
        # 添加对话历史（如果有）
        if conversation_history:
            messages.extend(conversation_history)
        
        # 添加用户当前消息
        messages.append({"role": "user", "content": user_message})
        
        # 准备请求头
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }
        
        # 准备请求体
        payload = {
            "model": self.config.model_id,
            "messages": messages,
            "stream": False,
        }
        
        logger.info(f"Text chat LLM request - Provider: {self.config.provider.value}, Model: {self.config.model_id}")
        
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                response = await client.post(self.config.endpoint, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                content = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content")
                )
                if content:
                    logger.info(f"Text chat LLM response received: {content[:50]}...")
                    return content
                return f"[{self.config.provider.value}] 未返回内容。"
        except asyncio.CancelledError:
            logger.warning("Text chat LLM request was cancelled")
            return f"[{self.config.provider.value}] 请求被取消，请重试。"
        except httpx.HTTPError as e:
            logger.warning(f"Text chat LLM HTTP error: {e}")
            return f"[{self.config.provider.value}] 接口不可用，请稍后再试。"
        except Exception as e:
            logger.exception(f"Text chat LLM error: {e}")
            return f"[{self.config.provider.value}] 生成回复时出错，请稍后再试。"

    async def generate_response_stream(self, user_message: str, conversation_history: Optional[List[Dict[str, str]]] = None) -> AsyncIterator[str]:
        """生成流式回复，不依赖情绪状态"""
        if not self.config.api_key:
            yield f"[{self.config.provider.value}] 未配置 API 密钥，无法生成回复。"
            return
        
        # 构建消息列表
        messages = []
        
        # 添加系统提示
        messages.append({"role": "system", "content": self.config.system_prompt})
        
        # 添加对话历史（如果有）
        if conversation_history:
            messages.extend(conversation_history)
        
        # 添加用户当前消息
        messages.append({"role": "user", "content": user_message})
        
        # 准备请求头
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }
        
        # 准备请求体
        payload = {
            "model": self.config.model_id,
            "messages": messages,
            "stream": True,  # 启用流式响应
        }
        
        logger.info(f"Text chat LLM stream request - Provider: {self.config.provider.value}, Model: {self.config.model_id}")
        
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                async with client.stream("POST", self.config.endpoint, headers=headers, json=payload) as response:
                    response.raise_for_status()
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
        except asyncio.CancelledError:
            logger.warning("Text chat LLM Stream request was cancelled")
            yield f"[{self.config.provider.value}] 流式请求被取消，请重试。"
        except httpx.HTTPError as e:
            logger.warning(f"Text chat LLM Stream HTTP error: {e}")
            yield f"[{self.config.provider.value}] 流式接口不可用，请稍后再试。"
        except Exception as e:
            logger.warning(f"Text chat LLM Stream error: {e}")
            yield f"[{self.config.provider.value}] 流式响应出错，请稍后再试。"

    def create_agent_message(self, text: str) -> AgentMessage:
        """创建AgentMessage对象，用于与现有系统兼容"""
        return AgentMessage(
            text=text,
            voice_style="balanced",
            language="zh",
            emotion="neutral",
            llm_provider=self.config.provider.value,
            tts_provider=None,
            audio_reference=None,
            audio_segments=None,
        )