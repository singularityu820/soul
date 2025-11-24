import React, { useState } from "react";
import "./styles/index.css";
import { login, register } from "../../auth.js";

export default function LoginModal({ onClose, onLoginSuccess }) {
  const [isLogin, setIsLogin] = useState(true); // true: 登录模式, false: 注册模式
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setMessage("");

    try {
      let result;
      if (isLogin) {
        result = await login(username, password);
      } else {
        result = await register(username, email, password);
      }

      if (result.success) {
        setMessage(isLogin ? "登录成功！" : "注册成功！");
        setTimeout(() => {
          onLoginSuccess();
          // 登录成功后跳转到用户界面
          if (window.navigate) {
            window.navigate("#/user");
          } else {
            window.location.hash = "#/user";
          }
        }, 1000);
      } else {
        setMessage(result.error || result.notice || (isLogin ? "登录失败" : "注册失败"));
      }
    } catch (error) {
      console.error(isLogin ? "登录错误:" : "注册错误:", error);
      setMessage("操作失败，请稍后再试");
    } finally {
      setIsLoading(false);
    }
  };

  const toggleMode = () => {
    setIsLogin(!isLogin);
    setMessage("");
    setUsername("");
    setPassword("");
    setEmail("");
  };

  return (
    <div className="login-modal">
      <div className="login-container">
        <div className="login-header">
          <h2>LetPrLogin</h2>
          <p>欢迎回来 - 登录或创建新账户</p>
        </div>
        <h3 className="form-title">{isLogin ? "登录" : "注册"}</h3>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="username">用户名</label>
            <input
              type="text"
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>
          {!isLogin && (
            <div className="form-group">
              <label htmlFor="email">邮箱</label>
              <input
                type="email"
                id="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
          )}
          <div className="form-group">
            <label htmlFor="password">密码</label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          {message && <div className="message">{message}</div>}
          <div className="form-actions">
            <button type="submit" disabled={isLoading}>
              {isLoading ? "处理中..." : (isLogin ? "登录" : "注册")}
            </button>
          </div>
        </form>
        <p className="toggle-text">
            {isLogin ? "还没有账户? " : "已有账号？ "}
            <span onClick={toggleMode}>
                {isLogin ? "立即注册" : "立即登录"}
            </span>
        </p>

      </div>
    </div>
  );
}