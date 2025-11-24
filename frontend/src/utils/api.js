import Cookies from "js-cookie";

// 服务器基础URL
const serverUrl = "http://localhost:8000/api/diary";

// 获取最新日记文本
export const getLatestDiaryText = async (username) => {
  try {
    const response = await fetch(`${serverUrl}/user/${username}/latest`, {
      method: 'GET',
      credentials: 'include', // 包含cookies
      headers: {
        'Content-Type': 'application/json'
      }
    });
    if (!response.ok) {
      if (response.status === 404) {
        return { content: "您还没有写过日记", entry_number: 0, total_count: 0 };
      }
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data = await response.json();
    
    // 获取日记总数
    try {
      const countResponse = await fetch(`${serverUrl}/user/${username}/count`);
      if (countResponse.ok) {
        const countData = await countResponse.json();
        data.total_count = countData.count || 0;
      } else {
        data.total_count = 0;
      }
    } catch (error) {
      console.error("获取日记总数失败:", error);
      data.total_count = 0;
    }
    
    return data;
  } catch (error) {
    console.error("获取最新日记失败:", error);
    return { content: "获取日记失败，请稍后再试", entry_number: 0, total_count: 0 };
  }
};

// 获取最近聊天记录
export const getRecentMessages = async (username, limit = 3) => {
  try {
    const response = await fetch(`http://localhost:8000/chat/user/${username}/recent?limit=${limit}`, {
      method: 'GET',
      credentials: 'include', // 包含cookies
      headers: {
        'Content-Type': 'application/json'
      }
    });
    
    if (!response.ok) {
      if (response.status === 401) {
        console.error("用户未登录或Cookie已过期");
        return [];
      }
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const data = await response.json();
    console.log("获取到的聊天记录:", data);
    return data.messages || data || [];
  } catch (error) {
    console.error("获取聊天记录失败:", error);
    // 如果获取失败，返回空数组
    return [];
  }
};

// 获取用户信息
export const getUserInfo = async () => {
  try {
    const userId = Cookies.get("userId");
    const username = Cookies.get("username");
    if (!userId || !username) {
      throw new Error("用户未登录");
    }
    
    // 由于后端没有专门的用户信息API，使用日记API获取用户信息
    const response = await fetch(`${serverUrl}/user/${userId}/count`);
    if (response.ok) {
      const data = await response.json();
      // 返回用户信息，包含日记数量
      return {
        userId: userId,
        username: username,
        diaryCount: data.count || 0,
        avatar: Cookies.get("avatar") || "avatar1"
      };
    } else {
      throw new Error(`获取用户信息失败: ${response.status}`);
    }
  } catch (error) {
    console.error("获取用户信息失败:", error);
    const userId = Cookies.get("userId");
    const username = Cookies.get("username");
    return {
      userId: userId,
      username: username,
      diaryCount: 0,
      avatar: Cookies.get("avatar") || "avatar1"
    };
  }
};

// 用户登录
export const login = async (username, password) => {
  try {
    // 由于后端没有认证API，使用本地验证
    // 在实际应用中，这里应该调用后端API进行验证
    const users = JSON.parse(localStorage.getItem("users") || "{}");
    
    if (!users[username]) {
      return { success: false, error: "用户不存在" };
    }
    
    if (users[username].password !== password) {
      return { success: false, error: "密码错误" };
    }
    
    Cookies.set("username", username, { expires: 7 }); // 7天有效期
    return { success: true, message: "登录成功" };
  } catch (error) {
    console.error("登录失败:", error);
    return { success: false, error: "登录失败" };
  }
};

// 用户登出
export const logout = async () => {
  try {
    // 由于使用本地验证，只需清除本地cookie
    Cookies.remove("username");
    return { success: true, message: "登出成功" };
  } catch (error) {
    console.error("登出失败:", error);
    return { success: false, error: "登出失败" };
  }
};

// 用户注册
export const register = async (username, password) => {
  try {
    // 由于后端没有注册API，使用本地存储
    // 在实际应用中，这里应该调用后端API进行注册
    const users = JSON.parse(localStorage.getItem("users") || "{}");
    
    if (users[username]) {
      return { success: false, error: "用户名已存在" };
    }
    
    // 保存用户信息到本地存储
    users[username] = {
      password: password,
      createdAt: new Date().toISOString()
    };
    localStorage.setItem("users", JSON.stringify(users));
    
    return { success: true, message: "注册成功" };
  } catch (error) {
    console.error("注册失败:", error);
    return { success: false, error: "注册失败" };
  }
};

// 检查登录状态
export const checkLoginStatus = () => {
  const username = Cookies.get("username");
  return !!username;
};