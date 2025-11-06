import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import AvatarCanvas from "../../components/AvatarCanvas.jsx";
import ChatWindow from "../../components/chat/ChatWindow.jsx";
import EmotionPanel from "../../components/chat/EmotionPanel.jsx";
import "./styles/index.css";

const API_PREFIX = "/api";

const makeWsUrl = (path) => {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  // 开发环境直接连接到后端端口
  const host = import.meta.env.DEV ? "localhost:8000" : window.location.host;
  return `${protocol}://${host}${path}`;
};

export default function ChatApp() {
  const [pipelineStatus, setPipelineStatus] = useState("connecting");
  const [pipelineEvent, setPipelineEvent] = useState(null);
  const [threads, setThreads] = useState([]);
  const [chatStatus, setChatStatus] = useState("idle");
  const [activeThreadId, setActiveThreadId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [messagesLoading, setMessagesLoading] = useState(false);

  const chatSocketRef = useRef(null);
  const messageIdsRef = useRef(new Set());
  const pipelineSocketRef = useRef(null);
  const pipelineInitializedRef = useRef(false); // 跟踪是否已初始化

  const emotion = pipelineEvent?.emotion ?? null;
  const avatarPose = pipelineEvent?.avatar ?? null;

  const activeThread = useMemo(
    () => threads.find((thread) => thread.thread_id === activeThreadId) || null,
    [threads, activeThreadId]
  );

  const refreshThreads = useCallback(async () => {
    try {
      const response = await fetch(`${API_PREFIX}/chat/threads`);
      if (!response.ok) throw new Error("failed to fetch threads");
      const data = await response.json();
      if (data.length === 0) {
        const created = await fetch(`${API_PREFIX}/chat/threads`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title: "随心对话", participants: ["me", "agent"] }),
        });
        if (created.ok) {
          const thread = await created.json();
          setThreads([thread]);
          setActiveThreadId(thread.thread_id);
        }
        return;
      }
      setThreads(data);
      setActiveThreadId((prev) => prev ?? data[0]?.thread_id ?? null);
    } catch (error) {
      console.error("Failed to load chat threads", error);
    }
  }, []);

  useEffect(() => {
    refreshThreads();
  }, [refreshThreads]);

  useEffect(() => {
    console.log('🎯 [DEBUG] Pipeline useEffect triggered');
    console.log('🎯 [DEBUG] pipelineInitializedRef.current:', pipelineInitializedRef.current);
    console.log('🎯 [DEBUG] pipelineSocketRef.current:', pipelineSocketRef.current);
    
    // 避免 StrictMode 双重挂载导致的重复连接
    if (pipelineInitializedRef.current) {
      console.log('🔄 [SKIP] Pipeline WebSocket already initialized, skipping second mount');
      return () => {
        // 空的 cleanup - 不关闭 WebSocket，不重置 ref
        console.log('🔄 [SKIP-CLEANUP] Empty cleanup for second mount (doing nothing)');
      };
    }
    
    console.log('✨ [INIT] Setting pipelineInitializedRef to true (will persist across StrictMode remount)');
    pipelineInitializedRef.current = true;
    
    const url = makeWsUrl("/ws/pipeline");
    console.log('🔌 [CONNECT] Creating pipeline WebSocket:', url);
    const socket = new WebSocket(url);
    pipelineSocketRef.current = socket;
    console.log('🔌 [CONNECT] WebSocket created, readyState:', socket.readyState, '(0=CONNECTING)');

    socket.onopen = () => {
      console.log('✅ [OPEN] Pipeline WebSocket connected successfully');
      setPipelineStatus("connected");
    };
    socket.onclose = (event) => {
      console.log('❌ [CLOSE] Pipeline WebSocket closed - code:', event.code, 'reason:', event.reason, 'wasClean:', event.wasClean);
      setPipelineStatus("disconnected");
      pipelineSocketRef.current = null;
    };
    socket.onerror = (error) => {
      console.error('❌ [ERROR] Pipeline WebSocket error:', error);
      console.error('❌ [ERROR] Socket readyState:', socket.readyState, '(3=CLOSED, 2=CLOSING, 1=OPEN, 0=CONNECTING)');
      setPipelineStatus("error");
    };
    socket.onmessage = (message) => {
      try {
        const payload = JSON.parse(message.data);
        setPipelineEvent(payload);
      } catch (error) {
        console.error("Failed to parse pipeline event", error);
      }
    };

    return () => {
      // 这是 StrictMode 的测试卸载 - 不做任何清理
      // ref 保持 true，这样第二次挂载会跳过连接
      console.log('🧹 [CLEANUP-FIRST] First mount cleanup (StrictMode test unmount)');
      console.log('🧹 [CLEANUP-FIRST] Intentionally NOT closing WebSocket or resetting ref');
      console.log('🧹 [CLEANUP-FIRST] This allows the connection to complete and second mount to skip');
    };
  }, []);

  useEffect(() => {
    if (!activeThreadId) return;

    setMessages([]);
    messageIdsRef.current = new Set();
    setMessagesLoading(true);

    // 加载历史消息
    const loadHistory = async () => {
      try {
        const response = await fetch(`${API_PREFIX}/chat/threads/${activeThreadId}/messages?limit=100`);
        if (response.ok) {
          const history = await response.json();
          setMessages(history);
          history.forEach(msg => messageIdsRef.current.add(msg.message_id));
        }
      } catch (error) {
        console.error("Failed to load message history", error);
      } finally {
        setMessagesLoading(false);
      }
    };

    loadHistory();

    const url = makeWsUrl(`/ws/chat?thread_id=${activeThreadId}`);
    const socket = new WebSocket(url);
    chatSocketRef.current = socket;

    socket.onopen = () => setChatStatus("connected");
    socket.onclose = () => setChatStatus("disconnected");
    socket.onerror = () => setChatStatus("error");
    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type !== "message") return;
        const { message } = payload;
        if (message.thread_id !== activeThreadId) return;
        
        // 对于流式更新:如果消息 ID 已存在,则更新该消息而不是追加新消息
        setMessages((prev) => {
          const existingIndex = prev.findIndex(m => m.message_id === message.message_id);
          if (existingIndex !== -1) {
            // 更新现有消息（流式更新）
            const updated = [...prev];
            updated[existingIndex] = message;
            return updated;
          } else {
            // 添加新消息
            if (messageIdsRef.current.has(message.message_id)) return prev;
            messageIdsRef.current.add(message.message_id);
            return [...prev, message].sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
          }
        });
      } catch (error) {
        console.error("Failed to parse chat event", error);
      }
    };

    return () => {
      socket.close();
      chatSocketRef.current = null;
    };
  }, [activeThreadId]);

  const handleSendMessage = useCallback(
    async (text) => {
      if (!activeThreadId) return;
      try {
        await fetch(`${API_PREFIX}/chat/threads/${activeThreadId}/messages`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text }),
        });
      } catch (error) {
        console.error("Failed to send chat message", error);
      }
    },
    [activeThreadId]
  );

  const handleCreateThread = useCallback(async () => {
    try {
      const response = await fetch(`${API_PREFIX}/chat/threads`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: `会话 ${threads.length + 1}`,
          participants: ["me", "agent"],
        }),
      });
      if (!response.ok) throw new Error("create thread failed");
      const thread = await response.json();
      setThreads((prev) => [thread, ...prev]);
      setActiveThreadId(thread.thread_id);
    } catch (error) {
      console.error("Failed to create chat thread", error);
    }
  }, [threads.length]);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-brand">
          <h1>灵伴 · Soulmate</h1>
          <span className="brand-subtitle">情绪共鸣的全天候聊天伙伴</span>
        </div>
        <div className="avatar-status">
          <span>表情矩阵</span>
          <AvatarCanvas pose={avatarPose} />
        </div>
      </header>
      <main className="messenger-layout">
        <ChatWindow
          thread={activeThread}
          threadId={activeThreadId}
          messages={messages}
          loading={messagesLoading && chatStatus === "connecting"}
          onSend={handleSendMessage}
        />
        <EmotionPanel emotion={emotion} pipelineStatus={pipelineStatus} />
      </main>
    </div>
  );
}


