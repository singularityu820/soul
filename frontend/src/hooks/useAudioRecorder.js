import { useState, useRef, useCallback } from "react";

/**
 * 音频录制 Hook
 * 
 * 提供录音、停止、上传音频的功能
 * 替代 WebRTC 的简单方案
 */
export function useAudioRecorder() {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [duration, setDuration] = useState(0);
  const [error, setError] = useState(null);

  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const streamRef = useRef(null);
  const timerRef = useRef(null);

  /**
   * 开始录音
   */
  const startRecording = useCallback(async () => {
    try {
      setError(null);
      
      // 请求麦克风权限
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          channelCount: 1,  // 单声道
          sampleRate: 16000,  // 16kHz 采样率
          echoCancellation: true,
          noiseSuppression: true,
        } 
      });
      
      streamRef.current = stream;
      audioChunksRef.current = [];

      // 创建 MediaRecorder
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported('audio/webm') 
          ? 'audio/webm' 
          : 'audio/ogg',
      });

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.start(100); // 每 100ms 收集一次数据
      mediaRecorderRef.current = mediaRecorder;
      setIsRecording(true);
      setDuration(0);

      // 启动计时器
      timerRef.current = setInterval(() => {
        setDuration((prev) => prev + 1);
      }, 1000);

      console.log("Recording started");
    } catch (err) {
      console.error("Failed to start recording:", err);
      setError(err.message || "无法访问麦克风");
    }
  }, []);

  /**
   * 停止录音
   */
  const stopRecording = useCallback(() => {
    return new Promise((resolve) => {
      if (mediaRecorderRef.current && isRecording) {
        mediaRecorderRef.current.onstop = () => {
          // 创建音频 Blob
          const audioBlob = new Blob(audioChunksRef.current, { 
            type: 'audio/webm' 
          });
          
          // 清理资源
          if (streamRef.current) {
            streamRef.current.getTracks().forEach((track) => track.stop());
            streamRef.current = null;
          }
          
          if (timerRef.current) {
            clearInterval(timerRef.current);
            timerRef.current = null;
          }

          setIsRecording(false);
          console.log(`Recording stopped. Duration: ${duration}s, Size: ${audioBlob.size} bytes`);
          resolve(audioBlob);
        };

        mediaRecorderRef.current.stop();
      } else {
        resolve(null);
      }
    });
  }, [isRecording, duration]);

  /**
   * 上传音频到服务器
   */
  const uploadAudio = useCallback(async (audioBlob, threadId = null) => {
    if (!audioBlob) {
      throw new Error("No audio to upload");
    }

    setIsProcessing(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append("audio", audioBlob, "recording.webm");
      if (threadId) {
        formData.append("thread_id", threadId);
      }
      formData.append("voice", "zhichu_emo");
      formData.append("locale", "zh-CN");

      const response = await fetch("/api/audio/conversation", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "上传失败");
      }

      const result = await response.json();
      console.log("Audio conversation result:", result);
      return result;
    } catch (err) {
      console.error("Failed to upload audio:", err);
      setError(err.message || "上传失败");
      throw err;
    } finally {
      setIsProcessing(false);
    }
  }, []);

  /**
   * 录音并上传 (一键操作)
   */
  const recordAndUpload = useCallback(async (threadId = null) => {
    if (isRecording) {
      // 停止录音并上传
      const audioBlob = await stopRecording();
      if (audioBlob) {
        return await uploadAudio(audioBlob, threadId);
      }
    } else {
      // 开始录音
      await startRecording();
    }
  }, [isRecording, startRecording, stopRecording, uploadAudio]);

  /**
   * 取消录音
   */
  const cancelRecording = useCallback(() => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
      }
      
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }

      audioChunksRef.current = [];
      setIsRecording(false);
      setDuration(0);
      console.log("Recording cancelled");
    }
  }, [isRecording]);

  return {
    isRecording,
    isProcessing,
    duration,
    error,
    startRecording,
    stopRecording,
    uploadAudio,
    recordAndUpload,
    cancelRecording,
  };
}
