import React, { useEffect, useState, useCallback } from 'react';
import './FoxMessage.css';
import foxhead from '../../assets/KawaiiChat/foxhead.jpg';

/**
 * 可爱狐狸风格的通用消息组件
 * @param {Object} props
 * @param {string} props.message - 消息内容
 * @param {string} props.type - 消息类型: 'success' | 'error' | 'info' | 'warning'
 * @param {number} props.duration - 显示时长（毫秒），默认3000
 * @param {Function} props.onClose - 关闭回调
 * @param {boolean} props.visible - 是否显示
 */
const FoxMessage = ({ 
  message, 
  type = 'info', 
  duration = 3000, 
  onClose,
  visible = true 
}) => {
  const [isVisible, setIsVisible] = useState(visible);
  const [isAnimating, setIsAnimating] = useState(false);

  const handleClose = useCallback(() => {
    setIsAnimating(false);
    setTimeout(() => {
      setIsVisible(false);
      if (onClose) {
        onClose();
      }
    }, 300); // 等待退出动画完成
  }, [onClose]);

  useEffect(() => {
    if (visible) {
      setIsVisible(true);
      setIsAnimating(true);
      
      // 延迟添加进入动画类
      setTimeout(() => {
        setIsAnimating(true);
      }, 10);

      // 自动关闭
      if (duration > 0) {
        const timer = setTimeout(() => {
          handleClose();
        }, duration);

        return () => clearTimeout(timer);
      }
    } else {
      handleClose();
    }
  }, [visible, duration, handleClose]);

  if (!isVisible) return null;

  // 根据类型选择表情和颜色
  const getTypeConfig = () => {
    switch (type) {
      case 'success':
        return {
          emoji: '✨',
          bgColor: '#FFE4E1',
          borderColor: '#FFB6C1',
          textColor: '#8B5A3C',
          icon: '✓'
        };
      case 'error':
        return {
          emoji: '😿',
          bgColor: '#FFE4E1',
          borderColor: '#FF6B6B',
          textColor: '#8B5A3C',
          icon: '✕'
        };
      case 'warning':
        return {
          emoji: '⚠️',
          bgColor: '#FFF8DC',
          borderColor: '#FFD700',
          textColor: '#8B5A3C',
          icon: '!'
        };
      default: // info
        return {
          emoji: '🦊',
          bgColor: '#FFE4E1',
          borderColor: '#FFB6C1',
          textColor: '#8B5A3C',
          icon: 'i'
        };
    }
  };

  const config = getTypeConfig();

  return (
    <div 
      className={`fox-message fox-message--${type} ${isAnimating ? 'fox-message--show' : 'fox-message--hide'}`}
      style={{
        backgroundColor: config.bgColor,
        borderColor: config.borderColor,
        color: config.textColor
      }}
    >
      <div className="fox-message__icon-wrapper">
        <img 
          src={foxhead} 
          alt="狐狸" 
          className="fox-message__fox-icon"
        />
        <span className="fox-message__emoji">{config.emoji}</span>
      </div>
      <div className="fox-message__content">
        <p className="fox-message__text">{message}</p>
      </div>
      <button 
        className="fox-message__close"
        onClick={handleClose}
        aria-label="关闭"
      >
        ×
      </button>
    </div>
  );
};

export default FoxMessage;

