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
├── core/                      # 核心模块
│   ├── config.py             # 配置管理
│   ├── ocr_engine.py         # OCR 引擎封装
│   ├── screenshot.py         # 截图功能
│   └── history.py            # 历史记录
├── interfaces/               # 界面实现
│   ├── fluent/              # Fluent Design 界面
│   ├── pyside6_dracula/    # PySide6 Dracula 风格
│   ├── pyqt6_ui/           # PyQt6 界面
│   └── tkinter_ui.py       # Tkinter 简洁界面
├── PaddleOCR-json/          # OCR 引擎（自带）
├── config.json              # 用户配置
├── history.json             # 识别历史
├── requirements.txt        # Python 依赖
└── run_fluent.py           # 启动脚本
```

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
