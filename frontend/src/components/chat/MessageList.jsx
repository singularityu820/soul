import { useEffect, useRef } from "react";
import PropTypes from "prop-types";
import MessageBubble from "./MessageBubble.jsx";

export default function MessageList({ messages, loading }) {
  const listRef = useRef(null);

  useEffect(() => {
    if (!listRef.current) return;
    listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages]);

  return (
    <div className="message-list" ref={listRef}>
      {loading && <div className="message-list__placeholder">正在加载历史消息…</div>}
      {messages.map((message) => (
        <MessageBubble key={message.message_id} message={message} />
      ))}
      {!loading && messages.length === 0 && (
        <div className="message-list__placeholder">和小精灵打个招呼吧 👋</div>
      )}
    </div>
  );
}

MessageList.propTypes = {
  messages: PropTypes.arrayOf(PropTypes.object).isRequired,
  loading: PropTypes.bool,
};
