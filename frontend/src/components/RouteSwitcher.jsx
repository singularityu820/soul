import React from "react";

export default function RouteSwitcher({ routes, current, onNavigate }) {
  const entries = Object.keys(routes);
  const labelOf = (path) => {
    switch (path) {
      case "#/":
        return "星空首页";
      // case "#/portal":
      //   return "星空入口";
      case "#/chatnew":
        return "新对话";
      case "#/portal-planb":
        return "星空入口(PlanB-3D)";
      case "#/kawaiichat":
        return "文本聊天";
      default:
        return path.replace(/^#\//, "");
    }
  };

  const handleChange = (e) => {
    const value = e.target.value;
    if (onNavigate) onNavigate(value);
    else window.location.hash = value;
  };

  return (
    <div className="route-switcher">
      <select value={current} onChange={handleChange} aria-label="页面切换">
        {entries.map((path) => (
          <option key={path} value={path}>
            {labelOf(path)}
          </option>
        ))}
      </select>
    </div>
  );
}


