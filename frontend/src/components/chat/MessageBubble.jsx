import PropTypes from "prop-types";

export default function MessageBubble({ message }) {
  const isAgent = message.role === "agent";
  const bubbleClass = `message-bubble ${isAgent ? "message-bubble--agent" : "message-bubble--user"}`;

  return (
    <div className={bubbleClass}>
      <div className="message-bubble__header">
        <span className="message-bubble__role">{isAgent ? "小精灵" : "我"}</span>
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
    emotion_label: PropTypes.string,
    emotion_score: PropTypes.number,
    voice_style: PropTypes.string,
    llm_provider: PropTypes.string,
    tts_provider: PropTypes.string,
    audio_reference: PropTypes.string,
  }).isRequired,
};
