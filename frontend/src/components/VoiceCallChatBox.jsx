import PropTypes from 'prop-types';
import './VoiceCallChatBox.css';

export default function VoiceCallChatBox({ transcript, response, className = '' }) {
  if (!transcript && !response) return null;

  return (
    <div className={`voice-call-transcript ${className}`.trim()}>
      {transcript && (
        <div className="transcript-user">
          <strong>你：</strong> {transcript}
        </div>
      )}
      {response && (
        <div className="transcript-ai">
          <strong>AI：</strong> {response}
        </div>
      )}
    </div>
  );
}

VoiceCallChatBox.propTypes = {
  transcript: PropTypes.string,
  response: PropTypes.string,
  className: PropTypes.string,
};
