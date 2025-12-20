import React, { useEffect, useRef, useState } from 'react';
import './styles/WordCloud.css';

// 直接导入wordcloud库
import wordcloud from 'wordcloud';

// 获取wordcloud库（支持多种加载方式）
const getWordCloudLib = () => {
  // 优先使用import导入的wordcloud
  if (wordcloud) {
    // wordcloud包可能导出函数或对象
    if (typeof wordcloud === 'function') {
      return wordcloud;
    }
    // 如果是对象，尝试获取default或直接使用
    return wordcloud.default || wordcloud;
  }
  
  // 尝试通过window.WordCloud（script标签引入）
  if (typeof window !== 'undefined' && window.WordCloud) {
    return window.WordCloud;
  }
  
  return null;
};

/**
 * 词云组件
 * 生成卡通风格的词云
 */
const WordCloud = ({ 
  text, 
  width = 600, 
  height = 400,
  className = '',
  onWordClick,
  onRendered // 渲染完成回调，返回canvas元素
}) => {
  const canvasRef = useRef(null);
  const [isRendered, setIsRendered] = useState(false);

  // 卡通风格的配色方案
  const cartoonColors = [
    '#FF6B9D', // 粉红色
    '#C44569', // 深粉色
    '#FFA07A', // 浅橙红色
    '#FFD700', // 金色
    '#FF69B4', // 热粉色
    '#FF1493', // 深粉色
    '#FF6347', // 番茄红
    '#FF8C00', // 深橙色
    '#FFB6C1', // 浅粉色
    '#FFC0CB', // 粉色
    '#FF69B4', // 热粉色
    '#DA70D6', // 兰花紫
    '#BA55D3', // 中兰花紫
    '#9370DB', // 中紫色
    '#8A2BE2', // 蓝紫色
    '#FFD700', // 金色
    '#FFA500', // 橙色
    '#FF7F50', // 珊瑚色
    '#FF6347', // 番茄红
    '#FF4500', // 橙红色
  ];

  // 中文分词函数（改进版本，提取更多词条）
  const segmentText = (text) => {
    if (!text) return [];
    
    const words = [];
    const chineseRegex = /[\u4e00-\u9fa5]+/g;
    const englishRegex = /[a-zA-Z]+/g;
    
    // 提取所有中文字符和词汇
    let match;
    const allChineseChars = [];
    while ((match = chineseRegex.exec(text)) !== null) {
      const segment = match[0];
      // 提取单字
      for (let i = 0; i < segment.length; i++) {
        allChineseChars.push(segment[i]);
      }
      // 提取2字词
      for (let i = 0; i < segment.length - 1; i++) {
        words.push(segment.substring(i, i + 2));
      }
      // 提取3字词
      for (let i = 0; i < segment.length - 2; i++) {
        words.push(segment.substring(i, i + 3));
      }
      // 提取4字词
      for (let i = 0; i < segment.length - 3; i++) {
        words.push(segment.substring(i, i + 4));
      }
    }
    
    // 添加单字（频率高的单字）
    words.push(...allChineseChars);
    
    // 提取英文单词
    while ((match = englishRegex.exec(text)) !== null) {
      const word = match[0].toLowerCase();
      if (word.length >= 2) {
        words.push(word);
      }
    }
    
    return words;
  };

  // 统计词频
  const countWords = (words) => {
    const wordCount = {};
    words.forEach(word => {
      wordCount[word] = (wordCount[word] || 0) + 1;
    });
    return wordCount;
  };

  // 转换为wordcloud需要的格式
  const formatWordCloudData = (wordCount) => {
    return Object.entries(wordCount).map(([text, value]) => [text, value]);
  };

  // 生成词云
  useEffect(() => {
    if (!text || !canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    
    // 清空画布
    ctx.clearRect(0, 0, width, height);

    // 分词和统计
    const words = segmentText(text);
    console.log('分词结果数量:', words.length);
    if (words.length === 0) {
      setIsRendered(false);
      return;
    }

    const wordCount = countWords(words);
    const wordCloudData = formatWordCloudData(wordCount);
    console.log('词云数据数量:', wordCloudData.length, '前10个词:', wordCloudData.slice(0, 10));

    if (wordCloudData.length === 0) {
      setIsRendered(false);
      return;
    }

    // 配置wordcloud选项 - 卡通风格，优化分布减少空白，显示更多词条
    // 按词频排序，只取前100个高频词
    const sortedData = wordCloudData.sort((a, b) => b[1] - a[1]).slice(0, 100);
    
    const options = {
      list: sortedData,
      gridSize: Math.round(4 * (width / 1024)), // 减小网格，让更多词能显示
      weightFactor: function (size) {
        // 调整权重，让词云分布更均匀，字体大小更合理
        return Math.pow(size, 0.5) * (width / 1024) * 20;
      },
      fontFamily: '"萌趣甜心体", "Microsoft YaHei", "Heiti SC", sans-serif',
      color: function (word, weight, fontSize, distance, theta) {
        // 根据权重和角度选择颜色，创造卡通效果
        const index = Math.floor(Math.random() * cartoonColors.length);
        return cartoonColors[index];
      },
      rotateRatio: 0.4, // 40%的词会旋转，增加动感
      rotationSteps: 2, // 旋转角度：0, 90
      backgroundColor: 'transparent',
      minSize: 14, // 减小最小字体，让更多词能显示
      drawOutOfBound: false, // 不允许绘制到边界外，确保所有词都在可见区域
      shrinkToFit: true, // 收缩适应，让词条充分利用空间
      shape: 'circle', // 圆形形状，更卡通
      ellipticity: 0.65, // 椭圆度，让词云更圆润
      hover: function(item, dimension, event) {
        if (onWordClick) {
          canvas.style.cursor = 'pointer';
        }
      },
      click: function(item) {
        if (onWordClick) {
          onWordClick(item);
        }
      }
    };

    try {
      const WordCloudLib = getWordCloudLib();
      if (WordCloudLib && typeof WordCloudLib === 'function') {
        WordCloudLib(canvas, options);
        setIsRendered(true);
        // 渲染完成后回调
        if (onRendered && canvas) {
          onRendered(canvas);
        }
      } else {
        console.warn('wordcloud库未正确加载，请确保已安装wordcloud包或通过script标签引入');
        setIsRendered(false);
      }
    } catch (error) {
      console.error('生成词云失败:', error);
      setIsRendered(false);
    }
  }, [text, width, height, onWordClick, onRendered]);

  return (
    <div className={`wordcloud-container ${className}`}>
      <canvas
        ref={canvasRef}
        width={width}
        height={height}
        className="wordcloud-canvas"
        style={{
          width: `${width}px`,
          height: `${height}px`,
          maxWidth: '100%',
          maxHeight: '100%',
          objectFit: 'contain',
        }}
      />
      {!isRendered && text && (
        <div className="wordcloud-loading">
          <div className="wordcloud-loading-spinner"></div>
          <p>正在生成词云...</p>
        </div>
      )}
    </div>
  );
};

export default WordCloud;
