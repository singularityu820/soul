import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import AvatarCanvas from "../../components/AvatarCanvas.jsx";
import ChatSidebar from "../../components/chat/ChatSidebar.jsx";
import ChatWindow from "../../components/chat/ChatWindow.jsx";
import EmotionPanel from "../../components/chat/EmotionPanel.jsx";
import "./styles/index.css";

const API_PREFIX = "/api";

const makeWsUrl = (path) => {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const { host } = window.location;
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
  const [callStatus, setCallStatus] = useState(null);

  const chatSocketRef = useRef(null);
  const messageIdsRef = useRef(new Set());

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
    const url = makeWsUrl("/ws/pipeline");
    const socket = new WebSocket(url);

    socket.onopen = () => setPipelineStatus("connected");
    socket.onclose = () => setPipelineStatus("disconnected");
    socket.onerror = () => setPipelineStatus("error");
    socket.onmessage = (message) => {
      try {
        const payload = JSON.parse(message.data);
        setPipelineEvent(payload);
      } catch (error) {
        console.error("Failed to parse pipeline event", error);
      }
    };

    return () => socket.close();
  }, []);

  useEffect(() => {
    if (!activeThreadId) return;

    setMessages([]);
    messageIdsRef.current = new Set();
    setMessagesLoading(true);

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
        if (messageIdsRef.current.has(message.message_id)) return;
        messageIdsRef.current.add(message.message_id);
        setMessages((prev) => [...prev, message].sort((a, b) => new Date(a.created_at) - new Date(b.created_at)));
      } catch (error) {
        console.error("Failed to parse chat event", error);
      } finally {
        setMessagesLoading(false);
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

  const handleCallAction = useCallback(
    async (mode) => {
      if (!activeThreadId) {
        setCallStatus({ mode, message: "请选择会话后再发起通话" });
        return;
      }
      const roomId = `${activeThreadId}-${mode}`;
      setCallStatus({ mode, message: "正在建立信令连接…" });
      try {
        await fetch(`${API_PREFIX}/webrtc/${roomId}/offer`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            sdp: `${mode}-placeholder-${Date.now()}`,
            metadata: { initiator: "user" },
          }),
        });
        setCallStatus({ mode, message: "等待对端加入（占位模式）" });
      } catch (error) {
        console.error("Failed to publish WebRTC offer", error);
        setCallStatus({ mode, message: "信令未就绪，请稍后重试" });
      }
    },
    [activeThreadId]
  );

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
        {/* <ChatSidebar
          threads={threads}
          activeThreadId={activeThreadId}
          onSelectThread={setActiveThreadId}
          onCreateThread={handleCreateThread}
        /> */}
        <ChatWindow
          thread={activeThread}
          messages={messages}
          loading={messagesLoading && chatStatus === "connecting"}
          onSend={handleSendMessage}
          callStatus={callStatus}
          onCallAction={handleCallAction}
        />
        <EmotionPanel emotion={emotion} pipelineStatus={pipelineStatus} />
      </main>
    </div>
  );
}


