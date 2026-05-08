# OCR GUI Tool

基于 PaddleOCR-json 的 Windows OCR 截图识别工具，采用现代化的 Fluent Design 界面。

## 功能特点

- 🖼️ **截图识别** - 全局快捷键截图，即时 OCR 识别
- 📁 **批量识别** - 支持文件夹批量处理，递归扫描子目录
- 🌐 **多语言支持** - 中文（简体/繁体）、英文、日文、韩文等
- 📋 **结果处理** - 一键复制、导出 TXT/Excel
- 📜 **历史记录** - 本地保存识别历史，可追溯查看
- 🎨 **现代界面** - Fluent Design 风格，支持亮色/暗色主题
- 📄 **模板管理** - 自定义解析规则，快速提取结构化信息
- 🔧 **性能优化** - 识别结果缓存，提高重复识别速度
- ⚡ **异步处理** - 后台任务管理，不阻塞界面操作
- 🔌 **API 服务** - 可选的 API 服务端架构，支持远程调用

## 界面预览

### Fluent Design 界面
使用 PySide6-Fluent-Widgets 构建，符合 Windows 11 设计语言，提供现代化的用户体验。

## 技术栈

| 类别 | 技术 |
|------|------|
| OCR 引擎 | PaddleOCR-json |
| GUI 框架 | PySide6 + qfluentwidgets |
| API 框架 | FastAPI + Uvicorn |
| 语言 | Python 3.10+ |

## 安装

### 1. 克隆项目

```bash
git clone https://github.com/Sinory77/OCR-GUI-Tool.git
cd OCR-GUI-Tool
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 运行

```bash
# GUI 模式（推荐）
python run.py

