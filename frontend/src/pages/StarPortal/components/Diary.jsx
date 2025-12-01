import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import "./styles/diary.css";
import $, { error } from "jquery";
import "turn.js";
import turnVoiceSound from "./styles/turn-voice.mp3";
import { log } from "three";
import Cookies from "js-cookie";
import ImageGeneration from '../../../components/ImageGeneration';
import './styles/diary.css';
import './styles/DiarySave.css';
import { 
  generateImageWithEmotion, 
  adjustImage, 
  getEmotionTypes, 
  base64ToImageUrl, 
  getFullImageUrl 
} from '../../../services/imageGenerationService';
export default function Diary() {
  const [started, setStarted] = useState(false);
  const [coverSize, setCoverSize] = useState({ w: 360, h: 480 }); // 默认尺寸
  const containerRef = useRef(null);
  const flipRef = useRef(null);
  const currentPageRef = useRef(1);
  const animationTimersRef = useRef([]);
  const pageTextsRef = useRef([]);
  const animateTextRef = useRef(null);
  const turnSoundRef = useRef(null);
  const lastSoundPlayTimeRef = useRef(0); // 记录上次播放时间，防止重复播放
  const isTurningRef = useRef(false); // 标记是否正在翻页，防止重复触发
  let errorTimes = 0;
  
  // DOM缓存，减少重复查询
  const pageElementsCache = useRef(new Map());
  
  // 获取页面元素的辅助函数，使用缓存
  const getPageElement = useCallback((pageNum) => {
    if (!flipRef.current) return null;
    
    // 检查缓存
    if (pageElementsCache.current.has(pageNum)) {
      const cachedElement = pageElementsCache.current.get(pageNum);
      // 检查元素是否仍在DOM中
      if (document.contains(cachedElement)) {
        return cachedElement;
      } else {
        // 如果元素不在DOM中，从缓存中移除
        pageElementsCache.current.delete(pageNum);
      }
    }
    
    // 缓存中没有或已失效，重新查询
    const pageEl = flipRef.current.querySelector(`[data-page="${pageNum}"]`);
    if (pageEl) {
      // 添加到缓存
      pageElementsCache.current.set(pageNum, pageEl);
    }
    
    return pageEl;
  }, []);
  
  // 清理缓存的函数
  const clearPageElementsCache = useCallback(() => {
    pageElementsCache.current.clear();
  }, []);
  
  // 新增状态管理
  const [isGeneratingImage, setIsGeneratingImage] = useState(false);
  const [generatedImage, setGeneratedImage] = useState(null);
  const [emotionTags, setEmotionTags] = useState([]);
  const [showAdjustmentOptions, setShowAdjustmentOptions] = useState(false);
  const [currentPrompt, setCurrentPrompt] = useState('');
  const [imageGenerationError, setImageGenerationError] = useState(null);
  
  // 文生图界面相关的状态管理
  const [isDiaryOpen, setIsDiaryOpen] = useState(false);
  const [currentPage, setCurrentPage] = useState(0);
  const [showImageGeneration, setShowImageGeneration] = useState(false);
  const [diaryContentForImage, setDiaryContentForImage] = useState('');
  // 每页的文字内容（可按实际需求修改）
  // 每页的文字内容
  const pageTexts = useMemo(() => {
    const texts = [
      "", // 封面页无文字（第 0 页）
      "",
      "",
      "",
      "",
      "",
      ""
    ];
    // 同时保存到 ref，方便在回调中访问
    pageTextsRef.current = texts;
    return texts;
  }, []);

  // 加载日记页面图片
  const pages = useMemo(() => {
    // 使用img/diary目录中的图片
    const images = [
      "/img/diary/diaryPage1.jpg",
      "/img/diary/diaryPage2.jpg",
      "/img/diary/diaryPage3.jpg",
      "/img/diary/diaryPage4.jpg",
      "/img/diary/diaryPage5.jpg",
      "/img/diary/diaryPage6.jpg"
    ];
    return images;
  }, []);

  // 加载日记文本背景图片（可选）
  const textBackgrounds = useMemo(() => {
    const backgrounds = [
      "./img/diary/diaryText1.jpg",
      "./img/diary/diaryText2.jpg",
      "./img/diary/diaryText3.jpg",
      "./img/diary/diaryText4.jpg",
      "./img/diary/diaryText5.jpg",
      "./img/diary/diaryText6.jpg"
    ];
    return backgrounds;
  }, [])
    /**
   * 编辑指定页面的内容
   * @param {string} newText - 要写入的文本内容
   * @param {number} pageIndex - 第几篇日记 (1, 2, 3...)
   */
  const editPageContent = useCallback((newText, pageIndex) => {
    // 1. 边界检查
    if (!pageIndex || pageIndex < 1) {
        console.warn("页数无效，请输入从 1 开始的整数");
        return;
    }

    // 2. 更新内存数据 (Ref)
    // 我们的数组设计中，索引 1 对应第一篇日记，正好与传入的 pageIndex 对应
    if (pageTextsRef.current) {
      pageTextsRef.current[pageIndex] = newText;
    }

    // 3. 更新视觉 DOM (直接操作 HTML 节点)
    // 换算公式：第 1 篇日记 -> Turn.js 的第 3 页 (1 * 2 + 1)
    //          第 2 篇日记 -> Turn.js 的第 5 页 (2 * 2 + 1)
    const targetTurnPage = pageIndex * 2 + 1;

    // 使用缓存的getPageElement函数
    const pageEl = getPageElement(targetTurnPage);
    
    if (pageEl) {
      const textEl = pageEl.querySelector(".diary-text-display");
      if (textEl) {
        textEl.textContent = newText;
        
        // 如果有打字机效果的残留类名，建议移除以防样式冲突
        textEl.classList.remove("diary-text--typing");
        
        console.log(`✅ 已更新第 ${pageIndex} 篇日记 (Turn页码 ${targetTurnPage})`);
      } else {
          console.warn(`未找到页面 ${targetTurnPage} 的文字容器 .diary-text-display`);
      }
    }
  }, [getPageElement]);
  const computeSize = useCallback(() => {
    const parent = containerRef.current;
    if (!parent) return { w: 360, h: 480 };
    const maxW = Math.min(parent.clientWidth, 480);
    // 单页：竖版比例 3:4（w:h）
    const w = Math.max(280, Math.floor(maxW));
    const h = Math.min(Math.floor(w * (4 / 3)), Math.floor(window.innerHeight * 0.7));
    // 宽度设为原来的180%，高度设为原来的132%（增加10%）
    return { w: Math.floor(w * 2.52), h: Math.floor(h * 1.32) };
  }, []);

  // 在容器挂载后计算封面尺寸，并监听窗口大小变化
  useEffect(() => {

    if (!started && containerRef.current) {
      const updateSize = () => {
        const size = computeSize();
        setCoverSize(size);
      };
      
      // 初始计算
      updateSize();
      
      // 监听窗口大小变化
      window.addEventListener('resize', updateSize);
      
      //初始化containerRef.current
      return () => {
        window.removeEventListener('resize', updateSize);
      };
    }

  }, [started, computeSize]);

  // 文字函数 - 直接显示完整文字，不再使用动画
  const animateText = useCallback((pageNum) => {
    // 封面页（第1页）和左侧页面（偶数页）不显示文字
    // 只有右侧页面（奇数页，从3开始）才显示文字
    if (pageNum === 1 || pageNum % 2 === 0) {
      return;
    }

    // 将右侧页码转换为文字索引
    // 第3页 -> 索引1，第5页 -> 索引2，以此类推
    const textIndex = Math.floor((pageNum - 3) / 2) + 1;

    // 清除之前的定时器
    animationTimersRef.current.forEach(timer => clearTimeout(timer));
    animationTimersRef.current = [];

    // 获取文字内容（优先使用 ref）
    const texts = pageTextsRef.current.length > 0 ? pageTextsRef.current : pageTexts;
    const text = texts[textIndex] || "";

    if (!text) {
      return;
    }

    // 使用缓存的getPageElement函数直接获取页面元素
    const pageEl = getPageElement(pageNum);
    if (pageEl) {
      const textEl = pageEl.querySelector(".diary-text-display");
      if (textEl) {
        // 直接设置完整文字，不再使用动画
        try {
          textEl.textContent = text;
          // 确保移除打字效果的类
          textEl.classList.remove("diary-text--typing");
        } catch (err) {
          console.warn("Failed to set text content:", err);
        }
      }
    }
  }, [pageTexts, getPageElement]);

  // 同步 animateText 到 ref，确保 end 事件回调总是调用最新版本
  useEffect(() => {
    animateTextRef.current = animateText;
  }, [animateText]);

  // 播放翻页音效的函数（同步执行，不等待）
  const playTurnSoundImmediately = useCallback(() => {
    if (!turnSoundRef.current) return;
    //console.log("播放音效");
    // 防重复播放：如果 300ms 内已经播放过，或者音频正在播放，则跳过
    const now = Date.now();
    const audio = turnSoundRef.current;
    
    // 如果音频正在播放，说明已经播放过了，跳过
    if (!audio.paused && audio.currentTime < 0.1) {
      // console.log('跳过重复播放（音频正在播放）');
      return;
    }
    
    // 如果 300ms 内已经播放过，则跳过
    if (now - lastSoundPlayTimeRef.current < 300) {
      // console.log('跳过重复播放（时间间隔太短）');
      return;
    }
    lastSoundPlayTimeRef.current = now;
    
    // 如果音频正在播放，先暂停
    if (!audio.paused) {
      audio.pause();
    }
    // 重置到开头
    audio.currentTime = 0;
    // 立即播放，不等待任何异步操作
    try {

      const playPromise = audio.play();
      // console.log('播放翻页音效', 'readyState:', audio.readyState);
      if (playPromise) {
        playPromise.catch(err => {
          console.warn("Failed to play turn sound:", err);
        });
      }
    } catch (err) {
      console.warn("Failed to play turn sound:", err);
    }
  }, []);
  const handleTextChange = (e, pageNum) => {
      try {
        // 只处理右侧页面（奇数页）的文字编辑
        if (pageNum % 2 === 0) {
          return;
        }
        
        const text = e.target.innerText;
        // 计算对应的文字索引
        const textIndex = Math.floor((pageNum - 3) / 2) + 1;
        
        // 更新文字内容
        console.log(`页面 ${pageNum} 的文字已更新:`, text);
        
        // 安全地更新ref中的内容
        if (pageTextsRef.current && textIndex >= 0 && textIndex < pageTextsRef.current.length) {
          pageTextsRef.current[textIndex] = text;
        }
      } catch (e) {
        console.warn("[TEXT CHANGE] Error in handleTextChange:", e);
      }
    };

/**
   * 核心函数：获取并格式化日记数据
   * @param {string} userId - 用户ID
   * @param {number} limit - 最大获取篇数
   * @returns {Promise<Object>} - 返回要求的对象结构
   */
  const getFormattedDiaries = async (userId, limit) => {
    try {
      // 1. 构建请求 URL (处理查询参数)
      const response = await fetch(`/api/diary/user/${userId}?limit=${limit}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      
      // 2. 数据清洗与格式转换
      // 即使 data.diaries 为空，也要保证代码不报错
      const diariesList = data.diaries || [];

      const formattedResult = {
        diary_num: diariesList.length, // 获取到的篇数
        diary_id: diariesList.map(item => item.diary_id), // 提取所有ID组成数组
        diary_content: diariesList.map(item => item.content) // 提取所有内容组成数组
      };

      return formattedResult;

    } catch (error) {
      console.error("获取日记失败:", error);
      // 出错时返回空结构
      return { diary_num: 0, diary_id: [], diary_content: [] };
    }
  };
  window.getFormattedDiaries = getFormattedDiaries;
  const updateDiaryContent = async (diaryId, newContent) => {
  try {
    // 使用相对路径，让Vite代理转发到后端
    const response = await fetch(`/api/diary/${diaryId}`, {
      method: 'PUT', // 根据文档，更新使用 PUT 方法
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        content: newContent,
        // 文档中提到 metadata 可选，我们可以顺便记录一下更新原因
        metadata: {
          updated_at: new Date().toISOString(),
          reason: "用户编辑"
        }
      }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || '更新失败');
    }

    const updatedDiary = await response.json();
    // console.log('✅ 日记更新成功:', updatedDiary);
    //alert('更新成功！');
    return updatedDiary;

  } catch (error) {
    console.error('❌ 更新出错:', error);
    //alert('更新失败，请检查控制台');
  }
  };
  /**
 * 创建新日记 (带默认元数据)
 * @param {string} userId - 用户ID
 * @param {string} content - 日记内容
 * @returns {Promise<string|null>} - 成功返回 diary_id，失败返回 null
 */
  const createNewDiary = async (userId, content) => {
    try {
      // 1. 准备请求数据
      const requestBody = {
        user_id: userId,
        title: new Date().toLocaleDateString() + " 的日记",
        content: content,
        emotion_tags: [], 
        metadata: {
          "location": "未知",
          "weather": "未知",
          "mood_score": -1
        }
      };
      // 2. 发送请求 - 使用相对路径，让Vite代理转发到后端
      const response = await fetch(`/api/diary/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `创建失败: ${response.status}`);
      }

      // 3. 返回 ID
      const data = await response.json();
      console.log("✅ 日记创建成功，ID:", data.diary_id);
      return data.diary_id;

    } catch (error) {
      console.error("❌ 创建日记请求出错:",`user_id:${userId}    content:${content}`, error);

      return null;
    }
  };

  /**
   * 处理图片调整请求
   * @param {string} adjustmentType - 调整类型 ("warmer", "more_detail", "change_scene")
   */
  const handleImageAdjustment = async (adjustmentType) => {
    try {
      // 检查是否正在生成图片
      if (isGeneratingImage) {
        console.log('图片正在生成中，请稍候...');
        return;
      }
      
      // 获取所有日记内容
      const allTexts = pageTextsRef.current;
      let allDiaryContent = "";
      
      for (let i = 1; i <= 6; i++) {
        const content = allTexts[i];
        if (content && content.trim() !== "") {
          allDiaryContent += content + "\n\n";
        }
      }
      
      // 检查日记内容是否为空
      if (!allDiaryContent || allDiaryContent.trim() === "") {
        setImageGenerationError('日记内容为空，无法调整图片');
        return;
      }
      
      // 设置加载状态
      setIsGeneratingImage(true);
      setImageGenerationError(null);
      
      // 将英文调整类型转换为中文
      let adjustmentTypeChinese = "";
      switch(adjustmentType) {
        case "warmer":
          adjustmentTypeChinese = "风格更暖";
          break;
        case "more_detail":
          adjustmentTypeChinese = "增加细节";
          break;
        case "change_scene":
          adjustmentTypeChinese = "更换场景";
          break;
        default:
          adjustmentTypeChinese = adjustmentType;
      }
      
      // 调用imageGenerationService中的adjustImage函数
      const result = await adjustImage({
        original_prompt: currentPrompt || allDiaryContent,
        emotion: emotionTags.length > 0 ? emotionTags[0] : '平静',
        adjustment_type: adjustmentTypeChinese,
        size: "1024x1024",
        seed: -1,
        save_to_disk: true
      });
      
      // 检查结果
      if (result.success) {
        // 更新图片URL
        const imageUrl = result.image_url ? getFullImageUrl(result.image_url) : base64ToImageUrl(result.base64_data);
        setGeneratedImage(imageUrl);
        setCurrentPrompt(result.original_prompt || currentPrompt);
      } else {
        setImageGenerationError(result.message || '调整图片失败');
      }
      
    } catch (error) {
      console.error("图片调整失败:", error);
      setImageGenerationError('调整图片失败: ' + error.message);
    } finally {
      setIsGeneratingImage(false);
    }
  };
  // 优化的音频初始化 - 使用ref避免重复加载
  useEffect(() => {
    // 如果已经加载过音频，不再重复加载
    if (turnSoundRef.current) {
      return;
    }

    try {
      turnSoundRef.current = new Audio(turnVoiceSound);
      turnSoundRef.current.volume = 0.5;
      turnSoundRef.current.preload = "auto";
      // 强制加载音频到内存
      turnSoundRef.current.load();
    } catch (err) {
      console.warn("Failed to initialize audio:", err);
    }

    // 清理函数 - 确保组件卸载时释放资源
    return () => {
      if (turnSoundRef.current) {
        turnSoundRef.current.pause();
        turnSoundRef.current.src = "";
        turnSoundRef.current = null;
      }
    };
  }, []);
  // 【新增】预渲染文字函数：在翻页指令发出前，强制把下一页的字填好
  const preparePageText = useCallback((targetPageNum) => {
    // 只处理右侧有文字的页面（奇数页且大于1）
    if (targetPageNum > 1 && targetPageNum % 2 !== 0) {
      try {
        // 1. 获取文字内容
        const textIndex = Math.floor((targetPageNum - 3) / 2) + 1;
        const content = pageTextsRef.current[textIndex] || "";

        if (!content) return; // 如果内容为空，直接返回

        // 2. 使用缓存的getPageElement函数找到目标页面的 DOM
        const targetPageEl = getPageElement(targetPageNum);
        
        if (targetPageEl) {
          const textDisplayEl = targetPageEl.querySelector(".diary-text-display");
          if (textDisplayEl) {
            // 3. 强制填字，移除打字机光标
            textDisplayEl.textContent = content;
            textDisplayEl.classList.remove("diary-text--typing");
            // console.log(`[Pre-render] 已预填第 ${targetPageNum} 页文字`);
          }
        }
      } catch (err) {
        console.warn("预渲染文字出错:", err);
      }
    }
  }, [getPageElement]);
 
  const initFlip = useCallback(() => {
    if (!containerRef.current || !flipRef.current || !$.fn || !$.fn.turn) return;
    const el = flipRef.current;
    if (!el) return;
    const { w, h } = computeSize();

    // 销毁旧实例
    try { $(el).turn("destroy"); } catch (_) {}

    // 先绑定事件处理器（使用 jQuery 方式，更可靠）
    let lastHandledPage = 1;
    let isHandling = false;
    let isInitialLoad = true; // 标志：是否为初始加载

    // 优化后的页面切换处理函数 - 减少延迟和DOM操作
    const handlePageChange = (event, page, view) => {
      try {
        // 【核心修复】获取当前视图中的所有页码 (例如 [6, 7])
        // 如果 view 参数不存在，尝试通过 turn("view") 获取
        const currentView = view || $(el).turn("view");
        
        // 标记是否正在处理（原有逻辑保持）
        if (isHandling) return;
        isHandling = true;
        lastHandledPage = page;
        currentPageRef.current = page;

        // 清除之前的动画定时器
        animationTimersRef.current.forEach(timer => clearTimeout(timer));
        animationTimersRef.current = [];

        // 【优化】直接更新文字内容，不使用延迟
        try {
          // 【核心修复】遍历当前可见的所有页面，找到右侧页面（奇数页）进行更新
          currentView.forEach(p => {
            // p 是页码。我们只关心大于1的奇数页（右侧有字的页面）
            if (p > 1 && p % 2 !== 0) {
               // 计算文字索引
               const textIndex = Math.floor((p - 3) / 2) + 1;
               // 从 Ref 获取数据
               const texts = pageTextsRef.current.length > 0 ? pageTextsRef.current : pageTexts;
               const text = texts[textIndex] || "";
               
               // 使用缓存的getPageElement函数查找并更新 DOM
               const pageEl = getPageElement(p);
               if (pageEl) {
                 const textEl = pageEl.querySelector(".diary-text-display");
                 if (textEl) {
                   textEl.textContent = text;
                   // console.log(`[Fix] 已修复显示第 ${p} 页 (日记篇章 ${textIndex}) 的文字`);
                 }
               }
            }
          });
        } catch (err) {
          console.warn("Failed to set text content:", err);
        } finally {
          isHandling = false;
        }

      } catch (e) {
        console.warn("[PAGE CHANGE] Error in handlePageChange:", e);
        isHandling = false;
      }
    };
    
    

    // 初始化 Turn.js
    $(el).turn({
      width: w,
      height: h,
      display: "double",
      autoCenter: true,
      elevation: 30,
      acceleration: true,
      gradients: true,
      duration: 600,
      when: {
          start: (event, page, view) => {
            
            // start 事件在翻页开始时立即触发
            // 注意：page 参数可能是对象，需要检查
            const pageNum = typeof page === 'number' ? page : (page?.page || 1);
            //console.log('翻页开始 start 事件', 'page:', pageNum, 'page type:', typeof page);
            isTurningRef.current = true; // 标记正在翻页
            // 确保在翻页开始时立即播放声音
            playTurnSoundImmediately();
          },
        end: (event, page, view) => {
          // 翻页完成，重置标记
          isTurningRef.current = false;
          handlePageChange(event, page, view);
        },
        turning: (event, page, view) => {
            // turning 事件在翻页过程中触发
            console.log('翻页中 turning 事件', 'page:', page);
            // 不再阻止默认行为，让翻页更流畅
            // 不在turning事件中播放声音，避免重复播放
            // playTurnSoundImmediately();
          //写入文字
          
          // 在翻页开始时清除当前页的文字（使用缓存提高性能）
          try {
            const currentPage = $(el).turn("page");
            const pageEl = getPageElement(currentPage);
            if (pageEl) {
              const textEl = pageEl.querySelector(".diary-text-display");
              if (textEl) {
                textEl.textContent = "";
                textEl.classList.remove("diary-text--typing");
              }
            }
          } catch (e) {
            console.warn("[TURNING EVENT] Error clearing text:", e);
          }
        },
        turned: (event, page, view) => {
          // 确保文字动画在页面完全转向后也能触发
          handlePageChange(event, page, view);
        }
      }
    });
    // ... 在 $(el).turn({ ... }) 代码块结束之后 ...
    // ... 在 $(el).turn({ ... }) 代码块结束之后 ...

    // 1. 先解绑，防止热更新导致的重复绑定
    $(el).off("click", ".diary-page");

    // 2. 全局点击监听（智能区分编辑与翻页）
    $(el).on("click", ".diary-page", function(e) {
      
      // === A. 关键判断：是否点击了文字框 ===
      // 如果点击的目标是 text-display 或者它的子元素
      if ($(e.target).hasClass("diary-text-display") || $(e.target).closest(".diary-text-display").length > 0) {
          // console.log("点击了文字框 -> 进入编辑模式 (不翻页)");
          // 这里不调用 stopPropagation，允许浏览器默认行为（光标聚焦）
          return; 
      }

      // === B. 点击了页面边缘/空白处 -> 执行翻页逻辑 ===
      
      // 阻止冒泡，防止 turn.js 默认行为干扰我们手写的逻辑
      e.stopPropagation();

      // 如果正在翻页动画中，忽略点击
      if (isTurningRef.current) return;

      // 2. 判断翻页方向
      // 获取当前点击页面的页码
      const clickedPageNum = parseInt($(this).attr("data-page"), 10);
      
      if (clickedPageNum % 2 !== 0) {
          // --- 点击了右页 (奇数) 或 封面(1) -> 往后翻 (Next) ---
          
          // 预渲染下两页的文字（防止空白）
          // 比如当前是3，翻过去是4和5，我们要先把5填好
          preparePageText(clickedPageNum + 2);
          
          $(el).turn("next");
          
      } else {
          // --- 点击了左页 (偶数) -> 往前翻 (Previous) ---
          
          // 预渲染上一页的文字
          // 比如当前是4，翻回去是2和3，我们要先把3填好
          preparePageText(clickedPageNum - 1);
          
          $(el).turn("previous");
      }
    });
    // 显式设置初始页码为1，确保封面页正确显示
    setTimeout(() => {
      try {
        $(el).turn("page", 1);
        // console.log("[INIT] 已设置初始页码为1（封面页）");
      } catch (e) {
        console.warn("[INIT] 设置初始页码失败:", e);
      }
    }, 100);

  }, [computeSize, animateText, playTurnSoundImmediately, getPageElement]);

  useEffect(() => {
    if (!started) return;
    initFlip();
    
    let resizeTimer = null;
    
    const handleResize = () => {
      // 清除之前的定时器
      if (resizeTimer) {
        clearTimeout(resizeTimer);
      }
      
      // 设置新的定时器，延迟执行
      resizeTimer = setTimeout(() => {
        if (flipRef.current && $(flipRef.current).turn) {
          try {
            // 获取当前页码
            const currentPage = $(flipRef.current).turn("page");
            
            // 重新计算尺寸并应用
            const { w, h } = computeSize();
            $(flipRef.current).turn("size", w, h);
            
            // 恢复当前页码
            $(flipRef.current).turn("page", currentPage);
          } catch (e) {
            console.warn("Failed to handle resize:", e);
          }
        }
      }, 300); // 300ms 防抖延迟
    };
    
    window.addEventListener("resize", handleResize);
    // 单页模式：保留在第 1 页作为封面页

    return () => {
      window.removeEventListener("resize", handleResize);
      if (resizeTimer) {
        clearTimeout(resizeTimer);
      }
      // 清理动画定时器
      animationTimersRef.current.forEach(timer => clearTimeout(timer));
      animationTimersRef.current = [];
      // 清理轮询检测
      if (flipRef.current && flipRef.current._pageCheckInterval) {
        clearInterval(flipRef.current._pageCheckInterval);
      }
      // 移除事件监听器
      try {
        if (flipRef.current) {
          $(flipRef.current).off("end turned turning");
        }
        $(flipRef.current).turn("destroy");
      } catch (_) {}
    };
  }, [started, computeSize]); // 只依赖computeSize

  const handleStart = () => {
    setStarted(true);
    // 移除自动翻到第2页的代码，保持在封面页（第1页）
  };
  const pageIdsRef = useRef([]); 
  // 定义保存日记数据的函数 
  const Save_diaryData = async () => {
    // 1. 获取引用中的最新数据
    const allTexts = pageTextsRef.current;
    const allIds = pageIdsRef.current;
    
    // 简单校验
    if (!allIds || allIds.length === 0) {
      console.log("当前不存在原日记数据")
    }
    
    console.group("💾 正在保存日记...");
    
    // 2. 收集所有需要保存的任务 (Promise)
    const saveTasks = [];
    let savedCount = 0;
    let creatCount = 0;
    let diaryContents = []; // 存储所有日记内容，用于文生图
    
    // 遍历索引 1 到 6 (对应6篇日记)
    for (let i = 1; i <= 6; i++) {
      let diaryId = allIds[i];
      const content = allTexts[i];

      // 收集非空日记内容用于文生图
      if (content && content.trim() !== "") {
        diaryContents.push(content);
      }

      // 只有当 ID 存在时才执行更新 (防止更新空页或未加载的页)
      if (diaryId) {
        // 即使内容为空字符串也可能需要保存(用户可能清空了日记)，所以只判断 undefined
        if (content !== undefined) {
          console.log(`正在提交第 ${i} 篇 (ID: ${diaryId})...`);
          
          // 调用现有的 updateDiaryContent 函数
          // 这个函数返回一个 Promise，我们把它推入数组
          const task = updateDiaryContent(diaryId, content)
            .then(res => {
              if(res) savedCount++; // 统计成功数量
              return res;
            });
            
          saveTasks.push(task);
        }
      }else
      {
        if (content !== undefined && content !== "")
        {
          const task = createNewDiary(Cookies.get('username'),content).
            then(
              
              res => {
              pageIdsRef.current[i] = res;
              console.log("新建id为",res);
              if(res) {
                savedCount++; // 统计成功数量
                creatCount++;
              }
              return res;
            });
          saveTasks.push(task);
          
        }
      }
    }

    // 3. 并发执行所有保存请求
    if (saveTasks.length === 0) {
      alert("没有检测到有效的日记ID，无需保存。");
      console.groupEnd();
      return;
    }

    try {
      // 等待所有请求完成
      await Promise.all(saveTasks);
      
      console.log(`✅ 批量保存完成，共处理 ${saveTasks.length}条数据,其中新建了${creatCount} 条数据`);
      
      // 4. 如果有日记内容，显示文生图界面
      if (diaryContents.length > 0) {
        // 合并所有日记内容作为提示词
        const combinedContent = diaryContents.join("\n\n");
        setDiaryContentForImage(combinedContent);
        setShowImageGeneration(true);
        
        alert(`保存成功！已同步 ${savedCount} 篇日记。`);
      } else {
        alert(`保存成功！已同步 ${savedCount} 篇日记。`);
      }
      
    } catch (error) {
      console.error("❌ 批量保存过程中出现错误:", error);
      alert("保存过程中出现部分错误，请检查网络或控制台详情。");
    } finally {
      console.groupEnd();
    }
  };

  // 在组件挂载时自动调用handleStart，实现直接打开日记的效果
  useEffect(() => {
    handleStart();
  }, []);
  //初始化日记文本
  

  useEffect(() => {
    const load_data = async () => {
      let init_diary = await getFormattedDiaries(Cookies.get('username'), 6); 

      // 2. 安全检查：确保拿到数据了
      if (!init_diary || !init_diary.diary_content) return;

      for (let i = 0; i < init_diary.diary_num; i++) {

        const targetPageIndex = i + 1;
        if (targetPageIndex > 6) break;
        editPageContent(init_diary.diary_content[i], targetPageIndex);
        pageIdsRef.current[targetPageIndex] = init_diary.diary_id[i];
      }
    };
    load_data();
    
  }, []); // 依赖数组为空，只在挂载时执行一次
  
  if (!started) {
    return (
      <div className="diary-root" ref={containerRef} style={{ height: `${coverSize.h}px`, overflow: 'hidden' }}>
        <div 
          className="diary-book-cover diary-book-cover--standalone"
          onClick={handleStart} 
          role="button" 
          aria-label="打开日记"
          style={{ 
            width: `${coverSize.w}px`, 
            height: `${coverSize.h}px`,
            backgroundImage: `url('/img/diary/diaryTitlePage.jpg')`,
            backgroundSize: 'cover',
            backgroundPosition: 'center'
          }}
        >
          <div className="diary-cover-spine"></div>
        </div>
      </div>
    );
  }


  return (
    <div className="diary-root" ref={containerRef}>
      <div id="flipbook" className="diary-flipbook" ref={flipRef}>
        {/* 封面页（第1页）- 作为右页面，左侧空白 */}
        <div 
          className="diary-page diary-page--cover" 
          data-page={1}
          style={{ 
            backgroundImage: `url('/img/diary/diaryTitlePage.jpg')`, 
            backgroundSize: 'cover', 
            backgroundPosition: 'center',
            cursor: 'pointer' 
          }}
          onClick={(e) => {
            // 防止重复翻页
            playTurnSoundImmediately();
            if (isTurningRef.current) {
              e.preventDefault();
              e.stopPropagation();
              return;
            }
            
            // 阻止事件冒泡，避免 Turn.js 也处理这个点击
            e.stopPropagation();
            e.preventDefault();
            
            // 标记正在翻页
            isTurningRef.current = true;
            
            // 在点击时立即播放音效
            
            //playTurnSoundImmediately();
            
            try {
              if (flipRef.current && $.fn && $.fn.turn) {
                $(flipRef.current).turn("next");
              }
            } catch (err) {
              console.warn("Failed to turn page:", err);
              // 翻页失败时重置标记
              isTurningRef.current = false;
            }
          }}
        >
          {/* 移除嵌套的封面结构，直接使用背景图片显示 */}
        </div>
        
        {/* 创建6个左右页对，对应6个状态 */}
        {Array.from({ length: 6 }).map((_, idx) => {
          // 计算页码 - Turn.js会自动处理双面，这里确保页码连续
          const leftPageNum = idx * 2 + 2; // 左侧页面从2开始，依次为2,4,6...
          const rightPageNum = leftPageNum + 1; // 右侧页面为3,5,7...
          
          // 获取左右页面的图片资源
          const leftPageImg = textBackgrounds[idx]; // 左侧使用diaryText.jpg
          const rightPageImg = pages[idx]; // 右侧使用diaryPage.jpg
          
          // 获取对应的文字内容
          const text = pageTexts[idx + 1] || ""; // 文字索引从1开始（对应第一页内容）
          
          return (
            <React.Fragment key={idx}>
              {/* 左侧页面 - diaryText.jpg */}
              <div 
                className="diary-page diary-page--left" 
                data-page={leftPageNum} 
                style={{ backgroundImage: `url('${leftPageImg}')` }}
              />
              
              {/* 右侧页面 - diaryPage.jpg，包含可编辑文字显示区域 */}
              <div 
                className="diary-page diary-page--right" 
                data-page={rightPageNum} 
                style={{ backgroundImage: `url('${rightPageImg}')` }}
              >
                <div className="diary-text-container">
                  <div 
                    className="diary-text-display"
                    contentEditable
                    suppressContentEditableWarning={true}
                    onInput={(e) => handleTextChange(e, rightPageNum)}
                    style={{
                      outline: 'none',
                      cursor: 'text',
                      color: '#333',
                      fontFamily: '"萌趣甜心体", "Microsoft YaHei", "Heiti SC", sans-serif',
                      lineHeight: '1.5',
                      whiteSpace: 'pre-wrap',
                      wordWrap: 'break-word'
                    }}
                  ></div>
                </div>
              </div>
            </React.Fragment>
          );
        })}
      </div>
      {/* 添加半透明的保存按钮在日记右下侧 */}
      <div 
        className="diary-save-button"
        onClick={Save_diaryData}
        style={{
          position: 'absolute',
          bottom: '20px',
          right: '20px',
          width: '100px',
          height: '40px',
          backgroundImage: `url('/img/diary/button.png')`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          cursor: 'pointer',
          zIndex: 1000,
          opacity: 0.8,
          transition: 'opacity 0.3s ease',
          boxShadow: '0 2px 10px rgba(0, 0, 0, 0.3)'
        }}
        onMouseEnter={(e) => e.target.style.opacity = 1}
        onMouseLeave={(e) => e.target.style.opacity = 0.8}
        title="保存日记"
      >
        保存并文生图
      </div>
      
      {/* 文生图界面 - 直接使用ImageGeneration组件，去掉外层模态框 */}
      <ImageGeneration 
        isVisible={showImageGeneration}
        diaryContent={diaryContentForImage}
        onClose={() => setShowImageGeneration(false)}
        onSave={(data) => {
          // 将生成的图片和情绪信息传递回Diary组件
          if (data.generatedImage) {
            setGeneratedImage(data.generatedImage);
            setEmotionTags(data.emotion ? [data.emotion] : []);
            setShowAdjustmentOptions(true);
          }
          setShowImageGeneration(false);
        }}
      />
    </div>
  );
}