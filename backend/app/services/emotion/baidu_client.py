"""
百度云人脸情绪识别API客户端
"""
import base64
import json
import logging
import time
from typing import Dict, Any, Optional, List
import aiohttp
import asyncio

logger = logging.getLogger(__name__)


class BaiduFaceClient:
    """百度云人脸情绪识别API客户端"""
    
    def __init__(self, api_key: str, secret_key: str):
        """
        初始化百度云API客户端
        
        Args:
            api_key: 百度云API Key
            secret_key: 百度云Secret Key
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.access_token = None
        self.token_expires_at = 0
        self.base_url = "https://aip.baidubce.com"
        
    async def get_access_token(self) -> str:
        """
        获取百度云API访问令牌
        
        Returns:
            访问令牌
        """
        # 检查当前令牌是否仍然有效
        if self.access_token and time.time() < self.token_expires_at:
            return self.access_token
            
        # 获取新的访问令牌
        url = f"{self.base_url}/oauth/2.0/token"
        params = {
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.secret_key
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.access_token = data.get("access_token")
                        # 设置令牌过期时间，提前5分钟刷新
                        self.token_expires_at = time.time() + data.get("expires_in", 2592000) - 300
                        logger.info("Successfully obtained Baidu API access token")
                        return self.access_token
                    else:
                        logger.error(f"Failed to get access token: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error getting access token: {e}")
            return None
    
    async def detect_emotion(self, image_data: bytes) -> Optional[Dict[str, Any]]:
        """
        检测图像中的人脸情绪
        
        Args:
            image_data: 图像二进制数据
            
        Returns:
            情绪检测结果，包含情绪标签、置信度和人脸位置信息
        """
        # 获取访问令牌
        access_token = await self.get_access_token()
        if not access_token:
            logger.error("Failed to get access token for emotion detection")
            return None
            
        # 确保图像数据不为空
        if image_data is None or (hasattr(image_data, '__len__') and len(image_data) == 0):
            logger.error("Empty image data provided")
            return None
            
        # 将图像转换为base64编码
        try:
            image_base64 = base64.b64encode(image_data).decode('utf-8')
        except Exception as e:
            logger.error(f"Error encoding image to base64: {e}")
            return None
        
        # 准备请求参数
        url = f"{self.base_url}/rest/2.0/face/v3/detect"
        params = {
            "access_token": access_token
        }
        
        data = {
            "image": image_base64,
            "image_type": "BASE64",
            "face_field": "face_shape,emotion,expression,face_type,gender,age,beauty,mask,spoofing",
            "max_face_num": 10,
            "face_type": "LIVE"  # 指定检测真实人脸，避免误判
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, params=params, data=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        # 检查API返回状态
                        if result.get("error_code") == 0:
                            faces = result.get("result", {}).get("face_list", [])
                            if faces:
                                # 选择置信度最高的人脸
                                best_face = max(faces, key=lambda f: f.get("face_probability", 0))
                                
                                # 提取情绪信息
                                emotion_type = best_face.get("emotion", {}).get("type", "neutral")
                                emotion_probability = best_face.get("emotion", {}).get("probability", 0)
                                
                                # 映射百度云情绪类型到标准情绪类型
                                emotion_mapping = {
                                    "angry": "angry",
                                    "disgust": "disgust", 
                                    "fear": "fear",
                                    "happy": "happy",
                                    "sad": "sad",
                                    "surprise": "surprise",
                                    "neutral": "neutral",
                                    "pouty": "sad",  # 撅嘴映射为悲伤
                                    "grimace": "disgust",  # 鬼脸映射为厌恶
                                    "none": "neutral"
                                }
                                
                                emotion_label = emotion_mapping.get(emotion_type, "neutral")
                                
                                # 提取人脸位置信息
                                location = best_face.get("location", {})
                                face_bbox = {
                                    "x": int(location.get("left", 0)),
                                    "y": int(location.get("top", 0)),
                                    "width": int(location.get("width", 100)),
                                    "height": int(location.get("height", 100))
                                }
                                
                                # 构建返回结果，使用单一数据源避免冗余
                                return {
                                    "emotion": emotion_label,
                                    "confidence": float(emotion_probability),
                                    "face_position": [face_bbox],  # 前端使用的数组格式
                                    "face_bbox": face_bbox,       # 后端使用的字典格式
                                    "timestamp": time.time(),
                                    "raw_response": result  # 保存原始响应，便于调试
                                }
                            else:
                                logger.warning("No faces detected in the image")
                                return None
                        else:
                            error_code = result.get("error_code")
                            error_msg = result.get("error_msg", "Unknown error")
                            logger.error(f"Baidu API error: {error_code} - {error_msg}")
                            return None
                    else:
                        logger.error(f"HTTP error: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error detecting emotion with Baidu API: {e}")
            return None