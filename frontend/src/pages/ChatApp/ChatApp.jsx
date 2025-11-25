import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import AvatarCanvas from "../../components/AvatarCanvas.jsx";
import AudioRecordButton from "../../components/AudioRecordButton.jsx";
import ChatSidebar from "../../components/chat/ChatSidebar.jsx";
import ChatWindow from "../../components/chat/ChatWindow.jsx";
import EmotionPanel from "../../components/chat/EmotionPanel.jsx";
import "./styles/index.css";
import { resolveApiBaseUrl, resolveWebSocketUrl } from "../../utils/endpointResolver";
import { getRecentMessages } from "../../utils/api.js";

const API_PREFIX = resolveApiBaseUrl();
const PIPELINE_WS_OPTIONS = {
  envVar: "VITE_PIPELINE_WS_URL",
  windowKeys: [
    "pipelineWsUrl",
    "pipelineWSUrl",
    "pipelineWebsocketUrl",
    "pipelineSocketUrl",
    "pipelineStreamUrl",
  ],
};
const CHAT_WS_OPTIONS = {
  envVar: "VITE_CHAT_WS_URL",
  windowKeys: ["chatWsUrl", "chatSocketUrl", "chatWebsocketUrl"],
};

export default function ChatApp() {
  const [pipelineStatus, setPipelineStatus] = useState("connecting");
  const [pipelineEvent, setPipelineEvent] = useState(null);
  const [threads, setThreads] = useState([]);
  const [chatStatus, setChatStatus] = useState("idle");
  const [activeThreadId, setActiveThreadId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [recentMessages, setRecentMessages] = useState([]);

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
      const response = await fetch(`${API_PREFIX}/chat/threads`, {
        credentials: 'include', // 包含cookies
      });
      if (!response.ok) throw new Error("failed to fetch threads");
      const data = await response.json();
      if (data.length === 0) {
        const created = await fetch(`${API_PREFIX}/chat/threads`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title: "随心对话", participants: ["me", "agent"] }),
          credentials: 'include', // 包含cookies
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

  // 获取历史消息
  const fetchRecentMessages = useCallback(async () => {
    try {
      const messages = await getRecentMessages();
      setRecentMessages(messages);
      console.log("获取到的历史消息:", messages);
    } catch (error) {
      console.error("获取历史消息失败:", error);
      setRecentMessages([]);
    }
  }, []);

  useEffect(() => {
    refreshThreads();
    fetchRecentMessages(); // 获取历史消息
  }, [refreshThreads, fetchRecentMessages]);

  useEffect(() => {
    const url = resolveWebSocketUrl("/ws/pipeline", PIPELINE_WS_OPTIONS);
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

    const url = resolveWebSocketUrl(`/ws/chat?thread_id=${activeThreadId}`, CHAT_WS_OPTIONS);
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
      // 已迁移到全模态实时通话：不再将用户实时消息写入旧的 chat threads API。
      // 此处保留为 no-op，以避免向后端发送 POST 导致 404 日志。
      if (!activeThreadId) return;
      console.debug('[ChatApp] sendMessage skipped (all-modal realtime mode):', text.slice(0, 80));
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
        credentials: 'include', // 包含cookies
      });
      if (!response.ok) throw new Error("create thread failed");
      const thread = await response.json();
      setThreads((prev) => [thread, ...prev]);
      setActiveThreadId(thread.thread_id);
    } catch (error) {
      console.error("Failed to create chat thread", error);
    }
  }, [threads.length]);

  const handleDeleteThread = useCallback(
    async (threadId) => {
      try {
        // 发送DELETE请求到后端
        const response = await fetch(`${API_PREFIX}/chat/threads/${threadId}`, {
          method: "DELETE",
          credentials: 'include', // 包含cookies
        });

        if (!response.ok) {
          throw new Error("删除会话失败");
        }

        // 从状态中移除已删除的会话
        setThreads((prev) => prev.filter((thread) => thread.thread_id !== threadId));

        // 如果删除的是当前活跃会话，则选择第一个会话或清空选择
        if (threadId === activeThreadId) {
          const remainingThreads = threads.filter(t => t.thread_id !== threadId);
          if (remainingThreads.length > 0) {
            setActiveThreadId(remainingThreads[0].thread_id);
          } else {
            // 如果没有会话了，创建一个新会话
            handleCreateThread();
          }
        }
      } catch (error) {
        console.error("Failed to delete thread:", error);
        alert("删除会话失败，请重试");
      }
    },
    [activeThreadId, threads, handleCreateThread]
  );

  // 处理情绪检测结果
  const handleEmotionUpdate = useCallback((emotionData) => {
    // 更新当前情绪状态
    if (emotionData.type === 'eeg_waveform') {
      // 处理脑电波形数据
      setPipelineEvent(prev => ({
        ...prev,
        eeg_waveform: {
          waveform: emotionData.waveform,
          emotion: emotionData.emotion
        }
      }));
    } else if (emotionData.type === 'face_emotion') {
      // 处理面部情绪数据
      setPipelineEvent(prev => ({
        ...prev,
        face_emotion: {
          label: emotionData.emotion || emotionData.label,
          confidence: emotionData.confidence,
          face_position: emotionData.face_position
        }
      }));

      // 同时更新emotion状态，确保情绪雷达能接收到数据
      setPipelineEvent(prev => ({
        ...prev,
        emotion: emotionData.emotion || emotionData.label
      }));

      // 当检测到面部情绪时，获取对应的脑电波形数据
      // 这样可以确保脑电波形数据只在需要时获取，而不是每3秒获取一次
      fetchEEGWaveform(emotionData.emotion || emotionData.label);
    }
  }, []);

  // 获取情绪对应的脑电波形数据
  const fetchEEGWaveform = useCallback(async (emotion) => {
    if (!emotion) return;

    try {
      const response = await fetch(`${API_PREFIX}/eeg/face-waveform/${emotion}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const waveformData = await response.json();
        console.log('EEG waveform data:', waveformData);

        // 更新脑电波形数据
        setPipelineEvent(prev => ({
          ...prev,
          eeg_waveform: {
            waveform: waveformData,
            emotion: emotion
          }
        }));
      }
    } catch (error) {
      console.error('Error fetching EEG waveform:', error);
    }
  }, []);

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
          onDeleteThread={handleDeleteThread}
        />
        <ChatWindow
          thread={activeThread}
          messages={messages}
          recentMessages={recentMessages}
          loading={messagesLoading && chatStatus === "connecting"}
          onSend={handleSendMessage}
          emotionData={pipelineEvent?.face_emotion}
          onEmotionUpdate={handleEmotionUpdate}
        />
        <EmotionPanel
          emotion={pipelineEvent?.face_emotion ? {
            label: pipelineEvent.face_emotion.label || 'neutral',
            confidence: pipelineEvent.face_emotion.confidence || 0.5,
            mood_score: pipelineEvent.face_emotion.confidence || 0.5,
            components: [{
              source: 'face',
              label: pipelineEvent.face_emotion.label || 'neutral',
              confidence: pipelineEvent.face_emotion.confidence || 0.5,
              mood_score: pipelineEvent.face_emotion.confidence || 0.5
            }]
          } : null}
          pipelineStatus={pipelineStatus}
          faceEmotion={pipelineEvent?.face_emotion}
          eegWaveform={pipelineEvent?.eeg_waveform}
        />
      </main>

      {/* 实时语音按钮 (WebSocket 管道) */}
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
    </div>
  );
}
