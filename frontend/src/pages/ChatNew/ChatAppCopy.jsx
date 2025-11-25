import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ChatWindow from "../../components/chat/ChatWindow.jsx";
import { resolveApiBaseUrl, resolveWebSocketUrl } from "../../utils/endpointResolver";
import { safelyCloseWebSocket } from "../../utils/websocketHelpers";
import Cookies from 'js-cookie';

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

export default function ChatAppCopy() {
  const [pipelineEvent, setPipelineEvent] = useState(null);
  const [threads, setThreads] = useState([]);
  const [chatStatus, setChatStatus] = useState("idle");
  const [activeThreadId, setActiveThreadId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [messagesLoading, setMessagesLoading] = useState(false);

  const pipelineSocketRef = useRef(null);
  const pipelineReconnectTimerRef = useRef(null);
  const chatSocketRef = useRef(null);
  const messageIdsRef = useRef(new Set());

  const activeThread = useMemo(
    () => threads.find((thread) => thread.thread_id === activeThreadId) || null,
    [threads, activeThreadId]
  );

  const fetchEEGWaveform = useCallback(async (emotion) => {
    if (!emotion) return;

    try {
      const response = await fetch(`${API_PREFIX}/eeg/face-waveform/${emotion}`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
      });

      if (!response.ok) return;

      const waveformData = await response.json();

      setPipelineEvent((prev) => ({
        ...prev,
        eeg_waveform: {
          waveform: waveformData,
          emotion,
        },
      }));
    } catch (error) {
      console.error("Error fetching EEG waveform:", error);
    }
  }, []);

  const handleEmotionUpdate = useCallback(
    (emotionData) => {
      if (!emotionData) return;

      if (emotionData.type === "eeg_waveform") {
        setPipelineEvent((prev) => ({
          ...prev,
          eeg_waveform: {
            waveform: emotionData.waveform,
            emotion: emotionData.emotion,
          },
        }));
        return;
      }

      if (emotionData.type === "face_emotion") {
        const currentEmotion = emotionData.emotion || emotionData.label;

        setPipelineEvent((prev) => ({
          ...prev,
          face_emotion: {
            label: currentEmotion,
            confidence: emotionData.confidence,
            face_position: emotionData.face_position,
          },
          emotion: currentEmotion,
        }));

        fetchEEGWaveform(currentEmotion);
      }
    },
    [fetchEEGWaveform]
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

        if (!created.ok) return;

        const thread = await created.json();
        setThreads([thread]);
        setActiveThreadId(thread.thread_id);
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
    let shouldReconnect = true;

    const connect = () => {
      const url = resolveWebSocketUrl("/ws/pipeline", PIPELINE_WS_OPTIONS);
      const socket = new WebSocket(url);
      pipelineSocketRef.current = socket;

      socket.onmessage = (message) => {
        try {
          const payload = JSON.parse(message.data);
          setPipelineEvent(payload);
        } catch (error) {
          console.error("Failed to parse pipeline event", error);
        }
      };

      socket.onerror = (error) => {
        console.error("Pipeline socket error", error);
      };

      socket.onclose = () => {
        pipelineSocketRef.current = null;
        if (!shouldReconnect) return;
        pipelineReconnectTimerRef.current = window.setTimeout(connect, 2000);
      };
    };

    connect();

    return () => {
      shouldReconnect = false;
      if (pipelineReconnectTimerRef.current) {
        clearTimeout(pipelineReconnectTimerRef.current);
        pipelineReconnectTimerRef.current = null;
      }
      safelyCloseWebSocket(pipelineSocketRef.current, "ChatAppCopy pipeline cleanup");
      pipelineSocketRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!activeThreadId) return;

    setMessages([]);
    messageIdsRef.current = new Set();
    setMessagesLoading(true);

    const url = resolveWebSocketUrl(`/ws/chat?thread_id=${activeThreadId}`, CHAT_WS_OPTIONS);
    const socket = new WebSocket(url);
    chatSocketRef.current = socket;

    socket.onopen = () => setChatStatus("connecting");
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
        setMessages((prev) =>
          [...prev, message].sort(
            (a, b) => new Date(a.created_at) - new Date(b.created_at)
          )
        );
      } catch (error) {
        console.error("Failed to parse chat event", error);
      } finally {
        setMessagesLoading(false);
        setChatStatus("connected");
      }
    };

    return () => {
      safelyCloseWebSocket(chatSocketRef.current, "ChatAppCopy chat cleanup");
      chatSocketRef.current = null;
    };
  }, [activeThreadId]);

  const handleSendMessage = useCallback(
    async (text) => {
      // 全模态实时通话为主：不再写入旧的 chat threads API，避免 404
      if (!activeThreadId) return;
      console.debug('[ChatAppCopy] sendMessage skipped (all-modal realtime mode):', text.slice(0,80));
    },
    [activeThreadId]
  );

  if (!activeThread) {
    return <div className="chat-window__placeholder">正在初始化会话...</div>;
  }

  return (
    <ChatWindow
      thread={activeThread}
      messages={messages}
      loading={messagesLoading && chatStatus === "connecting"}
      onSend={handleSendMessage}
      emotionData={pipelineEvent?.face_emotion}
      onEmotionUpdate={handleEmotionUpdate}
    />
  );
}

