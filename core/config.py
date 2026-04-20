# 配置文件
# 核心层配置，不依赖任何界面

import os
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

# 配置日志
logger = logging.getLogger(__name__)

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent.resolve()

# PaddleOCR-json 引擎路径（默认值 - 使用相对路径）
DEFAULT_OCR_EXE = str(ROOT_DIR / "PaddleOCR-json" / "PaddleOCR-json.exe")
DEFAULT_MODELS_PATH = str(ROOT_DIR / "PaddleOCR-json" / "models")

# 支持的语言配置
LANGUAGES = {
    "简体中文": "config_chinese.txt",
    "繁体中文": "config_chinese_cht.txt",
    "English": "config_en.txt",
    "日本語": "config_japan.txt",
    "한국어": "config_korean.txt",
}

# 默认 OCR 参数（不再包含 limit_side_len，使用 PaddleOCR-json 默认值 960）
DEFAULT_ARGS = {
    "cls": True,              # 启用方向分类
    "use_angle_cls": True,    # 启用方向分类
    "enable_mkldnn": True,    # 启用 CPU 加速
    "det_db_thresh": 0.3,      # 检测阈值
    "det_db_box_thresh": 0.5, # 检测框阈值
    "det_db_unclip_ratio": 1.6, # 检测框扩展比例
}

# 截图快捷键
SCREENSHOT_HOTKEY = "F1"

# 窗口配置
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800

# 导出格式
EXPORT_FORMATS = ["TXT", "JSON", "Excel"]

# 历史记录文件路径
HISTORY_FILE = ROOT_DIR / "history.json"

# 配置文件路径
CONFIG_FILE = ROOT_DIR / "config.json"


