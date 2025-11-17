import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import "./styles/diary.css";
import $ from "jquery";
import "turn.js";
import turnVoiceSound from "./styles/turn-voice.mp3";
import { log } from "three";

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

  // 每页的文字内容（可按实际需求修改）
  const pageTexts = useMemo(() => {
    const texts = [
      "", // 封面页无文字（第 0 页）
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

  const pages = useMemo(() => {
    const modules = import.meta.glob("../styles/img/diary-lock-*.jpg", { eager: true });
    const items = Object.entries(modules)
      .map(([path, mod]) => {
        const match = path.match(/diary-lock-(\d+)\.jpg$/);
        const num = match ? parseInt(match[1], 10) : 0;
        return { num, url: mod.default };
      })
      .filter((it) => it.num > 0)
      .sort((a, b) => a.num - b.num)
      .map((it) => it.url);
    return items.length ? items : [];
  }, []);

  const computeSize = useCallback(() => {
    const parent = containerRef.current;
    if (!parent) return { w: 360, h: 480 };
    const maxW = Math.min(parent.clientWidth, 480);
    // 单页：竖版比例 3:4（w:h）
    const w = Math.max(280, Math.floor(maxW));
    const h = Math.min(Math.floor(w * (4 / 3)), Math.floor(window.innerHeight * 0.7));
    return { w, h };
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
      
      return () => {
        window.removeEventListener('resize', updateSize);
      };
    }
  }, [started, computeSize]);

  // 触发当前页文字逐个显示动画
  // pageNum: Turn.js 页码（1=封面，2=第一页内容，3=第二页内容...）
  const animateText = useCallback((pageNum) => {

    // 封面页（第1页）不显示文字
    if (pageNum === 1) {
      return;
    }

    // 将 Turn.js 页码转换为文字索引（页码-1，因为第1页是封面）
    const textIndex = pageNum - 1;

    // 清除之前的动画定时器
    animationTimersRef.current.forEach(timer => clearTimeout(timer));
    animationTimersRef.current = [];

    // 延迟执行，确保 Turn.js 完成 DOM 操作
    setTimeout(() => {
      // 获取文字内容（优先使用 ref）
      const texts = pageTextsRef.current.length > 0 ? pageTextsRef.current : pageTexts;
      const text = texts[textIndex] || "";

      if (!text) {
        return;
      }

      // 简化元素查找：优先使用 Turn.js view API，失败则使用 data-page
      let textEl = null;
      let retryCount = 0;
      const maxRetries = 8; // 增加重试次数

      const findTextElement = () => {
        // 方式1: 直接通过 data-page 属性查找（最可靠，因为所有页面都渲染了）
        const pageEl = flipRef.current?.querySelector(`[data-page="${pageNum}"]`);
        if (pageEl) {
          textEl = pageEl.querySelector(".diary-text-display");
          if (textEl) {
            return true;
          } else {
          }
        } else {
        }

        // 方式2: 通过 Turn.js 的 view API 获取当前可见页元素（备用）
        if (flipRef.current && $.fn && $.fn.turn) {
          try {
            const currentPageFromTurn = $(flipRef.current).turn("page");

            if (currentPageFromTurn === pageNum) {
              const turnPage = $(flipRef.current).turn("view");
              // turnPage 是 jQuery 对象，需要获取原生 DOM 元素
              if (turnPage && turnPage.length > 0) {
                const pageElement = turnPage.get(0) || turnPage[0];
                // 确保是 DOM 元素
                if (pageElement && pageElement.nodeType === 1) {
                  const foundEl = pageElement.querySelector ? pageElement.querySelector(".diary-text-display") : null;
                  if (foundEl) {
                    textEl = foundEl;
                    return true;
                  }
                }
              }
            }
          } catch (e) {
          }
        }

        return false;
      };

      // 重试查找元素
      const tryFind = () => {
        if (findTextElement() || retryCount >= maxRetries) {
          if (!textEl) {
            // 最后一次尝试：列出所有可用的元素
            if (flipRef.current) {
              const allPages = flipRef.current.querySelectorAll("[data-page]");
              const allTextDisplays = flipRef.current.querySelectorAll(".diary-text-display");
            }
            return;
          }
          continueAnimation();
        } else {
          retryCount++;
          setTimeout(tryFind, 200); // 减少重试延迟
        }
      };

      const continueAnimation = () => {
        if (!textEl) {
          return;
        }


        // 确保重置状态 - 使用找到的元素引用
        textEl.textContent = "";
        textEl.classList.remove("diary-text--typing");

        // 强制重排，确保重置生效
        void textEl.offsetWidth;

        // 延迟一小段时间后开始动画
        const startTimer = setTimeout(() => {
          // 再次验证元素是否还在且属于当前页
          let finalTextEl = textEl;
          try {
            const currentPage = $(flipRef.current)?.turn("page");
            if (currentPage && currentPage !== pageNum) {
              console.warn(`Page changed during animation setup: expected ${pageNum}, got ${currentPage}`);
              // 如果页码变了，尝试重新查找正确的元素（通过 data-page）
              const pageEl = flipRef.current?.querySelector(`[data-page="${currentPage}"]`);
              if (pageEl) {
                const viewTextEl = pageEl.querySelector(".diary-text-display");
                if (viewTextEl) {
                  finalTextEl = viewTextEl;
                }
              }
            } else {
              // 页码一致，使用 Turn.js view API 再次确认当前可见的元素
              try {
                const turnPage = $(flipRef.current)?.turn("view");
                if (turnPage && turnPage.length > 0) {
                  const pageElement = turnPage.get(0) || turnPage[0];
                  if (pageElement && pageElement.nodeType === 1 && pageElement.querySelector) {
                    const viewTextEl = pageElement.querySelector(".diary-text-display");
                    if (viewTextEl) {
                      finalTextEl = viewTextEl;
                    }
                  }
                }
              } catch (e) {
                // 如果出错，使用原来的 textEl
              }
            }
          } catch (e) {
            // 如果出错，使用原来的 textEl
            console.warn("Error verifying element:", e);
          }

          if (!finalTextEl || !finalTextEl.parentElement) {
            console.warn(`Text element for page ${pageNum} is no longer in DOM, trying to find again...`);
            // 最后尝试：直接通过 data-page 查找
            const pageEl = flipRef.current?.querySelector(`[data-page="${pageNum}"]`);
            if (pageEl) {
              finalTextEl = pageEl.querySelector(".diary-text-display");
            }
            if (!finalTextEl || !finalTextEl.parentElement) {
              console.error(`Failed to find text element for page ${pageNum}`);
              return;
            }
          }

          finalTextEl.classList.add("diary-text--typing");

          // 逐个字符显示
          const chars = text.split("");
          chars.forEach((char, idx) => {
            const timer = setTimeout(() => {
              // 每次更新前检查元素是否还存在，如果不存在则尝试重新查找
              let targetEl = finalTextEl;
              if (!targetEl || !targetEl.parentElement) {
                const pageEl = flipRef.current?.querySelector(`[data-page="${pageNum}"]`);
                if (pageEl) {
                  targetEl = pageEl.querySelector(".diary-text-display");
                }
              }

              if (targetEl && targetEl.parentElement) {
                targetEl.textContent += char;
                if (idx === chars.length - 1) {
                  targetEl.classList.remove("diary-text--typing");
                }
              }
            }, idx * 50); // 每个字符间隔 50ms，形成书写感
            animationTimersRef.current.push(timer);
          });
        }, 300);

        animationTimersRef.current.push(startTimer);
      };

      // 开始查找元素并执行动画
      tryFind();
    }, 500); // 等翻页动画完成（增加延迟确保 DOM 更新完成）
  }, [pageTexts]);

  // 同步 animateText 到 ref，确保 end 事件回调总是调用最新版本
  useEffect(() => {
    animateTextRef.current = animateText;
  }, [animateText]);

  // 播放翻页音效的函数（同步执行，不等待）
  const playTurnSoundImmediately = useCallback(() => {
    if (!turnSoundRef.current) return;
    
    // 防重复播放：如果 300ms 内已经播放过，或者音频正在播放，则跳过
    const now = Date.now();
    const audio = turnSoundRef.current;
    
    // 如果音频正在播放，说明已经播放过了，跳过
    if (!audio.paused && audio.currentTime < 0.1) {
      console.log('跳过重复播放（音频正在播放）');
      return;
    }
    
    // 如果 300ms 内已经播放过，则跳过
    if (now - lastSoundPlayTimeRef.current < 300) {
      console.log('跳过重复播放（时间间隔太短）');
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
      console.log('播放翻页音效', 'readyState:', audio.readyState);
      if (playPromise) {
        playPromise.catch(err => {
          console.warn("Failed to play turn sound:", err);
        });
      }
    } catch (err) {
      console.warn("Failed to play turn sound:", err);
    }
  }, []);

  // 初始化音频并预加载
  useEffect(() => {
    if (turnSoundRef.current) return;
    turnSoundRef.current = new Audio(turnVoiceSound);
    turnSoundRef.current.volume = 0.5; // 设置音量
    turnSoundRef.current.preload = "auto"; // 预加载音频
    // 强制加载音频到内存
    turnSoundRef.current.load();
    return () => {
      if (turnSoundRef.current) {
        turnSoundRef.current.pause();
        turnSoundRef.current = null;
      }
    };
  }, []);

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

    const handlePageChange = (event, page, view) => {
      // 确保获取正确的页码（Turn.js 页码：1=封面，2=第一页内容，3=第二页内容...）
      const pageNum = page || 1;

      // 封面页（第1页）不显示文字
      if (pageNum === 1) {
        lastHandledPage = pageNum;
        return;
      }

      // 如果是初始加载且是第1页，只记录页码，不触发动画
      if (isInitialLoad && pageNum === 1) {
        lastHandledPage = pageNum;
        return;
      }

      // 第一次真正的翻页后，标记初始加载完成
      if (isInitialLoad && pageNum !== 1) {
        isInitialLoad = false;
      }

      // 防抖：如果正在处理相同的页码，或者页码没有变化，则忽略
      if (isHandling || (pageNum === lastHandledPage && lastHandledPage !== 1)) {
        return;
      }

      lastHandledPage = pageNum;
      currentPageRef.current = pageNum;
      isHandling = true;

      // 将 Turn.js 页码转换为文字索引（页码-1，因为第1页是封面）
      const textIndex = pageNum - 1;

      const texts = pageTextsRef.current.length > 0 ? pageTextsRef.current : [];

      // 清除之前的动画定时器
      animationTimersRef.current.forEach(timer => clearTimeout(timer));
      animationTimersRef.current = [];

      // 延迟执行动画，确保 Turn.js 完成 DOM 操作
      // 使用 ref 调用，确保总是调用最新版本的函数
      setTimeout(() => {
        if (animateTextRef.current) {
          animateTextRef.current(pageNum); // 传递 Turn.js 页码
        } else {
          console.error(`[PAGE CHANGE] ✗ animateTextRef.current is null!`);
        }
        isHandling = false;
      }, 400);
    };

    // 初始化 Turn.js
    $(el).turn({
      width: w,
      height: h,
      display: "single",
      autoCenter: true,
      elevation: 50,
      acceleration: true,
      gradients: true,
      duration: 600,
      when: {
        start: (event, page, view) => {
          // start 事件在翻页开始时立即触发
          // 注意：page 参数可能是对象，需要检查
          const pageNum = typeof page === 'number' ? page : (page?.page || 1);
          console.log('翻页开始 start 事件', 'page:', pageNum, 'page type:', typeof page);
          isTurningRef.current = true; // 标记正在翻页
          // 只在 turning 事件还没触发时播放（通过检查时间戳）
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
          // 优先在 turning 事件中播放（因为它的参数更可靠）
          // 防重复机制会在函数内部处理
          playTurnSoundImmediately();
          
          // 在翻页开始时清除当前页的文字（延迟执行，不阻塞音频播放）
          setTimeout(() => {
            try {
              const currentPage = $(el).turn("page");
              const pageEl = el.querySelector(`[data-page="${currentPage}"]`);
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
          }, 0);
        },
        turned: (event, page, view) => {
          // 备用方案：使用 turned 事件
          // handlePageChange(event, page, view);
        }
      }
    });

    // // 同时使用 jQuery 的 on 方法绑定事件（多重保障）
    // $(el).on("end", handlePageChange);
    // $(el).on("turned", handlePageChange);
    // // 绑定 turning 事件以清除文字和播放音效
    // $(el).on("turning", (event, page, view) => {
    //   // 播放翻页音效
    //   // if (turnSoundRef.current) {
    //   //   turnSoundRef.current.currentTime = 0; // 重置到开头
    //   //   turnSoundRef.current.play().catch(err => {
    //   //     console.warn("Failed to play turn sound:", err);
    //   //   });
    //   // }
      
    //   try {
    //     const currentPage = $(el).turn("page");
    //     const pageEl = el.querySelector(`[data-page="${currentPage}"]`);
    //     if (pageEl) {
    //       const textEl = pageEl.querySelector(".diary-text-display");
    //       if (textEl) {
    //         textEl.textContent = "";
    //         textEl.classList.remove("diary-text--typing");
    //       }
    //     }
    //   } catch (e) {
    //     // 忽略错误
    //   }
    // });

    // // 轮询检测页码变化（最终备用方案）
    // let lastDetectedPage = 1;
    // let isInitialized = false; // 标志：初始化是否完成

    // // 初始化时获取当前页码
    // setTimeout(() => {
    //   try {
    //     lastDetectedPage = $(el).turn("page") || 1;
    //   } catch (e) {
    //     lastDetectedPage = 1;
    //   }
    // }, 500);

    // const pageCheckInterval = setInterval(() => {
    //   // 在初始化完成前，只记录页码，不触发动画
    //   if (!isInitialized) {
    //     try {
    //       const currentPage = $(el).turn("page");
    //       if (currentPage) {
    //         lastDetectedPage = currentPage;
    //       }
    //     } catch (e) {
    //       // 忽略错误
    //     }
    //     return;
    //   }

    //   try {
    //     const currentPage = $(el).turn("page");
    //     if (currentPage && currentPage !== lastDetectedPage) {
    //       lastDetectedPage = currentPage;
    //       handlePageChange(null, currentPage, null);
    //     }
    //   } catch (e) {
    //     // Turn.js 可能还没初始化或已销毁
    //   }
    // }, 200); // 每 200ms 检查一次

    // // 保存 interval ID 以便清理
    // el._pageCheckInterval = pageCheckInterval;

    // // 初始化完成标记（封面不需要显示文字，所以直接标记完成）
    // setTimeout(() => {
    //   try {
    //     const currentPage = $(el).turn("page");
    //     // 封面页不需要显示文字，直接标记初始化完成
    //     setTimeout(() => {
    //       isInitialized = true;
    //       isInitialLoad = false;
    //     }, 500);
    //   } catch (e) {
    //     console.warn("Turn.js not ready yet, retrying...", e);
    //     setTimeout(() => {
    //       isInitialized = true;
    //       isInitialLoad = false;
    //     }, 1000);
    //   }
    // }, 800);
  }, [computeSize, animateText, playTurnSoundImmediately]);

  useEffect(() => {
    if (!started) return;
    initFlip();
    const onResize = () => {
      const { w, h } = computeSize();
      try {
        $(flipRef.current).turn("size", w, h);
      } catch (_) {}
    };
    window.addEventListener("resize", onResize);
    // 单页模式：保留在第 1 页作为封面页

    return () => {
      window.removeEventListener("resize", onResize);
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
  }, [started, initFlip, computeSize]);

  const handleStart = () => {
    setStarted(true);
    // 等待 Turn.js 初始化后，自动翻到第一页内容（第2页）
    setTimeout(() => {
      if (flipRef.current && $.fn && $.fn.turn) {
        try {
          $(flipRef.current).turn("page", 2);
        } catch (e) {
          setTimeout(() => {
            try {
              $(flipRef.current).turn("page", 2);
            } catch (e2) {
            }
          }, 500);
        }
      }
    }, 800);
  };
  
  // 翻页按钮（如果需要在 UI 中使用）
  const goPrev = () => { 
    try { 
      $(flipRef.current).turn("previous"); 
    } catch (_) {} 
  };
  
  const goNext = () => { 
    try { 
      $(flipRef.current).turn("next"); 
    } catch (_) {} 
  };

  if (!started) {
    return (
      <div className="diary-root" ref={containerRef} style={{ height: `${coverSize.h}px`, overflow: 'hidden' }}>
        <div 
          className="diary-book-cover diary-book-cover--standalone"
          onClick={handleStart} 
          role="button" 
          aria-label="打开日记"
          style={{ width: `${coverSize.w}px`, height: `${coverSize.h}px` }}
        >
          <div className="diary-cover-content">
            <div className="diary-cover-decoration diary-cover-decoration--top"></div>
            <div className="diary-cover-main">
              <div className="diary-cover-title">星空日记</div>
              <div className="diary-cover-ornament">✦</div>
            </div>
            <div className="diary-cover-decoration diary-cover-decoration--bottom"></div>
          </div>
          <div className="diary-cover-spine"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="diary-root" ref={containerRef}>
      <div id="flipbook" className="diary-flipbook" ref={flipRef}>
        {/* 封面页（第1页） */}
        <div 
          className="diary-page diary-page--cover" 
          data-page={1}
          onClick={(e) => {
            // 防止重复翻页
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
            playTurnSoundImmediately();
            
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
          style={{ cursor: 'pointer' }}
        >
          <div className="diary-book-cover diary-book-cover--page">
            <div className="diary-cover-content">
              <div className="diary-cover-decoration diary-cover-decoration--top"></div>
              <div className="diary-cover-main">
                <div className="diary-cover-title">星空日记</div>
                <div className="diary-cover-ornament">✦</div>
              </div>
              <div className="diary-cover-decoration diary-cover-decoration--bottom"></div>
            </div>
            <div className="diary-cover-spine"></div>
          </div>
        </div>
        
        {/* 内容页 */}
        {pages.map((img, idx) => {
          const pageNum = idx + 2; // 从第2页开始（封面是第1页）
          const text = pageTexts[idx + 1] || ""; // 文字索引从1开始（对应第一页内容）
          return (
            <div key={idx} className="diary-page" data-page={pageNum} style={{ backgroundImage: `url('${img}')` }}>
              {text && (
                <div className="diary-text-container">
                  <div className="diary-text-display"></div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
