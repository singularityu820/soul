import React, { useState, useMemo, useCallback } from 'react';
import WordCloud from './WordCloud';
import './styles/ImageGeneration.css';
import FoxMessage from './ui/FoxMessage';

/**
 * 词云预览弹框组件
 * 复用ImageGeneration的弹框样式
 */
const WordCloudPreview = ({ 
  isVisible, 
  diaryContent, 
  onClose, 
  onConfirm 
}) => {
  const [wordCloudSize, setWordCloudSize] = useState({ width: 800, height: 600 });
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

  // 处理确认
  const handleConfirm = () => {
    if (!diaryContent || diaryContent.trim() === '') {
      showMessage('日记内容为空，无法生成词云', 'warning');
      return;
    }
    
    if (onConfirm) {
      onConfirm();
    }
    showMessage('词云已添加到日记中！✨', 'success');
    setTimeout(() => {
      onClose();
    }, 1000);
  };

  // 处理关闭
  const handleClose = () => {
    setMessageState({ visible: false, message: '', type: 'info' });
    onClose();
  };

  // 处理词云点击
  const handleWordClick = useCallback((item) => {
    if (item && item[0]) {
      showMessage(`点击了词语: ${item[0]}`, 'info');
    }
  }, [showMessage]);

  if (!isVisible) return null;

  return (
    <div className="image-generation-overlay floating-window">
      <div className="image-generation-modal">
        <div className="image-generation-header">
          <h2>生成词云</h2>
          <button className="close-btn" onClick={handleClose}>×</button>
        </div>
        
        <div className="image-generation-content">
          <div className="diary-preview">
            <h3>日记内容预览</h3>
            <div className="diary-content">
              {diaryContent && diaryContent.length > 200 
                ? `${diaryContent.substring(0, 200)}...` 
                : diaryContent || '无内容'}
            </div>
          </div>

          <div className="wordcloud-preview-container">
            <h3 style={{ 
              textAlign: 'center', 
              marginBottom: '20px',
              color: '#333',
              fontFamily: '"萌趣甜心体", "Microsoft YaHei", "Heiti SC", sans-serif'
            }}>
              词云预览
            </h3>
            <div style={{
              width: '100%',
              minHeight: '600px',
              maxHeight: '600px',
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              background: 'linear-gradient(135deg, #FFF8DC 0%, #FFFEF5 100%)',
              borderRadius: '12px',
              padding: '20px',
              border: '1px solid #F5DEB3',
              overflow: 'auto'
            }}>
              {diaryContent && diaryContent.trim() ? (
                <WordCloud
                  text={diaryContent}
                  width={wordCloudSize.width}
                  height={wordCloudSize.height}
                  onWordClick={handleWordClick}
                />
              ) : (
                <div style={{
                  color: '#999',
                  fontFamily: '"萌趣甜心体", "Microsoft YaHei", "Heiti SC", sans-serif'
                }}>
                  暂无内容可生成词云
                </div>
              )}
            </div>
          </div>
        </div>
        
        <div className="image-generation-footer">
          <button className="cancel-btn" onClick={handleClose}>取消</button>
          <button 
            className="save-btn" 
            onClick={handleConfirm}
            disabled={!diaryContent || diaryContent.trim() === ''}
            style={{ marginLeft: '12px' }}
          >
            确定添加
          </button>
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

export default WordCloudPreview;
