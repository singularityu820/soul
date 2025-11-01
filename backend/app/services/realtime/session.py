from __future__ import annotations

import asyncio
import logging
import math
import os
import time
from typing import Optional, Callable, Awaitable, Deque
from collections import deque

from aiortc import (
    RTCPeerConnection,
    RTCSessionDescription,
    MediaStreamTrack,
    RTCConfiguration,
    RTCIceServer,
    RTCIceCandidate,
    VideoStreamTrack,
)
from aiortc.sdp import candidate_from_sdp
from av import AudioFrame, VideoFrame
from av.audio.resampler import AudioResampler
import numpy as np

from ...schemas import WebRTCCandidate

logger = logging.getLogger(__name__)


class AgentAudioTrack(MediaStreamTrack):
    """
    自定义音频轨道，用于将 TTS 生成的音频流推送到 WebRTC 连接。
    """

    kind = "audio"

    def __init__(self) -> None:
        super().__init__()
        self._queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._sample_rate = 16000
        self._channels = 1
        self._timestamp = 0
        self._samples_per_frame = int(self._sample_rate * 0.02)  # 20ms frames

    async def recv(self) -> AudioFrame:
        """
        从队列读取音频数据并返回 AudioFrame。
        """
        # 等待音频数据
        try:
            audio_data = await asyncio.wait_for(self._queue.get(), timeout=0.5)
        except asyncio.TimeoutError:
            # 如果没有数据，发送静音帧
            audio_data = b"\x00" * (self._samples_per_frame * 2 * self._channels)

        # 将字节转换为 numpy 数组
        samples = np.frombuffer(audio_data, dtype=np.int16).reshape(1, -1)

        # 创建 AudioFrame
        frame = AudioFrame.from_ndarray(samples, format="s16", layout="mono")
        frame.sample_rate = self._sample_rate
        frame.pts = self._timestamp
        frame.time_base = "1/16000"

        self._timestamp += samples.shape[1]

        return frame

    async def push_audio(self, audio_bytes: bytes) -> None:
        """
        推送 TTS 生成的音频数据到队列。
        
        Args:
            audio_bytes: PCM 16-bit 音频数据
        """
        await self._queue.put(audio_bytes)

    def stop(self) -> None:
        """停止音频轨道"""
        super().stop()
        # 清空队列
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break


