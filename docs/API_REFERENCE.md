# OCR-GUI-Tool API 参考文档

## 目录

- [核心模块](#核心模块)
  - [ConfigManager](#configmanager)
  - [OCREngine](#ocrengine)
  - [ResultManager](#resultmanager)
  - [ResultExporter](#resultexporter)
  - [ScreenshotManager](#screenshotmanager)

---

## 核心模块

### ConfigManager

配置管理器，负责加载、保存和验证应用配置。

#### 类方法

```python
class ConfigManager:
    """配置管理器 - 单例模式"""
    
    def get(key: str, default: Any = None) -> Any:
        """获取配置值"""
        
    def set(key: str, value: Any) -> bool:
        """设置配置值并保存"""
        
    def save() -> bool:
        """保存配置到文件"""
```

#### 便捷方法

```python
# OCR 引擎配置
def get_ocr_exe_path() -> str
def set_ocr_exe_path(path: str) -> bool
def get_models_path() -> str
def set_models_path(path: str) -> bool

# 语言配置
def get_language() -> str
def set_language(language: str) -> bool

# 功能开关
def get_auto_copy() -> bool
def set_auto_copy(enabled: bool) -> bool
def get_auto_detect() -> bool
def set_auto_detect(enabled: bool) -> bool

# 识别参数
def get_confidence_threshold() -> int  # 0-100
def set_confidence_threshold(threshold: int) -> bool
def get_long_image_mode() -> bool
def set_long_image_mode(enabled: bool) -> bool
def get_slice_height() -> int  # 500-5000
def set_slice_height(height: int) -> bool
def get_slice_overlap() -> int  # 0-500
def set_slice_overlap(overlap: int) -> bool

# 历史记录
def get_history_storage_limit() -> int  # 10-1000
def set_history_storage_limit(limit: int) -> bool
def get_history_display_limit() -> int  # 10-500
def set_history_display_limit(limit: int) -> bool

# 路径验证
def validate_path(path: str) -> bool  # 检查路径是否在安全范围内
def auto_detect_paths() -> dict  # 自动检测 OCR 引擎路径
```

#### 使用示例

```python
from core.config import get_config_manager

config = get_config_manager()

# 读取配置
language = config.get_language()
threshold = config.get_confidence_threshold()

# 修改配置
if config.set_language("English"):
    print("语言切换成功")

# 验证路径
if config.validate_path("/safe/path/file.txt"):
    print("路径安全")
```

---

### OCREngine

OCR 引擎封装类，管理 PaddleOCR-json 进程和识别任务。

#### 初始化

```python
engine = OCREngine(
    exe_path: Optional[str] = None,
    models_path: Optional[str] = None,
    language: str = "简体中文",
    custom_args: Optional[Dict[str, Any]] = None
)
```

#### 核心方法

```python
# 初始化和关闭
def initialize() -> bool
def close() -> None

# 识别方法
def recognize(image_path: str) -> Dict[str, Any]
def recognize_bytes(image_bytes: bytes) -> Dict[str, Any]
def recognize_auto(
    image_path: str,
    config=None,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> Dict[str, Any]

# 超长图切片识别
def recognize_long_image(
    image_path: str,
    slice_height: int = 2000,
    overlap: int = 100,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> Dict[str, Any]

# 语言切换
def set_language(language: str) -> bool

# 参数更新
def update_args(new_args: Dict[str, Any]) -> None
```

#### 返回结果格式

```python
{
    "code": 100,           # 状态码
    "data": [...],         # 原始识别数据
    "texts": ["文本1", "文本2"],  # 提取的纯文本列表
    "success": True        # 是否成功
}
```

#### 状态码说明

| 代码 | 说明 |
|------|------|
| 100 | 识别成功 |
| 101 | 未识别到文字 |
| 200 | 图片路径不存在 |
| 202 | 文件无法打开 |
| 203 | 图片解码失败 |
| 901 | 引擎实例不存在 |
| 902 | 子进程崩溃或连接失败 |

#### 使用示例

```python
from core.ocr_engine import get_ocr_engine

engine = get_ocr_engine()

# 普通识别
result = engine.recognize("image.png")
if result["success"]:
    for text in result["texts"]:
        print(text)

# 自动识别（支持超长图）
result = engine.recognize_auto(
    "long_image.png",
    progress_callback=lambda current, total: print(f"进度: {current}/{total}")
)

# 切换语言
if engine.set_language("English"):
    result = engine.recognize("english_image.png")
```

---

### ResultManager

识别结果和历史记录管理器。

#### 初始化

```python
manager = ResultManager(history_file: Optional[str] = None)
```

#### 核心方法

```python
# 结果管理
def add_result(image_path: str, ocr_result: Dict[str, Any]) -> Dict[str, Any]
def get_result(image_path: str) -> Optional[Dict[str, Any]]
def get_current_results() -> Dict[str, Dict[str, Any]]
def clear_current_results() -> None

# 历史记录
def get_history(limit: Optional[int] = None) -> List[Dict[str, Any]]
def get_history_count() -> int
def delete_history(index: int) -> bool
def clear_history() -> bool

# 文本处理
def get_combined_text(separator: str = '\n') -> str
def format_result_for_display(ocr_result: Dict[str, Any]) -> Dict[str, Any]
```

#### 历史记录条目格式

```python
{
    'path': 'image.png',
    'filename': 'image.png',
    'text': '合并的文本',
    'full_texts': ['行1', '行2'],
    'time': '2024-01-01 12:00',
    'success': True
}
```

#### 使用示例

```python
from core.result_manager import get_result_manager

manager = get_result_manager()

# 添加识别结果
entry = manager.add_result("image.png", ocr_result)

# 获取历史记录（最近 50 条）
history = manager.get_history()

# 删除第一条历史记录
manager.delete_history(0)

# 获取合并文本
combined = manager.get_combined_text(separator='\n---\n')
```

---

### ResultExporter

识别结果导出器，支持 TXT、JSON、Excel 格式。

#### 初始化

```python
exporter = ResultExporter()
```

#### 核心方法

```python
# 添加结果
def add_result(image_path: str, ocr_result: Dict[str, Any]) -> None
def clear() -> None

# 批量导出
def export_txt(file_path: Optional[str] = None) -> str
def export_json(file_path: Optional[str] = None, include_details: bool = True) -> str
def export_excel(file_path: Optional[str] = None) -> Optional[str]

# 单个导出
def export(
    result: Dict[str, Any],
    format_type: str,
    filename: Optional[str] = None,
    output_dir: Optional[str] = None
) -> Optional[str]

# 文本处理
def get_combined_text(separator: str = '\n') -> str
```

#### 使用示例

```python
from core.exporter import get_exporter

exporter = get_exporter()

# 添加多个结果
exporter.add_result("image1.png", result1)
exporter.add_result("image2.png", result2)

# 批量导出
txt_file = exporter.export_txt("results.txt")
json_file = exporter.export_json("results.json")
excel_file = exporter.export_excel("results.xlsx")

# 单个导出
exporter.export(result, "TXT", filename="single_result", output_dir="./output")
```

---

### ScreenshotManager

截图管理器，提供多种截图功能和快捷键管理。

#### 初始化

```python
from core.screenshot import get_screenshot_manager

manager = get_screenshot_manager()
```

#### 核心方法

```python
# 全屏截图
def capture_full_screen(save_to_history: bool = True) -> Optional[str]

# 区域截图
def capture_screen_region(x: int, y: int, width: int, height: int, 
                        save_to_history: bool = True) -> Optional[str]

# 窗口截图
def capture_window(hwnd: int) -> Optional[str]

# 延迟截图
def capture_with_delay(delay: int = 3) -> Optional[str]

# 截图为 QPixmap（界面使用）
def capture_screen_to_pixmap()

# 截图为字节数据
def capture_screen_as_bytes() -> Tuple[Optional[bytes], int, int]

# 保存到剪贴板
def save_to_clipboard(image_path: str) -> bool

# 历史记录管理
def get_history() -> list
def clear_history()
```

#### HotkeyManager

```python
# 初始化
from core.screenshot import get_hotkey_manager

hotkey_manager = get_hotkey_manager()

# 注册快捷键
hotkey_id = hotkey_manager.register("F1", callback_function)

# 开始监听
hotkey_manager.start_listening()

# 停止监听
hotkey_manager.stop_listening()

# 注销快捷键
hotkey_manager.unregister(hotkey_id)
```

#### 使用示例

```python
from core.screenshot import get_screenshot_manager, get_hotkey_manager

# 截图管理
manager = get_screenshot_manager()

# 截取全屏
temp_path = manager.capture_full_screen()
if temp_path:
    print(f"全屏截图已保存: {temp_path}")

# 截取指定区域
region_path = manager.capture_screen_region(100, 100, 800, 600)

# 延迟截图
delayed_path = manager.capture_with_delay(5)  # 5秒后截图

# 保存到剪贴板
manager.save_to_clipboard(temp_path)

# 快捷键管理
hotkey_manager = get_hotkey_manager()

def on_screenshot():
    print("快捷键触发截图")
    manager.capture_full_screen()

# 注册快捷键
hotkey_id = hotkey_manager.register("F1", on_screenshot)

# 开始监听
hotkey_manager.start_listening()
```

---

## 全局函数

### 获取全局实例

```python
from core.config import get_config_manager
from core.ocr_engine import get_ocr_engine, reset_ocr_engine
from core.result_manager import get_result_manager
from core.exporter import get_exporter, reset_exporter
from core.screenshot import get_screenshot_manager, get_hotkey_manager

# 获取单例
config = get_config_manager()
engine = get_ocr_engine()
manager = get_result_manager()
exporter = get_exporter()
screenshot_manager = get_screenshot_manager()
hotkey_manager = get_hotkey_manager()

# 重置实例（用于重新配置）
reset_ocr_engine(exe_path=new_path, language="English")
reset_exporter()
```

---

## 错误处理

所有核心模块都使用 Python 标准 `logging` 模块记录日志：

```python
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 日志级别
logger.debug("调试信息")
logger.info("一般信息")
logger.warning("警告信息")
logger.error("错误信息", exc_info=True)  # 包含堆栈跟踪
```

---

## 线程安全

所有全局实例获取函数都是线程安全的，使用双重检查锁定模式：

```python
def get_ocr_engine() -> OCREngine:
    global _ocr_engine
    
    if _ocr_engine is None:
        with _get_lock():
            if _ocr_engine is None:
                _ocr_engine = OCREngine()
    
    return _ocr_engine
```