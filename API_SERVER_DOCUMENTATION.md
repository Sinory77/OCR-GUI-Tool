# OCR-GUI API 服务重构文档

## 项目架构

### 目录结构
```
api_server/
├── main.py                 # FastAPI主应用
├── client.py               # API客户端
├── adapter.py              # API适配器
├── routes/                 # API路由层
│   ├── task_routes.py      # 任务相关路由
│   └── ocr_routes.py       # OCR相关路由
├── services/               # 业务服务层
│   └── ocr_service.py      # OCR服务
├── tasks/                  # 异步任务管理层
│   └── task_manager.py     # 任务管理器
└── utils/                  # 工具公共层
    ├── response.py         # 统一响应格式
    └── exceptions.py       # 异常处理
```

## API接口说明

### 任务管理接口

#### GET /task/{task_id}
查询任务状态
- 参数：task_id (路径参数)
- 返回：任务详细信息

#### POST /task/submit
提交异步任务（预留接口）

#### DELETE /task/{task_id}
取消任务
- 参数：task_id (路径参数)

#### GET /task/
列出所有任务

### OCR接口

#### POST /ocr/initialize
初始化OCR引擎

#### POST /ocr/recognize/single
同步识别单张图片
- 请求体：{"image_path": "图片路径"}

#### POST /ocr/recognize/single_async
异步识别单张图片
- 请求体：{"image_path": "图片路径"}
- 返回：task_id

#### POST /ocr/recognize/batch
同步批量识别图片
- 请求体：{"image_paths": ["图片路径1", "图片路径2", ...]}

#### POST /ocr/recognize/batch_async
异步批量识别图片
- 请求体：{"image_paths": ["图片路径1", "图片路径2", ...]}
- 返回：task_id

#### GET /ocr/config
获取配置

#### POST /ocr/config
更新配置
- 请求体：配置数据

#### GET /ocr/templates
获取模板

#### POST /ocr/export
导出结果
- 请求体：{"export_format": "格式", "output_path": "输出路径", "results": 结果数组}

#### POST /ocr/parse_text
解析文本
- 请求体：{"text": "文本内容", "template_id": "模板ID"}

#### POST /ocr/screenshot
截图
- 请求体：{"region": {"x": 0, "y": 0, "width": 100, "height": 100}}

## 统一响应格式

```json
{
  "success": true/false,
  "code": 200,
  "message": "描述信息",
  "data": {},
  "timestamp": "ISO时间戳"
}
```

## 任务状态

- pending: 待处理
- running: 运行中
- completed: 已完成
- failed: 执行失败
- cancelled: 已取消

## 启动命令

```bash
# 启动API服务器
python start_api.py

# 或者直接使用uvicorn
uvicorn api_server.main:app --host 127.0.0.1 --port 8000 --reload
```

## UI层调用示例

```python
from api_server.adapter import api_adapter

# 同步识别单张图片
result = api_adapter.recognize_single_image("path/to/image.jpg")
if result.success:
    print("识别成功:", result.data)
else:
    print("识别失败:", result.error.message)

# 异步识别单张图片
result = api_adapter.recognize_single_image_async("path/to/image.jpg")
if result.success:
    task_id = result.data['task_id']
    print(f"任务已提交，ID: {task_id}")
```

## 特性

1. **分层解耦**：UI界面层与业务逻辑完全分离
2. **异步任务**：所有计算、文件IO、数据处理在后台线程执行
3. **统一API**：提供标准化的任务提交和查询接口
4. **线程安全**：内置任务管理器确保线程安全
5. **错误处理**：全局异常捕获和处理
6. **向后兼容**：通过适配器保持与现有代码的兼容性
```