# OCR GUI Tool

基于 PaddleOCR-json 的 Windows OCR 截图识别工具，支持多种界面风格。

## 功能特点

- 🖼️ **截图识别** - 全局快捷键截图，即时 OCR 识别
- 📁 **批量识别** - 支持文件夹批量处理，递归扫描子目录
- 🌐 **多语言支持** - 中文（简体/繁体）、英文、日文、韩文、俄文等
- 📋 **结果处理** - 一键复制、导出 TXT/Excel
- 📜 **历史记录** - 本地保存识别历史，可追溯查看
- 🎨 **现代界面** - Fluent Design 风格，支持亮色/暗色主题

## 界面预览

### Fluent Design 界面（推荐）
使用 PySide6-Fluent-Widgets 构建，符合 Windows 11 设计语言。

### 其他界面
- PyQt6 风格
- Tkinter 简洁版
- Web 界面

## 技术栈

| 类别 | 技术 |
|------|------|
| OCR 引擎 | PaddleOCR-json |
| GUI 框架 | PySide6 + qfluentwidgets |
| 语言 | Python 3.10+ |

## 安装

### 1. 克隆项目

```bash
git clone https://github.com/Sinory77/OCR-GUI-Tool.git
cd OCR-GUI-Tool
```

### 2. 安装依赖

```bash
pip install PySide6 PySide6-Fluent-Widgets Pillow openpyxl pyperclip
```

### 3. 运行

```bash
python run_fluent.py
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
   - 在设置页面选择识别语言
   - 支持语言：中英日韩俄文等

4. **导出结果**
   - TXT 文本格式
   - Excel 表格格式（包含图片路径和识别结果）

## 项目结构

```
OCR-GUI-Tool/
├── core/                              # 核心业务逻辑
│   ├── __init__.py                    # 模块初始化
│   ├── config.py                      # 配置管理（读写 config.json）
│   ├── ocr_engine.py                  # OCR 引擎封装（启动进程、发送图片、解析结果）
│   ├── screenshot.py                  # 全局截图功能（调用 Win32 API）
│   ├── hotkey.py                      # 全局快捷键注册
│   ├── history.py                     # 历史记录管理（增删改查）
│   └── api/                           # API 接口
│       └── __init__.py
│
├── interfaces/                        # 界面层（所有 UI 实现）
│   │
│   ├── fluent/                        # ⭐ Fluent Design 界面（推荐）
│   │   ├── __init__.py
│   │   ├── main_window.py             # 主窗口（NavigationInterface + StackedWidget）
│   │   ├── resource.py                # 资源文件
│   │   └── pages/                     # 页面组件
│   │       ├── __init__.py
│   │       ├── ocr_page.py            # OCR 识别页面（截图、拖拽、批量识别）
│   │       ├── history_page.py        # 历史记录页面
│   │       └── settings_page.py       # 设置页面（引擎路径、语言、快捷键等）
│   │
│   ├── pyside6_dracula/              # PySide6 Dracula 风格界面
│   │   ├── main.py
│   │   ├── modules/
│   │   └── widgets/
│   │
│   ├── pyqt6_ui/                     # PyQt6 界面
│   │   ├── PyDracula/
│   │   │   ├── main.py
│   │   │   └── modules/
│   │   └── ...
│   │
│   ├── web_ui/                       # Web 界面（pywebview）
│   │   ├── web_ui.py
│   │   └── web/
│   │       ├── index.html
│   │       ├── styles.css
│   │       └── app.js
│   │
│   └── tkinter_ui.py                 # Tkinter 简洁界面
│
├── PaddleOCR-json/                    # OCR 引擎（独立可执行文件）
│   ├── PaddleOCR-json.exe             # 主程序
│   ├── *.dll                          # 依赖的动态链接库
│   └── models/                        # OCR 模型文件
│       ├── config_chinese.txt         # 中文识别配置
│       ├── config_chinese_cht.txt     # 繁体识别配置
│       ├── config_en.txt             # 英文识别配置
│       ├── config_japan.txt           # 日文识别配置
│       ├── config_korean.txt          # 韩文识别配置
│       ├── config_cyrillic.txt        # 俄文识别配置
│       └── ch_PP-OCRv3_det_infer/    # 检测模型
│       └── ch_PP-OCRv3_rec_infer/    # 识别模型
│       └── ...
│
├── api/                               # 预留 API 模块
│   └── __init__.py
│
├── config.json                        # 用户配置文件（运行时生成）
├── history.json                       # 识别历史记录（运行时生成）
├── requirements.txt                   # Python 依赖列表
├── README.md                          # 项目说明文档
├── .gitignore                         # Git 忽略规则
├── main.py                            # 统一入口（支持选择界面类型）
├── run_fluent.py                      # 启动 Fluent 界面
├── run_pyqt6.py                       # 启动 PyQt6 界面
└── run_pyside6_dracula.py             # 启动 Dracula 界面
```

## 目录说明

### `core/` - 核心模块
| 文件 | 说明 |
|------|------|
| `config.py` | 配置文件读写，持久化用户设置 |
| `ocr_engine.py` | 封装 PaddleOCR-json 进程管理、通讯协议、状态码处理 |
| `screenshot.py` | 调用 Windows API 实现全局截图 |
| `hotkey.py` | 注册/注销全局快捷键 |
| `history.py` | 历史记录 CRUD 操作，支持存储/显示上限 |

### `interfaces/` - 界面实现
| 目录 | 说明 |
|------|------|
| `fluent/` | **推荐** - PySide6 + qfluentwidgets，Fluent Design 风格 |
| `pyside6_dracula/` | PySide6 + Dracula 暗色主题 |
| `pyqt6_ui/` | PyQt6 + PyDracula 主题 |
| `web_ui/` | 浏览器内嵌 Web 界面（pywebview） |
| `tkinter_ui.py` | Tkinter 原生界面，零依赖 |

### `PaddleOCR-json/` - OCR 引擎
| 文件/目录 | 说明 |
|------|------|
| `PaddleOCR-json.exe` | OCR 主程序（独立进程运行） |
| `*.dll` | 依赖库（OpenCV、MKL 等） |
| `models/config_*.txt` | 各种语言的识别配置 |
| `models/*_infer/` | 预训练模型（检测+识别+方向分类） |

### 根目录配置文件
| 文件 | 说明 |
|------|------|
| `config.json` | 用户配置（exe 路径、语言、快捷键等） |
| `history.json` | 识别历史记录 |
| `requirements.txt` | Python 依赖（pip install -r requirements.txt） |

## 配置说明

配置文件 `config.json`：

```json
{
  "exe_path": "PaddleOCR-json/PaddleOCR-json.exe",
  "models_path": "PaddleOCR-json/models",
  "language": "chinese_cht",
  "auto_copy": true,
  "scan_subdirs": false
}
```

## 常见问题

### Q: 启动报错找不到 PaddleOCR-json.exe
**A**: 确保 `PaddleOCR-json/` 文件夹在项目根目录，配置文件中的路径正确。

### Q: 识别速度慢
**A**: 首次运行需要加载模型，后续会缓存。确保使用 SSD 存储。

### Q: 快捷键冲突
**A**: 在设置页面可以查看/修改快捷键配置。

## 更新日志

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