class AgentWebRTCSession:
    """
    管理单个 Agent WebRTC 会话，处理音频接收和 TTS 音频推送。
    """

    def __init__(
        self,
        room_id: str,
        on_audio_received: Optional[Callable[[bytes], Awaitable[None]]] = None,
        on_local_candidate: Optional[Callable[[Optional[WebRTCCandidate]], Awaitable[None]]] = None,
        mode: str = "voice",
    ) -> None:
        self.room_id = room_id
        self._on_audio_received = on_audio_received
        self._on_local_candidate = on_local_candidate
        self._mode = (mode or "voice").lower()

        # 配置 ICE 服务器 (localhost 连接不需要 STUN/TURN)
        ice_servers = []
        
        # 自定义 TURN 服务器(如果需要外网连接)
        turn_server = os.getenv("TURN_SERVER")
        if turn_server:
            turn_username = os.getenv("TURN_USERNAME", "")
            turn_credential = os.getenv("TURN_CREDENTIAL", "")
            if turn_username and turn_credential:
                ice_servers.append(
                    RTCIceServer(
                        urls=turn_server,
                        username=turn_username,
                        credential=turn_credential,
                        credentialType="password",
                    )
                )
                logger.info("Using custom TURN server: %s", turn_server)

        config = RTCConfiguration(
            iceServers=ice_servers,
        )
        self._pc = RTCPeerConnection(configuration=config)

        # Agent 音频轨道（用于推送 TTS 音频）
        self._agent_audio_track = AgentAudioTrack()
        self._pc.addTrack(self._agent_audio_track)

        # Agent 视频轨道（用于视频通话模式下推送占位画面）
        self._agent_video_track: Optional[AgentVideoTrack] = None
        if self._mode == "video":
            self._agent_video_track = AgentVideoTrack()
            self._pc.addTrack(self._agent_video_track)

        # 接收的音频轨道
        self._incoming_audio_track: Optional[MediaStreamTrack] = None
        self._incoming_video_track: Optional[MediaStreamTrack] = None

        # 音频缓冲配置，允许更快速地触发 ASR
        self._audio_buffer: list[bytes] = []
        self._buffered_bytes: int = 0
        self._target_sample_rate = 16000
        self._bytes_per_dispatch = int(self._target_sample_rate * 0.25 * 2)
        self._max_buffer_interval = 1.0
        self._last_dispatch_time = time.monotonic()
        self._recording_task: Optional[asyncio.Task] = None
        self._frames_logged = 0
        self._pending_remote_candidates: Deque[WebRTCCandidate] = deque()
        self._resampler: Optional[AudioResampler] = None
        self._input_sample_rate: Optional[int] = None

        # 设置事件处理
        self._setup_handlers()

        logger.info("WebRTC session created for room: %s", room_id)

    def _setup_handlers(self) -> None:
        """设置 RTCPeerConnection 事件处理器"""

        @self._pc.on("track")
        async def on_track(track: MediaStreamTrack) -> None:
            logger.info("Received %s track from peer", track.kind)
            if track.kind == "audio":
                self._incoming_audio_track = track
                # 启动音频接收任务
                self._recording_task = asyncio.create_task(self._receive_audio(track))
            elif track.kind == "video":
                self._incoming_video_track = track
                logger.debug("Video track received for room %s", self.room_id)

        @self._pc.on("connectionstatechange")
        async def on_connectionstatechange() -> None:
            logger.info("Connection state: %s", self._pc.connectionState)
            if self._pc.connectionState == "failed":
                await self.close()

        @self._pc.on("iceconnectionstatechange")
        async def on_iceconnectionstatechange() -> None:
            logger.info("ICE connection state: %s", self._pc.iceConnectionState)

        @self._pc.on("icecandidate")
        async def on_icecandidate(candidate: Optional[RTCIceCandidate]) -> None:
            if candidate is None:
                logger.info("Local ICE gathering completed for room: %s", self.room_id)
                if self._on_local_candidate:
                    await self._on_local_candidate(None)
                return

            logger.info(
                "Local ICE candidate gathered for room %s: %s",
                self.room_id,
                candidate.candidate,
            )
            if self._on_local_candidate:
                model = WebRTCCandidate(
                    candidate=candidate.candidate,
                    sdp_mid=candidate.sdpMid,
                    sdp_mline_index=candidate.sdpMLineIndex,
                    username_fragment=candidate.usernameFragment,
                )
                await self._on_local_candidate(model)

    async def _receive_audio(self, track: MediaStreamTrack) -> None:
        """
        从接收的音频轨道读取音频帧并处理。
        """
        try:
            while True:
                try:
                    frame = await track.recv()
                    if self._resampler is None or self._input_sample_rate != frame.sample_rate:
                        self._input_sample_rate = frame.sample_rate or self._target_sample_rate
                        self._resampler = AudioResampler(
                            format="s16",
                            layout="mono",
                            rate=self._target_sample_rate,
                        )

                    audio_chunks: list[bytes] = []
                    if self._resampler is not None:
                        resampled_frames = self._resampler.resample(frame)
                        if resampled_frames is None:
                            continue
                        for resampled in resampled_frames:
                            samples = resampled.to_ndarray(format="s16", layout="mono")
                            audio_chunks.append(samples.tobytes())
                    else:
                        samples = frame.to_ndarray(format="s16", layout="mono")
                        audio_chunks.append(samples.tobytes())

                    for chunk in audio_chunks:
                        self._audio_buffer.append(chunk)
                        self._buffered_bytes += len(chunk)

                    if self._frames_logged < 5:
                        self._frames_logged += 1
                        logger.info(
                            "Frame received for room %s: samples=%d input_rate=%s buffered=%d",
                            self.room_id,
                            frame.samples,
                            getattr(frame, "sample_rate", "unknown"),
                            self._buffered_bytes,
                        )

                    now = time.monotonic()
                    should_dispatch = (
                        self._buffered_bytes >= self._bytes_per_dispatch
                        or (self._audio_buffer and now - self._last_dispatch_time >= self._max_buffer_interval)
                    )
                    if should_dispatch and self._audio_buffer:
                        reason = (
                            "size"
                            if self._buffered_bytes >= self._bytes_per_dispatch
                            else "timeout"
                        )
                        buffered = self._buffered_bytes
                        combined = b"".join(self._audio_buffer)
                        self._audio_buffer.clear()
                        self._buffered_bytes = 0
                        self._last_dispatch_time = now

                        if self._on_audio_received and combined:
                            logger.info(
                                "Dispatching resampled audio chunk (%d bytes @%dHz) for room %s via %s trigger (buffered=%d)",
                                len(combined),
                                self._target_sample_rate,
                                self.room_id,
                                reason,
                                buffered,
                            )
                            # 调用独立任务以避免阻塞接收循环
                            asyncio.create_task(self._on_audio_received(combined))

                except Exception as e:
                    logger.error("Error receiving audio frame: %s", e)
                    break
        finally:
            if self._audio_buffer:
                combined = b"".join(self._audio_buffer)
                self._audio_buffer.clear()
                self._buffered_bytes = 0
                if self._on_audio_received and combined:
                    logger.info(
                        "Flushing residual audio chunk (%d bytes @%dHz) for room %s",
                        len(combined),
                        self._target_sample_rate,
                        self.room_id,
                    )
                    asyncio.create_task(self._on_audio_received(combined))
            logger.info("Audio receiving stopped for room: %s", self.room_id)

    async def handle_offer(self, offer_sdp: str) -> str:
        """
        处理来自客户端的 offer 并返回 answer。

        Args:
            offer_sdp: 客户端的 SDP offer

        Returns:
            answer_sdp: 服务端的 SDP answer
        """
        # 设置远端描述
        offer = RTCSessionDescription(sdp=offer_sdp, type="offer")
        await self._pc.setRemoteDescription(offer)
        await self._drain_pending_remote_candidates()

        # 创建 answer
        answer = await self._pc.createAnswer()
        await self._pc.setLocalDescription(answer)

        logger.info("Generated answer for room: %s", self.room_id)
        return self._pc.localDescription.sdp

    async def _drain_pending_remote_candidates(self) -> None:
        while self._pending_remote_candidates:
            pending = self._pending_remote_candidates.popleft()
            await self._apply_remote_candidate(pending)

    async def _apply_remote_candidate(self, candidate: WebRTCCandidate) -> None:
        if not candidate.candidate:
            logger.info("Remote ICE gathering completed signal for room: %s", self.room_id)
            await self._pc.addIceCandidate(None)
            return

        candidate_sdp = candidate.candidate
        if candidate_sdp.startswith("candidate:"):
            candidate_sdp = candidate_sdp[len("candidate:") :]

        rtc_candidate = candidate_from_sdp(candidate_sdp)
        rtc_candidate.sdpMid = candidate.sdp_mid
        rtc_candidate.sdpMLineIndex = candidate.sdp_mline_index

        await self._pc.addIceCandidate(rtc_candidate)
        logger.info(
            "Remote ICE candidate added for room %s: %s",
            self.room_id,
            candidate.candidate,
        )

    async def add_remote_candidate(self, candidate: WebRTCCandidate) -> None:
        """接收来自客户端的 ICE 候选并添加到连接"""
        if not self._pc.remoteDescription:
            logger.debug(
                "Queuing remote ICE candidate for room %s until offer is applied",
                self.room_id,
            )
            self._pending_remote_candidates.append(candidate)
            return

        await self._apply_remote_candidate(candidate)

    async def push_tts_audio(self, audio_bytes: bytes) -> None:
        """
        推送 TTS 生成的音频到 WebRTC 连接。

        Args:
            audio_bytes: PCM 16-bit 音频数据
        """
        await self._agent_audio_track.push_audio(audio_bytes)

    async def close(self) -> None:
        """关闭 WebRTC 连接和资源"""
        logger.info("Closing WebRTC session for room: %s", self.room_id)

        # 停止录音任务
        if self._recording_task and not self._recording_task.done():
            self._recording_task.cancel()
            try:
                await self._recording_task
            except asyncio.CancelledError:
                pass

        # 停止音频轨道
        if self._agent_audio_track:
            self._agent_audio_track.stop()

        if self._agent_video_track:
            self._agent_video_track.stop()

        # 关闭 PeerConnection
        await self._pc.close()

    @property
    def connection_state(self) -> str:
        """返回当前连接状态"""
        return self._pc.connectionState

    @property
    def ice_connection_state(self) -> str:
        """返回 ICE 连接状态"""
        return self._pc.iceConnectionState


