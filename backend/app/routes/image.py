#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文生图API路由
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import os
import uuid
import time
from datetime import datetime

from app.services.image_generation import XunfeiImageGenerator

# 创建路由器
router = APIRouter(prefix="/image", tags=["image"])

# 配置API参数
APPID = "0a40443c"
APIKey = "2bdde62a5752a75466bfcd8f7ed24887"
APISecret = "NzZiNGQyYTk0NzAwNmUwZjk5MWYwN2Y2"

# 创建文生图服务实例
image_generator = XunfeiImageGenerator(APPID, APIKey, APISecret)

# 请求模型
class ImageGenerationRequest(BaseModel):
    prompt: str
    temperature: Optional[float] = 0.5
    max_tokens: Optional[int] = 2048
    save_to_disk: Optional[bool] = True

# 响应模型
class ImageGenerationResponse(BaseModel):
    success: bool
    image_url: Optional[str] = None
    image_data: Optional[str] = None
    message: str


@router.post("/generate", response_model=ImageGenerationResponse)
async def generate_image(request: ImageGenerationRequest):
    """
    生成图片
    
    Args:
        request: 图片生成请求参数
    
    Returns:
        生成的图片URL或base64数据
    """
    try:
        # 生成唯一文件名
        timestamp = int(time.time())
        unique_id = str(uuid.uuid4())[:8]
        filename = f"image_{timestamp}_{unique_id}.png"
        save_path = os.path.join("generated_images", filename)
        
        # 生成图片
        if request.save_to_disk:
            # 保存到磁盘
            result_path = image_generator.generate_and_save_image(
                request.prompt, 
                save_path,
                request.temperature,
                request.max_tokens
            )
            
            if result_path:
                # 返回文件路径
                return ImageGenerationResponse(
                    success=True,
                    image_url=f"/generated_images/{filename}",
                    message="图片生成成功"
                )
            else:
                return ImageGenerationResponse(
                    success=False,
                    message="图片生成失败"
                )
        else:
            # 返回base64数据
            image_data = image_generator.generate_image(
                request.prompt,
                request.temperature,
                request.max_tokens
            )
            
            if image_data:
                return ImageGenerationResponse(
                    success=True,
                    image_data=image_data,
                    message="图片生成成功"
                )
            else:
                return ImageGenerationResponse(
                    success=False,
                    message="图片生成失败"
                )
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成图片时出错: {str(e)}")


@router.get("/generated/{filename}")
async def get_generated_image(filename: str):
    """
    获取生成的图片
    
    Args:
        filename: 图片文件名
    
    Returns:
        图片文件
    """
    from fastapi.responses import FileResponse
    
    file_path = os.path.join("generated_images", filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="图片不存在")
    
    return FileResponse(file_path)