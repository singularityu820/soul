// 在浏览器控制台中暴露API函数
import { getInfoAtServer, writeInfoAtServer, testInfoAtServer, setHistoryShow, setRijiText } from './auth.js';

// 将函数暴露到全局作用域
if (typeof window !== 'undefined') {
    // 暴露到浏览器全局对象
    window.getInfoAtServer = getInfoAtServer;
    window.writeInfoAtServer = writeInfoAtServer;
    window.testInfoAtServer = testInfoAtServer;
    window.setHistoryShow = setHistoryShow;
    window.setRijiText = setRijiText;
    
    // 添加一些便利函数
    window.authAPI = {
    getInfoAtServer,
    writeInfoAtServer,
    testInfoAtServer,
    setHistoryShow,
    setRijiText,
    // 获取用户信息
        async getUserInfo(username) {
            console.log('🔍 正在获取用户信息...');
            try {
                const result = await getInfoAtServer(username);
                console.log('✅ 用户信息获取成功:', result);
                return result;
            } catch (error) {
                console.error('❌ 获取用户信息失败:', error);
                throw error;
            }
        },
        // 写入用户信息
        async setUserInfo(username, data) {
            console.log('📝 正在写入用户信息...');
            try {
                const result = await writeInfoAtServer(username, data);
                console.log('✅ 用户信息写入成功:', result);
                return result;
            } catch (error) {
                console.error('❌ 写入用户信息失败:', error);
                throw error;
            }
        }
    };
    
    // 在控制台显示可用函数
    console.log('🚀 Auth API 已暴露到控制台！');
    console.log('📋 可用函数:');
    console.log('  • getInfoAtServer(name) - 获取用户信息');
    console.log('  • writeInfoAtServer(name, data) - 写入用户信息');
    console.log('  • testInfoAtServer(name, testInfo) - 测试信息');
    console.log('  • setHistoryShow(index, avatarFileName, text) - 设置历史记录显示');
    console.log('  • setRijiText(text) - 设置日记文本');
    console.log('  • authAPI.getUserInfo(username) - 获取用户信息（增强版）');
    console.log('  • authAPI.setUserInfo(username, data) - 写入用户信息（增强版）');
    console.log('');
    console.log('💡 使用示例:');
    console.log('  getInfoAtServer("testuser")');
    console.log('  writeInfoAtServer("newuser", {message: "password123"})');
    console.log('  testInfoAtServer("testuser", "testdata")');
    console.log('  setHistoryShow(1, "head1.jpg", "更新后的历史记录内容")');
    console.log('  setRijiText("今天是个好日子")');
    console.log('  authAPI.getUserInfo("testuser")');
}

export default null;