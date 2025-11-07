import PropTypes from "prop-types";

export default function CallControls({ status, onAction }) {
  const buttons = [
    { id: "video", label: "视频通话", icon: "📹" },
    { id: "voice", label: "语音通话", icon: "🎧" },
    { id: "share", label: "屏幕共享", icon: "🖥" },
  ];

  return (
    <div className="call-controls">
      {buttons.map((button) => (
        <button
          key={button.id}
          type="button"
          className={`call-btn ${status?.mode === button.id ? "call-btn--active" : ""}`}
          onClick={() => onAction(button.id)}
        >
          <span aria-hidden="true">{button.icon}</span>
          {button.label}
        </button>
      ))}
      {status && status.message && <span className="call-status">{status.message}</span>}
    </div>
  );
}

CallControls.propTypes = {
  status: PropTypes.shape({
    mode: PropTypes.string,
    message: PropTypes.string,
  }),
  onAction: PropTypes.func.isRequired,
};
