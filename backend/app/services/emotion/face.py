from __future__ import annotations

import asyncio
import time
import random
import logging
from dataclasses import dataclass
from typing import Optional, Any, Dict

try:
    from deepface import DeepFace
except Exception:  # pragma: no cover - DeepFace optional
    DeepFace = None  # type: ignore

from .baidu_client import BaiduFaceClient
from ...config import FaceEmotionConfig
from ...schemas import ChannelEmotion

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class FaceObservation:
    label: str
    confidence: float
    intensity: float
    faces_detected: int
    timestamp: float


class FaceEmotionTool:
    """Face emotion tool with optional DeepFace integration.

    Usage patterns:
    - If you have DeepFace installed and want to use its emotion model, set
      `use_deepface=True` and optionally pass `deepface_kwargs` to control
      analyzer behaviour (e.g. detector_backend, enforce_detection).
    - Call `update_frame(frame)` with an RGB numpy array or bytes (image file
      bytes). The tool will attempt to run DeepFace.analyze on the latest
      frame inside `analyze()` (non-blocking to the event loop).

    The class is defensive: if DeepFace is not available or analysis fails,
    it falls back to a lightweight simulated output so the pipeline keeps
    operating.
    """

    def __init__(
        self,
        config: FaceEmotionConfig | None = None,
        *,
        use_deepface: bool = False,
        deepface_kwargs: Optional[Dict[str, Any]] = None,
        use_baidu_api: bool = True,
        baidu_api_key: Optional[str] = None,
        baidu_secret_key: Optional[str] = None,
    ) -> None:
        self.config = config or FaceEmotionConfig()
        self._rng = random.Random()
        self._lock = asyncio.Lock()
        self._latest: Optional[FaceObservation] = None

        # Frame for model inference (store RGB numpy array or raw bytes)
        self._latest_frame: Optional[Any] = None
        
        # 添加_latest_observation属性初始化
        self._latest_observation: Optional[Dict[str, Any]] = None

        # DeepFace integration flags/options
        self.use_deepface = bool(use_deepface and DeepFace is not None)
        self.deepface_kwargs = deepface_kwargs or {}
        
        # 百度云API集成
        self.use_baidu_api = use_baidu_api
        self.baidu_client = None
        if self.use_baidu_api and baidu_api_key and baidu_secret_key:
            self.baidu_client = BaiduFaceClient(baidu_api_key, baidu_secret_key)
            logger.info("Baidu API client initialized")
        elif self.use_baidu_api:
            logger.warning("Baidu API requested but credentials not provided")

        if use_deepface and DeepFace is None:
            # warn via metadata at runtime; no import at module import time
            self.use_deepface = False
            logger.warning("DeepFace not available, falling back to simulation")
        else:
            logger.info(f"DeepFace available and enabled: {self.use_deepface}")

    async def update_observation(
        self, label: str, confidence: float, intensity: float, faces_detected: int
    ) -> None:
        observation = FaceObservation(
            label=label,
            confidence=confidence,
            intensity=intensity,
            faces_detected=faces_detected,
            timestamp=time.time(),
        )
        async with self._lock:
            self._latest = observation

    async def update_frame(self, frame: Any) -> None:
        """Store a recent frame for later inference.

        Expected frame: RGB numpy array (H,W,3) is preferred. If bytes are
        provided, DeepFace wrapper will attempt to decode when available.
        """
        async with self._lock:
            self._latest_frame = frame

    async def detect_from_frame(self, frame_array: Any) -> Optional[Dict[str, Any]]:
        """
        从视频帧检测情绪
        
        Args:
            frame_array: 视频帧的numpy数组 (RGB格式)
            
        Returns:
            情绪结果字典，包含情绪标签和置信度等信息
        """
        try:
            # 优先使用百度云API进行情绪检测
            if self.use_baidu_api and self.baidu_client:
                # 确保图像格式正确：转换为RGB格式的字节数据
                if hasattr(frame_array, 'shape') and len(frame_array.shape) == 3:
                    # 如果是numpy数组，确保是RGB格式
                    import numpy as np
                    if frame_array.shape[2] == 4:  # RGBA
                        frame_array = frame_array[:, :, :3]  # 移除alpha通道
                    elif frame_array.shape[2] == 1:  # 灰度图
                        frame_array = np.stack([frame_array[:, :, 0]] * 3, axis=2)  # 转换为RGB
                    
                    # 确保是uint8格式
                    if frame_array.dtype != np.uint8:
                        frame_array = (frame_array * 255).astype(np.uint8)
                    
                    # 转换为字节数据
                    import io
                    from PIL import Image
                    img = Image.fromarray(frame_array)
                    img_byte_arr = io.BytesIO()
                    img.save(img_byte_arr, format='JPEG', quality=90)
                    image_bytes = img_byte_arr.getvalue()
                else:
                    # 如果不是numpy数组，直接使用原始数据
                    image_bytes = frame_array
                
                # 调用百度云API
                baidu_result = await self.baidu_client.detect_emotion(image_bytes)
                
                if baidu_result:
                    # 百度云API已经返回了正确格式的数据，包含face_position和face_bbox
                    # 更新观察数据
                    await self.update_observation_dict(baidu_result)
                    return baidu_result
                else:
                    logger.warning("Baidu API detection failed, falling back to simulation")
            
            # 如果百度云API不可用或失败，尝试使用DeepFace
            if self.use_deepface:
                deepface_result = await self._run_deepface(frame_array)
                
                if deepface_result:
                    # 处理DeepFace返回的结果
                    # DeepFace.analyze可能返回单个字典或列表，统一处理为列表
                    if isinstance(deepface_result, dict):
                        candidates = [deepface_result]
                    elif isinstance(deepface_result, list):
                        candidates = deepface_result
                    else:
                        candidates = []
                    
                    if candidates:
                        # 选择置信度最高的人脸
                        best = None
                        best_conf = -1.0
                        for c in candidates:
                            # 获取情绪映射
                            emotion_map = c.get("emotion") or c.get("emotions") or {}
                            if isinstance(emotion_map, dict) and emotion_map:
                                # 获取主导情绪
                                dominant = c.get("dominant_emotion")
                                if dominant and dominant in emotion_map:
                                    conf = float(emotion_map[dominant]) / 100.0
                                else:
                                    # 回退到最高分数
                                    conf = max(float(v) for v in emotion_map.values()) / 100.0
                            else:
                                # 某些版本返回dominant_emotion和dominant_emotion_score
                                dom = c.get("dominant_emotion")
                                conf = float(c.get("dominant_emotion_score", 0.0))
                                if conf > 1.0:
                                    conf = conf / 100.0
                            
                            # 添加置信度阈值过滤，避免低置信度结果
                            if conf < 0.3:  # 设置最低置信度阈值
                                continue
                                
                            if conf > best_conf:
                                best_conf = conf
                                best = c
                        
                        if best:
                            # 提取情绪信息
                            emotion_map = best.get("emotion") or best.get("emotions") or {}
                            dominant = best.get("dominant_emotion")
                            if dominant is None and isinstance(emotion_map, dict) and emotion_map:
                                dominant = max(emotion_map, key=lambda k: emotion_map[k])
                            
                            if isinstance(emotion_map, dict) and dominant in emotion_map:
                                conf_val = float(emotion_map[dominant]) / 100.0
                            else:
                                conf_val = float(best.get("dominant_emotion_score", 0.0))
                                if conf_val > 1.0:
                                    conf_val = conf_val / 100.0
                            
                            emotion_label = str(dominant) if dominant else str(best.get("dominant_emotion", "neutral"))
                            confidence = max(0.0, min(1.0, conf_val or 0.0))
                            
                            # 获取人脸位置信息
                            region = best.get("region", {})
                            if region:
                                face_bbox = {
                                    "x": region.get("x", 100),
                                    "y": region.get("y", 100),
                                    "width": region.get("w", 100),
                                    "height": region.get("h", 100)
                                }
                            else:
                                # 如果没有人脸位置信息，使用默认值
                                if hasattr(frame_array, 'shape'):
                                    height, width = frame_array.shape[:2]
                                    face_bbox = {
                                        "x": int(width * 0.3),
                                        "y": int(height * 0.2),
                                        "width": int(width * 0.4),
                                        "height": int(height * 0.5)
                                    }
                                else:
                                    face_bbox = {"x": 0, "y": 0, "width": 100, "height": 100}
                            
                            # 构建情绪结果，确保包含face_position数组格式
                            emotion_result = {
                                "emotion": emotion_label,
                                "confidence": confidence,
                                "face_position": [face_bbox],  # 确保返回数组格式
                                "face_bbox": face_bbox,
                                "timestamp": time.time()
                            }
                            
                            # 更新观察数据，包括face_bbox
                            await self.update_observation_dict(emotion_result)
                            
                            return emotion_result
            
            # 如果所有检测方法都失败，回退到模拟数据
            logger.warning("All emotion detection methods failed, falling back to simulation")
            emotions = ["neutral", "happy", "sad", "angry", "fear", "surprise", "disgust"]
            # 优化情绪权重，使情绪分布更加均匀
            weights = [0.7, 0.1, 0, 0.05, 0.05, 0.05, 0.05]  # 降低fear权重，增加其他情绪权重
            emotion_label = self._rng.choices(emotions, weights=weights, k=1)[0]
            confidence = self._rng.uniform(0.6, 0.95)
            
            # 模拟人脸位置信息
            if hasattr(frame_array, 'shape'):
                height, width = frame_array.shape[:2]
                face_bbox = {
                    "x": int(width * 0.3),
                    "y": int(height * 0.2),
                    "width": int(width * 0.4),
                    "height": int(height * 0.5)
                }
            else:
                face_bbox = {"x": 0, "y": 0, "width": 100, "height": 100}
            
            # 构建情绪结果，确保包含face_position数组格式
            emotion_result = {
                "emotion": emotion_label,
                "confidence": confidence,
                "face_position": [face_bbox],  # 确保返回数组格式
                "face_bbox": face_bbox,
                "timestamp": time.time()
            }
            
            # 更新观察数据，包括face_bbox
            await self.update_observation_dict(emotion_result)
            
            return emotion_result
            
        except Exception as e:
            logger.error("Error in detect_from_frame: %s", e)
            return None

    async def update_observation_dict(self, observation: Dict[str, Any]) -> None:
        """
        更新面部情绪观察数据
        
        Args:
            observation: 观察数据，包含情绪标签和置信度等信息
        """
        self._latest_observation = {
            "emotion": observation.get("emotion", "neutral"),
            "confidence": observation.get("confidence", 0.0),
            "face_position": observation.get("face_position", [{"x": 0, "y": 0, "width": 100, "height": 100}]),
            "face_bbox": observation.get("face_bbox", {"x": 0, "y": 0, "width": 100, "height": 100}),
            "timestamp": observation.get("timestamp", time.time())
        }
        
        # 同时更新_latest属性，确保analyze方法能获取到最新数据
        faces_detected = observation.get("faces_detected", 1)
        obs = FaceObservation(
            label=observation.get("emotion", "neutral"),
            confidence=observation.get("confidence", 0.0),
            intensity=observation.get("confidence", 0.0),
            faces_detected=faces_detected,
            timestamp=time.time(),
        )
        async with self._lock:
            self._latest = obs
    
    def get_latest_observation(self) -> Dict[str, Any]:
        """获取最新的观察数据"""
        if self._latest_observation is None:
            return {
                "emotion": "neutral",
                "confidence": 0.0,
                "face_position": [{"x": 0, "y": 0, "width": 100, "height": 100}],
                "face_bbox": {"x": 0, "y": 0, "width": 100, "height": 100},
                "timestamp": time.time()
            }
        return self._latest_observation

    async def _run_deepface(self, frame: Any) -> Optional[Dict[str, Any]]:
        """Run DeepFace.analyze in a thread and return the raw result.

        Returns None if DeepFace not available or if analysis fails.
        """
        if not self.use_deepface:
            return None

        def _call():
            try:
                # DeepFace.analyze accepts numpy RGB arrays or image paths.
                # Ensure enforce_detection=False by default when we pass cropped
                # images (we may pass full frames too).
                kwargs = dict(self.deepface_kwargs)
                kwargs.setdefault("actions", ["emotion"])
                kwargs.setdefault("enforce_detection", False)
                kwargs.setdefault("detector_backend", "ssd")
                result = DeepFace.analyze(frame, **kwargs)
                return result
            except Exception as e:
                logger.error(f"DeepFace.analyze failed: {e}")
                return None

        return await asyncio.to_thread(_call)

    async def infer_and_update(self) -> None:
        """Try to infer emotions from the latest frame using Baidu API or DeepFace and
        update the internal observation. Best-effort; failures are ignored so
        the system falls back to simulation.
        """
        async with self._lock:
            frame = self._latest_frame

        if frame is None:
            return

        # 优先使用百度云API进行情绪检测
        if self.use_baidu_api and self.baidu_client:
            try:
                # 确保图像格式正确：转换为RGB格式的字节数据
                if hasattr(frame, 'shape') and len(frame.shape) == 3:
                    # 如果是numpy数组，确保是RGB格式
                    import numpy as np
                    if frame.shape[2] == 4:  # RGBA
                        frame_array = frame[:, :, :3]  # 移除alpha通道
                    elif frame.shape[2] == 1:  # 灰度图
                        frame_array = np.stack([frame[:, :, 0]] * 3, axis=2)  # 转换为RGB
                    else:
                        frame_array = frame
                    
                    # 确保是uint8格式
                    if frame_array.dtype != np.uint8:
                        frame_array = (frame_array * 255).astype(np.uint8)
                    
                    # 转换为字节数据
                    import io
                    from PIL import Image
                    img = Image.fromarray(frame_array)
                    img_byte_arr = io.BytesIO()
                    img.save(img_byte_arr, format='JPEG', quality=90)
                    image_bytes = img_byte_arr.getvalue()
                else:
                    # 如果不是numpy数组，直接使用原始数据
                    image_bytes = frame
                
                # 调用百度云API
                baidu_result = await self.baidu_client.detect_emotion(image_bytes)
                
                if baidu_result:
                    # 百度云API已经返回了正确格式的数据，包含face_position和face_bbox
                    # 更新观察数据
                    await self.update_observation_dict(baidu_result)
                    return
                else:
                    logger.warning("Baidu API detection failed, falling back to DeepFace")
            except Exception as e:
                logger.error(f"Error in Baidu API emotion detection: {e}")
                # 继续尝试DeepFace
        
        # 如果百度云API不可用或失败，尝试使用DeepFace
        if self.use_deepface:
            raw = await self._run_deepface(frame)
            if not raw:
                return

            # DeepFace.analyze may return a dict for a single face, or a list for
            # multiple faces depending on version. Normalize to list of dicts.
            if isinstance(raw, dict):
                candidates = [raw]
            elif isinstance(raw, list):
                candidates = raw
            else:
                logger.warning(f"Unexpected DeepFace result type: {type(raw)}")
                return
            
            # Choose the face with highest dominant emotion confidence when
            # multiple faces present.
            best = None
            best_conf = -1.0
            for i, c in enumerate(candidates):
                # DeepFace may return an 'emotion' dict mapping names to scores
                emotion_map = c.get("emotion") or c.get("emotions") or {}
                
                if isinstance(emotion_map, dict) and emotion_map:
                    # Scores often in 0-100; normalize to 0-1
                    # pick dominant emotion if present
                    dominant = c.get("dominant_emotion")
                    
                    if dominant and dominant in emotion_map:
                        conf = float(emotion_map[dominant]) / 100.0
                    else:
                        # fallback to max score
                        conf = max(float(v) for v in emotion_map.values()) / 100.0
                else:
                    # Some versions return a 'dominant_emotion' and 'dominant_emotion_score'
                    dom = c.get("dominant_emotion")
                    conf = float(c.get("dominant_emotion_score", 0.0))
                    if conf > 1.0:
                        conf = conf / 100.0

                # 添加置信度阈值过滤
                if conf < 0.3:  # 设置最低置信度阈值
                    continue
                    
                if conf > best_conf:
                    best_conf = conf
                    best = c

            if best is None:
                logger.warning("No valid face candidate found")
                return

            emotion_map = best.get("emotion") or best.get("emotions") or {}
            dominant = best.get("dominant_emotion")
            if dominant is None and isinstance(emotion_map, dict) and emotion_map:
                dominant = max(emotion_map, key=lambda k: emotion_map[k])

            if isinstance(emotion_map, dict) and dominant in emotion_map:
                conf_val = float(emotion_map[dominant]) / 100.0
            else:
                conf_val = float(best.get("dominant_emotion_score", 0.0))
                if conf_val > 1.0:
                    conf_val = conf_val / 100.0

            label = str(dominant) if dominant else str(best.get("dominant_emotion", self.config.fallback_emotion))
            confidence = max(0.0, min(1.0, conf_val or 0.0))
            intensity = confidence
            faces_detected = len(candidates)
            
            # 获取人脸位置信息
            region = best.get("region", {})
            if region:
                face_bbox = {
                    "x": region.get("x", 0),
                    "y": region.get("y", 0),
                    "width": region.get("w", 100),
                    "height": region.get("h", 100)
                }
            else:
                # 如果没有人脸位置信息，使用默认值
                if hasattr(frame, 'shape'):
                    height, width = frame.shape[:2]
                    face_bbox = {
                        "x": int(width * 0.3),
                        "y": int(height * 0.2),
                        "width": int(width * 0.4),
                        "height": int(height * 0.5)
                    }
                else:
                    face_bbox = {"x": 0, "y": 0, "width": 100, "height": 100}

            await self.update_observation(
                label=label,
                confidence=confidence,
                intensity=intensity,
                faces_detected=faces_detected
            )
            
            # 更新_latest_observation，包含人脸位置信息
            await self.update_observation_dict({
                "emotion": label,
                "confidence": confidence,
                "face_bbox": face_bbox,
                "faces_detected": faces_detected
            })

    async def analyze(self) -> ChannelEmotion:
        # 初始化face_bbox变量，防止未定义错误
        face_bbox = {"x": 0, "y": 0, "width": 100, "height": 100}
        
        # Attempt model inference first (best-effort). Any error falls through
        # to the simulated fallback.
        try:
            await self.infer_and_update()
        except Exception as e:
            logger.error(f"Error in emotion inference: {e}", exc_info=True)
            # keep going to fallback behavior
            pass

        async with self._lock:
            observation = self._latest

        if observation is None or self._is_stale(observation):
            # 如果没有有效观察数据，生成模拟数据并返回
            simulated = self._simulate_emotion()
            # 添加模拟的人脸位置信息
            face_bbox = {"x": 0, "y": 0, "width": 100, "height": 100}  # 默认值
            if hasattr(self, '_latest_frame') and self._latest_frame is not None:
                height, width = self._latest_frame.shape[:2]
                face_bbox = {
                    "x": int(width * 0.3),
                    "y": int(height * 0.2),
                    "width": int(width * 0.4),
                    "height": int(height * 0.5)
                }
            # 更新观察数据
            await self.update_observation(
                label=simulated.label,
                confidence=simulated.confidence,
                intensity=simulated.confidence,
                faces_detected=1
            )
            
            # 创建metadata并返回结果
            metadata = {
                "faces_detected": 1,
                "notes": f"Simulated face emotion. Detection method: {'Baidu API' if self.use_baidu_api and self.baidu_client else 'DeepFace' if self.use_deepface else 'Simulation'}",
                "deepface_available": bool(DeepFace is not None),
                "baidu_api_available": bool(self.use_baidu_api and self.baidu_client),
                "face_bbox": face_bbox
            }
            
            return ChannelEmotion(
                source="face",
                label=simulated.label,
                confidence=simulated.confidence,
                mood_score=simulated.mood_score,
                metadata=metadata,
            )

        # 确保使用最新的观察数据，而不是可能过时的数据
        if hasattr(self, '_latest_observation') and self._latest_observation:
            # 使用最新的观察数据，包含最新的情绪和人脸位置
            mood_score = self._map_label_to_mood(
                self._latest_observation.get("emotion", observation.label), 
                self._latest_observation.get("confidence", observation.confidence)
            )
            confidence = max(0.0, min(1.0, self._latest_observation.get("confidence", observation.confidence)))
            label = self._latest_observation.get("emotion", observation.label)
            # 确保face_bbox变量已定义
            if 'face_bbox' in self._latest_observation:
                face_bbox = self._latest_observation['face_bbox']
        else:
            # 回退到原始观察数据
            mood_score = self._map_label_to_mood(observation.label, observation.intensity)
            confidence = max(0.0, min(1.0, observation.confidence * 0.9 + 0.1))
            label = observation.label
            # 确保face_bbox变量已定义
            face_bbox = {"x": 0, "y": 0, "width": 100, "height": 100}

        metadata = {
            "faces_detected": observation.faces_detected,
            "notes": f"Detection method: {'Baidu API' if self.use_baidu_api and self.baidu_client else 'DeepFace' if self.use_deepface else 'Simulation'}",
            "deepface_available": bool(DeepFace is not None),
            "baidu_api_available": bool(self.use_baidu_api and self.baidu_client),
            "face_bbox": face_bbox
        }
        
        return ChannelEmotion(
            source="face",
            label=label,
            confidence=confidence,
            mood_score=mood_score,
            metadata=metadata,
        )

    def _simulate_emotion(self) -> ChannelEmotion:
        rng = self._rng
        # 提高neutral情绪的选择概率，降低fear等其他情绪的概率
        # 使用加权随机选择，neutral有50%概率，其他情绪各约8.3%概率
        emotions = ["neutral", "happy", "surprise", "sad", "angry", "disgust", "fear"]
        weights = [0.5, 0.083, 0.083, 0.083, 0.083, 0.083, 0.083]  # neutral权重更高
        label = rng.choices(emotions, weights=weights, k=1)[0]
        intensity = rng.uniform(0.2, 0.8)
        mood_score = self._map_label_to_mood(label, intensity)
        confidence = rng.uniform(0.4, 0.7)
        metadata = {"notes": "Simulated face emotion. Supply real detections or frame/model to override."}
        return ChannelEmotion(
            source="face",
            label=label,
            confidence=confidence,
            mood_score=mood_score,
            metadata=metadata,
        )

    def _map_label_to_mood(self, label: str, intensity: float) -> float:
        label = label.lower()
        mapping = {
            "happy": 0.8,
            "joyful": 0.9,
            "surprise": 0.3,
            "neutral": 0.0,
            "sad": -0.6,
            "angry": -0.8,
            "disgust": -0.5,
            "fear": -0.7,
            "calm": 0.2,
            "stressed": -0.4,
            "anxious": -0.6,
        }
        base = mapping.get(label, 0.0)
        return max(-1.0, min(1.0, base * intensity))

    def _is_stale(self, observation: FaceObservation) -> bool:
        # age = time.time() - observation.timestamp
        # # 增加过期时间阈值，从1秒降低到0.3秒，确保更频繁地使用真实检测结果
        # return age > max(0.3, 1.0 / self.config.decay_per_second)
        return False
