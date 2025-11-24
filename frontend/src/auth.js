// 认证相关的API函数
import Cookies from 'js-cookie';
export const targetUrl = "http://localhost:5173/user.html";
export const LoginUrl = "http://localhost:5173/index.html";
const serverUrl = "http://localhost:8000";
export async function getInfoAtServer(name) {

    let response =await fetch(`${serverUrl}/info`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        type:"getInfo",
                        name:name
                    })
                });
    //结构
    /*{
     "code": 200,
     "data": "string"
    }
   */
  try
  {
    if (!response.ok) {
            throw new Error('getInfoAtServer response was not ok');
        }
    
    let JsonResponse =  await response.json();
    if(JsonResponse.code !== 200)
        throw new Error('getInfoAtServer responseCode was not ok');
    
    // 如果data为空字符串，返回空对象而不是尝试解析
    if (!JsonResponse.data || JsonResponse.data.trim() === '') {
      return {};
    }
    
    return JSON.parse(JsonResponse.data);
  } catch (e) {
    // 记录错误并向上层抛出，便于调试
    console.error('getInfoAtServer 异常:', e);
    return {username:"NULL"};
  }
    
}
export async function writeInfoAtServer(name,data)
{//data是一个JS对象
    let data_JSON = JSON.stringify(data);
    let response =await fetch(`${serverUrl}/info`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        type:"writeInfo",
                        name:name,
                        data:data_JSON
                    })
                });
    if (!response.ok) {
        throw new Error('writeInfoAtServer response was not ok');
    }
    return await response.json();
}
export async function testInfoAtServer(name,testInfo)
{
    
    try
    {
        await writeInfoAtServer(name,{message:testInfo});
        let temp = (await getInfoAtServer(name)).message;
        if(temp === testInfo)
        {
            return true;
        }else
        {
            return false;
        }
    }catch(e)
    {
        console.log("ERROR IN TESTINFOATSERVER");
        console.log(e);
        return false;
    }
    
}

/* 
    结构为
    username
    username-head
    username-message
*/
/**
 * 显示参数信息
 * @param {string} title - 标题
 * @param {Object} params - 参数对象
 */
function showParamsDialog(title, params) {
    const paramsText = Object.entries(params)
        .map(([key, value]) => `${key}: "${value}"`)
        .join('\n');
    
    console.log(`${title}\n\n${paramsText}`);
}

/**
 * 显示Cookie信息
 * @param {string} title - 标题
 * @param {Object} cookies - Cookie对象
 */
function showCookiesDialog(title, cookies) {
    const cookieText = Object.entries(cookies)
        .map(([key, value]) => `${key}: "${value}"`)
        .join('\n');
    
    console.log(`${title}\n\n${cookieText}`);
}



/**
 * 检查登录状态
 * @returns {boolean} 是否已登录
 */

// 检查登录状态
export function checkLoginStatus() {
    const username = Cookies.get('username');
    const isLoggedIn = !!username;
    
    console.log('=== 登录状态检查 ===');
    console.log(`用户名: ${username || '未设置'}`);
    console.log(`登录状态: ${isLoggedIn ? '已登录' : '未登录'}`);
    
    const status = isLoggedIn ? `当前用户: ${username}` : '未登录';
    console.log(`登录状态检查结果:\n${status}`);
    
    return isLoggedIn;
}

/**
 * 用户登录函数
 * @param {string} username - 用户名
 * @param {string} password - 密码
 * @returns {Promise<boolean>} - 登录结果
 */
export async function login(username, password) {
    // 显示传递给函数的参数
    showParamsDialog('🔐 登录函数被调用', { username, password });
    console.log('Login function called with:', { username, password });
    //用户信息是个对象，里面是key = username {message = "xxxx"}
    let messagePack = await getInfoAtServer(username)
    
        if(messagePack.message === password)
        {
            console.log('登录成功');
            Cookies.set('username', username, { expires: 7, path: '/' });
            // 同时设置用户ID作为Cookie，这里我们使用用户名作为用户ID
            Cookies.set('userId', username, { expires: 7, path: '/' });
            // 移除自动跳转，让组件处理跳转逻辑
            // skipToMain();
            return {success:true};
        }else if((typeof messagePack.message)==="string")
        {
            console.log("登录失败");
            return {success:false,notice:"密码错误"};
        }else{
            console.log("登录失败");
            return {success:false,notice:"用户不存在"};
        }
    
    
}

/**
 * 用户注册函数
 * @param {string} username - 用户名
 * @param {string} email - 邮箱
 * @param {string} password - 密码
 * @returns {Promise<boolean>} - 注册结果
 */
export async function register(username, email, password) {
    // 显示传递给函数的参数
    showParamsDialog('📝 注册函数被调用', { username, email, password });
    
    console.log('Register function called with:', { username, email, password });
    
    let messageData = await getInfoAtServer(username);
    if(messageData.message === password)
    {
        console.log(`该用户已存在`);
        return {success:false, notice:"用户名已存在"};
    }else
    {
        writeInfoAtServer(username,{message:password});
        console.log(`✅ 注册成功!\n\n用户名: ${username}\n邮箱: ${email}`);
        // 移除自动登录，让组件处理登录逻辑
        // if(await login(username, password))
        // {
        //     return true;
        // }
        // else
        // {
        //     console.log("注册后无法登录");
        //     throw new Error("注册后无法登录");
        //     return false;
        // }
        return {success:true};
    }
    
}

