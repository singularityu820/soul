# 日记API接口文档

## 概述
本文档描述了日记存储模块的所有API接口，包括请求参数和响应数据的JSON格式示例。

## 基础信息
- **基础URL**: `http://localhost:8000`
- **Content-Type**: `application/json`
- **认证方式**: 暂无（后续可添加JWT等认证机制）

---

## 1. 创建日记

### 接口地址
`POST /diary/`

### 请求参数
```json
{
  "user_id": "test_user_001",
  "title": "我的第一篇日记",
  "content": "今天天气真好，阳光明媚。我决定开始写日记，记录生活中的点点滴滴。这是一个很好的习惯，可以帮助我更好地了解自己。",
  "emotion_tags": ["开心", "平静", "思考"],
  "metadata": {
    "location": "北京",
    "weather": "晴天",
    "mood_score": 8
  }
}
```

### 响应数据
```json
{
  "diary_id": "c5d100025f92459f80b6688c34b7979e",
  "user_id": "test_user_001",
  "title": "我的第一篇日记",
  "content": "今天天气真好，阳光明媚。我决定开始写日记，记录生活中的点点滴滴。这是一个很好的习惯，可以帮助我更好地了解自己。",
  "preview": "今天天气真好，阳光明媚。我决定开始写日记，记录生活中的点点滴滴。这是一个很好的习惯，可以帮助我更好地...",
  "entry_number": 1,
  "emotion_tags": ["开心", "平静", "思考"],
  "created_at": "2023-11-18T15:30:00.000Z",
  "updated_at": "2023-11-18T15:30:00.000Z",
  "metadata": {
    "location": "北京",
    "weather": "晴天",
    "mood_score": 8
  }
}
```

---

## 2. 获取日记详情

### 接口地址
`GET /diary/{diary_id}`

### 路径参数
- `diary_id`: 日记ID，例如：`c5d100025f92459f80b6688c34b7979e`

### 响应数据
```json
{
  "diary_id": "c5d100025f92459f80b6688c34b7979e",
  "user_id": "test_user_001",
  "title": "我的第一篇日记",
  "content": "今天天气真好，阳光明媚。我决定开始写日记，记录生活中的点点滴滴。这是一个很好的习惯，可以帮助我更好地了解自己。",
  "preview": "今天天气真好，阳光明媚。我决定开始写日记，记录生活中的点点滴滴。这是一个很好的习惯，可以帮助我更好地...",
  "entry_number": 1,
  "emotion_tags": ["开心", "平静", "思考"],
  "created_at": "2023-11-18T15:30:00.000Z",
  "updated_at": "2023-11-18T15:30:00.000Z",
  "metadata": {
    "location": "北京",
    "weather": "晴天",
    "mood_score": 8
  }
}
```

### 错误响应（404）
```json
{
  "detail": "Diary not found"
}
```

---

## 3. 更新日记

### 接口地址
`PUT /diary/{diary_id}`

### 路径参数
- `diary_id`: 日记ID，例如：`c5d100025f92459f80b6688c34b7979e`

### 请求参数
```json
{
  "title": "更新后的日记标题",
  "content": "这是更新后的日记内容。今天我学到了很多新知识，感觉很有收获。",
  "emotion_tags": ["成长", "思考", "满足"],
  "metadata": {
    "location": "上海",
    "weather": "多云",
    "mood_score": 7,
    "updated_reason": "补充了今天的收获"
  }
}
```

### 响应数据
```json
{
  "diary_id": "c5d100025f92459f80b6688c34b7979e",
  "user_id": "test_user_001",
  "title": "更新后的日记标题",
  "content": "这是更新后的日记内容。今天我学到了很多新知识，感觉很有收获。",
  "preview": "这是更新后的日记内容。今天我学到了很多新知识，感觉很有收获。",
  "entry_number": 1,
  "emotion_tags": ["成长", "思考", "满足"],
  "created_at": "2023-11-18T15:30:00.000Z",
  "updated_at": "2023-11-18T16:45:00.000Z",
  "metadata": {
    "location": "上海",
    "weather": "多云",
    "mood_score": 7,
    "updated_reason": "补充了今天的收获"
  }
}
```

