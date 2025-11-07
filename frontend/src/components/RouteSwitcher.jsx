import React from "react";

export default function RouteSwitcher({ routes, current, onNavigate }) {
  const entries = Object.keys(routes);
  const labelOf = (path) => {
    switch (path) {
      case "#/":
        return "首页";
      case "#/portal":
        return "星空入口";
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


