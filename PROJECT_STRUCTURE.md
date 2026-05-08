# OCR GUI Tool - 项目结构说明

> **版本**: v2.1.0
> **最后更新**: 2026-05-08
> **技术栈**: Python 3.10+ | PySide6 | qfluentwidgets | PaddleOCR-json | FastAPI

---

## 📁 项目目录树

```
OCR-GUI-Tool/
│
├── 📄 main.py                           # 主入口（启动 Fluent 界面）
├── 📄 run.py                            # 快速测试入口（推荐 IDE 调试）
├── 📄 requirements.txt                   # Python 依赖清单
├── 📄 requirements-dev.txt               # 开发依赖
├── 📄 pytest.ini                        # pytest 配置
├── 📄 README.md                         # 项目使用说明
├── 📄 PROJECT_STRUCTURE.md              # 本文件 - 项目结构说明
│
├── 🔧 core/                             # 核心业务逻辑层
│   ├── __init__.py
│   ├── config.py                        # 配置管理器
│   ├── ocr_engine.py                    # OCR 引擎封装
│   ├── result_manager.py                # 识别结果管理器
│   ├── exporter.py                      # 结果导出器（TXT/Excel）
│   ├── template_manager.py              # 模板管理器
│   ├── text_parser.py                   # 文本解析器
│   ├── screenshot.py                     # 截图功能
│   ├── async_worker.py                  # 异步工作线程
│   ├── deduplication.py                 # 去重功能
│   ├── error_handler.py                 # 错误处理
│   └── enhanced_error_handler.py        # 增强错误处理
│
├── 🎨 interfaces/                        # 界面层
│   ├── __init__.py
│   │
│   └── fluent/                          # ⭐ Fluent Design 界面
│       ├── __init__.py
│       ├── main_window.py               # 主窗口（导航栏 + 页面切换）
│       ├── ui_utils.py                   # 界面工具函数
│       ├── ui_config.py                  # UI 配置管理
│       ├── error_ui.py                   # 错误界面组件
│       │
│       ├── components/                   # 可复用组件
│       │   └── screenshot_window.py     # 截图窗口
│       │
│       └── pages/                       # 页面组件
│           ├── __init__.py
│           ├── ocr_page.py              # OCR 识别页面
│           ├── history_page.py          # 历史记录页面
│           ├── template_page.py         # 模板管理页面
│           └── settings_page.py         # 设置页面
│
├── 🔌 api/                              # API 接口层
│   ├── __init__.py
│   ├── PPOCR_api.py                     # PaddleOCR API 封装
│   ├── core_api.py                      # 核心 API
│   └── ocr_api.py                       # OCR 接口
│
├── 🖥️ api_server/                       # API 服务端（可选）
│   ├── __init__.py
│   ├── main.py                          # FastAPI 主应用
│   ├── adapter.py                       # API 适配器
│   ├── client.py                        # API 客户端
│   │
│   ├── routes/                          # 路由层
│   │   ├── __init__.py
│   │   ├── ocr_routes.py               # OCR 相关路由
│   │   └── task_routes.py              # 任务相关路由
│   │
│   ├── services/                        # 业务服务层
│   │   └── ocr_service.py
│   │
│   ├── tasks/                           # 异步任务管理层
│   │   └── task_manager.py
│   │
│   └── utils/                           # 工具公共层
│       ├── exceptions.py
│       └── response.py
│
├── 🧪 tests/                            # 单元测试
│   ├── __init__.py
│   ├── test_config.py                  # 配置管理测试
│   ├── test_result_manager.py          # 结果管理测试
│   ├── test_exporter.py                 # 导出功能测试
│   ├── test_error_handler.py           # 错误处理测试
│   ├── test_error_ui.py                # 错误界面测试
│   ├── test_data_baohuodan.txt         # 测试数据：报货单样本
│   └── test_data_jianyi.txt            # 测试数据：简易样本
│
├── 📦 PaddleOCR-json/                   # OCR 引擎（外部依赖）
│   ├── PaddleOCR-json.exe
│   ├── *.dll
│   └── models/                          # OCR 模型文件
│
├── 📝 templates/                        # ⭐ 解析模板存储目录
│   ├── 576b8c32.json                   # 通用模板
│   ├── animal_quarantine.json          # 动物检疫证明模板
│   ├── baohuodan.json                  # 报货单模板
│   └── jianyi.json                     # 简易模板
│
├── 📂 config/                           # 配置目录
│   ├── config.json                     # 用户配置
│   └── ui_config.json                  # UI 配置
│
└── 📚 docs/                             # 文档
    ├── API_REFERENCE.md
    ├── DEVELOPER_GUIDE.md
    ├── OPTIMIZATION_SUMMARY.md
    ├── PERFORMANCE_MONITORING.md
    └── interrupt_mechanism.md
```

