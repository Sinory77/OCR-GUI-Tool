# Core 模块 - 核心业务逻辑
# 所有界面都调用这里的功能

from .ocr_engine import OCREngine, get_ocr_engine, reset_ocr_engine
from .result_manager import ResultManager, get_result_manager
from .exporter import ResultExporter, get_exporter, reset_exporter
from .screenshot import ScreenshotManager, get_screenshot_manager, get_hotkey_manager
from .config import LANGUAGES, DEFAULT_ARGS, WINDOW_WIDTH, WINDOW_HEIGHT, EXPORT_FORMATS, DEFAULT_OCR_EXE, DEFAULT_MODELS_PATH

__all__ = [
    # OCR 引擎
    'OCREngine', 'get_ocr_engine', 'reset_ocr_engine',
    # 结果管理
    'ResultManager', 'get_result_manager',
    # 导出
    'ResultExporter', 'get_exporter', 'reset_exporter',
    # 截图
    'ScreenshotManager', 'get_screenshot_manager', 'get_hotkey_manager',
    # 配置
    'LANGUAGES', 'DEFAULT_ARGS', 'WINDOW_WIDTH', 'WINDOW_HEIGHT', 'EXPORT_FORMATS',
    'DEFAULT_OCR_EXE', 'DEFAULT_MODELS_PATH',
]