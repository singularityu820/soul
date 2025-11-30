import React, { useState, useEffect, useRef } from "react";
import "./styles/index.css";
import Cookies from "js-cookie";
import { getLatestDiaryText, getRecentMessages, getUserInfo } from "../../utils/api";
import { getInfoAtServer, writeInfoAtServer } from "../../auth.js";

export default function UserCenter() {
  // 状态管理
  const [userInfo, setUserInfo] = useState(null);
  const [selectedAvatar, setSelectedAvatar] = useState(null);
  const [showAvatarModal, setShowAvatarModal] = useState(false);
  const [latestDiary, setLatestDiary] = useState("这里是日记内容，将通过JavaScript动态更新。最多显示4行文字，超出部分将会被省略。");
  const [diaryCount, setDiaryCount] = useState(0);
  const [recentMessages, setRecentMessages] = useState([]);
  const [tempMessage, setTempMessage] = useState("");
  const [gameProgress, setGameProgress] = useState({
    level: 1,
    experience: 0,
    nextLevelExp: 100,
    achievements: ["新手玩家", "首次登录"]
  });
  const [gameRate, setGameRate] = useState(0);
  
  // 引用
  const tempMessageTimeoutRef = useRef(null);

  // 初始化
  useEffect(() => {
    // 检查登录状态
    const username = Cookies.get("username");
    if (!username) {
      // 未登录，跳转到登录页
      window.navigate("#/");
      return;
    }
    
    const initializeData = async () => {
      // 加载用户信息
      await loadUserInfo();
      
      // 加载最新日记
      await loadLatestDiary();
      
      // 加载最近聊天记录
      await loadRecentMessages();
      
      // 加载游戏进度
      await loadGameProgress();
    };
    
    initializeData();
    
    // 设置定时器，每30秒从后端获取速率并影响前端展示
    const syncInterval = setInterval(async () => {
      const username = Cookies.get("username");
      if (username) {
        try {
          const rateObj = await getInfoAtServer(`${username}-gamerate`);
          const rRaw = rateObj?.message?.rate;
          const rNum = typeof rRaw === 'number' ? rRaw : parseFloat(rRaw);
          if (!isNaN(rNum)) {
            const clamped = Math.max(0, Math.min(1, rNum));
            setGameRate(clamped);
            console.log("定时获取并更新游戏速率成功:", clamped);
          }
        } catch (error) {
          console.log("定时获取游戏速率失败:", error);
        }
      }
    }, 30000);
    
    return () => clearInterval(syncInterval);
  }, []);

  // 加载游戏进度
  const loadGameProgress = async () => {
    try {
      const username = Cookies.get("username");
      if (username) {
        let rateLoaded = false;
        
        // 优先尝试从服务器获取游戏进度
        try {
          const rateObj = await getInfoAtServer(`${username}-gamerate`);
          const rRaw = rateObj?.message?.rate;
          const rNum = typeof rRaw === 'number' ? rRaw : parseFloat(rRaw);
          if (!isNaN(rNum)) {
            const clamped = Math.max(0, Math.min(1, rNum));
            setGameRate(clamped);
            rateLoaded = true;
            console.log("从服务器加载游戏速率成功:", clamped);
            
            // 根据rate值反推游戏进度
            const experience = Math.round(clamped * 100); // 假设nextLevelExp为100
            const gameProgress = {
              level: 1,
              experience: experience,
              nextLevelExp: 100,
              achievements: ["新手玩家", "首次登录"]
            };
            setGameProgress(gameProgress);
            localStorage.setItem(`gameProgress_${username}`, JSON.stringify(gameProgress));
          }
        } catch (serverError) {
          console.log("从服务器获取游戏进度失败，尝试本地存储:", serverError);
        }
        
        // 如果服务器没有加载到rate数据，再尝试从本地存储获取
        if (!rateLoaded) {
          const savedProgress = localStorage.getItem(`gameProgress_${username}`);
          
          if (savedProgress) {
            const localProgress = JSON.parse(savedProgress);
            setGameProgress(localProgress);
            console.log("从本地存储加载游戏进度:", localProgress);
            
            // 尝试将本地数据同步到服务器
            try {
              const rate = localProgress.nextLevelExp > 0 ? localProgress.experience / localProgress.nextLevelExp : 0;
              await writeInfoAtServer(`${username}-gamerate`, { message: { rate } });
              setGameRate(Math.max(0, Math.min(1, rate)));
              console.log("本地游戏进度已同步到服务器");
            } catch (syncError) {
              console.log("同步本地游戏进度到服务器失败:", syncError);
            }
          } else {
            // 只有在服务器和本地都没有数据时，才初始化默认进度
            console.log("服务器和本地都没有游戏进度数据，初始化默认进度");
            const defaultProgress = {
              level: 1,
              experience: 0,
              nextLevelExp: 100,
              achievements: ["新手玩家", "首次登录"]
            };
            localStorage.setItem(`gameProgress_${username}`, JSON.stringify(defaultProgress));
            setGameProgress(defaultProgress);
            
            // 尝试将默认进度同步到服务器
            try {
              const rate = defaultProgress.nextLevelExp > 0 ? defaultProgress.experience / defaultProgress.nextLevelExp : 0;
              await writeInfoAtServer(`${username}-gamerate`, { message: { rate } });
              setGameRate(Math.max(0, Math.min(1, rate)));
              console.log("默认游戏进度已同步到服务器");
            } catch (syncError) {
              console.log("同步默认游戏进度到服务器失败:", syncError);
            }
          }
        }
      }
    } catch (error) {
      console.error("加载游戏进度失败:", error);
      showTempMessage("加载游戏进度失败");
    }
  };

  // 更新游戏进度
  const updateGameProgress = async (newProgress) => {
    try {
      const username = Cookies.get("username");
      if (username) {
        // 更新本地状态
        setGameProgress(newProgress);
        
        // 更新本地存储作为备份
        localStorage.setItem(`gameProgress_${username}`, JSON.stringify(newProgress));
        
        // 尝试将进度更新到服务器
        try {
          const rate = newProgress.nextLevelExp > 0 ? newProgress.experience / newProgress.nextLevelExp : 0;
          await writeInfoAtServer(`${username}-gamerate`, { message: { rate } });
          setGameRate(Math.max(0, Math.min(1, rate)));
          console.log("游戏进度已更新到服务器:", newProgress);
        } catch (serverError) {
          console.log("更新游戏进度到服务器失败，仅本地更新:", serverError);
        }
      }
    } catch (error) {
      console.error("更新游戏进度失败:", error);
      showTempMessage("更新游戏进度失败");
    }
  };

  // 添加经验值
  const addExperience = async (amount) => {
    setGameProgress(prev => {
      const newProgress = { ...prev };
      newProgress.experience += amount;
      
      // 检查是否升级
      while (newProgress.experience >= newProgress.nextLevelExp) {
        newProgress.experience -= newProgress.nextLevelExp;
        newProgress.level += 1;
        newProgress.nextLevelExp = Math.floor(newProgress.nextLevelExp * 1.5);
        
        // 添加新成就
        const achievement = `达到等级 ${newProgress.level}`;
        if (!newProgress.achievements.includes(achievement)) {
          newProgress.achievements.push(achievement);
        }
        
        showTempMessage(`恭喜升级到等级 ${newProgress.level}！`);
      }
      
      // 异步更新服务器和本地存储
      updateGameProgress(newProgress);
      
      return newProgress;
    });
  };

  // 添加成就
  const addAchievement = async (achievement) => {
    setGameProgress(prev => {
      if (!prev.achievements.includes(achievement)) {
        const newProgress = {
          ...prev,
          achievements: [...prev.achievements, achievement]
        };
        
        // 异步更新服务器和本地存储
        updateGameProgress(newProgress);
        
        showTempMessage(`获得新成就: ${achievement}`);
        return newProgress;
      }
      return prev;
    });
  };

  // 加载用户信息
  const loadUserInfo = async () => {
    try {
      const userInfo = await getUserInfo();
      if (userInfo) {
        setUserInfo(userInfo);
        // 确保用户ID和用户名一致
        if (userInfo.userId && userInfo.username) {
          Cookies.set('userId', userInfo.userId, { expires: 7, path: '/' });
          Cookies.set('username', userInfo.username, { expires: 7, path: '/' });
          
          // 获取用户头像
          const savedAvatar = Cookies.get(`avatar_${userInfo.username}`);
          if (savedAvatar) {
            setSelectedAvatar(savedAvatar);
          } else {
            // 如果没有保存的头像，显示选择弹窗
            setShowAvatarModal(true);
          }
        }
      }
    } catch (error) {
      console.error("加载用户信息失败:", error);
      showTempMessage("加载用户信息失败");
    }
  };

  // 加载最新日记
  const loadLatestDiary = async () => {
    try {
      const username = Cookies.get("username");
      console.log("loadLatestDiary: username =", username);
      if (username) {
        const diaryData = await getLatestDiaryText(username);
        console.log("loadLatestDiary: diaryData =", diaryData);
        
        // 处理各种可能的返回格式
        if (diaryData && diaryData.preview) {
          setLatestDiary(diaryData.preview);
          console.log("loadLatestDiary: 设置日记内容(diaryData.preview) =", diaryData.preview);
        } else if (diaryData && diaryData.content) {
          setLatestDiary(diaryData.content);
          console.log("loadLatestDiary: 设置日记内容(diaryData.content) =", diaryData.content);
        } else if (typeof diaryData === 'string') {
          setLatestDiary(diaryData);
          console.log("loadLatestDiary: 设置日记内容(string) =", diaryData);
        } else {
          console.log("loadLatestDiary: 未找到有效的日记内容，使用默认值");
          setLatestDiary("您还没有写过日记");
        }
        
        // 设置日记总数
        if (diaryData && diaryData.total_count !== undefined) {
          setDiaryCount(diaryData.total_count);
          console.log("loadLatestDiary: 设置日记总数 =", diaryData.total_count);
        } else {
          setDiaryCount(0);
        }
      } else {
        console.log("loadLatestDiary: 未找到username，使用默认值");
        setLatestDiary("请先登录");
        setDiaryCount(0);
      }
    } catch (error) {
      console.error("加载最新日记失败:", error);
      showTempMessage("加载最新日记失败");
      setLatestDiary("加载日记失败，请稍后再试");
      setDiaryCount(0);
    }
  };

  // 加载最近聊天记录
  const loadRecentMessages = async () => {
    try {
      const username = Cookies.get("username");
      console.log("loadRecentMessages: username =", username);
      if (username) {
        const messages = await getRecentMessages(username, 3);
        console.log("loadRecentMessages: 获取到的消息 =", messages);
        
        // 无论是否有消息，都更新状态
        if (messages && messages.length > 0) {
          // 转换消息格式以适应UI
          const formattedMessages = messages.map(msg => ({
            id: msg.message_id,
            text: msg.text,
            avatar: msg.role === "user" ? "head1" : "head2" // 根据角色选择头像
          }));
          setRecentMessages(formattedMessages);
          console.log("loadRecentMessages: 设置消息列表 =", formattedMessages);
        } else {
          // 如果没有消息，设置为空数组
          setRecentMessages([]);
          console.log("loadRecentMessages: 没有消息，设置为空数组");
        }
      } else {
        console.log("loadRecentMessages: 未找到username，设置为空数组");
        setRecentMessages([]);
      }
    } catch (error) {
      console.error("加载最近聊天记录失败:", error);
      showTempMessage("加载最近聊天记录失败");
      // 出错时也设置为空数组
      setRecentMessages([]);
    }
  };

  // 显示临时消息
  const showTempMessage = (message) => {
    setTempMessage(message);
    
    // 清除之前的定时器
    if (tempMessageTimeoutRef.current) {
      clearTimeout(tempMessageTimeoutRef.current);
    }
    
    // 3秒后隐藏消息
    tempMessageTimeoutRef.current = setTimeout(() => {
      setTempMessage("");
    }, 3000);
  };

  // 头像选择确认
  const handleAvatarConfirm = () => {
    if (selectedAvatar && userInfo) {
      // 保存用户头像选择
      Cookies.set(`avatar_${userInfo.username}`, selectedAvatar, { expires: 365 });
      setShowAvatarModal(false);
      showTempMessage("头像选择成功");
    }
  };

  // 头像选择取消
  const handleAvatarCancel = () => {
    setShowAvatarModal(false);
  };

  // 登出处理
  const handleLogout = async () => {
    try {
      // 清除用户名Cookie
      Cookies.remove("username");
      showTempMessage("登出成功");
      
      // 延迟跳转，让用户看到提示
      setTimeout(() => {
        window.navigate("#/");
      }, 1000);
    } catch (error) {
      console.error("登出失败:", error);
      showTempMessage("登出失败");
    }
  };

  // 刷新页面数据
  const handleRefresh = async () => {
    await loadUserInfo();
    await loadLatestDiary();
    await loadRecentMessages();
    await loadGameProgress();
    showTempMessage("数据已刷新");
  };

  // 处理进度条点击事件
  const handleProgressClick = () => {
    window.location.hash = "#/portal-planb";
  };

  // 处理通话记录点击事件
  const handleChatHistoryClick = () => {
    window.location.hash = "#/chatnew";
  };

  // 获取头像URL
  const getAvatarUrl = (avatarName) => {
    return `./img/${avatarName}.jpg`;
  };

  return (
    <div className="user-center">
      {/* 临时消息提示 */}
      {tempMessage && (
        <div className="temp-message">
          {tempMessage}
        </div>
      )}

      {/* 头像容器 */}
      <div className="avatar-container">
        {selectedAvatar ? (
          <img 
            src={getAvatarUrl(selectedAvatar)} 
            alt="用户头像" 
            className="avatar"
            onClick={() => setShowAvatarModal(true)}
          />
        ) : (
          <div className="avatar-loading">
            加载中...
          </div>
        )}
      </div>
      
      {/* 头像选择弹窗 */}
      {showAvatarModal && (
        <div className="avatar-modal">
          <div className="avatar-modal-content">
            <button className="modal-close" onClick={() => setShowAvatarModal(false)}>
              &times;
            </button>
            <h3 className="avatar-modal-title">选择头像</h3>
            <div className="avatar-options">
              <div 
                className={`avatar-option ${selectedAvatar === "head1" ? "selected" : ""}`}
                onClick={() => setSelectedAvatar("head1")}
              >
                <img src="./img/head1.jpg" alt="头像1" />
              </div>
              <div 
                className={`avatar-option ${selectedAvatar === "head2" ? "selected" : ""}`}
                onClick={() => setSelectedAvatar("head2")}
              >
                <img src="./img/head2.jpg" alt="头像2" />
              </div>
            </div>
            <div className="modal-buttons">
              <button className="modal-button cancel" onClick={handleAvatarCancel}>
                取消
              </button>
              <button className="modal-button confirm" onClick={handleAvatarConfirm}>
                确认
              </button>
            </div>
          </div>
        </div>
      )}
      
      {/* 刷新按钮 */}
      <div className="refresh-container">
        <button className="refresh-button" onClick={handleRefresh}>
          刷新
        </button>
      </div>
      
      {/* 登出按钮容器 */}
      <div className="logout-container">
        <button className="logout-button" onClick={handleLogout}>
          登出
        </button>
      </div>
      
      {/* 日记图片容器 */}
      <div className="riji-container">
        {/* 最新日记标题 */}
        <div className="diary-title">最新日记</div>
        {/* 日记文本显示区域 */}
        <div className="riji-text-container">
          <p className="riji-text">{latestDiary}</p>
        </div>
        {/* 日记总数显示 */}
        <div className="diary-count-badge">
          共{diaryCount}篇
        </div>
        <img src="./img/riji.png" alt="日记图片" className="riji-img" />
      </div>
      
      {/* 日记毛玻璃框 - 显示最近聊天记录 */}
      <div className="riji-glass-frame" onClick={handleChatHistoryClick} style={{ cursor: 'pointer' }}>
        <div className="chat-history-title">脑科小专家：小狐狸星屿</div>
        {recentMessages.length > 0 ? (
          recentMessages.map((message) => (
            <div key={message.id} className="history-item">
              <img 
                src={getAvatarUrl(message.avatar)} 
                alt="头像" 
                className="history-avatar"
              />
              <div className="history-content">
                <p className="history-text">{message.text}</p>
              </div>
            </div>
          ))
        ) : (
          <div className="no-messages">
            <p>暂无聊天记录</p>
          </div>
        )}
      </div>
      
      {/* 进度图片容器（根据后端 rate 切换贴图）*/}
      <div className="jindu-container" onClick={handleProgressClick} style={{ cursor: 'pointer' }}>
        <img src="./img/title.png" alt="标题" className="jindu-title" />
        {(() => {
          const index = Math.max(0, Math.min(5, Math.round(gameRate * 5)));
          const src = `./img/${index}.png`;
          return <img src={src} alt="进度图片" className="jindu-img" />;
        })()}
      </div>
    </div>
  );
}
