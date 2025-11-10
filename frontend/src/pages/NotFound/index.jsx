import React from "react";
import "./styles/index.css";

export default function NotFound() {
  return (
    <div className="nf-root">
      <div className="nf-bg" aria-hidden="true" />
      <div className="nf-content">
        <h2>页面未找到</h2>
        <p>请检查路径或返回首页</p>
        <button className="ghost-btn" onClick={() => window.navigate("#/")}>返回首页</button>
      </div>
    </div>
  );
}


