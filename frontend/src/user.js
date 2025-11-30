// user.html 专用JavaScript模块
import { checkLoginStatus, getAllCookies, getInfoAtServer, writeInfoAtServer, logout, LoginUrl } from './auth.js';
import Cookies from 'js-cookie';
/**
 * 页面专用工具函数
 */
const UserPageUtils = {
    /**
     * 显示用户信息
     * @param {string} username - 用户名
     */
    displayUserInfo(username) {
        const userInfoElement = document.getElementById('userInfo');
        if (userInfoElement) {
            userInfoElement.textContent = `当前用户: ${username}`;
            userInfoElement.style.color = '#4CAF50';
            userInfoElement.style.fontWeight = 'bold';
            userInfoElement.style.fontSize = '1.2em';
        }
        console.log('✅ 已登录用户:', username);
    },

    /**
     * 加载用户头像
     * @param {string} username - 用户名
     */
    async loadUserAvatar(username) {
        const avatarImg = document.getElementById('userAvatar');
        const avatarLoading = document.getElementById('avatarLoading');
        
        if (!avatarImg || !avatarLoading) {
            console.warn('❌ 未找到头像元素');
            return;
        }

        try {
            console.log('🖼️ 开始加载用户头像...');
            
            // 获取用户名+head的组合键
            const headInfo = await getInfoAtServer(`${username}-head`);
            
            console.log('🔍 头像信息响应:', headInfo);
            
            let avatarSrc = './img/head1.jpg'; // 默认头像
            
            if (headInfo && headInfo.message) {
                if (headInfo.message === 'head2') {
                    avatarSrc = './img/head2.jpg';
                    console.log('🎯 使用 head2 头像');
                } else if (headInfo.message === 'head1') {
                    avatarSrc = './img/head1.jpg';
                    console.log('🎯 使用 head1 头像');
                } else {
                    console.log('⚠️ 未知的头像类型，使用默认头像:', headInfo.message);
                }
            } else {
                console.log('⚠️ 未找到头像信息，使用默认头像');
            }
            
            // 设置头像源
            avatarImg.src = avatarSrc;
            
            // 头像加载完成后显示
            avatarImg.onload = () => {
                avatarLoading.style.display = 'none';
                avatarImg.style.display = 'block';
                console.log('✅ 头像加载成功:', avatarSrc);
            };
            
            // 如果加载失败，显示错误状态
            avatarImg.onerror = () => {
                avatarLoading.textContent = '头像加载失败';
                avatarLoading.style.color = '#ff6b6b';
                console.error('❌ 头像加载失败:', avatarSrc);
            };
            
        } catch (error) {
            console.error('❌ 加载头像时发生错误:', error);
            avatarLoading.textContent = '头像加载失败';
            avatarLoading.style.color = '#ff6b6b';
        }
    },

    /**
     * 显示加载状态
     */
    showLoadingStatus() {
        const userInfoElement = document.getElementById('userInfo');
        if (userInfoElement) {
            userInfoElement.textContent = '正在检查登录状态...';
            userInfoElement.style.color = '#FFA500';
        }
    },

    /**
     * 检查登录状态并处理
     */
    async checkLoginAndRedirect() {
        this.showLoadingStatus();
        
        // 获取用户名Cookie
        const username = Cookies.get('username');
        
        if (!username) {
            // 没有登录信息，跳转回首页
            console.warn('⚠️ 未检测到登录信息，正在跳转到登录页面...');
            window.location.href = '/';
            return false;
        } else {
            // 显示用户信息
            this.displayUserInfo(username);
            
            // 加载用户头像
            await this.loadUserAvatar(username);
            // 加载并展示游戏速率贴图
            await this.updateRateImage(username);
            
            return true;
        }
    },

    /**
     * 添加用户交互功能
     */
    addUserInteractions() {
        // 添加登出按钮事件
        this.addLogoutButton();
        
        // 添加用户信息刷新功能
        this.addRefreshButton();
        
        // 添加头像点击切换功能
        this.addAvatarClickHandler();
        
        // 添加日记图片点击跳转功能
        this.addRijiClickHandler();
        
        const username = Cookies.get('username');
        if (username) {
            setInterval(() => this.updateRateImage(username), 30000);
        }
    },
    
    /**
     * 添加日记图片点击跳转功能
     */
    addRijiClickHandler() {
        const rijiImg = document.querySelector('.riji-img');
        if (!rijiImg) {
            console.warn('❌ 未找到日记图片元素');
            return;
        }
        
        // 添加点击事件监听器
        rijiImg.addEventListener('click', () => {
            console.log('📝 点击日记图片，跳转到日记页面...');
            window.location.href = 'http://localhost:5173/#/';
        });
        
        // 添加鼠标悬停效果
        rijiImg.style.cursor = 'pointer';
        rijiImg.title = '点击进入日记页面';
        
        console.log('✅ 日记图片点击跳转功能已启用');
    },

    /**
     * 添加头像点击切换功能
     */
    addAvatarClickHandler() {
        const avatarImg = document.getElementById('userAvatar');
        if (!avatarImg) {
            console.warn('❌ 未找到头像元素');
            return;
        }

        // 移除之前的事件监听器（避免重复添加）
        avatarImg.removeEventListener('click', this.handleAvatarClick);
        
        // 创建处理函数并绑定到当前对象
        this.handleAvatarClick = () => {
            this.showAvatarModal();
        };

        // 添加点击事件监听器
        avatarImg.addEventListener('click', this.handleAvatarClick);
        
        // 添加鼠标悬停效果
        avatarImg.style.cursor = 'pointer';
        avatarImg.title = '点击选择头像';
        
        // 初始化弹窗
        this.initAvatarModal();
        
        console.log('✅ 头像点击选择功能已启用');
    },

    /**
     * 初始化头像选择弹窗
     */
    initAvatarModal() {
        // 绑定弹窗事件
        const modal = document.getElementById('avatarModal');
        const closeBtn = document.getElementById('modalClose');
        const cancelBtn = document.getElementById('cancelAvatar');
        const confirmBtn = document.getElementById('confirmAvatar');
        const avatarOptions = document.querySelectorAll('.avatar-option');

        if (!modal || !closeBtn || !cancelBtn || !confirmBtn) {
            console.warn('❌ 弹窗元素未找到');
            return;
        }

        // 关闭弹窗事件
        const closeModal = () => {
            modal.classList.remove('show');
            this.clearAvatarSelection();
        };

        closeBtn.addEventListener('click', closeModal);
        cancelBtn.addEventListener('click', closeModal);
        
        // 点击背景关闭弹窗
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeModal();
            }
        });

        // 头像选择事件
        avatarOptions.forEach(option => {
            option.addEventListener('click', () => {
                // 清除之前的选中状态
                avatarOptions.forEach(opt => opt.classList.remove('selected'));
                // 选中当前选项
                option.classList.add('selected');
            });
        });

        // 确认按钮事件
        confirmBtn.addEventListener('click', async () => {
            const selectedOption = document.querySelector('.avatar-option.selected');
            if (!selectedOption) {
                this.showTempMessage('⚠️ 请选择一个头像', 'info');
                return;
            }

            const selectedAvatar = selectedOption.dataset.avatar;
            await this.confirmAvatarSelection(selectedAvatar);
            closeModal();
        });

        console.log('✅ 弹窗事件绑定完成');
    },

    async updateRateImage(username) {
        try {
            const rateObj = await getInfoAtServer(`${username}-gamerate`);
            const rRaw = rateObj?.message?.rate;
            const rNum = typeof rRaw === 'number' ? rRaw : parseFloat(rRaw);
            
            // 只有当获取到有效rate值时才更新，否则保持当前状态
            if (!isNaN(rNum)) {
                const rate = Math.max(0, Math.min(1, rNum));
                const index = Math.max(0, Math.min(5, Math.round(rate * 5)));
                const imgEl = document.querySelector('.jindu-container .jindu-img');
                if (imgEl) {
                    imgEl.src = `./img/${index}.png`;
                }
                console.log('更新游戏速率贴图:', { rate, index });
            } else {
                console.warn('获取到无效的rate值，保持当前状态:', rRaw);
            }
        } catch (error) {
            console.warn('获取游戏速率失败，保持当前状态:', error);
        }
    },

    /**
     * 显示头像选择弹窗
     */
    async showAvatarModal() {
        const modal = document.getElementById('avatarModal');
        if (!modal) {
            console.warn('❌ 弹窗元素未找到');
            return;
        }

        // 获取当前头像信息并预选
        const username = Cookies.get('username');
        if (username) {
            try {
                const currentHeadInfo = await getInfoAtServer(`${username}-head`);
                const currentAvatarType = currentHeadInfo?.message || 'head1';
                
                // 预选当前头像
                const currentOption = document.querySelector(`[data-avatar="${currentAvatarType}"]`);
                if (currentOption) {
                    currentOption.classList.add('selected');
                }
            } catch (error) {
                console.warn('⚠️ 获取当前头像信息失败:', error);
            }
        }

        // 显示弹窗
        modal.classList.add('show');
    },

    /**
     * 清除头像选择状态
     */
    clearAvatarSelection() {
        const avatarOptions = document.querySelectorAll('.avatar-option');
        avatarOptions.forEach(option => {
            option.classList.remove('selected');
        });
    },

    /**
     * 确认头像选择
     */
    async confirmAvatarSelection(avatarType) {
        const username = Cookies.get('username');
        if (!username) {
            this.showTempMessage('❌ 未找到用户名，无法更换头像', 'error');
            return;
        }

        try {
            console.log(`🔄 更换头像为: ${avatarType}`);
            
            // 更新服务器数据
            await writeInfoAtServer(`${username}-head`, {
                message: avatarType
            });
            
            // 重新加载头像
            await this.loadUserAvatar(username);
            
        } catch (error) {
            console.error('❌ 头像更换失败:', error);
            this.showTempMessage('❌ 头像更换失败，请重试', 'error');
        }
    },

    /**
     * 显示临时消息
     * @param {string} message - 消息内容
     * @param {string} type - 消息类型 ('success' | 'error' | 'info')
     */
    showTempMessage(message, type = 'info') {
        // 移除已存在的消息
        const existingMessage = document.getElementById('tempMessage');
        if (existingMessage) {
            existingMessage.remove();
        }

        // 创建新消息元素
        const messageElement = document.createElement('div');
        messageElement.id = 'tempMessage';
        messageElement.textContent = message;
        
        // 设置样式
        const colors = {
            success: '#4CAF50',
            error: '#f44336',
            info: '#2196F3'
        };
        
        messageElement.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            background: ${colors[type]};
            color: white;
            border-radius: 4px;
            font-size: 14px;
            font-weight: bold;
            z-index: 10000;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            opacity: 0;
            transition: opacity 0.3s ease;
            max-width: 300px;
            word-wrap: break-word;
        `;

        // 添加到页面
        document.body.appendChild(messageElement);
        
        // 显示动画
        setTimeout(() => {
            messageElement.style.opacity = '1';
        }, 10);
        
        // 3秒后自动移除
        setTimeout(() => {
            messageElement.style.opacity = '0';
            setTimeout(() => {
                if (messageElement.parentNode) {
                    messageElement.parentNode.removeChild(messageElement);
                }
            }, 300);
        }, 3000);
    },

    /**
     * 添加登出按钮事件
     */
    addLogoutButton() {
        const logoutButton = document.getElementById('logoutButton');
        if (logoutButton) {
            logoutButton.addEventListener('click', async () => {
                if (confirm('确定要登出吗？')) {
                    try {
                        console.log('🚪 正在登出...');
                        logoutButton.disabled = true;
                        logoutButton.textContent = '⏳ 登出中...';
                        
                        // 执行登出操作
                        await logout();
                        
                        // 跳转到登录页面
                        console.log('🔗 跳转到登录页面:', LoginUrl);
                        window.location.href = LoginUrl;
                        
                    } catch (error) {
                        console.error('❌ 登出过程中发生错误:', error);
                        this.showTempMessage('❌ 登出失败，请重试', 'error');
                        
                        // 恢复按钮状态
                        logoutButton.disabled = false;
                        logoutButton.textContent = '登出';
                    }
                }
            });
            console.log('✅ 登出按钮事件绑定完成');
        } else {
            console.warn('❌ 未找到登出按钮元素');
        }
    },

    /**
     * 添加刷新按钮
     */
    addRefreshButton() {
        const container = document.querySelector('.container');
        if (container) {
            const refreshButton = document.createElement('button');
            refreshButton.textContent = '🔄 刷新用户信息';
            refreshButton.style.cssText = `
                margin-top: 15px;
                padding: 8px 16px;
                background: #2196F3;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
            `;
            
            refreshButton.addEventListener('click', async () => {
                refreshButton.disabled = true;
                refreshButton.textContent = '⏳ 刷新中...';
                
                await this.checkLoginAndRedirect();
                
                setTimeout(() => {
                    refreshButton.disabled = false;
                    refreshButton.textContent = '🔄 刷新用户信息';
                }, 1000);
            });
            
            container.appendChild(refreshButton);
        }
    },

    /**
     * 显示当前时间
     */
    showCurrentTime() {
        const timeElement = document.createElement('p');
        timeElement.id = 'currentTime';
        timeElement.style.cssText = `
            color: #666;
            font-size: 0.9em;
            margin-top: 10px;
        `;
        
        const updateTime = () => {
            const now = new Date();
            timeElement.textContent = `访问时间: ${now.toLocaleString('zh-CN')}`;
        };
        
        updateTime();
        setInterval(updateTime, 1000);
        
        const container = document.querySelector('.container');
        if (container) {
            container.appendChild(timeElement);
        }
    }
};

/**
 * 页面初始化函数
 */
async function initializeUserPage() {
    console.log('🚀 初始化用户页面...');
    
    // 无论登录状态如何，都添加日记图片点击事件
    UserPageUtils.addRijiClickHandler();
    
    // 检查登录状态
    const isLoggedIn = await UserPageUtils.checkLoginAndRedirect();
    
    if (isLoggedIn) {
        // 添加其他用户交互功能
        UserPageUtils.addLogoutButton();
        UserPageUtils.addRefreshButton();
        UserPageUtils.addAvatarClickHandler();
        
        // 显示当前时间
        UserPageUtils.showCurrentTime();
        
        // 添加页面可见性监听
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden && Cookies.get('username')) {
                // 页面重新可见时，刷新用户信息
                UserPageUtils.displayUserInfo(Cookies.get('username'));
            }
        });
        
        console.log('✅ 用户页面初始化完成');
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', initializeUserPage);

// 导出模块（如果需要在其他文件中使用）
export { UserPageUtils, initializeUserPage };
