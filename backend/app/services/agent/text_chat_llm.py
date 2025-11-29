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
    provider: LLMProvider = LLMProvider.COZE
    api_key: Optional[str] = None
    model_id: str = ""
    endpoint: str = "https://api.coze.cn/v3/chat"
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
            if self.config.provider == LLMProvider.COZE:
                self.config.api_key = os.getenv("COZE_API_KEY", "pat_iohHxuKegfTwBdPxQByEOv6LRxXbz5LBPgwN53GMvCFy7lA1rB6f7MxjxjekKLyp")
            elif self.config.provider == LLMProvider.OPENAI:
                self.config.api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
            elif self.config.provider == LLMProvider.ZHIPU:
                self.config.api_key = os.getenv("ZHIPUAI_API_KEY")
            elif self.config.provider == LLMProvider.MODEL_SCOPE:
                self.config.api_key = os.getenv("MODELSCOPE_API_KEY")
        
        # 如果配置中没有提供模型ID，尝试从环境变量获取
        if not self.config.model_id:
            self.config.model_id = os.getenv("LLM_MODEL_ID", "default")

    async def generate_response(self, user_message: str, conversation_history: Optional[List[Dict[str, str]]] = None) -> str:
        """生成回复，不依赖情绪状态"""
        if not self.config.api_key:
            return f"[{self.config.provider.value}] 未配置 API 密钥，无法生成回复。"
        
        # 构建消息列表
        messages = []
        
        # 扣子智能体不需要系统提示，直接使用对话历史和用户消息
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
        if self.config.provider == LLMProvider.COZE:
            # Coze API requires bot_id instead of model
            bot_id = os.getenv("COZE_BOT_ID", "7577955978616995903")
            
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
                "user_id": "default_user",
                "additional_messages": additional_messages,
                "stream": True,  # 使用流式响应
                "auto_save_history": True
            }
            logger.info(f"Text chat LLM request - Provider: {self.config.provider.value}, Bot ID: {bot_id}")
        else:
            # Other providers
            payload = {
                "model": self.config.model_id,
                "messages": messages,
                "stream": False,
            }
            logger.info(f"Text chat LLM request - Provider: {self.config.provider.value}, Model: {self.config.model_id}")
        
        try:
            # 对于扣子API，使用流式响应获取完整回复
            if self.config.provider == LLMProvider.COZE:
                # 1. 发送流式请求
                async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                    # 2. 发送请求并处理流式响应
                    async with client.stream("POST", self.config.endpoint, headers=headers, json=payload) as response:
                        response.raise_for_status()
                        
                        # 3. 初始化变量
                        full_response = ""
                        
                        # 4. 遍历所有行
                        async for line in response.aiter_lines():
                            logger.debug(f"Coze stream: Raw line: '{line}'")
                            if line.strip():
                                # 5. 处理data行
                                if line.startswith("data: "):
                                    data_str = line[6:].strip()
                                    logger.debug(f"Coze stream: Data string: '{data_str}'")
                                    
                                    # 处理特殊情况：data字段被双引号包裹
                                    if data_str.startswith('"') and data_str.endswith('"'):
                                        data_str = data_str[1:-1]
                                        logger.debug(f"Coze stream: Stripped data string: '{data_str}'")
                                    
                                    if data_str == "[DONE]":
                                        logger.debug("Coze stream: Received [DONE] signal")
                                        break
                                    
                                    try:
                                        import json
                                        data = json.loads(data_str)
                                        logger.debug(f"Coze stream: Parsed data: {json.dumps(data, ensure_ascii=False)}")
                                        
                                        # 6. 处理扣子API的响应格式
                                        if isinstance(data, dict):
                                            # 处理 conversation.message.delta 事件 - 增量内容
                                            if data.get("event") == "conversation.message.delta":
                                                # 检查是否是assistant的回复
                                                if data.get("data", {}).get("role") == "assistant":
                                                    chunk = data.get("data", {}).get("content", "")
                                                    if chunk:
                                                        full_response += chunk
                                                        logger.debug(f"Coze stream: Added delta chunk: '{chunk}', full_response now: '{full_response[:50]}...'")
                                            # 处理 conversation.message.completed 事件 - 完整内容
                                            elif data.get("event") == "conversation.message.completed":
                                                print("识别到完成符号")
                                                # 只处理answer类型的completed事件，避免重复
                                                msg_type = data.get("data", {}).get("type")
                                                if msg_type == "answer":
                                                    completed_content = data.get("data", {}).get("content", "")
                                                    if completed_content:
                                                        # 检查是否与当前full_response有重叠，只使用新增部分
                                                        if completed_content.startswith(full_response):
                                                            # 完整内容是当前内容的延续，只添加新增部分
                                                            new_content = completed_content[len(full_response):]
                                                            if new_content:
                                                                full_response += new_content
                                                                logger.debug(f"Coze stream: Added new content from completed event: '{new_content}', full_response now: '{full_response[:50]}...'")
                                                        else:
                                                            # 完整内容与当前内容不连续，直接使用完整内容
                                                            full_response = completed_content
                                                            logger.debug(f"Coze stream: Received non-overlapping completed answer: '{full_response[:50]}...'")
                                            # 处理旧格式的流式响应（直接包含role和content字段）
                                            elif "content" in data and data.get("role") == "assistant":
                                                chunk = data["content"]
                                                if chunk:
                                                    full_response += chunk
                                                    logger.debug(f"Coze stream: Added legacy chunk: '{chunk}', full_response now: '{full_response[:50]}...'")
                                            # 处理旧格式的messages字段
                                            elif "messages" in data:
                                                for msg in data["messages"]:
                                                    if msg.get("role") == "assistant" and "content" in msg:
                                                        msg_content = msg["content"]
                                                        # 检查是否与当前full_response有重叠，只使用新增部分
                                                        if msg_content.startswith(full_response):
                                                            # 完整内容是当前内容的延续，只添加新增部分
                                                            new_content = msg_content[len(full_response):]
                                                            if new_content:
                                                                full_response += new_content
                                                                logger.debug(f"Coze stream: Added new content from messages: '{new_content}', full_response now: '{full_response[:50]}...'")
                                                        else:
                                                            # 完整内容与当前内容不连续，直接使用完整内容
                                                            full_response = msg_content
                                                            logger.debug(f"Coze stream: Received non-overlapping complete message: '{full_response[:50]}...'")
                                    except json.JSONDecodeError as e:
                                        logger.error(f"Failed to parse JSON from Coze stream: '{data_str}', error: {e}")
                                        continue
                            else:
                                logger.debug(f"Coze stream: Skipping empty line")
                        
                        # 9. 如果收集到了片段，返回拼接后的结果
                        if full_response:
                            logger.info(f"Text chat LLM response received (from chunks): {full_response[:50]}...")
                            return full_response
                        
                        # 10. 如果没有找到任何回复，返回错误信息
                        logger.warning(f"Coze API returned empty response")
                        return f"[{self.config.provider.value}] 未返回内容。"
            else:
                # Other providers
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
        
        # 扣子智能体不需要系统提示，直接使用对话历史和用户消息
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
        if self.config.provider == LLMProvider.COZE:
            # Coze API requires bot_id instead of model
            bot_id = os.getenv("COZE_BOT_ID", "7577955978616995903")
            
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
                "user_id": "default_user",
                "additional_messages": additional_messages,
                "stream": True,  # 启用流式响应
                "auto_save_history": True
            }
            logger.info(f"Text chat LLM stream request - Provider: {self.config.provider.value}, Bot ID: {bot_id}")
        else:
            # Other providers
            payload = {
                "model": self.config.model_id,
                "messages": messages,
                "stream": True,  # 启用流式响应
            }
            logger.info(f"Text chat LLM stream request - Provider: {self.config.provider.value}, Model: {self.config.model_id}")
        
        # 添加内容去重机制 - 使用更严格的哈希策略
        yielded_contents = set()  # 用于记录已发送的内容，避免重复
        
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                async with client.stream("POST", self.config.endpoint, headers=headers, json=payload) as response:
                    response.raise_for_status()
                    
                    # Coze stream handling
                    if self.config.provider == LLMProvider.COZE:
                        # 使用与test_coze_final.py相同的流式处理逻辑，但去掉message_ids检查，确保所有响应块都能被处理
                        async for line in response.aiter_lines():
                            if not line:
                                continue
                            
                            # 检查是否是数据行
                            if line.startswith("data:"):
                                data_str = line[5:].strip()
                                
                                # 检查是否结束
                                if data_str == "[DONE]":
                                    logger.info("Coze stream: Received [DONE] signal")
                                    break
                                
                                try:
                                    # 解析JSON数据
                                    import json
                                    data = json.loads(data_str)
                                    logger.debug(f"Coze stream: Parsed data: {json.dumps(data, ensure_ascii=False)}")
                                    
                                    # 检查数据是否是字典类型
                                    if isinstance(data, dict):
                                        # 处理 conversation.message.delta 事件 - 增量内容
                                        if data.get("event") == "conversation.message.delta":
                                            # 检查是否是assistant的回复
                                            if data.get("data", {}).get("role") == "assistant":
                                                content = data.get("data", {}).get("content", "")
                                                if content:
                                                    # 只处理text类型的内容，忽略JSON格式的verbose内容
                                                    if data.get("data", {}).get("content_type") == "text" and not content.startswith("{"):
                                                        logger.debug(f"Coze stream: Yielding delta chunk: '{content}'")
                                                        yield content
                                        # 处理 conversation.message.completed 事件 - 完整内容
                                        elif data.get("event") == "conversation.message.completed":
                                            # 只处理answer类型的completed事件
                                            msg_type = data.get("data", {}).get("type")
                                            if msg_type == "answer":
                                                completed_content = data.get("data", {}).get("content", "")
                                                if completed_content:
                                                    # 只处理text类型的内容，忽略JSON格式的verbose内容
                                                    if data.get("data", {}).get("content_type") == "text" and not completed_content.startswith("{"):
                                                        # 检查是否与之前的内容有重叠，只使用新增部分
                                                        if completed_content in yielded_contents:
                                                            logger.debug(f"Coze stream: Skipping duplicate completed content")
                                                            continue
                                                        
                                                        # 计算新增内容
                                                        new_content = ""
                                                        for prev_content in yielded_contents:
                                                            if completed_content.startswith(prev_content):
                                                                new_content = completed_content[len(prev_content):]
                                                                break
                                                        
                                                        if new_content:
                                                            # 只发送新增部分
                                                            logger.debug(f"Coze stream: Yielding new content from completed event: '{new_content}'")
                                                            yield new_content
                                                            # 更新已发送内容集合
                                                            yielded_contents.add(completed_content)
                                                        elif not yielded_contents:
                                                            # 如果是第一次收到内容，直接发送
                                                            logger.debug(f"Coze stream: Yielding first completed content: '{completed_content}'")
                                                            yield completed_content
                                                            yielded_contents.add(completed_content)
                                        # 处理旧格式的流式响应（直接包含role和content字段）
                                        elif data.get("role") == "assistant":
                                            # 处理所有类型的assistant回复，包括answer、verbose和follow_up
                                            content = data.get("content", "")
                                            if content:
                                                # 只处理text类型的内容，忽略JSON格式的verbose内容
                                                if data.get("content_type") == "text" and not content.startswith("{"):
                                                    logger.debug(f"Coze stream: Yielding legacy chunk: '{content}'")
                                                    yield content
                                except (json.JSONDecodeError, AttributeError) as e:
                                    # 忽略解析错误，继续处理下一行
                                    logger.warning(f"Failed to parse JSON from Coze stream: {data_str}, error: {e}")
                                    continue
                    else:
                        # Other providers stream handling
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