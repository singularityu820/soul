#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
讯飞星火文生图API服务模块
可直接集成到项目中使用
"""

import base64
import hashlib
import hmac
import json
import time
import requests
from datetime import datetime
from urllib.parse import urlencode, quote
import os


class XunfeiImageGenerator:
    """讯飞星火文生图API服务类"""
    
    def __init__(self, appid, api_key, api_secret):
        """
        初始化文生图服务
        
        Args:
            appid: 应用ID
            api_key: API Key
            api_secret: API Secret
        """
        self.appid = appid
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_url = "https://spark-api.cn-huabei-1.xf-yun.com/v2.1/tti"
    
    def generate_auth_url(self):
        """
        生成鉴权URL
        
        Returns:
            带鉴权参数的完整URL
        """
        # 生成RFC1123格式的日期
        date = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
        
        # 从URL中解析host
        from urllib.parse import urlparse
        parsed_url = urlparse(self.api_url)
        host = parsed_url.netloc
        
        # 拼接字符串 - 使用POST方法
        signature_origin = f"host: {host}\ndate: {date}\nPOST {parsed_url.path} HTTP/1.1"
        
        # 使用hmac-sha256进行加密
        signature_sha = hmac.new(
            self.api_secret.encode('utf-8'),
            signature_origin.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        
        # base64编码
        signature = base64.b64encode(signature_sha).decode(encoding='utf-8')
        
        # 构建authorization_origin
        authorization_origin = f'api_key="{self.api_key}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature}"'
        
        # base64编码authorization
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')
        
        # 将请求的鉴权参数组合为字典
        v = {
            "authorization": authorization,
            "date": date,
            "host": host
        }
        
        # 拼接鉴权参数，生成url
        url = self.api_url + '?' + urlencode(v)
        
        return url
    
    def generate_image(self, prompt, temperature=0.5, max_tokens=2048):
        """
        生成图片
        
        Args:
            prompt: 图片描述文本
            temperature: 控制生成随机性，范围0-1
            max_tokens: 最大令牌数
        
        Returns:
            生成的图片base64数据，失败返回None
        """
        # 生成鉴权URL
        auth_url = self.generate_auth_url()
        
        # 构建请求数据
        data = {
            "header": {
                "app_id": self.appid
            },
            "parameter": {
                "chat": {
                    "domain": "general",
                    "temperature": temperature,
                    "max_tokens": max_tokens
                }
            },
            "payload": {
                "message": {
                    "text": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                }
            }
        }
        
        # 发送请求
        headers = {
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.post(auth_url, json=data, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            
            # 检查响应状态
            if result.get('header', {}).get('code') != 0:
                error_msg = result.get('header', {}).get('message', '未知错误')
                print(f"API返回错误: {error_msg}")
                return None
            
            # 提取图片数据
            if 'payload' in result and 'choices' in result['payload']:
                return result['payload']['choices']['text'][0]['content']
            elif 'payload' in result and 'message' in result['payload'] and 'result' in result['payload']['message']:
                return result['payload']['message']['result']
            else:
                print("响应中未找到图片数据")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"请求异常: {e}")
            return None
        except Exception as e:
            print(f"处理响应时出错: {e}")
            return None
    
    def generate_and_save_image(self, prompt, save_path, temperature=0.5, max_tokens=2048):
        """
        生成图片并保存到文件
        
        Args:
            prompt: 图片描述文本
            save_path: 图片保存路径
            temperature: 控制生成随机性，范围0-1
            max_tokens: 最大令牌数
        
        Returns:
            成功返回保存路径，失败返回None
        """
        # 生成图片
        image_data = self.generate_image(prompt, temperature, max_tokens)
        
        if image_data:
            try:
                # 解码base64图片数据
                image_binary = base64.b64decode(image_data)
                
                # 确保目录存在
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                
                # 保存图片
                with open(save_path, 'wb') as f:
                    f.write(image_binary)
                
                return save_path
            except Exception as e:
                print(f"保存图片时出错: {e}")
                return None
        else:
            return None


# 示例使用
if __name__ == "__main__":
    # 配置API参数
    APPID = "0a40443c"
    APIKey = "2bdde62a5752a75466bfcd8f7ed24887"
    APISecret = "NzZiNGQyYTk0NzAwNmUwZjk5MWYwN2Y2"
    
    # 创建文生图服务实例
    generator = XunfeiImageGenerator(APPID, APIKey, APISecret)
    
    # 生成图片
    prompt = "一只可爱的橙色小猫在花园里玩耍，阳光明媚，卡通风格"
    save_path = "generated_images/service_test.png"
    
    print(f"正在生成图片，描述: {prompt}")
    result = generator.generate_and_save_image(prompt, save_path)
    
    if result:
        print(f"图片生成成功，保存到: {result}")
    else:
        print("图片生成失败!")