# MEMORY.md

## 用户信息
- 用户位于中国

## 项目信息

### OCR-GUI-Tool 项目
- **位置**: `C:\Users\Sinory\Desktop\测试用\识别工具\OCR-GUI-Tool`
- **描述**: PaddleOCR 图形界面识别工具

### 技术架构 v2.0（已重构）

#### 核心层 `core/`
- `ocr_engine.py` - OCR 引擎封装（PaddleOCR-json）
- `result_manager.py` - 结果和历史记录管理（业务逻辑）
- `exporter.py` - 导出功能（TXT/JSON/Excel）
- `screenshot.py` - 截图功能
- `config.py` - 配置

#### 界面层 `interfaces/`
- `tkinter_ui.py` - Tkinter GUI 界面（调用 core）
- `web_ui/` - pywebview Web 界面（调用 core）
  - `api/` - 暴露给 JS 的 API

#### 主入口
- `main.py` - 统一入口，支持选择界面
  - `python main.py --ui tkinter` - Tkinter 界面
  - `python main.py --ui web` - Web 界面
  - `python main.py --ui pyqt6` - PyQt6 界面（简洁风格）
  - `python main.py --ui pyside6` - PySide6 界面
- `run_pyside6_dracula.py` - PySide6 独立启动脚本

#### PySide6 版本（2026-04-10 新建）
- **位置**：`interfaces/pyside6_dracula/`（独立于 pyqt6_ui）
- **说明**：从 PyDracula（PyQt6）移植，主要差异：`pyqtSignal` → `Signal`，`QEvent.MouseButtonDblClick` → `QEvent.Type.MouseButtonDblClick`
- **导航修复**：`btn_home` 跳转到 `ocr_page` 而非模板自带的空白 `home` 页

#### Fluent Design 界面（2026-04-10 新建）
- **位置**：`interfaces/fluent/`
- **依赖**：PySide6-Fluent-Widgets（v1.11.2）
- **启动命令**：`python main.py --ui fluent`
- **目录结构**：
  - `main_window.py` - FluentWindow 主窗口（侧边导航）
  - `pages/ocr_page.py` - OCR 识别页面（拖拽/选择图片、识别、导出）
  - `pages/history_page.py` - 历史记录页面（列表、详情、重新识别）
  - `pages/settings_page.py` - 设置页面（引擎设置、主题）
- **功能**：
  - 拖拽/选择图片进行 OCR 识别
  - 多语言支持
  - 识别结果复制和导出（TXT/JSON/Excel）
  - 历史记录查看和管理
  - 跟随系统主题（浅色/深色）

#### 设计原则
- **核心功能与界面分离**：core 模块不依赖任何界面
- **界面只负责交互**：调用 core 模块实现功能
- **支持多界面**：可以同时使用 Tkinter 或 pywebview

### 已修复的 Bug（2026-04-09）
- **`初始化失败: Cannot read properties of undefined (reading 'api')`**
  - 根因：`DOMContentLoaded` 时 `window.pywebview.api` 尚未注入
  - 修复：`app.js` 增加 `_waitForPywebview()` 等待 `pywebviewready` 事件 + 轮询保险
  - 修复：`web_ui.py` 的 `CombinedApi` 从 `get_web_api().__class__` 改为直接继承 `WebApi`
  - 修复：`api/__init__.py` 补充缺失的 `get_settings`、`save_settings`、`add_history` 方法
  - 修复：`recognize` 返回值 `texts` 数组转 `text` 字符串（JS/Python 对齐）

- **`NameError: name 'window' is not defined` + `open_file_dialog is not a function`**（旧版 `app.py` 入口）
  - 根因：`api/ocr_api.py` 里直接引用了未定义的全局 `window`；方法名与 JS 调用不符
  - 修复：`OcrApi` 增加 `self._window = None`，由 `app.py` 在 `create_window()` 后注入
  - 修复：`_init_async` 和 `screenshot` 改用 `self._window or webview.windows[0]`
  - 修复：补充 `open_file_dialog()`、`open_files_dialog()` 方法别名（对齐 JS 调用）
  - 修复：`api/ocr_api.py` 顶部补充 `import webview`

