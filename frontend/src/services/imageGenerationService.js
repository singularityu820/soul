/**
 * 文生图API服务
 * 用于调用后端的情绪识别与文生图API
 */

// API基础URL
const API_BASE_URL = 'https://xbxm.cloud:443/volcano-image-emotion';

/**
 * 基于日记内容和情绪生成图片
 * @param {Object} params - 请求参数
 * @param {string} params.text_content - 日记文本内容
 * @param {string} [params.custom_prompt] - 自定义图片提示词
 * @param {string} [params.size='1024x1024'] - 图片尺寸
 * @param {number} [params.seed=-1] - 随机种子
 * @param {boolean} [params.save_to_disk=true] - 是否保存到磁盘
 * @returns {Promise<Object>} 生成结果
 */
export const generateImageWithEmotion = async (params) => {
  try {
    const response = await fetch(`${API_BASE_URL}/generate-with-emotion`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(params),
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('生成图片失败:', error);
    throw error;
  }
};

/**
 * 根据用户选择调整图片
 * @param {Object} params - 请求参数
 * @param {string} params.original_prompt - 原始提示词
 * @param {string} params.emotion - 情绪类型
 * @param {string} params.adjustment_type - 调整类型
 * @param {string} [params.size='1024x1024'] - 图片尺寸
 * @param {number} [params.seed=-1] - 随机种子
 * @param {boolean} [params.save_to_disk=true] - 是否保存到磁盘
 * @returns {Promise<Object>} 调整结果
 */
export const adjustImage = async (params) => {
  try {
    const response = await fetch(`${API_BASE_URL}/adjust-image`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(params),
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('调整图片失败:', error);
    throw error;
  }
};

/**
 * 获取所有可用的情绪类型
 * @returns {Promise<Object>} 情绪类型列表
 */
export const getEmotionTypes = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/emotion-types`);
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('获取情绪类型失败:', error);
    throw error;
  }
};

/**
 * 获取特定情绪的调整选项
 * @param {string} emotion - 情绪类型
 * @returns {Promise<Object>} 情绪调整选项
 */
export const getEmotionAdjustmentOptions = async (emotion) => {
  try {
    const response = await fetch(`${API_BASE_URL}/adjustment-options/${emotion}`);
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('获取情绪调整选项失败:', error);
    throw error;
  }
};

/**
 * 将base64图片数据转换为可显示的URL
 * @param {string} base64Data - base64编码的图片数据
 * @returns {string} 图片URL
 */
export const base64ToImageUrl = (base64Data) => {
  if (!base64Data) return '';
  
  // 检查是否已经包含data URL前缀
  if (base64Data.startsWith('data:')) {
    return base64Data;
  }
  
  // 添加data URL前缀
  return `data:image/png;base64,${base64Data}`;
};

/**
 * 获取完整图片URL
 * @param {string} imagePath - 图片路径
 * @returns {string} 完整图片URL
 */
export const getFullImageUrl = (imagePath) => {
  if (!imagePath) return '';
  
  // 如果已经是完整URL，直接返回
  if (imagePath.startsWith('http://') || imagePath.startsWith('https://') || imagePath.startsWith('data:')) {
    return imagePath;
  }
  
  // 否则拼接后端URL
  return `https://xbxm.cloud:443${imagePath}`;
};