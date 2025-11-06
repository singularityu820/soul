import PropTypes from "prop-types";

const defaultPose = {
  expression: "neutral",
  pose: "idle",
  energy: 0.3,
  color_theme: "#118ab2",
};

export default function AvatarCanvas({ pose }) {
  const state = pose ?? defaultPose;
  const energyPercent = Math.round(state.energy * 100);

  return (
    <div
      className="avatar-wrapper"
      style={{ borderColor: state.color_theme, boxShadow: `0 0 16px ${state.color_theme}55` }}
    >
      <div className={`sprite sprite-${state.expression} sprite-${state.pose}`}></div>
      <div className="avatar-meta">
        <span>表情：{state.expression}</span>
        <span>姿态：{state.pose}</span>
        <span>能量：{energyPercent}%</span>
        {state.emphasis && <span>提示：{state.emphasis}</span>}
      </div>
    </div>
  );
}

AvatarCanvas.propTypes = {
  pose: PropTypes.shape({
    expression: PropTypes.string,
    pose: PropTypes.string,
    energy: PropTypes.number,
    color_theme: PropTypes.string,
    emphasis: PropTypes.string,
  }),
};
