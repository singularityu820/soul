/**
 * Audio Worklet Processor for real-time audio capture
 * 
 * 用于实时音频采集的 AudioWorklet 处理器
 * 比 ScriptProcessor 延迟更低，且不会阻塞主线程
 */
class AudioCaptureProcessor extends AudioWorkletProcessor {
  process(inputs, outputs, parameters) {
    const input = inputs[0];
    
    if (input && input.length > 0) {
      const channelData = input[0]; // 获取第一个声道
      
      if (channelData && channelData.length > 0) {
        // 转换为 Int16Array (PCM 16bit)
        const pcmData = new Int16Array(channelData.length);
        
        for (let i = 0; i < channelData.length; i++) {
          // 将 float32 [-1, 1] 转换为 int16 [-32768, 32767]
          const s = Math.max(-1, Math.min(1, channelData[i]));
          pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        
        // 发送音频数据到主线程
        this.port.postMessage(pcmData.buffer, [pcmData.buffer]);
      }
    }
    
    // 返回 true 保持处理器活跃
    return true;
  }
}

registerProcessor('audio-capture-processor', AudioCaptureProcessor);
