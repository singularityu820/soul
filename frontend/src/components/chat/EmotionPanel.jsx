import PropTypes from "prop-types";
import EmotionDashboard from "../EmotionDashboard.jsx";

export default function EmotionPanel({ emotion, pipelineStatus, faceEmotion, eegWaveform }) {
  return (
    <aside className="emotion-panel">
      <header>
        <h2>情绪雷达</h2>
        <span className={`status status-${pipelineStatus}`}>{pipelineStatus}</span>
      </header>
      <EmotionDashboard emotion={emotion} faceEmotion={faceEmotion} eegWaveform={eegWaveform} />
    </aside>
  );
}

EmotionPanel.propTypes = {
  emotion: PropTypes.object,
  pipelineStatus: PropTypes.string,
  faceEmotion: PropTypes.shape({
    label: PropTypes.string,
    confidence: PropTypes.number,
    face_position: PropTypes.arrayOf(
      PropTypes.shape({
        x: PropTypes.number,
        y: PropTypes.number,
        width: PropTypes.number,
        height: PropTypes.number
      })
    )
  }),
  eegWaveform: PropTypes.shape({
    waveform: PropTypes.shape({
      channels: PropTypes.objectOf(PropTypes.arrayOf(PropTypes.number)),
    }),
    emotion: PropTypes.string
  })
};
