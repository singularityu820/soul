import PropTypes from "prop-types";

function WaveformChart({ waveform }) {
  if (!waveform) {
    return <div className="waveform-placeholder">EEG 模拟信号加载中…</div>;
  }

  const channels = Object.entries(waveform.channels ?? {});
  if (!channels.length) {
    return <div className="waveform-placeholder">暂无波形数据</div>;
  }

  return (
    <div className="waveform-grid">
      {channels.map(([channel, samples]) => (
        <div key={channel} className="waveform-channel">
          <h4>{channel}</h4>
          <svg viewBox="0 0 200 60" preserveAspectRatio="none">
            {samples.length > 1 && (
              <polyline
                points={samples
                  .slice(-200)
                  .map((value, index, array) => {
                    const x = (index / (array.length - 1)) * 200;
                    const normalized = (value + 50) / 100; // approximate scaling
                    const y = 60 - Math.min(Math.max(normalized, 0), 1) * 60;
                    return `${x},${y}`;
                  })
                  .join(" ")}
                fill="none"
                stroke="#06d6a0"
                strokeWidth="1"
              />
            )}
          </svg>
        </div>
      ))}
    </div>
  );
}

WaveformChart.propTypes = {
  waveform: PropTypes.shape({
    channels: PropTypes.objectOf(PropTypes.arrayOf(PropTypes.number)),
  }),
};

export default function EmotionDashboard({ emotion }) {
  if (!emotion) {
    return (
      <div className="emotion-dashboard">
        <p>等待情感数据流…</p>
      </div>
    );
  }

  return (
    <div className="emotion-dashboard">
      <header>
        <h2>融合情感</h2>
        <div className="emotion-current">
          <span className="emotion-label">{emotion.label}</span>
          <span className="emotion-score">
            mood {emotion.mood_score.toFixed(2)} · conf {" "}
            {emotion.confidence.toFixed(2)}
          </span>
        </div>
      </header>
      <section className="emotion-components">
        <h3>通道贡献</h3>
        <ul>
          {emotion.components.map((component, index) => (
            <li key={`${component.source}-${index}`}>
              <span className="component-source">{component.source}</span>
              <span className="component-label">{component.label}</span>
              <span className="component-score">
                mood {component.mood_score.toFixed(2)} / conf {" "}
                {component.confidence.toFixed(2)}
              </span>
            </li>
          ))}
        </ul>
      </section>
      <section className="waveform-section">
        <h3>EEG 波形</h3>
        <WaveformChart waveform={emotion.waveform} />
      </section>
    </div>
  );
}

EmotionDashboard.propTypes = {
  emotion: PropTypes.shape({
    label: PropTypes.string.isRequired,
    confidence: PropTypes.number.isRequired,
    mood_score: PropTypes.number.isRequired,
    components: PropTypes.arrayOf(
      PropTypes.shape({
        source: PropTypes.string.isRequired,
        label: PropTypes.string.isRequired,
        confidence: PropTypes.number.isRequired,
        mood_score: PropTypes.number.isRequired,
      })
    ).isRequired,
    waveform: PropTypes.shape({
      channels: PropTypes.objectOf(PropTypes.arrayOf(PropTypes.number)),
    }),
  }),
};
