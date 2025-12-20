import React, { useState, useEffect, useCallback } from 'react';
import './styles/ImageGeneration.css';
import FoxMessage from './ui/FoxMessage';
import { 
  generateImageWithEmotion, 
  adjustImage, 
  getEmotionTypes,
  getEmotionAdjustmentOptions,
  base64ToImageUrl, 
  getFullImageUrl 
} from '../services/imageGenerationService';

/**
 * 文生图组件
 * 用于在日记保存时生成基于情绪的图片
 */
const ImageGeneration = ({ 
  isVisible, 
  diaryContent, 
  onClose, 
  onSave 
}) => {
  // 状态管理
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedImage, setGeneratedImage] = useState(null);
  const [emotion, setEmotion] = useState('');
  const [confidence, setConfidence] = useState(0);
  const [adjustmentOptions, setAdjustmentOptions] = useState({});
  const [selectedAdjustment, setSelectedAdjustment] = useState('');
  const [isAdjusting, setIsAdjusting] = useState(false);
  const [error, setError] = useState('');
  const [emotionTypes, setEmotionTypes] = useState([]);
  const [selectedEmotion, setSelectedEmotion] = useState('');
  const [imageStyle, setImageStyle] = useState('realistic'); // realistic, anime, oil_painting
  const [imageSize, setImageSize] = useState('1024x1024'); // 1024x1024, 1024x768, 768x1024
  const [originalPrompt, setOriginalPrompt] = useState(''); // 保存原始提示词
  
  // 消息提示状态管理
  const [messageState, setMessageState] = useState({
    visible: false,
    message: '',
    type: 'info'
  });
  
  // 显示消息的辅助函数
  const showMessage = useCallback((message, type = 'info') => {
    setMessageState({
      visible: true,
      message,
      type
    });
  }, []);
  
  // 关闭消息
  const handleMessageClose = useCallback(() => {
    setMessageState(prev => ({ ...prev, visible: false }));
  }, []);

  // 获取情绪类型
  useEffect(() => {
    const fetchEmotionTypes = async () => {
      try {
        const data = await getEmotionTypes();
        setEmotionTypes(data.emotion_types || []);
      } catch (err) {
        console.error('获取情绪类型失败:', err);
      }
    };
    
    fetchEmotionTypes();
  }, []);

  // 当组件显示且有日记内容时，不自动生成图片，让用户手动选择
  useEffect(() => {
    // 不自动生成图片，让用户手动选择
  }, [isVisible, diaryContent]);

  // 获取情绪调整选项
  useEffect(() => {
    const fetchAdjustmentOptions = async () => {
      if (emotion) {
        try {
          const data = await getEmotionAdjustmentOptions(emotion);
          if (data.success) {
            setAdjustmentOptions(data.adjustment_options || {});
          }
        } catch (err) {
          console.error('获取情绪调整选项失败:', err);
        }
      }
    };
    
    fetchAdjustmentOptions();
  }, [emotion]);

  // 生成图片
  const handleGenerateImage = async () => {
    if (!diaryContent) return;
    
    setIsGenerating(true);
    setError('');
    
    try {
      const result = await generateImageWithEmotion({
        text_content: diaryContent,
        emotion: selectedEmotion || undefined, // 如果用户选择了情绪，则使用用户选择的
        style: imageStyle, // 添加风格选项
        size: imageSize,
        seed: -1,
        save_to_disk: true
      });
      
      if (result.success) {
        setGeneratedImage(result.image_url ? getFullImageUrl(result.image_url) : base64ToImageUrl(result.base64_data));
        setEmotion(result.emotion);
        setConfidence(result.confidence);
        setAdjustmentOptions(result.adjustment_options || {});
        setOriginalPrompt(result.original_prompt || ''); // 保存原始提示词
        setError(''); // 清除错误
        showMessage('图片生成成功！✨', 'success');
      } else {
        const errorMsg = result.message || '生成图片失败';
        setError(errorMsg);
        showMessage(errorMsg, 'error');
      }
    } catch (err) {
      const errorMsg = '生成图片失败: ' + err.message;
      setError(errorMsg);
      showMessage(errorMsg, 'error');
    } finally {
      setIsGenerating(false);
    }
  };

  // 调整图片
  const handleAdjustImage = async () => {
    if (!selectedAdjustment || !generatedImage) return;
    
    setIsAdjusting(true);
    setError('');
    
    try {
      // 使用后端返回的情绪调整选项，不需要转换
      const result = await adjustImage({
        original_prompt: originalPrompt, // 使用保存的原始提示词
        emotion: emotion,
        adjustment_type: selectedAdjustment, // 直接使用用户选择的选项
        size: imageSize,
        seed: -1,
        save_to_disk: true
      });
      
      if (result.success) {
        setGeneratedImage(result.image_url ? getFullImageUrl(result.image_url) : base64ToImageUrl(result.base64_data));
        setError(''); // 清除错误
        showMessage('图片调整成功！✨', 'success');
      } else {
        const errorMsg = result.message || '调整图片失败';
        setError(errorMsg);
        showMessage(errorMsg, 'error');
      }
    } catch (err) {
      const errorMsg = '调整图片失败: ' + err.message;
      setError(errorMsg);
      showMessage(errorMsg, 'error');
    } finally {
      setIsAdjusting(false);
    }
  };

  // 保存日记和图片
  const handleSave = () => {
    if (!generatedImage) {
      showMessage('请先生成图片再保存哦～', 'warning');
      return;
    }
    
    if (onSave) {
      onSave({
        diaryContent,
        generatedImage,
        emotion,
        confidence
      });
    }
    showMessage('保存成功！日记和图片已保存 🦊', 'success');
    // 延迟关闭，让用户看到成功消息
    setTimeout(() => {
      onClose();
    }, 1000);
  };

  // 重置状态
  const handleClose = () => {
    setGeneratedImage(null);
    setEmotion('');
    setConfidence(0);
    setAdjustmentOptions({});
    setSelectedAdjustment('');
    setError('');
    setSelectedEmotion('');
    setOriginalPrompt('');
    setMessageState({ visible: false, message: '', type: 'info' });
    onClose();
  };

  if (!isVisible) return null;

  return (
    <div className="image-generation-overlay floating-window">
      <div className="image-generation-modal">
        <div className="image-generation-header">
          <h2>情绪文生图</h2>
          <button className="close-btn" onClick={handleClose}>×</button>
        </div>
        
        <div className="image-generation-content">
          {!generatedImage ? (
            <div className="options-container">
              <div className="diary-preview">
                <h3>日记内容预览</h3>
                <div className="diary-content">
                  {diaryContent && diaryContent.length > 200 
                    ? `${diaryContent.substring(0, 200)}...` 
                    : diaryContent || '无内容'}
                </div>
              </div>
              
              <div className="generation-options">
                <div className="option-group">
                  <label htmlFor="emotion-select">情绪选择（可选）</label>
                  <select 
                    id="emotion-select" 
                    value={selectedEmotion} 
                    onChange={(e) => setSelectedEmotion(e.target.value)}
                  >
                    <option value="">自动识别情绪</option>
                    {emotionTypes.map((emotionType) => (
                      <option key={emotionType} value={emotionType}>
                        {emotionType}
                      </option>
                    ))}
                  </select>
                </div>
                
                <div className="option-group">
                  <label htmlFor="style-select">图片风格</label>
                  <select 
                    id="style-select" 
                    value={imageStyle} 
                    onChange={(e) => setImageStyle(e.target.value)}
                  >
                    <option value="realistic">写实风格</option>
                    <option value="anime">动漫风格</option>
                    <option value="oil_painting">油画风格</option>
                    <option value="watercolor">水彩风格</option>
                    <option value="sketch">素描风格</option>
                  </select>
                </div>
                
                <div className="option-group">
                  <label htmlFor="size-select">图片尺寸</label>
                  <select 
                    id="size-select" 
                    value={imageSize} 
                    onChange={(e) => setImageSize(e.target.value)}
                  >
                    <option value="1024x1024">正方形 (1024×1024)</option>
                  </select>
                </div>
              </div>
              
              <button 
                className="generate-btn" 
                onClick={handleGenerateImage}
                disabled={isGenerating || !diaryContent}
              >
                {isGenerating ? '生成中...' : '生成图片'}
              </button>
              
            </div>
          ) : (
            <div className="result-container">
              <div className="image-container">
                <img src={generatedImage} alt="生成的图片" />
              </div>
              
              <div className="emotion-info">
                <h3>情感倾向: {emotion}</h3>
                <p>置信度: {(confidence * 100).toFixed(1)}%</p>
              </div>

              {Object.keys(adjustmentOptions).length > 0 && (
                <div className="adjustment-section">
                  <h3>调整图片</h3>
                  <div className="adjustment-options">
                    {Object.entries(adjustmentOptions).map(([key, value]) => (
                      <button
                        key={key}
                        className={`adjustment-btn ${selectedAdjustment === key ? 'selected' : ''}`}
                        onClick={() => setSelectedAdjustment(key)}
                      >
                        {key}
                      </button>
                    ))}
                  </div>
                  <button 
                    className="adjust-apply-btn" 
                    onClick={handleAdjustImage}
                    disabled={!selectedAdjustment || isAdjusting}
                  >
                    {isAdjusting ? '调整中...' : '应用调整'}
                  </button>
                </div>
              )}
              
              <div className="action-buttons">
                <button className="regenerate-btn" onClick={handleGenerateImage} disabled={isGenerating}>
                  {isGenerating ? '生成中...' : '重新生成'}
                </button>
                <button className="save-btn" onClick={handleSave}>保存日记和图片</button>
              </div>
            </div>
          )}
        </div>
        
        <div className="image-generation-footer">
          <button className="cancel-btn" onClick={handleClose}>取消</button>
        </div>
      </div>
      
      {/* 可爱狐狸风格的消息提示 */}
      <FoxMessage
        visible={messageState.visible}
        message={messageState.message}
        type={messageState.type}
        duration={3000}
        onClose={handleMessageClose}
      />
    </div>
  );
};

export default ImageGeneration;