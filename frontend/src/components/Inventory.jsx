import React, { useState } from "react";
import "./Inventory.css";

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

  return (
    <div className={`inventory-container ${isCollapsed ? 'collapsed' : ''}`}>
      {isCollapsed ? (
        <div className="inventory-icon-button" onClick={handleToggleCollapse} title="展开物品栏">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M4 6H20M4 12H20M4 18H20" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            <rect x="2" y="2" width="20" height="20" rx="2" stroke="currentColor" strokeWidth="1.5" fill="none" opacity="0.3"/>
          </svg>
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

