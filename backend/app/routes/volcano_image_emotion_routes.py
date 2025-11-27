#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
火山文生图情绪识别与图片调整API路由
"""

import base64
import os
import uuid
from datetime import datetime
from typing import Optional, Dict, List

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from app.services.volcano_image_generation import VolcanoImageGenerator
from app.services.emotion_recognition import EmotionRecognitionService


# 创建路由器
router = APIRouter(prefix="/volcano-image-emotion", tags=["volcano-image-emotion"])


# 请求模型
class EmotionBasedImageRequest(BaseModel):
    """基于情绪的图片生成请求模型"""
    text_content: str = Field(..., description="日记文本内容", min_length=1, max_length=2000)
    custom_prompt: Optional[str] = Field(None, description="自定义图片提示词", max_length=1000)
    size: str = Field(default="1024x1024", description="图片尺寸", pattern="^(1024x1024|1024x1792|1792x1024)$")
    seed: int = Field(default=-1, description="随机种子，-1表示随机")


# 响应模型
class EmotionBasedImageResponse(BaseModel):
    """基于情绪的图片生成响应模型"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    image_url: Optional[str] = Field(None, description="生成的图片URL")
    base64_data: Optional[str] = Field(None, description="base64编码的图片数据")
    emotion: str = Field(..., description="识别的情绪")
    confidence: float = Field(..., description="情绪识别置信度")
    original_prompt: str = Field(..., description="原始提示词")
    adjustment_options: Dict[str, str] = Field(..., description="可用的调整选项")
    timestamp: str = Field(..., description="生成时间戳")


# 图片调整请求模型
class ImageAdjustmentRequest(BaseModel):
    """图片调整请求模型"""
    original_prompt: str = Field(..., description="原始提示词", min_length=1, max_length=1000)
    emotion: str = Field(..., description="情绪类型")
    adjustment_type: str = Field(..., description="调整选项，如'风格更暖'、'增加细节'、'更换场景'")
    size: str = Field(default="1024x1024", description="图片尺寸", pattern="^(1024x1024|1024x1792|1792x1024)$")
    seed: int = Field(default=-1, description="随机种子，-1表示随机")


