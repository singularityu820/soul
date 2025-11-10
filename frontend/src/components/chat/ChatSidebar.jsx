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

export default function ChatSidebar({ threads, activeThreadId, onSelectThread, onCreateThread, onDeleteThread }) {
  const handleDeleteThread = async (e, threadId) => {
    e.stopPropagation(); // 防止触发选择会话事件
    
    if (!window.confirm("确定要删除这个会话吗？")) {
      return;
    }
    
    // 调用父组件的删除函数
    if (onDeleteThread) {
      onDeleteThread(threadId);
    }
  };

  return (
    <aside className="chat-sidebar">
      <div className="chat-sidebar__header">
        <h2>会话</h2>
        <button type="button" onClick={onCreateThread} className="ghost-btn">
          新建
        </button>
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
                <button 
                  className="thread-item__delete"
                  onClick={(e) => handleDeleteThread(e, thread.thread_id)}
                  title="删除会话"
                >
                  ✕
                </button>
              </div>
            </li>
          );
        })}
        {threads.length === 0 && <li className="thread-empty">暂无会话，点击"新建"。</li>}
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
  onDeleteThread: PropTypes.func,
};
