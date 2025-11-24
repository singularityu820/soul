"""Video emotion detection routes."""

import io
import logging
import time
from typing import Optional

import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from PIL import Image

from ..dependencies import get_face_tool, get_pipeline

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/video/emotion")
async def detect_video_emotion(
    frame: UploadFile = File(...),
    room_id: Optional[str] = Form(None),
) -> dict:
    """
    视频情绪检测接口
    
    接收视频帧，使用FaceEmotionTool进行情绪检测，返回检测结果
    
    Args:
        frame: 视频帧图像文件
        room_id: 可选的房间ID，用于将结果发送到特定房间
    
    Returns:
        {
            "emotion": "检测到的情绪",
            "confidence": 置信度,
            "face_position": {"x": x, "y": y, "width": w, "height": h}
        }
    """
    try:
        face_tool = get_face_tool()
        pipeline = await get_pipeline()
        
        # 1. 读取视频帧数据
        frame_data = await frame.read()
        logger.info(f"Received video frame: {len(frame_data)} bytes, content_type={frame.content_type}")
        
        # 2. 将帧数据转换为numpy数组
        # 将字节数据转换为PIL Image
        image = Image.open(io.BytesIO(frame_data))
        
        # 转换为numpy数组 (RGB格式)
        frame_array = np.array(image)
        logger.info(f"Converted frame to numpy array with shape: {frame_array.shape}")
        
        # 3. 使用FaceEmotionTool进行情绪检测
        logger.info("Calling face_tool.update_frame")
        await face_tool.update_frame(frame_array)
        logger.info("Calling face_tool.analyze")
        emotion_result = await face_tool.analyze()
        logger.info(f"Emotion analysis result: {emotion_result}")
        
        # 4. 获取最新的人脸检测结果
        face_bbox = None
        if hasattr(face_tool, '_latest_observation') and face_tool._latest_observation:
            face_bbox = face_tool._latest_observation.get('face_bbox')
            logger.info(f"Face bbox from _latest_observation: {face_bbox}")
        
        # 如果从_latest_observation获取不到，尝试从metadata获取
        if not face_bbox and hasattr(emotion_result, 'metadata') and emotion_result.metadata:
            face_bbox = emotion_result.metadata.get('face_bbox')
            logger.info(f"Face bbox from metadata: {face_bbox}")
        
        # 5. 构建返回结果
        result = {
            "emotion": emotion_result.label,
            "confidence": emotion_result.confidence,
            "mood_score": emotion_result.mood_score,
            "source": emotion_result.source,
        }
        
        if face_bbox:
            result["face_position"] = [face_bbox]
            logger.info(f"Using face_bbox in result: {face_bbox}")
        else:
            # 如果没有人脸位置信息，生成默认位置
            height, width = frame_array.shape[:2]
            default_bbox = {
                "x": int(width * 0.3),
                "y": int(height * 0.2),
                "width": int(width * 0.4),
                "height": int(height * 0.5)
            }
            result["face_position"] = [default_bbox]
            logger.info(f"Using default face bbox: {default_bbox}")
        
        # 6. 如果有房间ID，通过WebSocket发送结果到前端
        if room_id:
            try:
                # 通过pipeline的WebSocket发送情绪数据
                await pipeline.broadcast_face_emotion(room_id, {
                    "label": emotion_result.label,
                    "confidence": emotion_result.confidence,
                    "face_position": [face_bbox] if face_bbox else None,
                    "timestamp": time.time()
                })
                logger.info(f"Emotion result sent to room {room_id}")
            except Exception as e:
                logger.error(f"Failed to send emotion result to room {room_id}: {e}")
        
        logger.info(f"Final emotion detection result: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Video emotion detection failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"情绪检测失败: {str(e)}")
