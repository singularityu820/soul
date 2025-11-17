# Soul Emotion Agent

Multimodal real-time emotion companion that fuses simulated EEG signals and facial expression analysis to animate a virtual sprite and drive proactive conversational responses. The project is split into a FastAPI backend that orchestrates the emotion pipeline and a React front-end dashboard for visualization and interaction.

## Features

- **EEG simulator & classifier**: Emits synthetic BCI frames that follow the documented POST payload (serial/page timestamps, sample_size, point_timestamp/point_data, error_data) and derives spectral band features for the placeholder classifier.
- **Face emotion tool**: Accepts detections through an API endpoint and falls back to a stochastic simulator until a real YOLO-style model is connected.
- **Emotion fusion**: Combines EEG and face channels into a single affective state with weighted confidence tracking.
- **Messenger-style UI**: React front-end now mimics a full chat companion with thread list, rich message bubbles, call/screen-share entry points, and emotion-aware context.
- **Avatar orchestration**: Translates emotion outputs into sprite expressions, poses, and color themes.
- **Modular memory stack**: Working/episodic/semantic/perceptual memories routed through a unified manager with vector search, graph relations, and RAG-ready document ingestion.
- **LLM/TTS provider orchestration**: Auto-detects OpenAI, ModelScope, Zhipu AI, vLLM, or Ollama backends, and now streams GPT-SoVITs TTS requests chunk-by-chunk on punctuation/voice markers (replacing `0.0.0.0` URLs with the configured public base) while falling back to sandbox stubs when credentials are missing.
- **WebRTC voice calling**: Real-time audio communication via WebRTC, enabling microphone capture → backend Agent processing → TTS audio streaming back to the browser with low latency. Uses aiortc on the backend and native WebRTC APIs on the frontend.
- **ASR integration**: Automatic speech recognition (Whisper API, Azure Speech, DashScope Qwen ASR, ModelScope) converts user voice to text, which feeds into the LLM conversation pipeline. Supports Chinese, English, Japanese, and more.
- **WebSocket streaming**: Pushes emotion, avatar, and agent events to the UI in real time.
- **Front-end dashboard**: React UI showing EEG waveforms, channel contributions, agent log, and manual user memory inputs.

## Project Structure

```
backend/
  app/
    services/
      agent/         # LLM, TTS, agent orchestration, memory adapter
      emotion/       # EEG simulator, face tool, fusion pipeline, avatar
      chat/          # Chat service and websocket emitters
      realtime/      # WebRTC signaling hub
    memory/          # Modular memory system (manager, types, storage, RAG)
    config.py        # Configuration dataclasses
    main.py          # FastAPI entrypoint and routes
    schemas.py       # Shared Pydantic schemas
  pyproject.toml     # Python project metadata
  requirements.txt   # Backend dependencies
frontend/
  src/               # React components
  package.json       # Front-end dependencies and scripts
``` 

## Getting Started

### Backend (FastAPI)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The backend exposes:
- `GET /health` – quick heartbeat with the latest inferred emotion.
- `POST /ingest/face` – submit face emotion detections (label, confidence, intensity).
- `POST /agent/user-message` – store user inputs for memory and future RAG.
- `GET /memory/snapshot` – inspect recent memory events.
- `WS /ws/pipeline` – subscribe to fused emotion updates, avatar states, and agent messages.
- `GET /chat/threads` – list chat threads; `POST` to create a new one.
- `GET /chat/threads/{id}/messages` – fetch recent messages; `POST` to append a user message and trigger the agent response.
- `WS /ws/chat?thread_id=...` – live stream chat events (history + incremental updates).
- `POST /webrtc/{room}/offer` – initiate WebRTC voice call, returns SDP answer for real-time audio.
- `DELETE /webrtc/{room}` – close active WebRTC session and release resources.
- `WS /ws/webrtc/{room}` – subscribe to signaling updates in real time.

### 3. 启动前端 (React + Vite)

```bash
cd frontend
npm install
npm run dev
```

The dev server proxies API and WebSocket calls to `http://localhost:8000`. Open the printed Vite URL to see the dashboard.

## Extending with Real Signals

