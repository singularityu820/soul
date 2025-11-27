#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
火山方舟文生图API路由
"""

import base64
import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from app.services.volcano_image_generation import VolcanoImageGenerator


# 创建路由器
router = APIRouter(prefix="/volcano-image", tags=["volcano-image"])


# 请求模型
class ImageGenerationRequest(BaseModel):
    """图片生成请求模型"""
    prompt: str = Field(..., description="图片描述文本", min_length=1, max_length=1000)
    size: str = Field(default="1024x1024", description="图片尺寸", pattern="^(1024x1024|1024x1792|1792x1024)$")
    seed: int = Field(default=-1, description="随机种子，-1表示随机")


# 响应模型
class ImageGenerationResponse(BaseModel):
    """图片生成响应模型"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    image_url: Optional[str] = Field(None, description="生成的图片URL")
    base64_data: Optional[str] = Field(None, description="base64编码的图片数据")
    timestamp: str = Field(..., description="生成时间戳")


# 依赖注入函数
def get_image_generator():
    """获取图片生成器实例"""
    return VolcanoImageGenerator()


@router.post("/generate", response_model=ImageGenerationResponse)
async def generate_image(
    request: ImageGenerationRequest,
    save_to_disk: bool = Query(True, description="是否保存到磁盘"),
    generator: VolcanoImageGenerator = Depends(get_image_generator)
):
    """
    生成图片
    
    Args:
        request: 图片生成请求
        save_to_disk: 是否保存到磁盘
        generator: 图片生成器
        
    Returns:
        ImageGenerationResponse: 生成结果
    """
    try:
        timestamp = datetime.now().isoformat()
        
        if save_to_disk:
            # 生成图片并保存到磁盘
            filename = generator.generate_and_save_image(
                prompt=request.prompt,
                size=request.size,
                seed=request.seed
            )
            
            # 构建图片URL
            image_url = f"/generated_images/{filename}"
            
            return ImageGenerationResponse(
                success=True,
                message="图片生成成功",
                image_url=image_url,
                timestamp=timestamp
            )
        else:
            # 生成图片并返回base64
            base64_data = generator.generate_image_base64(
                prompt=request.prompt,
                size=request.size,
                seed=request.seed
            )
            
            return ImageGenerationResponse(
                success=True,
                message="图片生成成功",
                base64_data=base64_data,
                timestamp=timestamp
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成图片失败: {str(e)}")


@router.get("/models")
async def get_available_models():
    """
    获取可用的模型列表
    
    Returns:
        Dict: 模型列表
    """
    return {
        "models": [
            {
                "id": "doubao-seedream-4-0-250828",
                "name": "豆包文生图模型",
                "description": "火山方舟提供的文生图模型",
                "supported_sizes": ["1024x1024", "1024x1792", "1792x1024"]
            }
        ]
    }