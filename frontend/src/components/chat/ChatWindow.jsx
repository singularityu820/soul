import PropTypes from "prop-types";
import MessageList from "./MessageList.jsx";
import MessageComposer from "./MessageComposer.jsx";
import VoiceStreamButton from "../VoiceStreamButton.jsx";

export default function ChatWindow({
  thread,
  threadId,
  messages,
  loading,
  onSend,
}) {
  if (!thread) {
    return <div className="chat-window__placeholder">请选择或创建一个会话。</div>;
  }

  return (
    <section className="chat-window">
      <header className="chat-window__header">
        <div>
          <h2>{thread.title}</h2>
          <span className="chat-window__participants">
            {thread.participants?.join(" · ") || "仅自己"}
          </span>
        </div>
        <VoiceStreamButton threadId={threadId} disabled={!thread} />
      </header>
      <MessageList messages={messages} loading={loading} />
      <MessageComposer onSend={onSend} disabled={!thread} />
    </section>
  );
}

ChatWindow.propTypes = {
  thread: PropTypes.shape({
    thread_id: PropTypes.string,
    title: PropTypes.string,
    participants: PropTypes.arrayOf(PropTypes.string),
  }),
  threadId: PropTypes.string,
  messages: PropTypes.arrayOf(PropTypes.object).isRequired,
  loading: PropTypes.bool,
  onSend: PropTypes.func.isRequired,
};
