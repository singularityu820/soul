# Soul Emotion Agent

多模态情感伙伴：融合模拟 EEG、面部情绪和 LLM/TTS 流水线，驱动虚拟角色的表情、语音和对话。后端使用 FastAPI，前端使用 React/Vite 仪表盘与聊天界面。

## 核心特性

- EEG 与人脸情绪融合，带置信度权重，可直接使用内置模拟器。
- Qwen Omni Realtime 低延迟语音双工 WebSocket（`/ws/voice-stream`），内置 VAD 与工具调用。
- 模块化记忆（工作/情景/语义/感知），可接入向量检索与 RAG。
- LLM/TTS/ASR 自动探测，缺省回落沙盒；头像/情绪状态实时推送到前端。
- 情绪小游戏与陪伴玩法，基于当前情绪/记忆动态驱动头像与交互。
- 情绪日记：支持创建/更新/搜索/标签统计，前端有预览与时间线入口。

## 快速上手

Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000 --app-dir backend
```

Frontend

```bash
cd frontend
npm install
npm run dev
```

Vite 开发服务器默认反向代理到 `http://localhost:8000`。

## 主要接口

- `GET /health`：心跳与最新情绪。
- `POST /ingest/face`：提交人脸情绪检测。
- `POST /agent/user-message`：写入用户消息供记忆/RAG。
- `GET /memory/snapshot`：查看近期记忆事件。
- `WS /ws/pipeline`：情绪融合、头像、智能体事件流。
- `GET/POST /chat/threads`，`/chat/threads/{id}/messages`：会话与消息。
- `WS /ws/chat?thread_id=...`：聊天实时流。
- `POST /audio/conversation`：ASR → LLM → TTS 管线。
- `WS /ws/voice-stream`：Qwen Omni 实时语音（<500ms 音频到音频）。
- `POST /api/diary/`：创建情绪日记。
- `GET /api/diary/{diary_id}`：读取单篇日记；`PUT` 更新，`DELETE` 删除。
- `GET /api/diary/user/{user_id}`：分页日记列表；`/latest` 最新一篇；`/count` 数量统计。
- `GET /api/diary/user/{user_id}/search?query=...`：全文搜索日记。
- `GET /api/diary/user/{user_id}/emotion-tags`：情绪标签分布；`/previews` 最新若干篇预览。

## 环境变量

- LLM：`OPENAI_API_KEY`、`MODELSCOPE_API_KEY`、`ZHIPUAI_API_KEY`、`VLLM_ENDPOINT`、`OLLAMA_ENDPOINT` 或 `LLM_PROVIDER`。
- TTS：`AZURE_TTS_KEY`、`EDGE_TTS_KEY`、AWS 凭据、`COQUI_TTS_ENDPOINT`、`OLLAMA_TTS_ENDPOINT`、`SOVITS_ENDPOINT` 或 `TTS_PROVIDER`。
- ASR（回退）：`OPENAI_API_KEY`、`AZURE_SPEECH_KEY` + `AZURE_SPEECH_REGION`、`DASHSCOPE_API_KEY`、`MODELSCOPE_API_KEY` 或 `ASR_PROVIDER`。
- 语音流地址覆写：`frontend/.env` 中设置 `VITE_VOICE_STREAM_WS_URL`。
- 语音情绪回退映射 EEG：`SPEECH_EMOTION_FALLBACK=1`（可选 `DASHSCOPE_API_KEY`）。

