# OCR GUI Tool

基于 PaddleOCR-json 的 Windows OCR 桌面工具，采用 Fluent Design 界面，支持批量识别、模板提取、Excel 数据透视、检疫证查询等功能。

## 功能特点

- 🖼️ **截图识别** - 全局快捷键截图，即时 OCR 识别
- 📁 **批量识别** - 支持文件夹批量处理，识别中实时显示进度
- 🌐 **多语言支持** - 中文（简体/繁体）、英文、日文、韩文等
- 📋 **结果导出** - 支持 TXT / JSON / Excel 三种格式
- 📜 **历史记录** - 本地保存识别历史，可追溯查看
- 🎨 **现代界面** - Fluent Design 风格，支持亮色/暗色主题
- 📄 **模板管理** - 自定义解析规则，快速提取结构化信息
- 🔧 **性能优化** - 识别结果缓存、文件去重、内容去重
- ⚡ **异步处理** - TaskManager 统一调度，不阻塞界面
- 📊 **Excel 透视** - 数据清洗、透视表、大表虚拟滚动渲染
- 🔍 **检疫证查询** - 对接四川省动物检疫 API，支持 7 种证书类型
- 🔌 **EventBus** - 核心层主动推送状态变更，UI 自动响应

## 界面预览

### Fluent Design 界面
使用 PySide6-Fluent-Widgets 构建，符合 Windows 11 设计语言，提供现代化的用户体验。

## 技术栈

| 类别 | 技术 |
|------|------|
| OCR 引擎 | PaddleOCR-json |
| GUI 框架 | PySide6 + qfluentwidgets |
| 数据处理 | pandas + openpyxl |
| 语言 | Python 3.13+ |

## 架构

四层分层架构：

```
界面层 (UI Layer)  → CoreAPI (纯接口层)  → TaskManager (调度层)  → 执行器 (核心层)
```

界面层仅负责显示和交互，核心层完全不操作界面代码。EventBus 实现核心到界面的主动推送。

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
│   ├── PPOCR_api.py                 # PaddleOCR API 封装（不可修改）
│   └── core_api.py                  # 核心 API — 纯接口，不包含业务逻辑
│
├── core/                            # 核心业务逻辑
│   ├── config.py                    # 配置管理
│   ├── ocr_engine.py                # OCR 引擎封装
│   ├── screenshot.py                # 全局截图功能
│   ├── result_manager.py            # 结果管理 + 历史记录
│   ├── exporter.py                  # 结果导出 (TXT/JSON/Excel)
│   ├── task_manager.py              # 统一任务调度
│   ├── template_manager.py          # 模板管理
│   ├── text_parser.py               # 文本解析
│   ├── batch_events.py              # 批量事件定义
│   ├── batch_session.py             # 批量识别会话
│   ├── batch_session_worker.py      # 批量会话工作线程
│   ├── cert_query.py                # 检疫证查询 (API 对接)
│   ├── excel_models.py              # Excel 数据模型
│   ├── excel_processor.py           # Excel 清洗/透视
│   ├── log_context.py               # 日志上下文
│   ├── deduplication.py             # 去重功能
│   └── error_handler.py             # 错误处理
│
├── interfaces/                      # 界面层
│   └── fluent/                      # Fluent Design 界面
│       ├── main_window.py           # 主窗口 + 导航
│       ├── ui_utils.py              # 界面工具函数
│       ├── ui_config.py             # UI 配置
│       ├── error_ui.py              # 错误界面
│       ├── components/              # 组件
│       │   └── screenshot_window.py # 截图窗口
│       └── pages/                   # 页面
│           ├── ocr_page.py          # OCR 识别
│           ├── history_page.py      # 历史记录
│           ├── template_page.py     # 模板管理
│           ├── settings_page.py     # 设置
│           ├── cert_query_page.py   # 检疫证查询
│           └── excel_page.py        # Excel 数据透视
│
├── docs/                            # 文档
│   ├── PROJECT_MEMORY.md            # 项目记忆（架构约定+开发历史）
│   ├── API_REFERENCE.md
│   ├── DEVELOPER_GUIDE.md
│   └── ...
│
├── config/                          # 配置文件
├── templates/                       # 模板文件
├── tests/                           # 测试
├── PaddleOCR-json/                  # OCR 引擎（外部依赖）
├── main.py / run.py                 # 入口
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
| `exporter.py` | 结果导出功能，支持 TXT/JSON/Excel |
| `task_manager.py` | 统一任务调度，所有功能通过 TaskManager 执行 |
| `template_manager.py` | 模板管理，支持自定义解析规则 |
| `text_parser.py` | 文本解析，根据模板提取结构化信息 |
| `batch_events.py` | 批量识别事件定义 |
| `batch_session.py` | 批量识别会话状态管理 |
| `batch_session_worker.py` | 批量会话后台工作线程 |
| `cert_query.py` | 检疫证查询，对接四川省动物检疫 API |
| `excel_models.py` | Excel 数据清洗/透视数据模型 |
| `excel_processor.py` | Excel 加载/清洗/透视/导出核心执行器 |
| `deduplication.py` | 文件去重 + 内容去重（SimHash 精确匹配） |
| `error_handler.py` | 错误处理 |

### `interfaces/fluent/` - 界面实现

| 文件/目录 | 说明 |
|------|------|
| `main_window.py` | 主窗口，包含导航和页面管理 |
| `ui_utils.py` | 界面工具函数，统一管理中文对话框 |
| `ui_config.py` | UI 配置管理 |
| `error_ui.py` | 错误界面组件 |
| `pages/ocr_page.py` | OCR 识别页面（截图、拖拽、批量） |
| `pages/history_page.py` | 历史记录页面 |
| `pages/template_page.py` | 模板管理页面 |
| `pages/settings_page.py` | 设置页面（OCR 引擎、个性化） |
| `pages/cert_query_page.py` | 检疫证查询页面 |
| `pages/excel_page.py` | Excel 数据透视页面 |

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

### v2.3.0 (2026-06-03)
- 新增检疫证查询功能（7 种证书类型，API 对接 scahi.org.cn）
- 新增 Excel 数据透视模块（清洗/透视/虚拟滚动渲染）
- 重构为四层架构：UI → CoreAPI → TaskManager → Executors
- 新增 TaskManager 统一调度、EventBus 核心推送
- 删除旧 api_server 模块（架构迁移）
- 提取字段列智能显隐（无模板时自动隐藏）
- 导出原始文本开关移至 OCR 设置分组

### v2.2.0 (2026-05-29)
- 批量识别会话管理（batch_session）
- OCR 引擎优雅关闭机制（exit 指令 + 5s 超时 + taskkill 后备）
- StateToolTip 自动淡出修复
- 历史记录-缓存同步一致性修复
- 文件列表双击识别修复

### v2.1.0 (2026-05-08)
- 项目清理，删除 38 个测试/调试文件
- 新增 core/deduplication.py（去重功能）
- 更新工具栏布局为两行设计
- 完善中断机制文档

### v2.0.0 (2026-04-20)
- 添加模板管理功能，支持自定义解析规则
- 实现识别结果缓存
- 优化异步任务管理
- 统一 Fluent Design 界面风格

### v1.0.0 (2026-04-13)
- 初始版本发布

## License

MIT License

## 致谢

- [PaddleOCR-json](https://github.com/hiroi-sora/PaddleOCR-json) - OCR 引擎
- [PySide6-Fluent-Widgets](https://github.com/zhiyiYo/PySide6-Fluent-Widgets) - Fluent Design 组件库