---

## 🏗️ 架构分层

### 1️⃣ **核心层 (core/)** - 业务逻辑

| 模块 | 职责 | 关键类/函数 |
|------|------|-------------|
| `config.py` | 配置持久化、读取、验证 | `ConfigManager`, `get_config_manager()` |
| `ocr_engine.py` | OCR 引擎进程管理、通讯 | `OCREngine`, `get_ocr_engine()` |
| `result_manager.py` | 识别结果存储、查询 | `ResultManager`, `get_result_manager()` |
| `exporter.py` | 结果导出（TXT/Excel） | `Exporter`, `get_exporter()` |
| `template_manager.py` | 模板 CRUD、序列化 | `TemplateManager`, `ParseTemplate`, `ParseRule` |
| `text_parser.py` | 基于模板的文本解析 | `TextParser` |
| `screenshot.py` | Windows 截图 API 封装 | `ScreenshotManager`, `capture_screen()` |
| `async_worker.py` | 异步任务调度 | `AsyncWorker`, `TaskManager` |
| `deduplication.py` | 识别结果去重 | `Deduplicator` |
| `error_handler.py` | 错误处理 | `ErrorHandler` |
| `enhanced_error_handler.py` | 增强错误处理 | `EnhancedErrorHandler` |

**设计模式**:
- **单例模式**: 所有管理器通过 `get_xxx()` 获取全局唯一实例
- **观察者模式**: 信号槽机制通知 UI 更新
- **工厂模式**: 根据配置创建不同语言的 OCR 引擎

---

### 2️⃣ **界面层 (interfaces/fluent/)** - 用户交互

#### 主窗口 (`main_window.py`)

```
MainWindow (FluentWindow)
├── initWindow()          # 窗口属性（尺寸、标题、居中）
├── initCore()            # 初始化核心模块
├── initNavigation()      # 创建页面并注册导航项
├── connectSignals()      # 连接跨页面信号
└── closeEvent()          # 清理资源（停止线程、关闭引擎）
```

**导航结构**:
```
顶部导航:
  ├─ 🔍 文字识别 (ocr_page)
  ├─ 🏷️ 模板管理 (template_page)
  └─ 📜 识别历史 (history_page)

底部导航:
  └─ ⚙️ 设置 (settings_page)
```

#### 页面组件

| 页面 | 文件 | 功能 |
|------|------|------|
| OCR 识别 | `ocr_page.py` | 截图识别、拖拽图片、批量处理、结果显示 |
| 模板管理 | `template_page.py` | 模板 CRUD、规则编辑、解析预览测试 |
| 识别历史 | `history_page.py` | 历史列表、详情查看、删除记录 |
| 设置 | `settings_page.py` | 引擎路径、模型目录、语言、自动检测 |

#### 可复用组件

| 组件 | 文件 | 用途 |
|------|------|------|
| 截图窗口 | `screenshot_window.py` | 全屏遮罩、十字光标、矩形选区 |
| 错误界面 | `error_ui.py` | 错误展示组件 |

---

### 3️⃣ **API 层 (api/)** - 外部接口

| 模块 | 说明 |
|------|------|
| `ocr_api.py` | 封装 OCR 引擎的 HTTP/API 调用 |
| `PPOCR_api.py` | PaddleOCR 原生 API 兼容层 |
| `core_api.py` | 核心 API 封装 |

---

### 4️⃣ **API 服务端 (api_server/)** - 可选服务端架构

```
api_server/
├── main.py              # FastAPI 应用入口
├── adapter.py           # API 适配器（桥接 core 层）
├── client.py            # API 客户端
│
├── routes/              # 路由层
│   ├── ocr_routes.py   # OCR 相关接口
│   └── task_routes.py  # 任务管理接口
│
├── services/            # 业务服务层
│   └── ocr_service.py
│
├── tasks/               # 异步任务管理
│   └── task_manager.py
│
└── utils/               # 工具层
    ├── exceptions.py
    └── response.py
```

---

### 5️⃣ **测试层 (tests/)** - 质量保证

