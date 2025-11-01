import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import AvatarCanvas from "./components/AvatarCanvas.jsx";
import AudioRecordButton from "./components/AudioRecordButton.jsx";
import ChatSidebar from "./components/chat/ChatSidebar.jsx";
import ChatWindow from "./components/chat/ChatWindow.jsx";
import EmotionPanel from "./components/chat/EmotionPanel.jsx";
import { useWebRTC } from "./hooks/useWebRTC.js";

const API_PREFIX = "/api";

const makeWsUrl = (path) => {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  // 使用后端的 WebSocket 地址
  const host = window.location.hostname;
  const port = 8000;  // 后端端口
  return `${protocol}://${host}:${port}${path}`;
};

export default function App() {
  const [pipelineStatus, setPipelineStatus] = useState("connecting");
  const [pipelineEvent, setPipelineEvent] = useState(null);
  const [threads, setThreads] = useState([]);
  const [chatStatus, setChatStatus] = useState("idle");
  const [activeThreadId, setActiveThreadId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [callStatus, setCallStatus] = useState(null);
  const [activeCallRoomId, setActiveCallRoomId] = useState(null);

  const chatSocketRef = useRef(null);
  const messageIdsRef = useRef(new Set());
  const remoteAudioRef = useRef(null);

  // WebRTC hook
  const {
    startCall,
    stopCall,
    connectionState,
    isConnecting,
    remoteAudioRef: webrtcAudioRef,
  } = useWebRTC(
    activeCallRoomId,
    (remoteStream) => {
      console.log("Remote audio stream received", remoteStream);
      if (remoteAudioRef.current) {
        remoteAudioRef.current.srcObject = remoteStream;
      }
    },
    (error) => {
      console.error("WebRTC error:", error);
      setCallStatus({ mode: callStatus?.mode, message: `连接失败: ${error.message}` });
    }
  );

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

      // 如果已有通话，先停止
      if (activeCallRoomId) {
        stopCall();
        setActiveCallRoomId(null);
        setCallStatus(null);
        return;
      }

      // 启动新通话
      setActiveCallRoomId(roomId);
      setCallStatus({ mode, message: "正在建立连接…" });

      try {
        await startCall({ roomId, mode });
        setCallStatus({ mode, message: "通话已建立" });
      } catch (error) {
        console.error("Failed to start call", error);
        setCallStatus({ mode, message: "连接失败，请重试" });
        setActiveCallRoomId(null);
      }
    },
    [activeThreadId, activeCallRoomId, startCall, stopCall]
  );

  // 监听连接状态变化
  useEffect(() => {
    if (connectionState === "connected") {
      setCallStatus((prev) => prev ? { ...prev, message: "通话中" } : null);
    } else if (connectionState === "failed") {
      setCallStatus((prev) => prev ? { ...prev, message: "连接失败" } : null);
      setActiveCallRoomId(null);
    } else if (connectionState === "closed") {
      setCallStatus(null);
      setActiveCallRoomId(null);
    }
  }, [connectionState]);

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
        <ChatSidebar
          threads={threads}
          activeThreadId={activeThreadId}
          onSelectThread={setActiveThreadId}
          onCreateThread={handleCreateThread}
        />
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
      
      {/* HTTP 音频录制按钮 (WebRTC 替代方案) */}
      <div style={{ 
        borderTop: '1px solid rgba(80, 120, 160, 0.25)', 
        background: 'rgba(8, 25, 41, 0.5)',
        padding: '1rem 0'
      }}>
        <AudioRecordButton 
          threadId={activeThreadId}
          onResponse={(result) => {
            console.log("Audio response received:", result);
            // 可以在这里触发界面更新
          }}
          disabled={!activeThreadId}
        />
      </div>
      
      {/* 隐藏的音频元素用于播放远端音频 */}
      <audio ref={remoteAudioRef} autoPlay style={{ display: "none" }} />
      {/* 将 webrtcAudioRef 传递给底层 hook */}
      <audio ref={webrtcAudioRef} autoPlay style={{ display: "none" }} />
    </div>
  );
}
