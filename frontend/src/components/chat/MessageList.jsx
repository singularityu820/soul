import { useEffect, useRef } from "react";
import PropTypes from "prop-types";
import MessageBubble from "./MessageBubble.jsx";
import "./MessageList.css";

export default function MessageList({ messages, recentMessages, loading }) {
  const listRef = useRef(null);

  useEffect(() => {
    if (!listRef.current) return;
    listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages, recentMessages]);

  // 确保 messages 和 recentMessages 是数组，即使它们是 undefined
  const safeMessages = Array.isArray(messages) ? messages : [];
  const safeRecentMessages = Array.isArray(recentMessages) ? recentMessages : [];

  return (
    <div className="message-list" ref={listRef}>
      {/* 显示历史消息 */}
      {safeRecentMessages.length > 0 && (
        <>
          <div className="message-list__section-title">历史消息</div>
          {safeRecentMessages.map((message) => (
            <MessageBubble key={`recent-${message.message_id}`} message={message} />
          ))}
        </>
      )}
      
      {/* 显示当前会话消息 */}
      {safeMessages.length > 0 && (
        <>
          {safeRecentMessages.length > 0 && (
            <div className="message-list__section-title">当前会话</div>
          )}
          {safeMessages.map((message) => (
            <MessageBubble key={message.message_id} message={message} />
          ))}
        </>
      )}
      
      {loading && <div className="message-list__placeholder">正在加载历史消息…</div>}
      {!loading && safeMessages.length === 0 && safeRecentMessages.length === 0 && (
        <div className="message-list__placeholder">和小精灵打个招呼吧 👋</div>
      )}
    </div>
  );
}

MessageList.propTypes = {
  messages: PropTypes.arrayOf(PropTypes.object),
  recentMessages: PropTypes.arrayOf(PropTypes.object),
  loading: PropTypes.bool,
};
