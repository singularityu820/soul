import { useState, useCallback, useRef, useEffect } from 'react';

/**
 * 音频队列 Hook
 * 
 * 用于管理和顺序播放多个音频片段。
 * 支持：
 * - 添加音频到队列
 * - 按顺序播放
 * - 清空队列（打断时）
 * - 停止当前播放
 */
export function useAudioQueue() {
  const [queue, setQueue] = useState([]);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentAudio, setCurrentAudio] = useState(null);
  const audioRef = useRef(null);
  const audioContextRef = useRef(null);

  // 初始化 AudioContext
  useEffect(() => {
    if (!audioContextRef.current) {
      audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
    }
    
    return () => {
      if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
        audioContextRef.current.close();
      }
    };
  }, []);

  /**
   * 添加音频到队列
   */
  const enqueue = useCallback((audioUrl, metadata = {}) => {
    console.log('[AudioQueue] Enqueue:', audioUrl, metadata);
    setQueue(prev => [...prev, { url: audioUrl, metadata }]);
  }, []);

  /**
   * 清空队列并停止当前播放
   */
  const clear = useCallback(() => {
    console.log('[AudioQueue] Clearing queue');
    setQueue([]);
    
    // 停止当前播放
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
    }
    
    setIsPlaying(false);
    setCurrentAudio(null);
  }, []);

  /**
   * 播放下一个音频
   */
  const playNext = useCallback(async () => {
    if (queue.length === 0) {
      console.log('[AudioQueue] Queue empty, stopping');
      setIsPlaying(false);
      setCurrentAudio(null);
      return;
    }

    setIsPlaying(true);
    const { url, metadata } = queue[0];
    setCurrentAudio({ url, metadata });

    try {
      console.log('[AudioQueue] Playing:', url);
      
      // 下载音频
      const response = await fetch(url);
      const arrayBuffer = await response.arrayBuffer();
      
      // 解码音频
      const audioContext = audioContextRef.current;
      const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
      
      // 创建音频源
      const source = audioContext.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioContext.destination);
      
      // 保存引用用于停止
      audioRef.current = source;
      
      // 播放完成后移除并播放下一个
      await new Promise((resolve, reject) => {
        source.onended = resolve;
        source.onerror = reject;
        source.start(0);
      });
      
      console.log('[AudioQueue] Finished playing:', url);
      
      // 移除已播放的音频
      setQueue(prev => prev.slice(1));
      
    } catch (error) {
      console.error('[AudioQueue] Play error:', error);
      // 出错也移除，继续下一个
      setQueue(prev => prev.slice(1));
    }
  }, [queue]);

  /**
   * 当队列有内容且没有在播放时，开始播放
   */
  useEffect(() => {
    if (queue.length > 0 && !isPlaying) {
      playNext();
    }
  }, [queue, isPlaying, playNext]);

  return {
    enqueue,
    clear,
    queueLength: queue.length,
    isPlaying,
    currentAudio,
  };
}
