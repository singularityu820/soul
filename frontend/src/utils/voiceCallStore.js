// Simple pub/sub store for voice call transcript/response
let data = { transcript: null, response: null };
const listeners = new Set();

export function setVoiceCallData(newData) {
  data = { ...data, ...newData };
  listeners.forEach((cb) => {
    try { cb(data); } catch (e) { console.error('voiceCallStore listener error', e); }
  });
}

export function getVoiceCallData() {
  return { ...data };
}

export function subscribeVoiceCall(cb) {
  listeners.add(cb);
  // call immediately with current data
  try { cb(data); } catch (e) { console.error('voiceCallStore initial callback error', e); }
  return () => listeners.delete(cb);
}
