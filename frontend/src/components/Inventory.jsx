import React, { useState, useEffect } from "react";
import "./Inventory.css";
import bagIcon from "../pages/StarPortalPlanB/styles/img/bag.png";

/**
 * 物品栏组件
 * @param {Array} items - 物品列表，格式: [{ id, name, icon, count, description }]
 * @param {Function} onItemClick - 点击物品时的回调函数
 * @param {Boolean} visible - 是否显示物品栏
 * @param {Boolean} collapsed - 是否折叠（默认false）
 * @param {Function} onCollapseToggle - 切换折叠状态的回调函数
 */
export default function Inventory({ 
  items = [], 
  onItemClick, 
  visible = true,
  collapsed = false,
  onCollapseToggle
}) {
  const [selectedItem, setSelectedItem] = useState(null);
  const [isCollapsed, setIsCollapsed] = useState(collapsed);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // 检测弹框是否打开
  useEffect(() => {
    const checkModal = () => {
      const modal = document.querySelector('.ui-modal.is-open');
      setIsModalOpen(!!modal);
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
  }, []);

  const handleItemClick = (item) => {
    setSelectedItem(item);
    if (onItemClick) {
      onItemClick(item);
    }
  };

  const handleToggleCollapse = () => {
    const newCollapsed = !isCollapsed;
    setIsCollapsed(newCollapsed);
    if (onCollapseToggle) {
      onCollapseToggle(newCollapsed);
    }
  };

  if (!visible) return null;

  // 如果弹框打开，隐藏物品栏
  if (isModalOpen) return null;

  return (
    <div className={`inventory-container ${isCollapsed ? 'collapsed' : ''}`}>
      {isCollapsed ? (
        <div className="inventory-icon-button" onClick={handleToggleCollapse} title="展开物品栏">
          <img src={bagIcon} alt="物品栏" className="inventory-bag-icon" />
        </div>
      ) : (
        <>
          <div className="inventory-header" onClick={handleToggleCollapse}>
            <h3 className="inventory-title">物品栏</h3>
            <button 
              className="inventory-toggle"
              onClick={(e) => {
                e.stopPropagation();
                handleToggleCollapse();
              }}
              aria-label="折叠物品栏"
            >
              ▼
            </button>
          </div>
          
          <div className="inventory-grid">
            {items.length === 0 ? (
              <div className="inventory-empty">
                <p>物品栏为空</p>
              </div>
            ) : (
              items.map((item) => (
                <div
                  key={item.id}
                  className={`inventory-item ${selectedItem?.id === item.id ? 'selected' : ''}`}
                  onClick={() => handleItemClick(item)}
                  title={item.description || item.name}
                >
                  {item.icon ? (
                    <div className="inventory-item-icon">
                      {typeof item.icon === 'string' ? (
                        <img src={item.icon} alt={item.name} />
                      ) : (
                        item.icon
                      )}
                    </div>
                  ) : (
                    <div className="inventory-item-placeholder">
                      <span>?</span>
                    </div>
                  )}
                  <div className="inventory-item-info">
                    <div className="inventory-item-name">{item.name}</div>
                    {item.count !== undefined && item.count > 0 && (
                      <div className="inventory-item-count">{item.count}</div>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>

          {selectedItem && (
            <div className="inventory-detail">
              <h4>{selectedItem.name}</h4>
              {selectedItem.description && (
                <p>{selectedItem.description}</p>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