### 错误响应（404）
```json
{
  "detail": "Diary not found"
}
```

---

## 4. 删除日记

### 接口地址
`DELETE /diary/{diary_id}`

### 路径参数
- `diary_id`: 日记ID，例如：`c5d100025f92459f80b6688c34b7979e`

### 响应数据
成功删除时返回空响应，状态码为204 No Content。

### 错误响应（404）
```json
{
  "detail": "Diary not found"
}
```

---

## 5. 获取用户日记列表

### 接口地址
`GET /diary/user/{user_id}`

### 路径参数
- `user_id`: 用户ID，例如：`test_user_001`

### 查询参数
- `limit`: 可选，限制返回的日记数量，默认为10
- `offset`: 可选，偏移量，用于分页，默认为0

### 响应数据
```json
{
  "diaries": [
    {
      "diary_id": "a6b6d465aa4e4de9902bf6d415caebd7",
      "user_id": "test_user_001",
      "title": "第二篇测试日记",
      "content": "今天工作很顺利，完成了一个重要的项目。晚上和朋友一起吃饭，聊了很多有趣的话题。感觉生活充实而有意义。",
      "preview": "今天工作很顺利，完成了一个重要的项目。晚上和朋友一起吃饭，聊了很多有趣的话题。感觉生活充实而有意义。",
      "entry_number": 2,
      "emotion_tags": ["开心", "社交", "满足"],
      "created_at": "2023-11-18T16:00:00.000Z",
      "updated_at": "2023-11-18T16:00:00.000Z",
      "metadata": {
        "location": "北京",
        "activity": "聚餐"
      }
    },
    {
      "diary_id": "c5d100025f92459f80b6688c34b7979e",
      "user_id": "test_user_001",
      "title": "更新后的日记标题",
      "content": "这是更新后的日记内容。今天我学到了很多新知识，感觉很有收获。",
      "preview": "这是更新后的日记内容。今天我学到了很多新知识，感觉很有收获。",
      "entry_number": 1,
      "emotion_tags": ["成长", "思考", "满足"],
      "created_at": "2023-11-18T15:30:00.000Z",
      "updated_at": "2023-11-18T16:45:00.000Z",
      "metadata": {
        "location": "上海",
        "weather": "多云",
        "mood_score": 7
      }
    }
  ],
  "total": 2
}
```

---

## 6. 获取用户最新日记

### 接口地址
`GET /diary/user/{user_id}/latest`

### 路径参数
- `user_id`: 用户ID，例如：`test_user_001`

### 响应数据
```json
{
  "diary_id": "a6b6d465aa4e4de9902bf6d415caebd7",
  "user_id": "test_user_001",
  "title": "第二篇测试日记",
  "content": "今天工作很顺利，完成了一个重要的项目。晚上和朋友一起吃饭，聊了很多有趣的话题。感觉生活充实而有意义。",
  "preview": "今天工作很顺利，完成了一个重要的项目。晚上和朋友一起吃饭，聊了很多有趣的话题。感觉生活充实而有意义。",
  "entry_number": 2,
  "emotion_tags": ["开心", "社交", "满足"],
  "created_at": "2023-11-18T16:00:00.000Z",
  "updated_at": "2023-11-18T16:00:00.000Z",
  "metadata": {
    "location": "北京",
    "activity": "聚餐"
  }
}
```

### 错误响应（404）
```json
{
  "detail": "No diaries found for this user"
}
```

---

## 7. 获取日记预览列表

### 接口地址
`GET /diary/user/{user_id}/previews`

### 路径参数
- `user_id`: 用户ID，例如：`test_user_001`

### 查询参数
- `limit`: 可选，限制返回的日记数量，默认为10
- `offset`: 可选，偏移量，用于分页，默认为0