- **EEG**: Replace `EEGEmotionClassifier` logic with calls into your actual MLP tool/API. The `EEGStreamTool` already exposes a single integration point (`classify`).
- **Face recognition**: Feed results from a YOLO or other video pipeline to `/ingest/face` (or wire the detector directly into `FaceEmotionTool`).
- **LLM-driven agent**: The `LLMService` auto-picks a provider via env/endpoint probing; export `LLM_PROVIDER=openai|modelscope|zhipu|vllm|ollama` to override or supply the corresponding API keys/endpoints. Set `SOVITS_ENDPOINT` (plus optional `SOVITS_PUBLIC_BASE`, `SOVITS_APP_KEY`, `SOVITS_DOWNLOAD_URL`) so chunked GPT-SoVITs calls can stream audio as soon as punctuation/voice markers land in the LLM output.
- **Avatar rendering**: The front-end `AvatarCanvas` can be swapped with a richer WebGL canvas or a game engine stream that listens to the same WebSocket.
- **WebRTC voice calling**: Click the "语音通话" button in the UI to start a real-time audio call. The backend uses `aiortc` to establish peer connection, capture user microphone audio, and stream TTS responses back. Configure STUN/TURN servers via environment variables (`STUN_SERVER`, `TURN_SERVER`, `TURN_USERNAME`, `TURN_CREDENTIAL`) for NAT traversal. See `backend/.env.example` for reference.
- **ASR (Speech Recognition)**: Set `ASR_PROVIDER=openai|azure|dashscope|modelscope` and corresponding API keys (`OPENAI_API_KEY` for Whisper, `AZURE_SPEECH_KEY` + `AZURE_SPEECH_REGION` for Azure, `DASHSCOPE_API_KEY` for Qwen ASR). User voice is automatically transcribed and fed into the LLM conversation. Falls back to sandbox mode if no ASR provider is configured.
- Set `TTS_PROVIDER` (azure|edge|polly|coqui|ollama|sovits) or rely on auto detection (`AZURE_TTS_KEY`, `EDGE_TTS_KEY`, AWS credentials, or responsive Ollama endpoint).

## Next Steps

1. Swap simulated data sources with actual EEG/vision pipelines via the provided tool hooks.
2. Plug an LLM backend into `ConversationalAgent` and expand the memory store to a persistent vector DB.
3. Enhance the UI with 3D sprite animation and advanced analytics (timeline, emotion journaling).
4. Add automated tests and CI workflows as the logic stabilizes.

## Configuration Guides

- **[LLM Configuration](docs/LLM_CONFIGURATION.md)** - How to configure LLM providers (OpenAI, ModelScope, Zhipu, vLLM, Ollama) and troubleshoot connection issues
- **[WebRTC Voice Calling](docs/WEBRTC_GUIDE.md)** - Setup guide for real-time voice communication
- **[DashScope ASR Integration](docs/DASHSCOPE_ASR.md)** - Configure Alibaba Cloud's Qwen ASR service

### LLM/TTS/ASR Auto-detection Rules

1. Respect explicit `LLM_PROVIDER`/`TTS_PROVIDER`/`ASR_PROVIDER` overrides when present.
2. Otherwise use `LLMServiceConfig`/`TTSServiceConfig.preferred_provider` if supplied in code.
3. Probe well-known credentials/endpoints:
  - LLM: `OPENAI_API_KEY`, `MODELSCOPE_API_KEY`, `ZHIPUAI_API_KEY`, `VLLM_ENDPOINT`, `OLLAMA_ENDPOINT`.
  - TTS: `AZURE_TTS_KEY`, `EDGE_TTS_KEY`, `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY`, `COQUI_TTS_ENDPOINT`, `OLLAMA_TTS_ENDPOINT`, `SOVITS_ENDPOINT`.
  - ASR: `OPENAI_API_KEY` (Whisper), `AZURE_SPEECH_KEY` + `AZURE_SPEECH_REGION`, `DASHSCOPE_API_KEY` (Qwen ASR), `MODELSCOPE_API_KEY`.
4. When nothing matches, fall back to sandbox implementations that return placeholder text/audio references (no external calls).

Startup logs show the detected providers; adjust env vars to switch at runtime.