# 或使用 main.py
python main.py
```

## 使用方法

### 快捷键

| 功能 | 快捷键 |
|------|--------|
| 截图识别 | `Ctrl + Shift + F` |
| 打开图片 | `Ctrl + O` |
| 打开文件夹 | `Ctrl + Shift + O` |
| 复制结果 | `Ctrl + C` |
| 导出结果 | `Ctrl + E` |

### 基本操作

1. **截图识别**
   - 按下 `Ctrl + Shift + F`，鼠标变为十字光标
   - 拖动选择区域，松开鼠标自动识别
   - 识别结果自动显示在界面中

2. **批量识别**
   - 点击"打开文件夹"或拖入文件夹
   - 设置扫描子目录（可选）
   - 点击开始识别，结果以表格展示

3. **语言切换**
   - 在识别页面直接选择识别语言
   - 支持语言：简体中文、English、繁体中文、日本語、한국어

4. **导出结果**
   - TXT 文本格式
   - Excel 表格格式（包含图片路径和识别结果）

5. **模板管理**
   - 点击导航栏中的"模板管理"进入模板管理页面
   - 新建模板，添加解析规则（关键字、正则表达式、行号等）
   - 测试解析规则，查看提取效果
   - 保存模板，用于快速提取结构化信息

## 项目结构

```
OCR-GUI-Tool/
├── api/                              # API 接口层
│   ├── __init__.py
│   ├── PPOCR_api.py                 # PaddleOCR API 封装
│   ├── core_api.py                  # 核心 API
│   └── ocr_api.py                   # OCR 接口
│
├── api_server/                       # API 服务端（可选）
│   ├── main.py                      # FastAPI 主应用
│   ├── adapter.py                   # API 适配器
│   ├── client.py                    # API 客户端
│   ├── routes/                      # 路由层
│   │   ├── ocr_routes.py           # OCR 路由
│   │   └── task_routes.py         # 任务路由
│   ├── services/                    # 业务服务层
│   │   └── ocr_service.py
│   ├── tasks/                       # 异步任务管理层
│   │   └── task_manager.py
│   └── utils/                       # 工具公共层
│       ├── exceptions.py
│       └── response.py
│
├── core/                            # 核心业务逻辑
│   ├── __init__.py
│   ├── config.py                    # 配置管理
│   ├── ocr_engine.py                # OCR 引擎封装
│   ├── screenshot.py                # 全局截图功能
│   ├── result_manager.py            # 结果管理
│   ├── exporter.py                  # 结果导出
│   ├── template_manager.py          # 模板管理
│   ├── text_parser.py               # 文本解析
│   ├── async_worker.py              # 异步任务管理
│   ├── deduplication.py            # 去重功能
│   ├── error_handler.py            # 错误处理
│   └── enhanced_error_handler.py   # 增强错误处理
│
├── interfaces/                      # 界面层
│   ├── __init__.py
│   └── fluent/                      # Fluent Design 界面
│       ├── __init__.py
│       ├── main_window.py           # 主窗口
│       ├── ui_utils.py              # 界面工具函数
│       ├── ui_config.py             # UI 配置
│       ├── error_ui.py              # 错误界面
│       ├── components/              # 组件
│       │   └── screenshot_window.py # 截图窗口
│       └── pages/                  # 页面组件
│           ├── __init__.py
│           ├── ocr_page.py          # OCR 识别页面
│           ├── history_page.py      # 历史记录页面
│           ├── template_page.py     # 模板管理页面
│           └── settings_page.py     # 设置页面
│
├── config/                          # 配置文件目录
│   ├── config.json                 # 用户配置
│   └── ui_config.json               # UI 配置
│
├── templates/                       # 模板文件
│   ├── 576b8c32.json               # 通用模板
│   ├── animal_quarantine.json      # 动物检疫证明模板
│   ├── baohuodan.json             # 报货单模板
│   └── jianyi.json                # 检疫证明模板
│
├── tests/                           # 测试文件
│   ├── __init__.py
│   ├── test_config.py              # 配置测试
│   ├── test_result_manager.py      # 结果管理测试
│   ├── test_exporter.py           # 导出测试
│   ├── test_error_handler.py      # 错误处理测试
│   ├── test_error_ui.py           # 错误界面测试
│   ├── test_data_baohuodan.txt   # 测试数据
│   └── test_data_jianyi.txt       # 测试数据
│
├── docs/                            # 文档
│   ├── API_REFERENCE.md            # API 参考
│   ├── DEVELOPER_GUIDE.md          # 开发者指南
│   ├── OPTIMIZATION_SUMMARY.md     # 优化总结
│   ├── PERFORMANCE_MONITORING.md   # 性能监控
│   └── interrupt_mechanism.md     # 中断机制文档
│
├── PaddleOCR-json/                  # OCR 引擎（外部依赖）
│   ├── PaddleOCR-json.exe
│   ├── *.dll
│   └── models/
│
├── main.py                           # 主入口
├── run.py                            # 快速测试入口
├── requirements.txt                  # Python 依赖
├── requirements-dev.txt              # 开发依赖
├── pytest.ini                        # pytest 配置
└── README.md
```

## 目录说明

### `core/` - 核心模块

| 文件 | 说明 |
|------|------|
| `config.py` | 配置文件读写，持久化用户设置 |
| `ocr_engine.py` | 封装 PaddleOCR-json 进程管理、通讯协议 |
| `screenshot.py` | 调用 Windows API 实现全局截图 |
| `result_manager.py` | 识别结果管理，包括历史记录和缓存 |
| `exporter.py` | 结果导出功能，支持 TXT 和 Excel 格式 |
| `template_manager.py` | 模板管理，支持自定义解析规则 |
| `text_parser.py` | 文本解析，根据模板提取结构化信息 |
| `async_worker.py` | 异步任务管理，提高用户体验 |
| `deduplication.py` | 识别结果去重 |
| `error_handler.py` | 错误处理 |
| `enhanced_error_handler.py` | 增强错误处理 |

### `interfaces/fluent/` - 界面实现

| 文件/目录 | 说明 |
|------|------|
| `main_window.py` | 主窗口，包含导航和页面管理 |
| `ui_utils.py` | 界面工具函数，统一管理中文对话框 |
| `ui_config.py` | UI 配置管理 |
| `error_ui.py` | 错误界面组件 |
| `components/screenshot_window.py` | 截图窗口组件 |
| `pages/ocr_page.py` | OCR 识别页面，包含截图、拖拽、批量识别功能 |
| `pages/history_page.py` | 历史记录页面，管理识别历史 |
| `pages/template_page.py` | 模板管理页面，创建和测试解析模板 |
| `pages/settings_page.py` | 设置页面，配置 OCR 引擎和应用参数 |

### `api_server/` - API 服务端

| 文件/目录 | 说明 |
|------|------|
| `main.py` | FastAPI 主应用入口 |
| `adapter.py` | API 适配器 |
| `client.py` | API 客户端 |
| `routes/` | API 路由 |
| `services/` | 业务服务层 |
| `tasks/` | 异步任务管理 |
| `utils/` | 工具函数 |

## 配置说明

配置文件位于 `config/config.json`：

```json
{
  "ocr_exe_path": "PaddleOCR-json/PaddleOCR-json.exe",
  "models_path": "PaddleOCR-json/models",
  "language": "简体中文",
  "auto_copy": true,
  "scan_subdirs": false,
  "theme": "跟随系统",
  "confidence_threshold": 50,
  "auto_detect": false,
  "long_image_mode": true,
  "slice_height": 2000,
  "slice_overlap": 100,
  "history_storage_limit": 100,
  "history_display_limit": 50
}
```

## 常见问题

### Q: 启动报错找不到 PaddleOCR-json.exe
**A**: 确保 `PaddleOCR-json/` 文件夹在项目根目录，配置文件中的路径正确。

### Q: 识别速度慢
**A**: 首次运行需要加载模型，后续会缓存。确保使用 SSD 存储。

### Q: 快捷键冲突
**A**: 在设置页面可以查看/修改快捷键配置。

### Q: 模板解析不准确
**A**: 调整模板中的解析规则，使用正则表达式可以提高准确性。

## 更新日志

### v2.1.0 (2026-05-08)
- 项目清理，删除 38 个测试/调试文件
- 新增 api_server 模块（API 服务端架构）
- 新增 core/deduplication.py（去重功能）
- 新增 core/enhanced_error_handler.py（增强错误处理）
- 新增 interfaces/fluent/ui_config.py（UI 配置）
- 更新工具栏布局为两行设计
- 完善中断机制文档

### v2.0.0 (2026-04-20)
- 优化项目结构，移除多余 UI 实现
- 添加模板管理功能，支持自定义解析规则
- 实现识别结果缓存，提高重复识别速度
- 优化异步任务管理，提升用户体验
- 统一界面风格，使用 Fluent Design
- 添加性能监控和优化
- 完善文档和测试

### v1.0.0 (2026-04-13)
- 初始版本发布
- 支持多种界面风格
- 多语言 OCR 识别
- 历史记录功能

## License

MIT License

## 致谢

- [PaddleOCR-json](https://github.com/hiroi-sora/PaddleOCR-json) - OCR 引擎
- [PySide6-Fluent-Widgets](https://github.com/zhiyiYo/PySide6-Fluent-Widgets) - Fluent Design 组件库
