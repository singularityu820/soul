import { login, register, logout, getAllCookies, checkLoginStatus, targetUrl } from './auth.js';
import './style.css';
import Cookies from 'js-cookie';
// DOM 元素
let loginForm, registerForm, switchToRegister, switchToLogin, loginButton, registerButton;

// 初始化应用
function initApp() {
    setupElements();
    setupEventListeners();
    showLoginForm();
}

// 设置DOM元素引用
function setupElements() {
    loginForm = document.querySelector('#login-form');
    registerForm = document.querySelector('#register-form');
    switchToRegister = document.querySelector('#switch-to-register');
    switchToLogin = document.querySelector('#switch-to-login');
    loginButton = document.querySelector('#login-button');
    registerButton = document.querySelector('#register-button');
}

// 设置事件监听器
function setupEventListeners() {
    // 切换到注册表单
    switchToRegister.addEventListener('click', (e) => {
        e.preventDefault();
        showRegisterForm();
    });

    // 切换到登录表单
    switchToLogin.addEventListener('click', (e) => {
        e.preventDefault();
        showLoginForm();
    });

    // 登录表单提交
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        await handleLogin();
    });

    // 注册表单提交
    registerForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        await handleRegister();
    });

    // Cookie 操作按钮
    setupCookieButtons();
}

// 设置Cookie操作按钮
function setupCookieButtons() {
    // 在switch-forms div后添加Cookie操作按钮
    const switchFormsDiv = document.querySelector('.switch-forms');
    const cookieActionsDiv = document.createElement('div');
    cookieActionsDiv.className = 'cookie-actions';
    cookieActionsDiv.innerHTML = `
        <button type="button" id="showCookiesBtn" class="btn-secondary">🍪 查看Cookie</button>
        <button type="button" id="checkStatusBtn" class="btn-secondary">🔍 检查状态</button>
        <button type="button" id="logoutBtn" class="btn-danger">🚪 登出</button>
    `;
    
    // 将按钮添加到表单容器中
    switchFormsDiv.parentNode.insertBefore(cookieActionsDiv, switchFormsDiv.nextSibling);

    // 绑定事件
    document.getElementById('showCookiesBtn').addEventListener('click', handleShowCookies);
    document.getElementById('checkStatusBtn').addEventListener('click', handleCheckStatus);
    document.getElementById('logoutBtn').addEventListener('click', handleLogout);
}

// 显示登录表单
function showLoginForm() {
    loginForm.style.display = 'block';
    registerForm.style.display = 'none';
    switchToRegister.style.display = 'block';
    switchToLogin.style.display = 'none';
    clearMessages();
}

// 显示注册表单
function showRegisterForm() {
    loginForm.style.display = 'none';
    registerForm.style.display = 'block';
    switchToRegister.style.display = 'none';
    switchToLogin.style.display = 'block';
    clearMessages();
}

// 处理登录
async function handleLogin() {
    const username = document.querySelector('#login-username').value.trim();
    const password = document.querySelector('#login-password').value;
    const messageDiv = document.querySelector('#login-message');

    // 基础验证
    if (!username || !password) {
        showMessage(messageDiv, '请填写所有必填字段', 'error');
        return;
    }

    // 显示加载状态
    setButtonLoading(loginButton, true);

    try {
        await login(username, password).then((returnData)=>{
            let success = returnData.success;
            console.log(success);
            if (success) {
                showMessage(messageDiv, '登录成功！Cookie已设置', 'success');
            } else {
                showMessage(messageDiv, returnData.notice, 'error');
            }
        });
        
    } catch (error) {
        console.error('Login error:', error);
        showMessage(messageDiv, '登录失败，请稍后重试', 'error');
        throw new error(error);
    } finally {
        setButtonLoading(loginButton, false);
    }
}

// 处理注册
async function handleRegister() {
    const username = document.querySelector('#register-username').value.trim();
    const email = document.querySelector('#register-email').value.trim();
    const password = document.querySelector('#register-password').value;
    const confirmPassword = document.querySelector('#register-confirm-password').value;
    const messageDiv = document.querySelector('#register-message');

    // 基础验证
    if (!username || !email || !password || !confirmPassword) {
        showMessage(messageDiv, '请填写所有必填字段', 'error');
        return;
    }

    // 密码验证
    if (password !== confirmPassword) {
        showMessage(messageDiv, '密码不一致', 'error');
        return;
    }

    if (password.length < 6) {
        showMessage(messageDiv, '密码长度至少6位', 'error');
        return;
    }

    // 邮箱格式验证
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
        showMessage(messageDiv, '请输入有效的邮箱地址', 'error');
        return;
    }

    // 显示加载状态
    setButtonLoading(registerButton, true);

    try {
        const success = await register(username, email, password);
        
        if (success) {
            showMessage(messageDiv, '注册成功！', 'success');
        } else {
            showMessage(messageDiv, '注册失败，用户名或邮箱可能已存在', 'error');
        }
    } catch (error) {
        console.error('Register error:', error);
        showMessage(messageDiv, '注册失败，请稍后重试', 'error');
    } finally {
        setButtonLoading(registerButton, false);
    }
}

// 处理显示Cookie
function handleShowCookies() {
    try {
        getAllCookies();
        showMessage(document.querySelector('#login-message'), 'Cookie信息已在弹窗中显示', 'info');
    } catch (error) {
        console.error('Show cookies error:', error);
        showMessage(document.querySelector('#login-message'), '获取Cookie信息时发生错误', 'error');
    }
}

// 处理检查登录状态
function handleCheckStatus() {
    try {
        checkLoginStatus();
        showMessage(document.querySelector('#login-message'), '登录状态已在弹窗中显示', 'info');
    } catch (error) {
        console.error('Check status error:', error);
        showMessage(document.querySelector('#login-message'), '检查登录状态时发生错误', 'error');
    }
}

// 处理登出
async function handleLogout() {
    try {
        await logout();
        showMessage(document.querySelector('#login-message'), '登出成功，Cookie已清除', 'success');
    } catch (error) {
        console.error('Logout error:', error);
        showMessage(document.querySelector('#login-message'), '登出时发生错误', 'error');
    }
}

// 显示消息
function showMessage(element, message, type) {
    element.textContent = message;
    element.className = `message ${type}`;
    element.style.display = 'block';
}

// 清除消息
function clearMessages() {
    const messages = document.querySelectorAll('.message');
    messages.forEach(msg => {
        msg.style.display = 'none';
    });
}

// 设置按钮加载状态
function setButtonLoading(button, isLoading) {
    if (isLoading) {
        button.disabled = true;
        button.textContent = '处理中...';
    } else {
        button.disabled = false;
        button.textContent = button.id === 'login-button' ? '登录' : '注册';
    }
}

// DOM加载完成后初始化应用
document.addEventListener('DOMContentLoaded', initApp);

// 导出主要函数供测试使用
export { initApp, handleLogin, handleRegister };
if(typeof Cookies.get('username') ==="string")
{
    window.location.href = targetUrl;
}
