const CLOSE_CODE_NORMAL = 1000;

export const safelyCloseWebSocket = (socket, reason = "cleanup") => {
  if (!socket) return;

  const finalizeClose = () => {
    try {
      socket.close(CLOSE_CODE_NORMAL, reason);
    } catch (error) {
      console.warn("[WebSocket] Failed to close socket", error);
    }
  };

  if (socket.readyState === WebSocket.CONNECTING) {
    const handleOpen = () => {
      socket.removeEventListener("open", handleOpen);
      socket.removeEventListener("error", handleOpen);
      finalizeClose();
    };
    socket.addEventListener("open", handleOpen);
    socket.addEventListener("error", handleOpen);
    return;
  }

  finalizeClose();
};
