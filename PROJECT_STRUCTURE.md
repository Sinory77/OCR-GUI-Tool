# OCR GUI Tool - 项目结构说明

> **版本**: v2.0.0  
> **最后更新**: 2026-04-16  
> **技术栈**: Python 3.10+ | PySide6 | qfluentwidgets | PaddleOCR-json

---

## 📁 项目目录树

```
OCR-GUI-Tool/
│
├── 📄 main.py                          # 主入口（启动 Fluent 界面）
├── 📄 run.py                           # 快速测试入口（推荐 IDE 调试）
├── 📄 requirements.txt                 # Python 依赖清单
├── 📄 config.json                      # 用户配置文件（运行时生成）
├── 📄 history.json                     # 识别历史记录（运行时生成）
├── 📄 README.md                        # 项目使用说明
├── 📄 PROJECT_STRUCTURE.md             # 本文件 - 项目结构说明
│
├── 🔧 core/                            # 核心业务逻辑层
│   ├── __init__.py                     # 模块初始化与导出
│   ├── config.py                       # 配置管理器（读写 config.json）
│   ├── ocr_engine.py                   # OCR 引擎封装（进程管理、通讯协议）
│   ├── result_manager.py               # 识别结果管理器
│   ├── exporter.py                     # 结果导出器（TXT/Excel）
│   ├── template_manager.py             # 模板管理器（解析规则 CRUD）
│   ├── text_parser.py                  # 文本解析器（基于模板提取字段）
│   ├── screenshot.py                   # 截图功能（Windows API 调用）
│   ├── async_worker.py                 # 异步工作线程（非阻塞 UI）
│   └── performance_monitor.py          # 性能监控（耗时统计、资源使用）
│
├── 🎨 interfaces/                      # 界面层
│   ├── __init__.py                     # 包初始化
│   │
│   └── fluent/                         # ⭐ Fluent Design 界面（唯一保留的 UI）
│       ├── __init__.py                 # 包初始化
│       ├── main_window.py              # 主窗口（导航栏 + 页面切换）
│       │
│       ├── components/                 # 可复用组件
│       │   └── screenshot_window.py    # 截图窗口（十字光标、区域选择）
│       │
│       └── pages/                      # 页面组件
│           ├── __init__.py             # 包初始化
│           ├── ocr_page.py             # OCR 识别页面（截图、拖拽、批量处理）
│           ├── history_page.py         # 历史记录页面（列表展示、搜索、删除）
│           ├── template_page.py        # 模板管理页面（规则编辑、预览测试）
│           └── settings_page.py        # 设置页面（引擎配置、语言、快捷键）
│
├── 🔌 api/                             # API 接口层（预留扩展）
│   ├── __init__.py                     # 包初始化
│   ├── ocr_api.py                      # OCR API 封装
│   └── PPOCR_api.py                    # PaddleOCR API 兼容层
│
├── 🧪 tests/                           # 单元测试
│   ├── __init__.py                     # 包初始化
│   ├── test_config.py                  # 配置管理测试
│   ├── test_result_manager.py          # 结果管理测试
│   ├── test_exporter.py                # 导出功能测试
│   ├── test_data_baohuodan.txt         # 测试数据：报货单样本
│   └── test_data_jianyi.txt            # 测试数据：简易样本
│
├── 📦 PaddleOCR-json/                  # OCR 引擎（外部依赖，不纳入 Git）
│   ├── PaddleOCR-json.exe              # OCR 主程序
│   ├── *.dll                           # 动态链接库
│   └── models/                         # OCR 模型文件
│       ├── config_chinese.txt          # 简体中文配置
│       ├── config_chinese_cht.txt      # 繁体中文配置
│       ├── config_en.txt               # 英文配置
│       ├── config_japan.txt            # 日文配置
│       ├── config_korean.txt           # 韩文配置
│       ├── config_cyrillic.txt         # 俄文配置
│       └── *_infer/                    # 预训练模型目录
│
├── 📝 templates/                       # ⭐ 解析模板存储目录（TemplateManager 默认路径）
│   ├── animal_quarantine.json          # 动物检疫证明模板（13个规则）
│   ├── baohuodan.json                  # 报货单模板（7个规则）
│   └── jianyi.json                     # 简易模板（示例）
│
└── 🗂️ config.json                      # 用户配置文件（运行时生成）
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
| `screenshot.py` | Windows 截图 API 封装 | `capture_screen()`, `select_region()` |
| `async_worker.py` | 异步任务调度 | `AsyncWorker`, `TaskManager` |
| `performance_monitor.py` | 性能指标收集 | `PerformanceMonitor` |

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

---

### 3️⃣ **API 层 (api/)** - 外部接口

| 模块 | 说明 |
|------|------|
| `ocr_api.py` | 封装 OCR 引擎的 HTTP/API 调用（预留） |
| `PPOCR_api.py` | PaddleOCR 原生 API 兼容层 |

---

### 4️⃣ **测试层 (tests/)** - 质量保证

| 测试文件 | 覆盖模块 | 测试内容 |
|----------|----------|----------|
| `test_config.py` | `core/config.py` | 配置读写、默认值、路径验证 |
| `test_result_manager.py` | `core/result_manager.py` | 结果增删改查、持久化 |
| `test_exporter.py` | `core/exporter.py` | TXT/Excel 导出格式、编码 |
| `test_data_*.txt` | - | 测试数据样本（报货单、简易文本） |

**运行测试**:
```bash
pytest tests/ -v
```

---

### 5️⃣ **模板层 (templates/)** - 解析模板

| 文件 | 说明 |
|------|------|
| `animal_quarantine.json` | 动物检疫证明解析模板（13个规则） |
| `baohuodan.json` | 报货单解析模板（7个规则） |
| `jianyi.json` | 简易解析模板（示例） |

**重要说明**:
- `templates/` 是程序运行时实际使用的模板目录（TemplateManager 默认路径）
- 如果目录不存在，程序会自动创建
- 用户可以通过界面"模板管理"页面添加、编辑、删除模板
- 所有修改会立即同步到此目录下的 JSON 文件
- 建议定期备份此目录，防止数据丢失

---

### 6️⃣ **配置层 (config.json)** - 用户配置

**配置文件位置**: 项目根目录下的 `config.json`

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `ocr_exe_path` | OCR 引擎路径 | `PaddleOCR-json/PaddleOCR-json.exe` |
| `models_path` | 模型目录路径 | `PaddleOCR-json/models` |
| `language` | 识别语言 | `chinese` |
| `auto_detect` | 自动检测引擎 | `true` |
| `hotkey_screenshot` | 截图快捷键 | `Ctrl+Shift+F` |
| `auto_copy` | 自动复制结果 | `false` |
| `scan_subdirs` | 扫描子目录 | `true` |
| `theme` | 主题模式 | `auto` |

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
result_manager.py (保存结果到 history.json)
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

**模板存储位置**: `templates/*.json`

---

## 📊 核心数据结构

### 1. 配置结构 (`config.json`)

```json
{
  "ocr_exe_path": "PaddleOCR-json/PaddleOCR-json.exe",
  "models_path": "PaddleOCR-json/models",
  "language": "chinese",
  "auto_detect": true,
  "hotkey_screenshot": "Ctrl+Shift+F",
  "auto_copy": false,
  "scan_subdirs": true,
  "theme": "auto"
}
```

### 2. 识别结果结构

```json
{
  "id": "uuid-string",
  "filename": "example.png",
  "path": "C:/images/example.png",
  "text": "识别到的文本内容",
  "confidence": 0.95,
  "time": "2026-04-16 14:30:00",
  "language": "chinese"
}
```

### 3. 模板结构

```json
{
  "id": "animal_quarantine",
  "name": "动物检疫证明",
  "description": "用于解析动物检疫合格证明",
  "rules": [
    {
      "name": "货主",
      "type": "keyword",
      "keyword": "货主",
      "ignore_spaces": true,
      "use_next_line": true
    },
    {
      "name": "联系电话",
      "type": "regex",
      "pattern": "联系电话[：:]\\s*(\\d+)"
    }
  ]
}
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

**建议**: 在 IDE 中配置运行配置为 `run.py`，避免每次输入参数。

---

## 🎯 关键设计决策

### 1. 为什么只保留 Fluent 界面？

- ✅ **统一体验**: 避免多套 UI 维护成本
- ✅ **现代化**: Fluent Design 符合 Windows 11 审美
- ✅ **功能完整**: qfluentwidgets 提供丰富的组件
- ❌ 移除 Tkinter: 界面简陋、开发效率低
- ❌ 移除 Web UI: pywebview 依赖复杂、性能差
- ❌ 移除 PyQt6/PySide6 Dracula: 功能重复、维护负担

### 2. 为什么使用单例模式？

```python
# 全局唯一实例，避免重复创建
engine = get_ocr_engine()
results = get_result_manager()
config = get_config_manager()
```

**优势**:
- 内存效率高（只有一个实例）
- 状态一致（所有页面共享同一数据源）
- 线程安全（配合 QThread 使用）

### 3. 为什么使用异步工作线程？

```python
# 避免阻塞 UI
worker = OcrInitWorker(...)
worker.finished.connect(on_finished)
worker.start()
```

**原因**:
- OCR 引擎初始化耗时（1-3 秒）
- 批量识别需要处理大量图片
- 保持 UI 响应性（进度条、取消按钮）

---

## 🛠️ 开发指南

### 添加新功能

1. **核心逻辑** → 在 `core/` 下创建新模块
2. **界面页面** → 在 `interfaces/fluent/pages/` 下创建新页面
3. **注册导航** → 在 `main_window.py` 的 `initNavigation()` 中添加
4. **编写测试** → 在 `tests/` 下添加单元测试

### 修改现有功能

1. **定位模块**: 根据功能找到对应的 `core/xxx.py`
2. **修改逻辑**: 确保向后兼容（不影响现有配置）
3. **更新测试**: 运行 `pytest` 确保无回归
4. **更新文档**: 修改 `README.md` 或本文件

### 调试技巧

```python
# 1. 打印日志
print(f"[DEBUG] 当前配置: {config.get_all()}")

# 2. 使用 InfoBar 提示
from qfluentwidgets import InfoBar, InfoBarPosition
InfoBar.success(title="成功", content="操作完成", parent=self)

# 3. 检查信号连接
self.button.clicked.connect(self.on_click)  # 确保已连接

# 4. 查看异常堆栈
import traceback
try:
    ...
except Exception as e:
    traceback.print_exc()
```

---

## 📦 依赖说明

### 必需依赖

```txt
PySide6>=6.5.0              # Qt6 绑定（GUI 框架）
PySide6-Fluent-Widgets      # Fluent Design 组件库
Pillow>=9.0.0               # 图片处理（缩放、格式转换）
openpyxl>=3.0.0             # Excel 导出
pyperclip>=1.8.0            # 剪贴板操作（复制结果）
```

### 可选依赖

```txt
pytest>=7.0.0               # 单元测试框架
```

### 安装命令

```bash
pip install PySide6 PySide6-Fluent-Widgets Pillow openpyxl pyperclip
```

---

## 📝 文件统计

| 类别 | 文件数 | 代码行数 |
|------|--------|----------|
| 核心模块 (core/) | 9 | ~1,200 |
| 界面代码 (interfaces/fluent/) | 6 | ~1,800 |
| 测试代码 (tests/) | 5 | ~700 |
| API 层 (api/) | 2 | ~300 |
| 配置文件 | 2 | ~50 |
| **总计** | **24** | **~4,050** |

*注: 不包含注释和空行，不含 config/parsing_templates/ 下的模板文件*

---

## 🔮 未来规划

### 短期 (v2.1)
- [ ] 支持自定义快捷键
- [ ] 增加更多导出格式（PDF、Word）
- [ ] 优化批量识别性能（多线程）

### 中期 (v2.5)
- [ ] 云端同步历史记录
- [ ] AI 辅助模板生成
- [ ] 插件系统（扩展解析规则）

### 长期 (v3.0)
- [ ] 跨平台支持（Linux、macOS）
- [ ] 实时识别（摄像头输入）
- [ ] 协作功能（多人共享模板）

---

## 📞 联系方式

- **GitHub**: [Sinory77/OCR-GUI-Tool](https://github.com/Sinory77/OCR-GUI-Tool)
- **问题反馈**: 提交 Issue
- **功能建议**: 提交 Feature Request

---

**最后更新**: 2026-04-16  
**维护者**: Sinory
