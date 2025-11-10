import PropTypes from "prop-types";
import { useState } from "react";

export default function MessageComposer({ onSend, disabled }) {
  const [draft, setDraft] = useState("");

  const handleSend = () => {
    if (!draft.trim()) return;
    onSend(draft.trim());
    setDraft("");
  };

  const handleKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="message-composer">
      <textarea
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="输入消息，按 Enter 发送，Shift+Enter 换行"
        disabled={disabled}
      />
      <button type="button" onClick={handleSend} disabled={disabled}>
        发送
      </button>
    </div>
  );
}

MessageComposer.propTypes = {
  onSend: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
};
