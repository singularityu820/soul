import React, { useState, useEffect, useRef } from 'react';
import './KawaiiChat.css';

// 引入图片资源
import bgChat from '../../assets/KawaiiChat/bg_chat.jpg';
import bubbleFox from '../../assets/KawaiiChat/bubble_fox.png';
import bubbleUser from '../../assets/KawaiiChat/bubble_user.png';
import inputBar from '../../assets/KawaiiChat/input_bar.png';
import btnSend from '../../assets/KawaiiChat/btn_send.png';
import btnCall from '../../assets/KawaiiChat/btn_call.png';
import foxhead from '../../assets/KawaiiChat/foxhead.jpg';
// stickerFox 引用可以删掉了，因为下面不用了
// import stickerFox from '../../assets/KawaiiChat/sticker_fox.jpg';

const KawaiiChat = () => {
  // 1. 状态管理
  const [messages, setMessages] = useState([]); 
  const [inputValue, setInputValue] = useState('');
  const [threadId, setThreadId] = useState(null);
  
  const messagesEndRef = useRef(null);
  const wsRef = useRef(null);
  const currentThreadRef = useRef(null); // 用于跟踪当前连接的thread_id

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ==========================================
  // [辅助函数] 连接 WebSocket
  // ==========================================
  const connectWebSocket = (tid) => {
    // 如果当前已经连接到相同的thread_id，无需重新连接
    if (currentThreadRef.current === tid && wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      console.log(`✅ 已连接到会话 ${tid}，无需重新连接`);
      return;
    }
    
    console.log(`🔌 准备连接到会话: ${tid}，当前连接的是: ${currentThreadRef.current}`);
    
    // 如果有旧连接，先关闭
    if (wsRef.current) {
      console.log(`🔌 关闭旧的WebSocket连接: ${currentThreadRef.current}`);
      wsRef.current.close();
      wsRef.current = null;
    }

    const ws = new WebSocket(`ws://81.68.219.218:5173/ws/chat?thread_id=${tid}`);
    
    ws.onopen = () => {
      console.log(`✅ WebSocket 已连接到会话: ${tid}`);
      currentThreadRef.current = tid; // 更新当前连接的thread_id
    };
    
    ws.onmessage = (event) => {
      try {
        const response = JSON.parse(event.data);
        
        // 只处理系统通知消息，避免与fetch流式响应重复
        if (response.type === 'message' && response.message) {
          const msgData = response.message;
          // 只处理system角色的消息，忽略user和agent角色的消息
          if (msgData.role === 'system') {
            setMessages(prev => [...prev, {
              id: msgData.message_id,
              type: 'system',
              text: msgData.text
            }]);
          }
        }
        // 忽略stream_chunk类型的消息，避免与fetch流式响应重复
      } catch (error) {
        console.error('处理WebSocket消息错误:', error, '原始数据:', event.data);
      }
    };
    
    ws.onclose = () => {
      console.log(`🔌 WebSocket 连接已关闭: ${tid}`);
      // 只有当关闭的是当前活跃的连接时，才更新currentThreadRef
      if (currentThreadRef.current === tid) {
        currentThreadRef.current = null;
        wsRef.current = null;
      }
    };

    wsRef.current = ws;
  };

  // ==========================================
  // [核心逻辑] 初始化：加载最近会话或新建
  // ==========================================
  useEffect(() => {
    const initChat = async () => {
      try {
        let currentThreadId = null;

        // 获取会话列表
        const listRes = await fetch('http://81.68.219.218:5173/chat/threads');
        const threads = await listRes.json();

        if (threads.length > 0) {
          // 如果有旧会话，加载最新的
          const latestThread = threads[threads.length - 1];
          currentThreadId = latestThread.thread_id;
          console.log("📂 加载旧会话 ID:", currentThreadId);

          // 加载历史消息
          const historyRes = await fetch(`http://81.68.219.218:5173/chat/threads/${currentThreadId}/messages`);
          const history = await historyRes.json();
          
          const formattedHistory = history.map(m => ({
            id: m.message_id,
            type: m.role === 'agent' ? 'fox' : 'user',
            text: m.text
          }));
          
          if (formattedHistory.length === 0) {
            formattedHistory.push({ id: 'init-0', type: 'fox', text: '欢迎回来！我还记得你哦 🦊' });
          }
          setMessages(formattedHistory);

        } else {
          // 如果没有，新建
          await createNewChat();
          return; // createNewChat 会处理剩下的逻辑，这里直接返回
        }

        setThreadId(currentThreadId);
        connectWebSocket(currentThreadId);

      } catch (error) {
        console.error("❌ 初始化失败:", error);
        setMessages([{ id: 'err', type: 'fox', text: '无法连接到服务器大脑...' }]);
      }
    };

    initChat();

    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  // ==========================================
  // [新功能] 创建新会话
  // ==========================================
  const createNewChat = async () => {
    try {
        console.log("🆕 正在创建新会话...");
        const createRes = await fetch('http://81.68.219.218:5173/chat/threads', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: "新的一天" })
        });
        const newThread = await createRes.json();
        const newId = newThread.thread_id;

        // 更新状态
        setThreadId(newId);
        // 清空旧消息，显示新的开场白
        setMessages([{ id: 'new-start', type: 'fox', text: '你好呀，这是一个新的开始' }]);
        
        // 重新连接 WebSocket 到新频道
        connectWebSocket(newId);
        
    } catch (error) {
        console.error("创建新会话失败:", error);
    }
  };

  // ==========================================
  // 发送逻辑
  // ==========================================
  const handleSend = async () => {
    if (!inputValue.trim()) return;
    if (!threadId) return;

    const textToSend = inputValue;
    
    // 乐观更新 - 添加带有临时标记的用户消息
    const tempId = `temp-${Date.now()}`;
    setMessages(prev => [...prev, { 
      id: tempId, 
      type: 'user', 
      text: textToSend,
      isTemp: true // 添加临时标记
    }]);
    setInputValue('');

    try {
      // 使用流式接口发送消息
      const response = await fetch(`http://81.68.219.218:5173/chat/threads/${threadId}/text-messages-stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: textToSend })
      });

      if (!response.ok) {
        throw new Error(`发送失败: ${response.status}`);
      }

      // 处理流式响应
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let aiMessageId = null;
      let aiMessageText = '';
      let isFirstChunk = true;
      let lastProcessedContent = ''; // 记录上一次处理的内容，用于去重

      // 处理流式数据
      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          // 确保处理完缓冲区中剩余的数据
          if (buffer) {
            const events = buffer.split('\n\n');
            for (const event of events) {
              if (event) {
                processEvent(event);
              }
            }
          }
          break;
        }
        
        buffer += decoder.decode(value, { stream: true });
        
        // 按SSE事件分隔符处理数据
        const events = buffer.split('\n\n');
        buffer = events.pop() || '';
        
        for (const event of events) {
          if (event) {
            processEvent(event);
          }
        }
      }

      // 处理单个SSE事件
      function processEvent(event) {
        if (!event.startsWith('data: ')) return;
        
        const dataStr = event.slice(6).trim();
        if (!dataStr) return;
        
        if (dataStr === '[DONE]') return;
        
        try {
          const data = JSON.parse(dataStr);
          
          // 处理流式消息块 - 智能累加，避免重复
          if (data.type === 'chunk' && data.content) {
            // 去重处理：如果当前内容和上一次完全相同，跳过
            if (data.content === lastProcessedContent) {
              return;
            }
            
            // 智能累加逻辑：
            // 1. 如果当前内容是之前内容的延续（更长且包含之前的内容），直接使用当前内容
            // 2. 如果是全新的内容，累加
            if (data.content.includes(aiMessageText) && data.content.length > aiMessageText.length) {
              // 当前内容是之前内容的延续，直接替换（处理后端返回完整内容的情况）
              aiMessageText = data.content;
            } else {
              // 检查是否有重叠内容，只添加新增部分
              const overlapIndex = data.content.indexOf(aiMessageText);
              if (overlapIndex === 0) {
                // 当前内容是之前内容的延续，只添加新增部分
                const newContent = data.content.slice(aiMessageText.length);
                aiMessageText += newContent;
              } else if (!data.content.includes(lastProcessedContent) || data.content.length > lastProcessedContent.length) {
                // 新的内容片段，累加
                aiMessageText += data.content;
              }
            }
            
            // 更新最后处理的内容
            lastProcessedContent = data.content;
            
            if (isFirstChunk) {
              // 第一次收到数据，添加AI消息
              aiMessageId = Date.now();
              setMessages(prev => [...prev, { 
                id: aiMessageId, 
                type: 'fox', 
                text: aiMessageText,
                isTyping: true // 显示正在输入状态
              }]);
              isFirstChunk = false;
            } else {
              // 更新现有消息
              setMessages(prev => prev.map(msg => {
                if (msg.id === aiMessageId) {
                  return { ...msg, text: aiMessageText, isTyping: true };
                }
                return msg;
              }));
            }
          }
          // 处理完整消息 - 直接显示全部内容
          else if (data.type === 'full_message' && data.content) {
            // 去重处理：如果当前内容和上一次相同，跳过
            if (data.content === lastProcessedContent) {
              return;
            }
            
            // 更新最后处理的内容
            lastProcessedContent = data.content;
            
            // 使用完整消息内容替换当前显示
            aiMessageText = data.content;
            
            if (isFirstChunk) {
              // 第一次收到数据，添加AI消息
              aiMessageId = Date.now();
              setMessages(prev => [...prev, { 
                id: aiMessageId, 
                type: 'fox', 
                text: aiMessageText,
                isTyping: false
              }]);
              isFirstChunk = false;
            } else {
              // 更新现有消息，直接显示完整内容
              setMessages(prev => prev.map(msg => {
                if (msg.id === aiMessageId) {
                  return { ...msg, text: aiMessageText, isTyping: false };
                }
                return msg;
              }));
            }
          }
          // 处理完成事件，确保消息显示完整
          else if (data.type === 'done') {
            if (aiMessageId) {
              // 确保最终消息状态正确
              setMessages(prev => prev.map(msg => {
                if (msg.id === aiMessageId) {
                  return { ...msg, isTyping: false };
                }
                return msg;
              }));
            }
          }
        } catch (e) {
          console.error('解析流式数据错误:', e, '原始数据:', dataStr);
        }
      }
    } catch (error) {
      console.error("发送失败:", error);
      // 移除临时用户消息
      setMessages(prev => prev.filter(msg => !msg.isTemp));
      // 添加错误消息
      setMessages(prev => [...prev, { id: Date.now(), type: 'fox', text: '消息发送失败了...' }]);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') handleSend();
  };

  return (
    <div className="kawaii-app-container" style={{ backgroundImage: `url(${bgChat})` }}>
      <header className="kawaii-header">
        <div className="header-left"><img src={foxhead} alt="狐狸头像" className="avatar-icon" /></div>
        <div className="header-title">消息狐 (Online)</div>
        <div className="header-right">
          <img src={btnCall} alt="call" className="icon-call" />
          
          {/* 这里绑定了点击事件，点击 + 号创建新对话 */}
          <span className="icon-more" onClick={createNewChat} style={{cursor: 'pointer'}}>+</span>
          
        </div>
      </header>

      <main className="kawaii-main">
        {/* 已删除 center-decoration 区域 */}
        
        <div className="message-list">
          {messages.map((msg) => (
            <div key={msg.id} className={`message-row ${msg.type === 'user' ? 'row-right' : 'row-left'}`} style={{alignItems: 'flex-start'}}>
              {msg.type === 'fox' && <div className="chat-avatar"><img src={foxhead} alt="狐狸头像" style={{width: '100%', height: '100%', objectFit: 'cover', borderRadius: '50%'}} /></div>}
              <div 
                className="bubble-container"
                style={{ 
                  backgroundImage: `url(${msg.type === 'user' ? bubbleUser : bubbleFox})`,
                  color: msg.type === 'user' ? '#8b5e3c' : '#a67c52' 
                }}
              >
                <p className="message-text">{msg.text}{msg.isTyping && <span className="typing-indicator">...</span>}</p>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
      </main>

      <footer className="kawaii-footer">
        <div className="input-wrapper" style={{ backgroundImage: `url(${inputBar})` }}>
          <input 
            type="text" 
            placeholder="快和我说说话..." 
            className="custom-input"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
          />
        </div>
        <div className="send-btn-wrapper" onClick={handleSend}>
            <img src={btnSend} alt="Send" />
        </div>
      </footer>
    </div>
  );
};

export default KawaiiChat;