/**
 * 用户登出函数
 * @returns {Promise<boolean>} - 登出结果
 */
export async function logout() {
    // 显示传递给函数的参数（无参数）
    showParamsDialog('🚪 登出函数被调用', { info: '无参数' });
    
    console.log('Logout function called');
    
    // 清除用户名 Cookie
    Cookies.remove('username');
    
    console.log('🍪 用户名 Cookie 已清除');
    
    console.log('Logout successful');
    return true;
}

/**
 * 获取所有Cookie信息
 * @returns {Object} 当前所有Cookie
 */
export function getAllCookies() {
    const allCookies = Cookies.get();
    
    // 显示所有Cookie信息
    showCookiesDialog('🍪 当前所有Cookie', allCookies);
    
    return allCookies;
}
function skipToMain()
{
    // 使用React路由系统跳转到用户界面
    if (window.navigate) {
        window.navigate("#/user");
    } else {
        window.location.hash = "#/user";
    }
}

/**
 * 设置历史记录显示
 * @param {number} index - 第几条记录 (1-3)
 * @param {string} avatarFileName - 头像文件名 (如 'head1.jpg', 'head2.jpg')
 * @param {string} text - 显示的文本内容
 * @returns {boolean} - 是否设置成功
 */
export function setHistoryShow(index, avatarFileName, text) {
    // 验证参数
    if (typeof index !== 'number' || index < 1 || index > 3) {
        console.error('索引必须是1到3之间的数字');
        return false;
    }
    
    if (typeof avatarFileName !== 'string' || !avatarFileName) {
        console.error('头像文件名不能为空');
        return false;
    }
    
    if (typeof text !== 'string') {
        console.error('文本内容必须是字符串');
        return false;
    }
    
    try {
        // 只在浏览器环境中执行DOM操作
        if (typeof window !== 'undefined') {
            const itemElement = document.getElementById(`historyItem${index}`);
            const avatarElement = document.querySelector(`#historyItem${index} .history-avatar`);
            const textElement = document.getElementById(`historyText${index}`);
            
            if (itemElement && avatarElement && textElement) {
                // 设置头像
                avatarElement.src = `./img/${avatarFileName}`;
                avatarElement.alt = '头像';
                
                // 设置文本
                textElement.textContent = text;
                
                console.log(`历史记录${index}已更新: 头像=${avatarFileName}, 文本=${text}`);
                return true;
            } else {
                console.error('未找到历史记录元素');
                return false;
            }
        } else {
            console.error('当前环境不是浏览器环境');
            return false;
        }
    } catch (error) {
        console.error('设置历史记录时出错:', error);
        return false;
    }
}

/**
 * 设置日记文本显示
 * @param {string} text - 要显示的日记文本内容
 * @returns {boolean} - 是否设置成功
 */
export function setRijiText(text) {
    // 验证参数
    if (typeof text !== 'string') {
        console.error('文本内容必须是字符串');
        return false;
    }
    
    try {
        // 只在浏览器环境中执行DOM操作
        if (typeof window !== 'undefined') {
            const textElement = document.getElementById('rijiText');
            
            if (textElement) {
                // 设置文本内容
                textElement.textContent = text;
                
                console.log(`日记文本已更新: ${text.length > 50 ? text.substring(0, 50) + '...' : text}`);
                return true;
            } else {
                console.error('未找到日记文本元素');
                return false;
            }
        } else {
            console.error('当前环境不是浏览器环境');
            return false;
        }
    } catch (error) {
        console.error('设置日记文本时出错:', error);
        return false;
    }
}
async function setUserShows()
{
    let diaryText = await getLatestDiaryText(userId);
   // let historyData  = await 
}
/**
 * 获取指定用户的最新日记文本
 * @param {string} userId - 用户ID (例如: 'test_user_001')
 * @returns {Promise<string|null>} - 成功则返回日记正文(content)，没有日记或出错返回 null
 */
async function getLatestDiaryText(userId) {
    if (!userId) {
        console.error("User ID is required");
        return null;
    }

    const url = `${API_BASE}/diary/user/${userId}/latest`;

    try {
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Accept': 'application/json'
            }
            // 如果需要跨域携带 Cookie，请取消下面这行的注释
            // credentials: 'include' 
        });

        // 1. 处理 404 情况 (接口文档指明：No diaries found for this user)
        if (response.status === 404) {
            console.warn(`用户 ${userId} 还没有写过日记。`);
            return null;
        }

        // 2. 处理其他 HTTP 错误
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        // 3. 解析 JSON 并提取 content 字段
        const data = await response.json();
        
        // 打印完整数据方便调试（可选）
        console.log("获取到的日记信息:", data);

        return data.content; // 返回日记文本

    } catch (error) {
        console.error("获取日记失败:", error);
        return null;
    }
}