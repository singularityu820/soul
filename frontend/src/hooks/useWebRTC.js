import { useCallback, useEffect, useRef, useState } from "react";

// 自动检测 API 地址 - 使用当前页面的 hostname 而不是 localhost
const getApiPrefix = () => {
  // 如果通过 IP 访问页面,则使用该 IP 作为 API 地址
  const hostname = window.location.hostname;
  if (hostname !== 'localhost' && hostname !== '127.0.0.1') {
    return `http://${hostname}:8000`;
  }
  // 默认使用 localhost (仅用于开发)
  return "http://localhost:8000";
};

const API_PREFIX = getApiPrefix();
const WS_PREFIX = API_PREFIX.replace(/^http/, "ws");

// 开发环境下的替代方案，使用相对路径
const DEV_API_PREFIX = process.env.NODE_ENV === 'development' ? "http://localhost:8000" : API_PREFIX;
const DEV_WS_PREFIX = DEV_API_PREFIX.replace(/^http/, "ws");

export function useWebRTC(initialRoomId, onRemoteAudio, onError) {
  const [connectionState, setConnectionState] = useState("new");
  const [isConnecting, setIsConnecting] = useState(false);
  const peerConnectionRef = useRef(null);
  const localStreamRef = useRef(null);
  const remoteAudioRef = useRef(null);
  const signalingSocketRef = useRef(null);
  const roomIdRef = useRef(initialRoomId ?? null);

  useEffect(() => {
    roomIdRef.current = initialRoomId ?? null;
  }, [initialRoomId]);

  // localhost 连接不需要 STUN/TURN 服务器
  const iceServers = [];

  const closeSignaling = useCallback(() => {
    if (signalingSocketRef.current) {
      signalingSocketRef.current.close();
      signalingSocketRef.current = null;
    }
  }, []);

  const ensureSignaling = useCallback((roomId) => {
    if (!roomId || signalingSocketRef.current) {
      return;
    }
    try {
      const socket = new WebSocket(`${DEV_WS_PREFIX}/ws/webrtc/${roomId}`);
      socket.onclose = () => {
        if (signalingSocketRef.current === socket) {
          signalingSocketRef.current = null;
        }
      };
      socket.onerror = (event) => {
        console.error("Signaling socket error", event);
      };
      socket.onmessage = async (event) => {
        try {
          const message = JSON.parse(event.data);
          if (!peerConnectionRef.current) {
            return;
          }
          if (message.type === "candidate" && message.payload) {
            const candidate = message.payload;
            await peerConnectionRef.current.addIceCandidate(
              new RTCIceCandidate({
                candidate: candidate.candidate,
                sdpMid: candidate.sdp_mid ?? candidate.sdpMid ?? undefined,
                sdpMLineIndex: candidate.sdp_mline_index ?? candidate.sdpMLineIndex ?? undefined,
                usernameFragment: candidate.username_fragment ?? candidate.usernameFragment ?? undefined,
              })
            );
          }
        } catch (error) {
          console.error("Failed to process signaling message", error);
        }
      };
      signalingSocketRef.current = socket;
    } catch (error) {
      console.error("Failed to open signaling socket", error);
    }
  }, []);

  const sendCandidate = useCallback(async (roomId, candidate) => {
    try {
      console.log("Sending ICE candidate to server");
      await fetch(`${DEV_API_PREFIX}/webrtc/${roomId}/candidate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          candidate: candidate.candidate,
          sdp_mid: candidate.sdpMid,
          sdp_mline_index: candidate.sdpMLineIndex,
          username_fragment: candidate.usernameFragment ?? undefined,
        }),
      });
      console.log("ICE candidate sent successfully");
    } catch (error) {
      console.error("Failed to send ICE candidate", error);
    }
  }, []);

  const resolveRoomId = useCallback((candidateRoomId) => {
    if (candidateRoomId) {
      return candidateRoomId;
    }
    if (roomIdRef.current) {
      return roomIdRef.current;
    }
    throw new Error("roomId is required to start WebRTC call");
  }, []);

  const stopCall = useCallback(() => {
    console.log("Stopping call...");

    if (localStreamRef.current) {
      localStreamRef.current.getTracks().forEach((track) => {
        console.log(`Stopping ${track.kind} track`);
        track.stop();
      });
      localStreamRef.current = null;
    }

    if (peerConnectionRef.current) {
      try {
        peerConnectionRef.current.close();
      } catch (error) {
        console.error("Error closing peer connection:", error);
      }
      peerConnectionRef.current = null;
    }

    closeSignaling();

    if (remoteAudioRef.current) {
      remoteAudioRef.current.srcObject = null;
    }

    setConnectionState("closed");
    setIsConnecting(false);

    const activeRoomId = roomIdRef.current;
    if (activeRoomId) {
      fetch(`${DEV_API_PREFIX}/webrtc/${activeRoomId}`, {
        method: "DELETE",
      }).catch((err) => console.error("Failed to notify server:", err));
    }
    
    console.log("WebRTC call stopped");
  }, [closeSignaling]);

  const startCall = useCallback(
    async ({ roomId: explicitRoomId, mode = "voice" } = {}) => {
      if (isConnecting || peerConnectionRef.current) {
        console.log("Call already in progress");
        return;
      }

      const callRoomId = resolveRoomId(explicitRoomId);
      roomIdRef.current = callRoomId;

      setIsConnecting(true);
      setConnectionState("connecting");

      // 检查当前页面是否通过HTTPS访问
      const isSecureContext = window.isSecureContext || location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1';
      if (!isSecureContext && mode === "video") {
        throw new Error("视频通话需要安全连接(HTTPS)，请使用https://localhost或部署到HTTPS服务器");
      }

      try {
        console.log("Requesting user media with mode:", mode);
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
            sampleRate: 16000
          },
          video: mode === "video" ? {
            width: { ideal: 640 },
            height: { ideal: 480 },
            frameRate: { ideal: 30 }
          } : false,
        });
        
        console.log("Got user media stream:", stream.getTracks().map(t => `${t.kind}:${t.label}`));
        localStreamRef.current = stream;

        const pc = new RTCPeerConnection({ iceServers });
        peerConnectionRef.current = pc;

        pc.onicecandidate = (event) => {
          if (event.candidate) {
            console.log("Sending ICE candidate");
            sendCandidate(callRoomId, event.candidate);
          } else {
            console.log("All ICE candidates sent");
          }
        };

        // 添加音频轨道到连接
        const audioTracks = stream.getAudioTracks();
        if (audioTracks.length > 0) {
          console.log(`Adding audio track to peer connection: ${audioTracks[0].label}`);
          pc.addTrack(audioTracks[0], stream);
        } else {
          console.warn("No audio tracks found in user media stream");
        }
        
        // 如果是视频模式，添加视频轨道
        if (mode === "video") {
          const videoTracks = stream.getVideoTracks();
          if (videoTracks.length > 0) {
            console.log(`Adding video track to peer connection: ${videoTracks[0].label}`);
            pc.addTrack(videoTracks[0], stream);
          } else {
            console.warn("No video tracks found in user media stream");
          }
        }

        pc.ontrack = (event) => {
          console.log("Received remote track:", event.track.kind);
          const [remoteStream] = event.streams;
          if (event.track.kind === "audio") {
            if (remoteAudioRef.current) {
              remoteAudioRef.current.srcObject = remoteStream;
              remoteAudioRef.current.play().catch((err) => {
                console.error("Failed to play remote audio:", err);
              });
            }
            if (onRemoteAudio) {
              onRemoteAudio(remoteStream);
            }
          } else if (event.track.kind === "video") {
            console.log("Processing video track");
            // 确保视频流正确传递给VideoDisplay组件
            if (onRemoteAudio && typeof onRemoteAudio === 'function') {
              // 使用第二个参数标识这是视频流
              onRemoteAudio(remoteStream, 'video');
            }
          }
        };

        pc.onconnectionstatechange = () => {
          console.log("Connection state changed to:", pc.connectionState);
          setConnectionState(pc.connectionState);
          if (pc.connectionState === "failed" || pc.connectionState === "closed") {
            console.error("WebRTC connection failed or closed");
            stopCall();
          }
        };

        pc.oniceconnectionstatechange = () => {
          console.log("ICE connection state:", pc.iceConnectionState);
        };

        pc.onicecandidateerror = (event) => {
          console.error("ICE candidate error:", event);
        };

        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);

        console.log("Created offer, sending to server");
        const response = await fetch(`${DEV_API_PREFIX}/webrtc/${callRoomId}/offer`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            type: "offer",
            sdp: offer.sdp,
            metadata: { initiator: "user", mode },
          }),
        });

        if (!response.ok) {
          throw new Error(`Server returned ${response.status}`);
        }

        const answerData = await response.json();
        console.log("Received answer from server:", answerData);

        await pc.setRemoteDescription(
          new RTCSessionDescription({
            type: "answer",
            sdp: answerData.sdp,
          })
        );

        console.log("WebRTC connection established");
        ensureSignaling(callRoomId);

        try {
          const stateResponse = await fetch(`${DEV_API_PREFIX}/webrtc/${callRoomId}`);
          if (stateResponse.ok) {
            const state = await stateResponse.json();
            if (state.candidates) {
              console.log("Processing", state.candidates.length, "historical candidates");
              for (const candidate of state.candidates) {
                await pc.addIceCandidate(
                  new RTCIceCandidate({
                    candidate: candidate.candidate,
                    sdpMid: candidate.sdp_mid ?? candidate.sdpMid ?? undefined,
                    sdpMLineIndex: candidate.sdp_mline_index ?? candidate.sdpMLineIndex ?? undefined,
                    usernameFragment: candidate.username_fragment ?? candidate.usernameFragment ?? undefined,
                  })
                );
              }
            }
          }
        } catch (error) {
          console.warn("Failed to sync historical candidates", error);
        }

        setConnectionState("connected");
        setIsConnecting(false);
      } catch (error) {
        console.error("Failed to start call:", error);
        setConnectionState("failed");
        setIsConnecting(false);
        if (onError) {
          onError(error);
        }
        stopCall();
      }
    },
    [ensureSignaling, iceServers, isConnecting, onError, onRemoteAudio, resolveRoomId, sendCandidate, stopCall]
  );

  useEffect(() => () => stopCall(), [stopCall]);

  return {
    startCall,
    stopCall,
    connectionState,
    isConnecting,
    remoteAudioRef,
  };
}