- **"识别失败: 引擎未初始化" + 图片预览显示 alt 文字**（2026-04-09）
  - 根因1：`ocr_api.py` 调用 `get_ocr_engine(exe_path=..., models_path=...)` 但函数签名不接受参数，改为直接 `new OCREngine(...)` 实例化
  - 根因2：`recognize` 方法返回 `result.get('text', '')` 但引擎返回的是 `texts` 列表（无 `text` 字段），改为 `'\n'.join(texts)`
  - 根因3：`file://` 路径在 pywebview WebView2 中被安全策略拦截（含中文路径尤甚），新增 `get_image_base64()` API + JS `loadImage()` 改为 async，先尝试 `file:///`，失败则 fallback 到 base64

- **"识别失败: 图片路径无效: 3.22 44头.jpg" + 图片"加载中"卡住**（2026-04-09）
  - 根因1：JS 拖拽或截图传来的路径可能为相对路径，OCR 引擎无法处理
  - 根因2：`get_image_base64()` 失败时 JS 无错误提示，导致一直显示"加载中"
  - 修复：`ocr_api.py` 新增 `_resolve_path()` 统一将相对路径转为绝对路径，`recognize` 和 `get_image_base64` 均使用该方法
  - 修复：JS `loadImage` fallback 失败时展示具体错误信息而非"加载中"卡住

- **拖拽文件时路径为文件名而非完整路径**（2026-04-09）
  - 根因：WebView2 安全限制，`file.path` 只能拿到文件名（`3.22 44头.jpg`）而非完整路径
  - 修复：JS 拖拽时用 `FileReader.readAsDataURL()` 读取为 base64 → 调用 Python `save_temp_image()` 保存为临时文件 → OCR 使用该临时文件路径
  - 修复：`loadImage()` 支持可选 `dataUrl` 参数，有 dataUrl 时直接用它预览（无需跨域），无需文件路径

### 功能补充（2026-04-09）
- **PyQt6 UI 导出功能**：`interfaces/pyqt6_ui/qt6_ui.py` 原缺少导出功能，已添加：
  - 菜单栏：文件 → 导出结果 → TXT / JSON / Excel
  - 工具栏：💾 导出结果按钮（识别后启用）
  - 导出对话框：点击按钮弹出格式选择

- **PyQt6 UI 复制到剪贴板功能**（2026-04-09）：
  - 用户反馈 PyQt6 界面缺少复制功能
  - 添加：编辑菜单 → 复制结果（Ctrl+C）
  - 添加：工具栏 📋 复制按钮（识别后启用）
  - 添加：`copy_result()` 方法使用 `QGuiApplication.clipboard()` 复制文本
  - 添加：`clear_results()` 方法清空结果
  - 导出功能已正确调用 core 模块的 `get_exporter().export()`

- **PyQt6 UI 历史记录功能**（2026-04-09）：
  - 用户反馈 PyQt6 界面缺少历史记录功能
  - 添加：右侧面板历史记录区域（列表 + 按钮）
  - 添加：`add_to_history()`、`refresh_history_list()`、`view_history()`、`delete_history()`、`clear_history()` 方法
  - 识别完成后自动添加到历史记录
  - 所有功能调用 core 模块的 `result_manager`
  - **修复（2026-04-09）**：`view_history()` 改为加载到结果区域，支持复制和导出，与 pywebview 一致

- **PyQt6 UI 导出菜单**（2026-04-09）：
  - 用户要求导出按钮弹出菜单而不是窗口
  - 修改导出按钮为 QMenu 下拉菜单，包含 TXT/JSON/Excel 选项
  - 删除 `show_export_dialog()` 对话框方法

### PyDracula 风格界面（已弃用，2026-04-10 回滚）
- PyQt6 界面已回滚到简洁风格（`qt6_ui.py`）
- PyDracula 目录 `interfaces/pyqt6_ui/PyDracula/` 保留但不再使用
- PyQt6 入口已移除 `--ui pydracula`，合并到 `--ui pyqt6`
