# 使用百度云API进行面部情绪识别

本指南说明如何配置和使用百度云API替代DeepFace进行面部情绪识别。

## 为什么使用百度云API？

- **更高的准确率**：百度云的人脸情绪识别API通常比本地DeepFace模型具有更高的准确率
- **无需本地计算资源**：情绪检测在云端进行，不消耗本地计算资源
- **更好的稳定性**：云端服务通常比本地部署的模型更加稳定
- **数据格式兼容性**：已确保与现有系统完全兼容

## 配置步骤

### 1. 获取百度云API凭证

1. 访问[百度云AI开放平台](https://ai.baidu.com/)
2. 注册并登录账号
3. 创建应用，选择"人脸识别"服务
4. 获取API Key和Secret Key

### 2. 配置API凭证

编辑`backend/baidu_api_config.env`文件，填入您的API凭证：

```env
BAIDU_API_KEY=your_api_key_here
BAIDU_SECRET_KEY=your_secret_key_here
```

或者，您也可以直接在环境变量中设置这些值。

### 3. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

新增的依赖包括：
- `aiohttp>=3.8.0` - 用于异步HTTP请求
- `python-dotenv>=1.0.0` - 用于加载环境变量

## 使用方法

### 在代码中使用

```python
from app.services.emotion.face import FaceEmotionTool

# 创建FaceEmotionTool实例，使用百度云API
face_emotion_tool = FaceEmotionTool(
    use_deepface=False,  # 禁用DeepFace
    use_baidu_api=True,  # 启用百度云API
    baidu_api_key="your_api_key",
    baidu_secret_key="your_secret_key"
)

# 检测情绪
result = await face_emotion_tool.detect_from_frame(frame, frame_width=640, frame_height=480)
print(f"情绪: {result['emotion']}, 置信度: {result['confidence']}")
```

### 运行测试示例

```bash
cd backend
python test_baidu_emotion.py
```

### 测试数据格式兼容性

```bash
cd backend
python test_baidu_format.py
```

## 数据格式兼容性

为了确保百度云API与现有系统完全兼容，我们进行了以下修改：

### 1. 返回数据格式

百度云API现在返回以下格式的数据：

```json
{
  "emotion": "happy",
  "confidence": 0.85,
  "face_position": [
    {
      "x": 100,
      "y": 150,
      "width": 120,
      "height": 150
    }
  ],
  "face_bbox": {
    "x": 100,
    "y": 150,
    "width": 120,
    "height": 150
  },
  "timestamp": 1625097600.0
}
```

### 2. 关键修改点

1. **添加face_position数组**：确保前端可以正确处理人脸位置信息
2. **保留face_bbox对象**：保持与后端其他组件的兼容性
3. **统一情绪标签**：将百度云API的情绪标签映射到系统期望的格式
4. **统一置信度格式**：确保置信度值为浮点数

### 3. 情绪标签映射

百度云API的情绪标签已映射到系统期望的格式：

| 百度云API标签 | 系统标签 |
|--------------|---------|
| happy | happy |
| sad | sad |
| angry | angry |
| surprised | surprised |
| fear | fear |
| disgust | disgust |
| pouty | sad |
| grimace | disgust |

## API限制

百度云人脸识别API有以下限制：

- 免费用户：每天最多2,000次调用
- 付费用户：根据购买的套餐有不同的QPS限制
- 图片大小：不能超过10MB
- 图片格式：支持JPG、PNG、BMP等常见格式

请确保您的使用量符合API的限制要求。

## 故障排除

### 1. API凭证错误

如果看到"Failed to get access token"错误，请检查您的API Key和Secret Key是否正确。

### 2. 网络连接问题

确保您的服务器可以访问百度云API端点：
- `https://aip.baidubce.com/oauth/2.0/token`
- `https://aip.baidubce.com/rest/2.0/face/v3/detect`

### 3. 数据格式不兼容

```
错误: face_position格式不正确
```

解决方案：确保使用最新版本的代码，已修复数据格式兼容性问题

### 4. 图像格式问题

百度云API要求图像为Base64编码的JPEG格式。我们的代码已经处理了这一转换。

### 5. 未检测到人脸

```
警告: 未检测到人脸
```

解决方案：检查图像质量和人脸角度，确保人脸清晰可见

## 从DeepFace迁移到百度云API

如果您想从DeepFace迁移到百度云API，只需：

1. 按照上述步骤配置百度云API
2. 在创建FaceEmotionTool实例时设置`use_deepface=False`和`use_baidu_api=True`
3. 其余代码无需修改，接口保持一致

## 混合使用

您也可以同时配置DeepFace和百度云API，系统会优先使用百度云API，如果失败则回退到DeepFace：

```python
face_emotion_tool = FaceEmotionTool(
    use_deepface=True,  # 启用DeepFace作为备用
    use_baidu_api=True,  # 启用百度云API作为主要选择
    baidu_api_key="your_api_key",
    baidu_secret_key="your_secret_key"
)
```

## 性能优化建议

1. **缓存访问令牌**：百度云API的访问令牌有效期为30天，建议缓存以减少API调用
2. **图像预处理**：适当调整图像大小和质量，减少传输时间
3. **异步处理**：使用异步调用避免阻塞主线程
4. **错误重试**：实现适当的错误重试机制

## 更新日志

- **2023-07-01**: 初始版本，基本百度云API集成
- **2023-07-05**: 添加数据格式兼容性修复
- **2023-07-10**: 优化错误处理和回退机制