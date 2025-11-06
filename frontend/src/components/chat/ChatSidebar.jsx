import PropTypes from "prop-types";

function formatTimestamp(isoString) {
  if (!isoString) return "刚刚";
  try {
    return new Intl.DateTimeFormat("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(isoString));
  } catch (error) {
    return "刚刚";
  }
}

export default function ChatSidebar({ threads, activeThreadId, onSelectThread, onCreateThread }) {
  return (
    <aside className="chat-sidebar">
      <div className="chat-sidebar__header">
        <h2>主会话</h2>
      </div>
      <ul className="thread-list">
        {threads.map((thread) => {
          const isActive = thread.thread_id === activeThreadId;
          return (
            <li
              key={thread.thread_id}
              className={`thread-item ${isActive ? "thread-item--active" : ""}`}
              onClick={() => onSelectThread(thread.thread_id)}
            >
              <div className="thread-item__title">{thread.title}</div>
              <div className="thread-item__meta">
                <span>{thread.participants?.join(" · ") || "单人"}</span>
                <time>{formatTimestamp(thread.last_message_at)}</time>
              </div>
            </li>
          );
        })}
        {threads.length === 0 && <li className="thread-empty">正在加载会话...</li>}
      </ul>
    </aside>
  );
}

ChatSidebar.propTypes = {
  threads: PropTypes.arrayOf(
    PropTypes.shape({
      thread_id: PropTypes.string.isRequired,
      title: PropTypes.string.isRequired,
      participants: PropTypes.arrayOf(PropTypes.string),
      last_message_at: PropTypes.string,
    })
  ).isRequired,
  activeThreadId: PropTypes.string,
  onSelectThread: PropTypes.func.isRequired,
  onCreateThread: PropTypes.func.isRequired,
};
