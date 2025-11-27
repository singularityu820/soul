#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
火山方舟文生图服务
"""

import base64
import hashlib
import hmac
import json
import os
import time
import uuid
from datetime import datetime
from typing import Optional, Dict, Any

import requests


class VolcanoImageGenerator:
    """火山方舟文生图生成器"""
    
    def __init__(self):
        """
        初始化火山方舟文生图生成器
        """
        # 火山方舟API配置
        self.model_id = "doubao-seedream-4-0-250828"
        self.api_key = "b1d371ef-6ef8-449e-9e03-4eda9805708b"
        self.api_url = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
        
    def generate_image(self, prompt: str, size: str = "1024x1024", seed: int = -1) -> Dict[str, Any]:
        """
        生成图片
        
        Args:
            prompt: 图片描述文本
            size: 图片尺寸，默认1024x1024
            seed: 随机种子，默认-1表示随机
            
        Returns:
            Dict: 包含生成结果的字典
        """
        try:
            # 构建请求数据
            data = {
                "model": self.model_id,
                "prompt": prompt,
                "size": size,
                "seed": seed
            }
            
            # 设置请求头
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            # 发送请求
            response = requests.post(
                self.api_url,
                headers=headers,
                json=data,
                timeout=60
            )
            
            # 检查响应
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "data": result
                }
            else:
                return {
                    "success": False,
                    "error": f"API请求失败，状态码: {response.status_code}, 错误信息: {response.text}"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"生成图片时出错: {str(e)}"
            }
    
    def generate_and_save_image(self, prompt: str, output_dir: str = "generated_images", 
                               size: str = "1024x1024", seed: int = -1) -> str:
        """
        生成图片并保存到磁盘
        
        Args:
            prompt: 图片描述文本
            output_dir: 输出目录
            size: 图片尺寸
            seed: 随机种子
            
        Returns:
            str: 保存的文件名
        """
        # 生成图片
        result = self.generate_image(prompt, size, seed)
        
        if not result["success"]:
            raise Exception(f"生成图片失败: {result['error']}")
        
        # 获取图片数据
        data = result["data"]
        
        # 火山方舟API返回的图片数据格式可能不同，需要根据实际响应调整
        if "data" in data and len(data["data"]) > 0 and "url" in data["data"][0]:
            # 如果返回的是图片URL
            image_url = data["data"][0]["url"]
            
            # 下载图片
            response = requests.get(image_url, timeout=30)
            if response.status_code != 200:
                raise Exception(f"下载图片失败，状态码: {response.status_code}")
            
            image_data = response.content
        elif "data" in data and len(data["data"]) > 0 and "b64_json" in data["data"][0]:
            # 如果返回的是base64编码的图片数据
            image_data = base64.b64decode(data["data"][0]["b64_json"])
        else:
            raise Exception("无法从API响应中获取图片数据")
        
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 生成文件名
        timestamp = int(time.time())
        random_str = uuid.uuid4().hex[:8]
        filename = f"volcano_image_{timestamp}_{random_str}.png"
        filepath = os.path.join(output_dir, filename)
        
        # 保存图片
        with open(filepath, "wb") as f:
            f.write(image_data)
        
        return filename
    
    def generate_image_base64(self, prompt: str, size: str = "1024x1024", seed: int = -1) -> str:
        """
        生成图片并返回base64编码
        
        Args:
            prompt: 图片描述文本
            size: 图片尺寸
            seed: 随机种子
            
        Returns:
            str: base64编码的图片数据
        """
        # 生成图片
        result = self.generate_image(prompt, size, seed)
        
        if not result["success"]:
            raise Exception(f"生成图片失败: {result['error']}")
        
        # 获取图片数据
        data = result["data"]
        
        # 火山方舟API返回的图片数据格式可能不同，需要根据实际响应调整
        if "data" in data and len(data["data"]) > 0 and "url" in data["data"][0]:
            # 如果返回的是图片URL，下载并转换为base64
            image_url = data["data"][0]["url"]
            
            # 下载图片
            response = requests.get(image_url, timeout=30)
            if response.status_code != 200:
                raise Exception(f"下载图片失败，状态码: {response.status_code}")
            
            # 转换为base64
            image_data = response.content
            base64_data = base64.b64encode(image_data).decode('utf-8')
            return base64_data
        elif "data" in data and len(data["data"]) > 0 and "b64_json" in data["data"][0]:
            # 如果返回的是base64编码的图片数据
            return data["data"][0]["b64_json"]
        else:
            raise Exception("无法从API响应中获取图片数据")


# 测试函数
if __name__ == "__main__":
    generator = VolcanoImageGenerator()
    
    # 测试生成图片并保存
    try:
        print("正在生成图片...")
        filename = generator.generate_and_save_image(
            "一只可爱的橙色小猫在花园里玩耍，阳光明媚，卡通风格",
            size="1024x1024"
        )
        print(f"图片已保存到: {filename}")
    except Exception as e:
        print(f"生成图片失败: {e}")
    
    # 测试生成图片并返回base64
    try:
        print("\n正在生成图片(base64)...")
        base64_data = generator.generate_image_base64(
            "未来城市夜景，霓虹灯闪烁，赛博朋克风格",
            size="1024x1024"
        )
        print(f"图片数据长度: {len(base64_data)}")
    except Exception as e:
        print(f"生成图片失败: {e}")