# 图片调整响应模型
class ImageAdjustmentResponse(BaseModel):
    """图片调整响应模型"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    image_url: Optional[str] = Field(None, description="生成的图片URL")
    base64_data: Optional[str] = Field(None, description="base64编码的图片数据")
    original_prompt: str = Field(..., description="原始提示词")
    adjusted_prompt: str = Field(..., description="调整后的提示词")
    adjustment_type: str = Field(..., description="调整类型")
    timestamp: str = Field(..., description="生成时间戳")


# 依赖注入函数
def get_image_generator():
    """获取图片生成器实例"""
    return VolcanoImageGenerator()


def get_emotion_service():
    """获取情绪识别服务实例"""
    return EmotionRecognitionService()


@router.post("/generate-with-emotion", response_model=EmotionBasedImageResponse)
async def generate_image_with_emotion(
    request: EmotionBasedImageRequest,
    save_to_disk: bool = Query(True, description="是否保存到磁盘"),
    generator: VolcanoImageGenerator = Depends(get_image_generator),
    emotion_service: EmotionRecognitionService = Depends(get_emotion_service)
):
    """
    基于情绪生成图片
    
    Args:
        request: 图片生成请求
        save_to_disk: 是否保存到磁盘
        generator: 图片生成器
        emotion_service: 情绪识别服务
        
    Returns:
        EmotionBasedImageResponse: 生成结果
    """
    try:
        timestamp = datetime.now().isoformat()
        
        # 识别情绪
        emotion, confidence = emotion_service.recognize_emotion(request.text_content)
        
        # 生成融合情绪的提示词
        prompt = emotion_service.extract_image_prompt_with_emotion(
            request.text_content, 
            request.custom_prompt
        )
        
        # 获取调整选项
        adjustment_options = emotion_service.get_emotion_adjustment_options(emotion)
        
        if save_to_disk:
            # 生成图片并保存到磁盘
            filename = generator.generate_and_save_image(
                prompt=prompt,
                size=request.size,
                seed=request.seed
            )
            
            # 构建图片URL
            image_url = f"/generated_images/{filename}"
            
            return EmotionBasedImageResponse(
                success=True,
                message="图片生成成功",
                image_url=image_url,
                emotion=emotion,
                confidence=confidence,
                original_prompt=prompt,
                adjustment_options=adjustment_options,
                timestamp=timestamp
            )
        else:
            # 生成图片并返回base64
            base64_data = generator.generate_image_base64(
                prompt=prompt,
                size=request.size,
                seed=request.seed
            )
            
            return EmotionBasedImageResponse(
                success=True,
                message="图片生成成功",
                base64_data=base64_data,
                emotion=emotion,
                confidence=confidence,
                original_prompt=prompt,
                adjustment_options=adjustment_options,
                timestamp=timestamp
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成图片失败: {str(e)}")


@router.post("/adjust-image", response_model=ImageAdjustmentResponse)
async def adjust_image(
    request: ImageAdjustmentRequest,
    save_to_disk: bool = Query(True, description="是否保存到磁盘"),
    generator: VolcanoImageGenerator = Depends(get_image_generator),
    emotion_service: EmotionRecognitionService = Depends(get_emotion_service)
):
    """
    根据用户选择调整图片
    
    Args:
        request: 图片调整请求
        save_to_disk: 是否保存到磁盘
        generator: 图片生成器
        emotion_service: 情绪识别服务
        
    Returns:
        ImageAdjustmentResponse: 调整结果
    """
    try:
        timestamp = datetime.now().isoformat()
        
        # 获取调整选项
        adjustment_options = emotion_service.get_emotion_adjustment_options(request.emotion)
        
        # 获取调整描述
        adjustment_description = adjustment_options.get(request.adjustment_type, "")
        
        # 构建调整后的提示词
        if adjustment_description:
            adjusted_prompt = f"{request.original_prompt}, {adjustment_description}"
        else:
            adjusted_prompt = request.original_prompt
        
        if save_to_disk:
            # 生成图片并保存到磁盘
            filename = generator.generate_and_save_image(
                prompt=adjusted_prompt,
                size=request.size,
                seed=request.seed
            )
            
            # 构建图片URL
            image_url = f"/generated_images/{filename}"
            
            return ImageAdjustmentResponse(
                success=True,
                message="图片调整成功",
                image_url=image_url,
                original_prompt=request.original_prompt,
                adjusted_prompt=adjusted_prompt,
                adjustment_type=request.adjustment_type,
                timestamp=timestamp
            )
        else:
            # 生成图片并返回base64
            base64_data = generator.generate_image_base64(
                prompt=adjusted_prompt,
                size=request.size,
                seed=request.seed
            )
            
            return ImageAdjustmentResponse(
                success=True,
                message="图片调整成功",
                base64_data=base64_data,
                original_prompt=request.original_prompt,
                adjusted_prompt=adjusted_prompt,
                adjustment_type=request.adjustment_type,
                timestamp=timestamp
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"调整图片失败: {str(e)}")


@router.get("/emotion-types")
async def get_emotion_types(
    emotion_service: EmotionRecognitionService = Depends(get_emotion_service)
):
    """
    获取支持的情绪类型列表
    
    Args:
        emotion_service: 情绪识别服务
        
    Returns:
        Dict: 情绪类型列表
    """
    emotion_types = list(emotion_service.emotion_keywords.keys())
    
    return {
        "success": True,
        "message": "获取情绪类型成功",
        "emotion_types": emotion_types,
        "default_adjustment_options": ["风格更暖", "增加细节", "更换场景"]
    }


@router.get("/adjustment-options/{emotion}")
async def get_emotion_adjustment_options(
    emotion: str,
    emotion_service: EmotionRecognitionService = Depends(get_emotion_service)
):
    """
    获取特定情绪的调整选项
    
    Args:
        emotion: 情绪类型
        emotion_service: 情绪识别服务
        
    Returns:
        Dict: 情绪调整选项
    """
    try:
        adjustment_options = emotion_service.get_emotion_adjustment_options(emotion)
        
        return {
            "success": True,
            "message": "获取情绪调整选项成功",
            "emotion": emotion,
            "adjustment_options": adjustment_options
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"获取情绪调整选项失败: {str(e)}",
            "emotion": emotion,
            "adjustment_options": {}
        }