| 测试文件 | 覆盖模块 | 测试内容 |
|----------|----------|----------|
| `test_config.py` | `core/config.py` | 配置读写、默认值、路径验证 |
| `test_result_manager.py` | `core/result_manager.py` | 结果增删改查、持久化 |
| `test_exporter.py` | `core/exporter.py` | TXT/Excel 导出格式、编码 |
| `test_error_handler.py` | `core/error_handler.py` | 错误处理逻辑 |
| `test_error_ui.py` | `interfaces/fluent/error_ui.py` | 错误界面组件 |
| `test_data_*.txt` | - | 测试数据样本 |

**运行测试**:
```bash
pytest tests/ -v
```

---

### 6️⃣ **模板层 (templates/)** - 解析模板

| 文件 | 说明 |
|------|------|
| `576b8c32.json` | 通用解析模板 |
| `animal_quarantine.json` | 动物检疫证明解析模板 |
| `baohuodan.json` | 报货单解析模板 |
| `jianyi.json` | 简易解析模板 |

---

## 🔄 数据流

### 典型识别流程

```
用户操作 (截图/拖拽)
    ↓
screenshot.py / ocr_page.py
    ↓
ocr_engine.py (启动 PaddleOCR-json.exe)
    ↓
PaddleOCR-json 进程 (返回 JSON 结果)
    ↓
result_manager.py (保存结果到历史)
    ↓
ocr_page.py (更新 UI 显示)
    ↓
exporter.py (可选：导出为 TXT/Excel)
```

### 模板解析流程

```
用户选择模板 + 输入文本
    ↓
template_manager.py (从 templates/ 加载模板)
    ↓
text_parser.py (应用规则解析：keyword/regex/position)
    ↓
template_page.py (显示解析结果表格)
    ↓
用户可保存为新模板或修改现有模板
```

---

## 🚀 启动流程

### `main.py` 执行顺序

```python
1. 添加项目路径到 sys.path
2. 检查依赖 (PySide6, qfluentwidgets)
3. 设置高 DPI 支持
4. 创建 QApplication
5. 设置应用元数据 (名称、版本)
6. 设置主题 (Theme.AUTO - 跟随系统)
7. 创建 MainWindow 实例
   ├─ initWindow()      # 窗口属性
   ├─ initCore()        # 核心模块
   ├─ initNavigation()  # 页面和导航
   └─ loadTranslator()  # 国际化
8. 显示窗口
9. 进入事件循环 (app.exec())
```

### `run.py` vs `main.py`

| 特性 | `main.py` | `run.py` |
|------|-----------|----------|
| 用途 | 正式入口 | IDE 快速测试 |
| 参数 | 无 | 无 |
| 日志 | 无 | 无 |
| 单实例检查 | 无 | 无 |
| 适用场景 | 命令行启动 | F5 直接运行 |

---

## 📦 依赖说明

### 必需依赖

```txt
PySide6>=6.5.0              # Qt6 绑定（GUI 框架）
PySide6-Fluent-Widgets      # Fluent Design 组件库
Pillow>=9.0.0               # 图片处理
openpyxl>=3.0.0             # Excel 导出
pyperclip>=1.8.0            # 剪贴板操作
```

### 可选依赖

```txt
pytest>=7.0.0               # 单元测试框架
fastapi>=0.100.0           # API 服务端
uvicorn>=0.22.0             # ASGI 服务器
```

---

## 📝 文件统计

| 类别 | 文件数 |
|------|--------|
| 核心模块 (core/) | 11 |
| 界面代码 (interfaces/fluent/) | 10 |
| 测试代码 (tests/) | 8 |
| API 层 (api/) | 4 |
| API 服务端 (api_server/) | 9 |
| 配置文件 | 4 |
| **总计** | **46** |

---

## 🔮 未来规划

### 短期 (v2.2)
- [ ] 支持自定义快捷键
- [ ] 增加更多导出格式（PDF）
- [ ] 优化批量识别性能

### 中期 (v2.5)
- [ ] 云端同步历史记录
- [ ] AI 辅助模板生成
- [ ] API 服务端文档完善

### 长期 (v3.0)
- [ ] 跨平台支持（Linux、macOS）
- [ ] 实时识别（摄像头输入）
- [ ] 协作功能（多人共享模板）

---

## 📞 联系方式

- **GitHub**: [Sinory77/OCR-GUI-Tool](https://github.com/Sinory77/OCR-GUI-Tool)
- **问题反馈**: 提交 Issue

---

**最后更新**: 2026-05-08
**维护者**: Sinory
