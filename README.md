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
- **🆕 Qwen Omni Realtime**: 集成阿里云千问全模态实时大模型，实现 <500ms 超低延迟的实时语音对话，支持语音输入直接生成语音+文本输出，替代传统 ASR→LLM→TTS 三段式流程。保留工具调用能力，支持 4 种音色和服务端 VAD。
- **WebSocket voice streaming**: Low-latency voice loop built on `/ws/voice-stream`, now powered by Qwen-Omni-Realtime for near-instant audio-to-audio responses with automatic speech detection.
- **ASR integration** (legacy fallback): Automatic speech recognition (Whisper API, Azure Speech, DashScope Qwen ASR, ModelScope) as fallback when not using Qwen Omni Realtime.
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
      realtime/      # WebSocket voice streaming utilities
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
- `POST /audio/conversation` – upload audio to trigger the ASR → LLM → TTS pipeline and receive synthesized speech.
- `WS /ws/voice-stream` – **Qwen Omni Realtime** powered full-duplex WebSocket for ultra-low latency voice conversation (<500ms). Supports automatic VAD, 4 voice options, and tool calling integration. 详见 [Qwen Omni 快速开始](docs/QWEN_OMNI_QUICKSTART.md).

### 3. 启动前端 (React + Vite)

```bash
cd frontend
npm install
npm run dev
```

The dev server proxies API and WebSocket calls to `http://localhost:8000`. Open the printed Vite URL to see the dashboard.

#### Voice stream endpoint override

When you deploy the frontend behind a reverse proxy (non-`localhost:8000`), set `VITE_VOICE_STREAM_WS_URL` in `frontend/.env` to the absolute WebSocket endpoint (for example `wss://api.example.com/ws/voice-stream`). The `useVoiceStream` hook will try to infer sensible defaults—`ws://localhost:8000` during Vite dev ports (`5173`, `4173`, `3000`, `8080`), otherwise the current origin—but the explicit env var removes any ambiguity. You can also provide `window.__SOUL_CONFIG__.voiceStreamWsUrl` when embedding the bundle in another host page.

## Extending with Real Signals

- **EEG**: Replace `EEGEmotionClassifier` logic with calls into your actual MLP tool/API. The `EEGStreamTool` already exposes a single integration point (`classify`).
- **Face recognition**: Feed results from a YOLO or other video pipeline to `/ingest/face` (or wire the detector directly into `FaceEmotionTool`).
- **LLM-driven agent**: The `LLMService` auto-picks a provider via env/endpoint probing; export `LLM_PROVIDER=openai|modelscope|zhipu|vllm|ollama` to override or supply the corresponding API keys/endpoints. Set `SOVITS_ENDPOINT` (plus optional `SOVITS_PUBLIC_BASE`, `SOVITS_APP_KEY`, `SOVITS_DOWNLOAD_URL`) so chunked GPT-SoVITs calls can stream audio as soon as punctuation/voice markers land in the LLM output.
- **Avatar rendering**: The front-end `AvatarCanvas` can be swapped with a richer WebGL canvas or a game engine stream that listens to the same WebSocket.
- **WebSocket voice streaming**: Use the voice toggle in the chat UI to open `/ws/voice-stream`. Microphone audio is chunked to 16kHz PCM, streamed via WebSocket, and the backend responds with transcripts, streaming LLM chunks, and TTS segment URLs. No STUN/TURN setup is required.
- **ASR (Speech Recognition)**: Set `ASR_PROVIDER=openai|azure|dashscope|modelscope` and corresponding API keys (`OPENAI_API_KEY` for Whisper, `AZURE_SPEECH_KEY` + `AZURE_SPEECH_REGION` for Azure, `DASHSCOPE_API_KEY` for Qwen ASR). User voice is automatically transcribed and fed into the LLM conversation. Falls back to sandbox mode if no ASR provider is configured.
- Set `TTS_PROVIDER` (azure|edge|polly|coqui|ollama|sovits) or rely on auto detection (`AZURE_TTS_KEY`, `EDGE_TTS_KEY`, AWS credentials, or responsive Ollama endpoint).

## Next Steps

1. Swap simulated data sources with actual EEG/vision pipelines via the provided tool hooks.
2. Plug an LLM backend into `ConversationalAgent` and expand the memory store to a persistent vector DB.
3. Enhance the UI with 3D sprite animation and advanced analytics (timeline, emotion journaling).
4. Add automated tests and CI workflows as the logic stabilizes.

## Configuration Guides

- **🆕 [Qwen Omni Realtime 快速开始](docs/QWEN_OMNI_QUICKSTART.md)** - 千问全模态实时大模型集成指南（推荐）
- **🆕 [Qwen Omni Realtime 详细集成](docs/QWEN_OMNI_REALTIME_INTEGRATION.md)** - 完整的技术文档和API参考
- **[LLM Configuration](docs/LLM_CONFIGURATION.md)** - How to configure LLM providers (OpenAI, ModelScope, Zhipu, vLLM, Ollama) and troubleshoot connection issues
- **[WebSocket Voice Stream](docs/VOICE_STREAM_GUIDE.md)** - Legacy streaming voice pipeline guide (replaced by Qwen Omni)
- **[WebRTC Voice Calling (legacy)](docs/WEBRTC_GUIDE.md)** - Archived notes on the retired aiortc-based system
- **[DashScope ASR Integration](docs/DASHSCOPE_ASR.md)** - Configure Alibaba Cloud's Qwen ASR service (legacy fallback)

### LLM/TTS/ASR Auto-detection Rules

1. Respect explicit `LLM_PROVIDER`/`TTS_PROVIDER`/`ASR_PROVIDER` overrides when present.
2. Otherwise use `LLMServiceConfig`/`TTSServiceConfig.preferred_provider` if supplied in code.
3. Probe well-known credentials/endpoints:
  - LLM: `OPENAI_API_KEY`, `MODELSCOPE_API_KEY`, `ZHIPUAI_API_KEY`, `VLLM_ENDPOINT`, `OLLAMA_ENDPOINT`.
  - TTS: `AZURE_TTS_KEY`, `EDGE_TTS_KEY`, `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY`, `COQUI_TTS_ENDPOINT`, `OLLAMA_TTS_ENDPOINT`, `SOVITS_ENDPOINT`.
  - ASR: `OPENAI_API_KEY` (Whisper), `AZURE_SPEECH_KEY` + `AZURE_SPEECH_REGION`, `DASHSCOPE_API_KEY` (Qwen ASR), `MODELSCOPE_API_KEY`.
4. When nothing matches, fall back to sandbox implementations that return placeholder text/audio references (no external calls).

Startup logs show the detected providers; adjust env vars to switch at runtime.
