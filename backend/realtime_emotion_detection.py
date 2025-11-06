import asyncio
import cv2
import numpy as np
import os
import sys
import time
from typing import Optional

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.emotion.face import FaceEmotionTool
from app.services.emotion.baidu_client import BaiduFaceClient
from app.config import FaceEmotionConfig

class RealTimeEmotionDetector:
    """实时情绪检测器"""
    
    def __init__(self, api_key: str, secret_key: str):
        """初始化实时情绪检测器
        
        Args:
            api_key: 百度API Key
            secret_key: 百度Secret Key
        """
        self.config = FaceEmotionConfig()
        self.face_tool = FaceEmotionTool(
            config=self.config,
            use_deepface=False,  # 禁用DeepFace，只使用百度API
            use_baidu_api=True,
            baidu_api_key=api_key,
            baidu_secret_key=secret_key
        )
        
        # 初始化摄像头
        self.cap = None
        self.is_running = False
        
        # 统计信息
        self.frame_count = 0
        self.detection_count = 0
        self.start_time = None
        
    async def start_camera(self, camera_id: int = 0):
        """启动摄像头
        
        Args:
            camera_id: 摄像头ID，默认为0
        """
        self.cap = cv2.VideoCapture(camera_id)
        if not self.cap.isOpened():
            print(f"无法打开摄像头 {camera_id}")
            return False
            
        # 设置摄像头参数
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        
        self.is_running = True
        self.start_time = time.time()
        print("摄像头已启动，开始实时情绪检测...")
        return True
    
    def stop_camera(self):
        """停止摄像头"""
        self.is_running = False
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()
        print("摄像头已停止")
    
    def draw_emotion_info(self, frame: np.ndarray, emotion: str, confidence: float, 
                         face_bbox: dict, fps: float) -> np.ndarray:
        """在图像上绘制情绪信息
        
        Args:
            frame: 视频帧
            emotion: 检测到的情绪
            confidence: 置信度
            face_bbox: 人脸位置信息
            fps: 帧率
            
        Returns:
            绘制了情绪信息的图像
        """
        # 绘制人脸框
        x, y, w, h = face_bbox["x"], face_bbox["y"], face_bbox["width"], face_bbox["height"]
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
        
        # 准备情绪文本
        emotion_text = f"Emotion: {emotion} ({confidence:.2f})"
        
        # 绘制情绪文本背景
        text_size = cv2.getTextSize(emotion_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
        cv2.rectangle(frame, (x, y - 30), (x + text_size[0], y), (0, 255, 0), -1)
        
        # 绘制情绪文本
        cv2.putText(frame, emotion_text, (x, y - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
        
        # 绘制FPS
        fps_text = f"FPS: {fps:.1f}"
        cv2.putText(frame, fps_text, (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        # 绘制统计信息
        stats_text = f"Frames: {self.frame_count}, Detections: {self.detection_count}"
        cv2.putText(frame, stats_text, (10, 60), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        
        return frame
    
    async def detect_emotion(self, frame: np.ndarray) -> tuple:
        """检测图像中的情绪
        
        Args:
            frame: 视频帧
            
        Returns:
            (emotion, confidence, face_bbox) 元组
        """
        # 打印调试信息
        print(f"正在处理帧，尺寸: {frame.shape}, 数据类型: {frame.dtype}")
        
        # 检查图像质量
        if frame is None or frame.size == 0:
            print("错误: 帧为空")
            return "error", 0.0, {"x": 0, "y": 0, "width": 0, "height": 0}
        
        # 保存原始帧用于调试
        if self.frame_count % 50 == 0:  # 每50帧保存一次
            debug_path = f"debug_frame_{self.frame_count}.jpg"
            cv2.imwrite(debug_path, frame)
            print(f"保存调试图像到: {debug_path}")
        
        # 设置当前帧
        self.face_tool._latest_frame = frame
        
        # 调用修改后的infer_and_update方法
        await self.face_tool.infer_and_update()
        
        # 获取检测结果
        observation = self.face_tool.get_latest_observation()
        
        emotion = observation["emotion"]
        confidence = observation["confidence"]
        face_bbox = observation["face_bbox"]
        
        print(f"检测结果 - 情绪: {emotion}, 置信度: {confidence:.2f}, 人脸框: {face_bbox}")
        
        # 如果置信度大于0，则认为检测成功
        if confidence > 0:
            self.detection_count += 1
            print(f"成功检测到人脸！累计检测次数: {self.detection_count}")
        else:
            print("未检测到人脸或置信度过低")
            
        return emotion, confidence, face_bbox
    
    async def run(self):
        """运行实时情绪检测"""
        if not await self.start_camera():
            return
            
        try:
            last_time = time.time()
            
            while self.is_running:
                # 读取帧
                ret, frame = self.cap.read()
                if not ret:
                    print("无法读取摄像头帧")
                    break
                
                self.frame_count += 1
                
                # 每隔几帧检测一次情绪，减少API调用频率
                if self.frame_count % 5 == 0:
                    print(f"\n=== 第 {self.frame_count} 帧，开始检测 ===")
                    try:
                        # 检测情绪
                        emotion, confidence, face_bbox = await self.detect_emotion(frame)
                    except Exception as e:
                        print(f"情绪检测错误: {e}")
                        print(f"错误详情: {type(e).__name__}: {str(e)}")
                        emotion, confidence, face_bbox = "error", 0.0, {"x": 0, "y": 0, "width": 0, "height": 0}
                else:
                    # 使用上一帧的结果
                    emotion, confidence, face_bbox = getattr(self, 'last_result', 
                                                             ("neutral", 0.0, 
                                                              {"x": 0, "y": 0, "width": 0, "height": 0}))
                    print(f"第 {self.frame_count} 帧，使用缓存结果: {emotion}")
                
                # 保存当前结果
                self.last_result = (emotion, confidence, face_bbox)
                
                # 计算FPS
                current_time = time.time()
                fps = 1.0 / (current_time - last_time)
                last_time = current_time
                
                # 在图像上绘制情绪信息
                display_frame = self.draw_emotion_info(frame.copy(), emotion, confidence, face_bbox, fps)
                
                # 显示图像
                cv2.imshow("Real-time Emotion Detection", display_frame)
                
                # 按'q'键退出
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                    
        except KeyboardInterrupt:
            print("用户中断")
        finally:
            self.stop_camera()
            
            # 打印统计信息
            if self.start_time:
                elapsed_time = time.time() - self.start_time
                print(f"\n统计信息:")
                print(f"总帧数: {self.frame_count}")
                print(f"检测次数: {self.detection_count}")
                print(f"运行时间: {elapsed_time:.2f}秒")
                print(f"平均FPS: {self.frame_count / elapsed_time:.2f}")
                print(f"检测成功率: {self.detection_count / (self.frame_count / 5) * 100:.2f}%")

async def main():
    """主函数"""
    # 从环境变量获取API密钥
    api_key = os.getenv("BAIDU_API_KEY")
    secret_key = os.getenv("BAIDU_SECRET_KEY")
    
    # 如果环境变量中没有，则尝试从配置文件读取
    if not api_key or not secret_key:
        try:
            # 直接读取配置文件
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "baidu_api_config.env")
            if os.path.exists(config_path):
                try:
                    # 尝试使用UTF-8编码读取
                    with open(config_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith('BAIDU_API_KEY='):
                                api_key = line.split('=', 1)[1]
                            elif line.startswith('BAIDU_SECRET_KEY='):
                                secret_key = line.split('=', 1)[1]
                    print(f"已从配置文件加载API密钥: {config_path}")
                except UnicodeDecodeError:
                    # 如果UTF-8失败，尝试使用GBK编码
                    try:
                        with open(config_path, 'r', encoding='gbk') as f:
                            for line in f:
                                line = line.strip()
                                if line.startswith('BAIDU_API_KEY='):
                                    api_key = line.split('=', 1)[1]
                                elif line.startswith('BAIDU_SECRET_KEY='):
                                    secret_key = line.split('=', 1)[1]
                        print(f"已从配置文件加载API密钥 (使用GBK编码): {config_path}")
                    except Exception as e:
                        print(f"使用GBK编码读取配置文件也失败: {e}")
                except Exception as e:
                    print(f"读取配置文件失败: {e}")
            else:
                print(f"配置文件不存在: {config_path}")
        except Exception as e:
            print(f"读取配置文件失败: {e}")
    
    # 检查API密钥
    if not api_key or not secret_key:
        print("错误: 未设置百度API密钥")
        print("请设置环境变量 BAIDU_API_KEY 和 BAIDU_SECRET_KEY")
        print("或者创建 baidu_api_config.env 文件并设置密钥")
        return
    
    # 创建并运行实时情绪检测器
    detector = RealTimeEmotionDetector(api_key, secret_key)
    await detector.run()

if __name__ == "__main__":
    print("百度API实时情绪检测器")
    print("按 'q' 键退出")
    asyncio.run(main())