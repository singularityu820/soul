import PropTypes from "prop-types";
import EmotionDashboard from "../EmotionDashboard.jsx";

export default function EmotionPanel({ emotion, pipelineStatus }) {
  return (
    <aside className="emotion-panel">
      <header>
        <h2>情绪雷达</h2>
        <span className={`status status-${pipelineStatus}`}>{pipelineStatus}</span>
      </header>
      <EmotionDashboard emotion={emotion} />
    </aside>
  );
}

EmotionPanel.propTypes = {
  emotion: PropTypes.object,
  pipelineStatus: PropTypes.string,
};
