import React, { useState, useEffect, useRef } from 'react';
import './TestWebSocket.css';

const TestWebSocket = () => {
  const [status, setStatus] = useState('disconnected');
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [threadId, setThreadId] = useState('');
  const [logs, setLogs] = useState([]);
  const [language, setLanguage] = useState('zh');
  const socketRef = useRef(null);
  const messagesEndRef = useRef(null);

  const API_BASE = '';

  // 滚动到消息底部
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const addLog = (message) => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs(prev => [...prev, `[${timestamp}] ${message}`]);
    console.log(`[${timestamp}] ${message}`);
  };

  const showNotification = (message, type = 'info') => {
    addLog(`${type.toUpperCase()}: ${message}`);
  };

  const updateConnectionStatus = (connected) => {
    if (connected) {
      setStatus('connected');
      addLog('WebSocket connected');
    } else {
      setStatus('disconnected');
      addLog('WebSocket disconnected');
    }
  };

  const addMessage = (role, text, messageId = null, timestamp = null) => {
    const message = {
      role,
      text,
      messageId,
      timestamp: timestamp || new Date().toISOString()
    };
    setMessages(prev => [...prev, message]);
  };

  // 创建新会话
  const createNewThread = async () => {
    try {
      updateConnectionStatus(false);
      showNotification('正在创建新会话...', 'info');
      
      const response = await fetch(`${API_BASE}/chat/threads`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          title: 'WebSocket测试聊天',
          participants: ['user', 'agent']
        })
      });
      
      if (!response.ok) {
        throw new Error(`创建会话失败: ${response.status}`);
      }
      
      const thread = await response.json();
      const newThreadId = thread.thread_id;
      setThreadId(newThreadId);
      
      showNotification('新会话创建成功', 'success');
      
      // 清空消息
      setMessages([]);
      addMessage('agent', '新会话已创建，请输入您的消息开始对话。');
      
      // 连接WebSocket
      connectWebSocket(newThreadId);
    } catch (error) {
      console.error('创建会话错误:', error);
      showNotification(`创建会话失败: ${error.message}`, 'error');
      updateConnectionStatus(false);
    }
  };

  // 连接WebSocket
  const connectWebSocket = (id) => {
    if (!id) {
      console.error('无法连接WebSocket：缺少thread_id');
      return;
    }
    
    if (socketRef.current) {
      socketRef.current.close();
    }
    
    setStatus('connecting');
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/chat?thread_id=${id}`;
    addLog(`正在连接WebSocket: ${wsUrl}`);
    
    const socket = new WebSocket(wsUrl);
    socketRef.current = socket;
    
    socket.onopen = () => {
      console.log('WebSocket连接已建立');
      updateConnectionStatus(true);
      showNotification('已连接到聊天服务', 'success');
    };
    
    socket.onmessage = (event) => {
      try {
        console.log('收到原始WebSocket消息:', event.data);
        const data = JSON.parse(event.data);
        console.log('解析后的WebSocket消息:', data);
        
        // 处理ChatEvent格式的消息
        if (data.type === 'message' && data.message) {
          const message = data.message;
          console.log('处理ChatEvent消息:', message);
          if (message.role === 'agent') {
            addMessage('agent', message.text, message.message_id, message.created_at);
          }
        }
        // 处理删除事件
        else if (data.type === 'deleted') {
          console.log('收到删除事件:', data.thread_id);
        }
        // 兼容其他可能的消息格式
        else if (data.message) {
          const message = data.message;
          console.log('处理其他格式消息:', message);
          if (message.role === 'agent') {
            addMessage('agent', message.text, message.message_id, message.created_at);
          }
        }
      } catch (error) {
        console.error('处理WebSocket消息错误:', error);
        console.error('原始消息数据:', event.data);
      }
    };
    
    socket.onclose = (event) => {
      console.log('WebSocket连接已关闭，代码:', event.code, '原因:', event.reason);
      updateConnectionStatus(false);
      showNotification('与聊天服务的连接已断开', 'error');
      
      // 5秒后尝试重连
      setTimeout(() => {
        if (threadId) {
          connectWebSocket(threadId);
        }
      }, 5000);
    };
    
    socket.onerror = (error) => {
      console.error('WebSocket错误:', error);
      updateConnectionStatus(false);
      showNotification('WebSocket连接错误', 'error');
    };
  };

  // 发送消息
  const sendMessage = async () => {
    const text = inputText.trim();
    if (!text || !threadId) return;
    
    // 添加用户消息到界面
    addMessage('user', text);
    setInputText('');
    
    try {
      const response = await fetch(`${API_BASE}/chat/threads/${threadId}/text-messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          text: text,
          language: language
        })
      });
      
      if (!response.ok) {
        throw new Error(`发送消息失败: ${response.status}`);
      }
      
      // AI回复将通过WebSocket接收，这里不需要处理
      showNotification('消息已发送', 'success');
    } catch (error) {
      console.error('发送消息错误:', error);
      showNotification(`发送消息失败: ${error.message}`, 'error');
      addMessage('agent', `错误: ${error.message}`);
    }
  };

  const disconnect = () => {
    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }
  };

  const clearMessages = () => {
    setMessages([]);
    addMessage('agent', '消息已清空，请输入您的消息开始对话。');
  };

  const navigateToTextChat = () => {
    window.location.hash = '#/textchat';
  };

  useEffect(() => {
    // 创建初始会话
    createNewThread();
    
    return () => {
      if (socketRef.current) {
        socketRef.current.close();
      }
    };
  }, []);

  const getStatusClass = () => {
    switch (status) {
      case 'connected': return 'connected';
      case 'connecting': return 'connecting';
      default: return 'disconnected';
    }
  };

  const getStatusText = () => {
    switch (status) {
      case 'connected': return '已连接';
      case 'connecting': return '连接中...';
      default: return '未连接';
    }
  };

  return (
    <div className="test-websocket-container">
      <div className="test-header">
        <h1>WebSocket Connection Test</h1>
        <button onClick={navigateToTextChat} className="back-button">
          Back to Text Chat
        </button>
      </div>
      
      <div className="test-content">
        <div className="chat-panel">
          <div className="chat-header">
            <h2>文本聊天</h2>
            <div className={`status ${getStatusClass()}`}>
              <span className="status-indicator"></span>
              <span>{getStatusText()}</span>
            </div>
          </div>
          
          <div className="chat-messages">
            {messages.map((msg, index) => (
              <div key={index} className={`message ${msg.role}`}>
                <div className="message-info">
                  {msg.role === 'user' ? '用户' : 'AI助手'}
                  {msg.timestamp && ` · ${new Date(msg.timestamp).toLocaleTimeString()}`}
                </div>
                <div>{msg.text}</div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
          
          <div className="chat-input">
            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder="输入消息..."
              disabled={status !== 'connected'}
              onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
            />
            <button
              onClick={sendMessage}
              disabled={status !== 'connected' || !inputText.trim()}
            >
              发送
            </button>
          </div>
        </div>
        
        <div className="settings-panel">
          <h3>设置</h3>
          <div>
            <label>会话ID:</label>
            <input type="text" value={threadId} readOnly />
          </div>
          <div>
            <label>语言:</label>
            <select value={language} onChange={(e) => setLanguage(e.target.value)}>
              <option value="zh">中文</option>
              <option value="en">English</option>
            </select>
          </div>
          <div className="button-group">
            <button onClick={createNewThread}>新建会话</button>
            <button onClick={clearMessages}>清空消息</button>
            <button onClick={disconnect} disabled={status === 'disconnected'}>
              断开连接
            </button>
          </div>
          
          <h3>连接日志</h3>
          <div className="logs">
            {logs.map((log, index) => (
              <div key={index} className="log-entry">{log}</div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default TestWebSocket;