class AgentVideoTrack(VideoStreamTrack):
    """生成动态渐变画面的占位视频流，用于演示视频通话链路。"""

    kind = "video"

    def __init__(self, width: int = 640, height: int = 360, fps: int = 20) -> None:
        super().__init__()
        self._width = width
        self._height = height
        self._fps = max(1, fps)
        self._frame_interval = 1 / self._fps
        self._start = time.time()

    async def recv(self) -> VideoFrame:
        await asyncio.sleep(self._frame_interval)
        pts, time_base = await self.next_timestamp()

        elapsed = time.time() - self._start
        gradient = np.linspace(0, 255, self._width, dtype=np.uint8)
        band = np.tile(gradient, (self._height, 1))
        red = (np.sin(elapsed) + 1.0) * 127.0
        green = (np.cos(elapsed * 0.6) + 1.0) * 127.0
        blue = (np.sin(elapsed * 1.3 + math.pi / 4) + 1.0) * 127.0

        frame_array = np.stack(
            (
                (band * (red / 255.0)).astype(np.uint8),
                (band * (green / 255.0)).astype(np.uint8),
                (band * (blue / 255.0)).astype(np.uint8),
            ),
            axis=2,
        )

        frame = VideoFrame.from_ndarray(frame_array, format="bgr24")
        frame.pts = pts
        frame.time_base = time_base
        return frame
