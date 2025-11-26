const express = require('express');
const { v4: uuidv4 } = require('uuid');

const app = express();
const PORT = 8000;

// 中间件：解析 JSON 请求体
app.use(express.json());

// 模拟数据库：内存存储
let diaries = [];

/**
 * 辅助函数：生成预览文本 (前50个字符)
 */
const generatePreview = (content) => {
    if (!content) return "";
    return content.length > 50 ? content.substring(0, 50) + "..." : content;
};

// --- 1. 创建日记 ---
// 接口地址: POST /diary/
app.post('/diary/', (req, res) => {
    const { user_id, title, content, emotion_tags, metadata } = req.body;

    // 简单的参数校验
    if (!user_id || !content) {
        return res.status(422).json({ detail: "Missing user_id or content" });
    }

    // 计算该用户的 entry_number (当前篇数 + 1)
    const userEntryCount = diaries.filter(d => d.user_id === user_id).length;

    const now = new Date().toISOString();

    const newDiary = {
        diary_id: uuidv4().replace(/-/g, ''), // 生成32位无横杠UUID
        user_id,
        title: title || "无标题",
        content,
        preview: generatePreview(content),
        entry_number: userEntryCount + 1,
        emotion_tags: emotion_tags || [],
        created_at: now,
        updated_at: now,
        metadata: metadata || {}
    };

    diaries.push(newDiary);

    // 返回创建成功的日记对象
    res.status(201).json(newDiary);
});

// --- 3. 更新日记 ---
// 接口地址: PUT /diary/{diary_id}
app.put('/diary/:diary_id', (req, res) => {
    const { diary_id } = req.params;
    const { title, content, emotion_tags, metadata } = req.body;

    // 查找日记索引
    const diaryIndex = diaries.findIndex(d => d.diary_id === diary_id);

    if (diaryIndex === -1) {
        return res.status(404).json({ detail: "Diary not found" });
    }

    const currentDiary = diaries[diaryIndex];
    const now = new Date().toISOString();

    // 更新字段 (如果请求中提供了新值则更新，否则保持原样)
    const updatedDiary = {
        ...currentDiary,
        title: title !== undefined ? title : currentDiary.title,
        content: content !== undefined ? content : currentDiary.content,
        emotion_tags: emotion_tags !== undefined ? emotion_tags : currentDiary.emotion_tags,
        metadata: metadata !== undefined ? metadata : currentDiary.metadata,
        updated_at: now
    };

    // 如果内容变了，重新生成预览
    if (content !== undefined) {
        updatedDiary.preview = generatePreview(content);
    }

    // 保存回数组
    diaries[diaryIndex] = updatedDiary;

    res.json(updatedDiary);
});
// --- [新增] 4. 删除日记 ---
// 接口地址: DELETE /diary/{diary_id}
app.delete('/diary/:diary_id', (req, res) => {
    const { diary_id } = req.params;
    const diaryIndex = diaries.findIndex(d => d.diary_id === diary_id);

    if (diaryIndex === -1) {
        return res.status(404).json({ detail: "Diary not found" });
    }

    diaries.splice(diaryIndex, 1);
    res.status(204).send();
});
// --- 5. 获取用户日记列表 ---
// 接口地址: GET /diary/user/{user_id}
app.get('/diary/user/:user_id', (req, res) => {
    const { user_id } = req.params;
    // 获取分页参数，默认为 limit=10, offset=0
    const limit = parseInt(req.query.limit) || 10;
    const offset = parseInt(req.query.offset) || 0;

    // 筛选该用户的日记
    const userDiaries = diaries.filter(d => d.user_id === user_id);
    
    // 按时间倒序排列 (通常日记列表是看最新的)
    // 注意：API文档没明确指明排序，但通常Web开发中列表默认按创建时间倒序
    userDiaries.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

    // 执行分页
    const paginatedDiaries = userDiaries.slice(offset, offset + limit);

    const responseData = {
        diaries: paginatedDiaries,
        total: userDiaries.length
    };

    res.json(responseData);
});

// 启动服务器
app.listen(PORT, () => {
    console.log(`Server is running on http://localhost:${PORT}`);
    console.log(`Time: ${new Date().toLocaleString()}`);
});