import PropTypes from "prop-types";

export default function MessageBubble({ message }) {
  const isAgent = message.role === "agent";
  const bubbleClass = `message-bubble ${isAgent ? "message-bubble--agent" : "message-bubble--user"}`;

  // 对于用户消息，显示username；对于AI消息，显示"小精灵"
  const displayName = isAgent ? "小精灵" : (message.username || "我");

  return (
    <div className={bubbleClass}>
      <div className="message-bubble__header">
        <span className="message-bubble__role">{displayName}</span>
        <time>
          {new Date(message.created_at).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </time>
      </div>
      <p>{message.text}</p>
      <div className="message-bubble__footer">
        {isAgent && (
          <>
            {message.emotion_label && (
              <span className="chip">
                情绪 {message.emotion_label}
                {typeof message.emotion_score === "number" && ` (${message.emotion_score.toFixed(2)})`}
              </span>
            )}
            {message.voice_style && <span className="chip">语气 {message.voice_style}</span>}
            {message.llm_provider && <span className="chip">LLM {message.llm_provider}</span>}
            {message.tts_provider && <span className="chip">TTS {message.tts_provider}</span>}
            {message.audio_reference && <span className="chip">音频就绪</span>}
          </>
        )}
      </div>
    </div>
  );
}

MessageBubble.propTypes = {
  message: PropTypes.shape({
    message_id: PropTypes.string.isRequired,
    role: PropTypes.oneOf(["user", "agent", "system"]).isRequired,
    text: PropTypes.string.isRequired,
    created_at: PropTypes.string.isRequired,
    username: PropTypes.string, // 添加username字段
    emotion_label: PropTypes.string,
    emotion_score: PropTypes.number,
    voice_style: PropTypes.string,
    llm_provider: PropTypes.string,
    tts_provider: PropTypes.string,
    audio_reference: PropTypes.string,
  }).isRequired,
};
