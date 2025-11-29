import React, { useState, useEffect, useRef } from 'react';
import './KawaiiChat.css';

// 引入图片资源
import bgChat from '../../assets/KawaiiChat/bg_chat.jpg';
import bubbleFox from '../../assets/KawaiiChat/bubble_fox.png';
import bubbleUser from '../../assets/KawaiiChat/bubble_user.png';
import inputBar from '../../assets/KawaiiChat/input_bar.png';
import btnSend from '../../assets/KawaiiChat/btn_send.png';
import btnCall from '../../assets/KawaiiChat/btn_call.png';
// stickerFox 引用可以删掉了，因为下面不用了
// import stickerFox from '../../assets/KawaiiChat/sticker_fox.jpg';

const KawaiiChat = () => {
  // 1. 状态管理
  const [messages, setMessages] = useState([]); 
  const [inputValue, setInputValue] = useState('');
  const [threadId, setThreadId] = useState(null);
  
  const messagesEndRef = useRef(null);
  const wsRef = useRef(null);

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ==========================================
  // [辅助函数] 连接 WebSocket
  // ==========================================
  const connectWebSocket = (tid) => {
    // 如果有旧连接，先关闭
    if (wsRef.current) {
        wsRef.current.close();
    }

    const ws = new WebSocket(`ws://localhost:8000/ws/chat?thread_id=${tid}`);
    
    ws.onopen = () => console.log(`✅ WebSocket 已连接到会话: ${tid}`);
    
    ws.onmessage = (event) => {
      const response = JSON.parse(event.data);
      const msgData = response.message;

      // 收到后端推送的 AI 消息
      if (msgData.role === 'agent') {
        setMessages(prev => [...prev, {
          id: msgData.message_id,
          type: 'fox',
          text: msgData.text
        }]);
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
        const listRes = await fetch('http://localhost:8000/chat/threads');
        const threads = await listRes.json();

        if (threads.length > 0) {
          // 如果有旧会话，加载最新的
          const latestThread = threads[threads.length - 1];
          currentThreadId = latestThread.thread_id;
          console.log("📂 加载旧会话 ID:", currentThreadId);

          // 加载历史消息
          const historyRes = await fetch(`http://localhost:8000/chat/threads/${currentThreadId}/messages`);
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
        const createRes = await fetch('http://localhost:8000/chat/threads', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: "新的一天" })
        });
        const newThread = await createRes.json();
        const newId = newThread.thread_id;

        // 更新状态
        setThreadId(newId);
        // 清空旧消息，显示新的开场白
        setMessages([{ id: 'new-start', type: 'fox', text: '你好呀！这是一个全新的开始 🦊' }]);
        
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
    
    // 乐观更新
    const tempId = Date.now();
    setMessages(prev => [...prev, { id: tempId, type: 'user', text: textToSend }]);
    setInputValue('');

    try {
      await fetch(`http://localhost:8000/chat/threads/${threadId}/text-messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: textToSend })
      });
    } catch (error) {
      console.error("发送失败:", error);
      setMessages(prev => [...prev, { id: Date.now(), type: 'fox', text: '消息发送失败了...' }]);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') handleSend();
  };

  return (
    <div className="kawaii-app-container" style={{ backgroundImage: `url(${bgChat})` }}>
      <header className="kawaii-header">
        <div className="header-left"><span className="avatar-icon">🦊</span></div>
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
            <div key={msg.id} className={`message-row ${msg.type === 'user' ? 'row-right' : 'row-left'}`}>
              {msg.type === 'fox' && <div className="chat-avatar">🦊</div>}
              <div 
                className="bubble-container"
                style={{ 
                  backgroundImage: `url(${msg.type === 'user' ? bubbleUser : bubbleFox})`,
                  color: msg.type === 'user' ? '#8b5e3c' : '#a67c52' 
                }}
              >
                <p className="message-text">{msg.text}</p>
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