class ConfigManager:
    """配置管理器 - 核心层配置持久化"""

    _instance: Optional['ConfigManager'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._config_file = CONFIG_FILE
        self._data = self._load()

    def _load(self) -> Dict[str, Any]:
        """加载配置文件
        
        Returns:
            配置字典，如果加载失败则返回默认配置
        """
        if self._config_file.exists():
            try:
                with open(self._config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    logger.info(f"成功加载配置文件: {self._config_file}")
                    return config
            except json.JSONDecodeError as e:
                logger.error(f"配置文件格式错误: {e}")
            except Exception as e:
                logger.error(f"加载配置文件失败: {e}")
        return self._get_defaults()

    def _get_defaults(self) -> Dict[str, Any]:
        """获取默认配置
        
        Returns:
            默认配置字典
        """
        return {
            "ocr_exe_path": DEFAULT_OCR_EXE,
            "models_path": DEFAULT_MODELS_PATH,
            "language": "简体中文",
            "ui_language": "中文",
            "auto_copy": False,
            "theme": "跟随系统",
            "confidence_threshold": 50,
            "auto_detect": False,       # 自动检测开关状态
            "long_image_mode": True,    # 超长图切片识别模式（默认开启）
            "slice_height": 2000,       # 切片高度（像素）
            "slice_overlap": 100,       # 切片重叠像素（防止截断文字）
            "scan_subdirs": True,       # 是否扫描子目录
            "history_storage_limit": 100,  # 历史记录存储上限
            "history_display_limit": 50,   # 历史记录显示上限
        }

    def save(self) -> bool:
        """保存配置到文件
        
        Returns:
            是否保存成功
        """
        try:
            # 确保配置目录存在
            self._config_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 确保配置数据中没有不可序列化的对象
            serializable_data = {}
            for key, value in self._data.items():
                # 检查value是否可序列化
                if isinstance(value, (str, int, float, bool, list, dict, type(None))):
                    serializable_data[key] = value
                else:
                    # 尝试转换为字符串
                    try:
                        serializable_data[key] = str(value)
                    except:
                        # 如果转换失败，跳过该值
                        logger.warning(f"跳过不可序列化的配置项: {key}")
            
            with open(self._config_file, 'w', encoding='utf-8') as f:
                json.dump(serializable_data, f, ensure_ascii=False, indent=2)
            logger.info("配置已保存")
            return True
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值
        
        Args:
            key: 配置键名
            default: 默认值
            
        Returns:
            配置值或默认值
        """
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> bool:
        """设置配置值并立即保存
        
        Args:
            key: 配置键名
            value: 配置值
            
        Returns:
            是否保存成功
        """
        self._data[key] = value
        return self.save()
    
    def validate_path(self, path: str) -> bool:
        """验证路径是否在安全范围内（项目根目录内）
        
        Args:
            path: 要验证的路径
            
        Returns:
            路径是否安全
        """
        try:
            Path(path).resolve().relative_to(ROOT_DIR.resolve())
            return True
        except (ValueError, OSError):
            logger.warning(f"路径不在项目根目录内: {path}")
            return False

    def get_ocr_exe_path(self) -> str:
        """获取 OCR 程序路径
        
        Returns:
            OCR 可执行文件路径
        """
        path = self.get("ocr_exe_path", DEFAULT_OCR_EXE)
        # 验证路径存在性
        if not Path(path).exists():
            logger.warning(f"OCR 引擎路径不存在: {path}")
        return path

    def set_ocr_exe_path(self, path: str) -> bool:
        """设置 OCR 程序路径
        
        Args:
            path: OCR 可执行文件路径
            
        Returns:
            是否保存成功
        """
        if not Path(path).exists():
            logger.error(f"OCR 引擎路径不存在: {path}")
            return False
        return self.set("ocr_exe_path", path)

    def get_models_path(self) -> str:
        """获取模型文件夹路径
        
        Returns:
            模型文件夹路径
        """
        path = self.get("models_path", DEFAULT_MODELS_PATH)
        if not Path(path).exists():
            logger.warning(f"模型路径不存在: {path}")
        return path

    def set_models_path(self, path: str) -> bool:
        """设置模型文件夹路径
        
        Args:
            path: 模型文件夹路径
            
        Returns:
            是否保存成功
        """
        if not Path(path).exists():
            logger.error(f"模型路径不存在: {path}")
            return False
        return self.set("models_path", path)

    def get_language(self) -> str:
        """获取识别语言
        
        Returns:
            语言名称
        """
        lang = self.get("language", "简体中文")
        if lang not in LANGUAGES:
            logger.warning(f"不支持的语言: {lang}，使用默认简体中文")
            return "简体中文"
        return lang

    def set_language(self, language: str) -> bool:
        """设置识别语言
        
        Args:
            language: 语言名称
            
        Returns:
            是否保存成功
        """
        if language not in LANGUAGES:
            logger.error(f"不支持的语言: {language}")
            return False
        return self.set("language", language)

    def get_auto_copy(self) -> bool:
        """获取自动复制设置
        
        Returns:
            是否启用自动复制
        """
        return self.get("auto_copy", False)

    def set_auto_copy(self, enabled: bool) -> bool:
        """设置自动复制
        
        Args:
            enabled: 是否启用
            
        Returns:
            是否保存成功
        """
        return self.set("auto_copy", bool(enabled))

    def get_theme(self) -> str:
        """获取主题设置
        
        Returns:
            主题名称
        """
        return self.get("theme", "跟随系统")

    def set_theme(self, theme: str) -> bool:
        """设置主题
        
        Args:
            theme: 主题名称
            
        Returns:
            是否保存成功
        """
        return self.set("theme", theme)

    def get_confidence_threshold(self) -> int:
        """获取置信度阈值（0-100）
        
        Returns:
            置信度阈值
        """
        threshold = self.get("confidence_threshold", 50)
        # 确保在合理范围内
        return max(0, min(100, int(threshold)))

    def set_confidence_threshold(self, threshold: int) -> bool:
        """设置置信度阈值
        
        Args:
            threshold: 置信度阈值（0-100）
            
        Returns:
            是否保存成功
        """
        if not isinstance(threshold, (int, float)) or not (0 <= threshold <= 100):
            logger.error(f"无效的置信度阈值: {threshold}，应在 0-100 之间")
            return False
        return self.set("confidence_threshold", int(threshold))

    def get_auto_detect(self) -> bool:
        """获取自动检测开关状态
        
        Returns:
            是否启用自动检测
        """
        return self.get("auto_detect", False)

    def set_auto_detect(self, enabled: bool) -> bool:
        """设置自动检测开关状态
        
        Args:
            enabled: 是否启用
            
        Returns:
            是否保存成功
        """
        return self.set("auto_detect", bool(enabled))

    def get_scan_subdirs(self) -> bool:
        """获取是否扫描子目录
        
        Returns:
            是否扫描子目录
        """
        return self.get("scan_subdirs", True)
    
    def set_scan_subdirs(self, enabled: bool) -> bool:
        """设置是否扫描子目录
        
        Args:
            enabled: 是否启用
            
        Returns:
            是否保存成功
        """
        return self.set("scan_subdirs", bool(enabled))

    def get_long_image_mode(self) -> bool:
        """获取超长图切片识别模式
        
        Returns:
            是否启用超长图模式
        """
        return self.get("long_image_mode", True)

    def set_long_image_mode(self, enabled: bool) -> bool:
        """设置超长图切片识别模式
        
        Args:
            enabled: 是否启用
            
        Returns:
            是否保存成功
        """
        return self.set("long_image_mode", bool(enabled))

    def get_slice_height(self) -> int:
        """获取切片高度（像素）
        
        Returns:
            切片高度，范围 500-5000
        """
        height = self.get("slice_height", 2000)
        # 确保在合理范围内
        return max(500, min(5000, int(height)))

    def set_slice_height(self, height: int) -> bool:
        """设置切片高度（像素）
        
        Args:
            height: 切片高度，应在 500-5000 之间
            
        Returns:
            是否保存成功
        """
        if not isinstance(height, (int, float)) or not (500 <= height <= 5000):
            logger.error(f"无效的切片高度: {height}，应在 500-5000 之间")
            return False
        return self.set("slice_height", int(height))

    def get_slice_overlap(self) -> int:
        """获取切片重叠像素
        
        Returns:
            重叠像素数，范围 0-500
        """
        overlap = self.get("slice_overlap", 100)
        # 确保在合理范围内
        return max(0, min(500, int(overlap)))

    def set_slice_overlap(self, overlap: int) -> bool:
        """设置切片重叠像素
        
        Args:
            overlap: 重叠像素数，应在 0-500 之间
            
        Returns:
            是否保存成功
        """
        if not isinstance(overlap, (int, float)) or not (0 <= overlap <= 500):
            logger.error(f"无效的重叠像素: {overlap}，应在 0-500 之间")
            return False
        return self.set("slice_overlap", int(overlap))

    def get_history_storage_limit(self) -> int:
        """获取历史记录存储上限
        
        Returns:
            存储上限，范围 10-1000
        """
        limit = self.get("history_storage_limit", 100)
        return max(10, min(1000, int(limit)))
    
    def set_history_storage_limit(self, limit: int) -> bool:
        """设置历史记录存储上限
        
        Args:
            limit: 存储上限，应在 10-1000 之间
            
        Returns:
            是否保存成功
        """
        if not isinstance(limit, (int, float)) or not (10 <= limit <= 1000):
            logger.error(f"无效的存储上限: {limit}，应在 10-1000 之间")
            return False
        return self.set("history_storage_limit", int(limit))

    def get_history_display_limit(self) -> int:
        """获取历史记录显示上限
        
        Returns:
            显示上限，范围 10-500
        """
        limit = self.get("history_display_limit", 50)
        return max(10, min(500, int(limit)))
    
    def set_history_display_limit(self, limit: int) -> bool:
        """设置历史记录显示上限
        
        Args:
            limit: 显示上限，应在 10-500 之间
            
        Returns:
            是否保存成功
        """
        if not isinstance(limit, (int, float)) or not (10 <= limit <= 500):
            logger.error(f"无效的显示上限: {limit}，应在 10-500 之间")
            return False
        return self.set("history_display_limit", int(limit))
    
    def get_ui_language(self) -> str:
        """获取界面语言
        
        Returns:
            界面语言
        """
        return self.get("ui_language", "中文")
    
    def set_ui_language(self, language: str) -> bool:
        """设置界面语言
        
        Args:
            language: 界面语言
            
        Returns:
            是否保存成功
        """
        return self.set("ui_language", language)

    def auto_detect_paths(self):
        """
        自动搜索 PaddleOCR-json.exe 及 models 目录。

        搜索范围（严格限制）：
          仅从程序根目录（ROOT_DIR）向下递归搜索，绝不跨越根目录边界。
          不搜索系统目录、用户目录或任何根目录以外的路径。

        Returns
        -------
        dict with keys:
            "exe"    : str | None  找到的 exe 路径
            "models" : str | None  找到的 models 目录路径
            "message": str         人类可读的结果说明
        """
        import os

        result = {"exe": None, "models": None, "message": ""}

        # ── 安全边界：唯一搜索根为程序根目录 ──────────────────────────────
        # ROOT_DIR = Path(__file__).parent.parent.resolve()，即项目根目录。
        # 任何位于 ROOT_DIR 外部的路径均不在搜索范围内。
        search_root = ROOT_DIR

        if not search_root.exists():
            result["message"] = f"搜索根目录不存在: {search_root}"
            return result

        exe_found = None
        models_found = None

        try:
            for dirpath, dirnames, filenames in os.walk(search_root):
                dp = Path(dirpath)

                # ── 防御性边界检查：跳过逃逸出根目录的路径（符号链接等）──
                try:
                    dp.resolve().relative_to(search_root.resolve())
                except ValueError:
                    # 该目录不在 search_root 之下，直接跳过
                    dirnames.clear()
                    continue

                # 跳过常见无关目录，加快速度
                dirnames[:] = [
                    d for d in dirnames
                    if not d.startswith('.')
                    and d not in ('__pycache__', '.git', 'node_modules',
                                  'venv', '.venv', 'env', '.env',
                                  'dist', 'build', '.idea', '.vscode')
                ]

                # 搜索 exe
                if exe_found is None:
                    for fname in filenames:
                        if fname.lower() == 'paddleocr-json.exe':
                            exe_found = str(dp / fname)
                            break

                # 搜索 models 目录（要求非空）
                if models_found is None and 'models' in dirnames:
                    candidate = dp / 'models'
                    try:
                        if any(candidate.iterdir()):
                            models_found = str(candidate)
                    except PermissionError:
                        pass

                # 两者都找到则提前结束
                if exe_found and models_found:
                    break

        except PermissionError:
            pass

        # 写入配置
        if exe_found:
            self.set_ocr_exe_path(exe_found)
            result["exe"] = exe_found
        if models_found:
            self.set_models_path(models_found)
            result["models"] = models_found

        # 生成说明信息
        parts = []
        if exe_found:
            parts.append(f"exe: {exe_found}")
        else:
            parts.append("未找到 PaddleOCR-json.exe")
        if models_found:
            parts.append(f"models: {models_found}")
        else:
            parts.append("未找到 models 目录")
        result["message"] = "\n".join(parts)

        return result


# 全局配置管理器实例
_config_manager = None


def get_config_manager():
    """获取全局配置管理器"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def copy_to_clipboard(text: str) -> bool:
    """
    复制文本到剪贴板（核心层功能）
    
    Args:
        text: 要复制的文本
        
    Returns:
        bool: 是否成功
    """
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QGuiApplication
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(text)
        return True
    except Exception as e:
        print(f"复制到剪贴板失败: {e}")
        return False