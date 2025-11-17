import React, { useEffect, useState } from "react";
import "./Modal.css";

export default function Modal({ open, onClose, children, afterClose, isFullscreen = false }) {
  const [mounted, setMounted] = useState(open);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (mounted) {
      // 禁用背景页面滚动
      const originalOverflow = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      return () => {
        document.body.style.overflow = originalOverflow;
      };
    }
  }, [mounted]);

  useEffect(() => {
    if (open) {
      // 打开：挂载并在下一帧加 is-open 触发进入动画
      setMounted(true);
      requestAnimationFrame(() => setVisible(true));
    } else {
      // 关闭：去掉 is-open 触发退出动画；保持挂载直至过渡结束
      setVisible(false);
    }
  }, [open]);

  const handleBackdrop = () => {
    if (onClose) onClose();
  };

  const handleTransitionEnd = () => {
    if (!visible) {
      if (afterClose) afterClose();
      setMounted(false);
    }
  };

  if (!mounted) return null;

  return (
    <div className={`ui-modal${visible ? " is-open" : ""}${isFullscreen ? " is-fullscreen" : ""}`} role="dialog" aria-modal="true">
      <div className="ui-modal__backdrop" onClick={handleBackdrop} />
      <div className="ui-modal__content" onTransitionEnd={handleTransitionEnd}>
        <button className="ui-modal__close" onClick={handleBackdrop} aria-label="关闭">✕</button>
        <div className="ui-modal__body">{children}</div>
      </div>
    </div>
  );
}