### 响应数据
```json
{
  "previews": [
    {
      "diary_id": "a6b6d465aa4e4de9902bf6d415caebd7",
      "title": "第二篇测试日记",
      "preview": "今天工作很顺利，完成了一个重要的项目。晚上和朋友一起吃饭，聊了很多有趣的话题。感觉生活充实而有意义。",
      "entry_number": 2,
      "created_at": "2023-11-18T16:00:00.000Z"
    },
    {
      "diary_id": "c5d100025f92459f80b6688c34b7979e",
      "title": "更新后的日记标题",
      "preview": "这是更新后的日记内容。今天我学到了很多新知识，感觉很有收获。",
      "entry_number": 1,
      "created_at": "2023-11-18T15:30:00.000Z"
    }
  ],
  "total": 2
}
```

---

## 8. 搜索日记

### 接口地址
`GET /diary/user/{user_id}/search`

### 路径参数
- `user_id`: 用户ID，例如：`test_user_001`

### 查询参数
- `query`: 必需，搜索关键词
- `limit`: 可选，限制返回的日记数量，默认为10
- `offset`: 可选，偏移量，用于分页，默认为0

### 响应数据
```json
{
  "diaries": [
    {
      "diary_id": "c5d100025f92459f80b6688c34b7979e",
      "user_id": "test_user_001",
      "title": "更新后的日记标题",
      "content": "这是更新后的日记内容。今天我学到了很多新知识，感觉很有收获。",
      "preview": "这是更新后的日记内容。今天我学到了很多新知识，感觉很有收获。",
      "entry_number": 1,
      "emotion_tags": ["成长", "思考", "满足"],
      "created_at": "2023-11-18T15:30:00.000Z",
      "updated_at": "2023-11-18T16:45:00.000Z",
      "metadata": {
        "location": "上海",
        "weather": "多云",
        "mood_score": 7
      }
    }
  ],
  "total": 1,
  "query": "知识"
}
```

---

## 9. 获取用户日记总数

### 接口地址
`GET /diary/user/{user_id}/count`

### 路径参数
- `user_id`: 用户ID，例如：`test_user_001`

### 响应数据
```json
{
  "count": 5
}
```

---

## 10. 获取情绪标签统计

### 接口地址
`GET /diary/user/{user_id}/emotion-tags`

### 路径参数
- `user_id`: 用户ID，例如：`test_user_001`

### 响应数据
```json
{
  "emotion_tags": [
    {
      "tag": "开心",
      "count": 3
    },
    {
      "tag": "平静",
      "count": 2
    },
    {
      "tag": "思考",
      "count": 4
    },
    {
      "tag": "成长",
      "count": 2
    },
    {
      "tag": "满足",
      "count": 2
    },
    {
      "tag": "社交",
      "count": 1
    }
  ],
  "total_tags": 6,
  "total_mentions": 14
}
```

---

## 数据字段说明

### 通用字段
- `diary_id`: 日记唯一标识符，32位十六进制字符串
- `user_id`: 用户唯一标识符
- `title`: 日记标题
- `content`: 日记完整内容
- `preview`: 日记预览内容，自动生成，通常为内容的前50个字符
- `entry_number`: 用户日记序号，从1开始递增
- `emotion_tags`: 情绪标签列表，用于标记日记中的情绪
- `created_at`: 创建时间，ISO 8601格式
- `updated_at`: 最后更新时间，ISO 8601格式
- `metadata`: 元数据，JSON格式，可存储任意附加信息

### 分页参数
- `limit`: 每页返回的记录数，默认为10
- `offset`: 偏移量，用于分页，默认为0

---

## 错误响应格式

所有错误响应都遵循FastAPI的标准格式：

```json
{
  "detail": "错误描述信息"
}
```

常见HTTP状态码：
- 200: 成功
- 201: 创建成功
- 204: 删除成功（无内容返回）
- 404: 资源未找到
- 422: 请求参数验证失败
- 500: 服务器内部错误