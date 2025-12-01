import React, { useState, useEffect, useRef } from "react";
import settingIcon from "../pages/StarPortalPlanB/styles/img/setting.png";
import "./SettingsButton.css";

/**
 * 通用设置按钮组件
 * 固定在右上角，所有页面都可以使用
 * 点击展开菜单，包含回到首页等功能
 */
export default function SettingsButton() {
  const [isOpen, setIsOpen] = useState(false);
  const [isHovered, setIsHovered] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const menuRef = useRef(null);
  const buttonRef = useRef(null);

  // 检测弹框是否打开
  useEffect(() => {
    const checkModal = () => {
      const modal = document.querySelector('.ui-modal.is-open');
      const modalOpen = !!modal;
      setIsModalOpen(modalOpen);
      // 如果弹框打开，关闭设置菜单
      if (modalOpen && isOpen) {
        setIsOpen(false);
      }
    };

    // 初始检查
    checkModal();

    // 使用 MutationObserver 监听 DOM 变化
    const observer = new MutationObserver(checkModal);
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['class']
    });

    return () => {
      observer.disconnect();
    };
  }, [isOpen]);

  // 点击外部区域关闭菜单
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (
        menuRef.current &&
        buttonRef.current &&
        !menuRef.current.contains(event.target) &&
        !buttonRef.current.contains(event.target)
      ) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);

  const handleButtonClick = (e) => {
    e.stopPropagation();
    setIsOpen(!isOpen);
  };

  const handleGoHome = () => {
    if (window.navigate) {
      window.navigate("#/user");
    } else {
      window.location.hash = "#/user";
    }
    setIsOpen(false);
  };

  // 如果弹框打开，隐藏设置按钮
  if (isModalOpen) {
    return null;
  }

  return (
    <div className="settings-button-container">
      <button
        ref={buttonRef}
        className={`settings-button ${isOpen ? "active" : ""}`}
        onClick={handleButtonClick}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        aria-label="设置"
        title="设置"
      >
        <img 
          src={settingIcon} 
          alt="设置" 
          className="settings-icon"
        />
      </button>

      {isOpen && (
        <div ref={menuRef} className="settings-menu">
          <button
            className="settings-menu-item"
            onClick={handleGoHome}
            aria-label="回到首页"
          >
            <span className="settings-menu-text">回到首页</span>
          </button>
        </div>
      )}
    </div>
  );
}

