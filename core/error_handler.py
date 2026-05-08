# 错误处理模块
# 集中处理核心功能的错误，提供统一的错误管理机制

import logging
from typing import Dict, Any, Optional, TypeVar, Callable
from enum import Enum
from datetime import datetime
import traceback

# 配置日志
logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """错误类型枚举"""
    OCR_ENGINE = "ocr_engine"      # OCR 引擎错误
    CONFIG = "config"              # 配置错误
    FILE_OPERATION = "file_operation"  # 文件操作错误
    TEMPLATE = "template"          # 模板错误
    SCREENSHOT = "screenshot"      # 截图错误
    EXPORT = "export"              # 导出错误
    ASYNC_TASK = "async_task"      # 异步任务错误
    UNKNOWN = "unknown"            # 未知错误


class OCRError(Exception):
    """OCR 工具基础异常类"""
    
    def __init__(self, error_type: ErrorType, message: str, original_error: Optional[Exception] = None):
        """
        初始化异常
        
        Args:
            error_type: 错误类型
            message: 错误信息
            original_error: 原始异常
        """
        self.error_type = error_type
        self.message = message
        self.original_error = original_error
        self.timestamp = datetime.now()
        self.traceback = traceback.format_exc() if original_error else traceback.format_stack()
        super().__init__(message)


class OCREngineError(OCRError):
    """OCR 引擎异常"""
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(ErrorType.OCR_ENGINE, message, original_error)


class ConfigError(OCRError):
    """配置异常"""
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(ErrorType.CONFIG, message, original_error)


class FileOperationError(OCRError):
    """文件操作异常"""
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(ErrorType.FILE_OPERATION, message, original_error)


class TemplateError(OCRError):
    """模板异常"""
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(ErrorType.TEMPLATE, message, original_error)


class ScreenshotError(OCRError):
    """截图异常"""
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(ErrorType.SCREENSHOT, message, original_error)


class ExportError(OCRError):
    """导出异常"""
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(ErrorType.EXPORT, message, original_error)


class AsyncTaskError(OCRError):
    """异步任务异常"""
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(ErrorType.ASYNC_TASK, message, original_error)


class ErrorHandler:
    """错误处理器"""
    
    def __init__(self):
        """初始化错误处理器"""
        self.error_callbacks: Dict[ErrorType, list] = {}
        for error_type in ErrorType:
            self.error_callbacks[error_type] = []
        
        # 错误统计
        self.error_stats: Dict[ErrorType, int] = {}
        for error_type in ErrorType:
            self.error_stats[error_type] = 0
        
        # 错误恢复策略
        self.recovery_strategies: Dict[ErrorType, Callable[[OCRError], bool]] = {}
        self._init_recovery_strategies()
    
    def _init_recovery_strategies(self):
        """初始化错误恢复策略"""
        # 为常见错误类型添加恢复策略
        self.add_recovery_strategy(ErrorType.OCR_ENGINE, self._recover_ocr_engine)
        self.add_recovery_strategy(ErrorType.FILE_OPERATION, self._recover_file_operation)
        self.add_recovery_strategy(ErrorType.CONFIG, self._recover_config)
    
    def add_recovery_strategy(self, error_type: ErrorType, strategy: Callable[[OCRError], bool]):
        """
        添加错误恢复策略
        
        Args:
            error_type: 错误类型
            strategy: 恢复策略函数，返回是否恢复成功
        """
        self.recovery_strategies[error_type] = strategy
    
    def attempt_recovery(self, error: OCRError) -> bool:
        """
        尝试从错误中恢复
        
        Args:
            error: OCR 错误
            
        Returns:
            是否恢复成功
        """
        strategy = self.recovery_strategies.get(error.error_type)
        if strategy:
            try:
                return strategy(error)
            except Exception as e:
                logger.error(f"错误恢复策略执行失败: {e}")
        return False
    
    def _recover_ocr_engine(self, error: OCRError) -> bool:
        """
        恢复 OCR 引擎错误
        
        Args:
            error: OCR 错误
            
        Returns:
            是否恢复成功
        """
        try:
            # 注意：不再尝试创建新的 OCR 引擎实例，因为这可能导致循环导入
            # 错误恢复应该由调用方处理，而不是在错误处理器中创建新的实例
            logger.info("OCR 引擎错误恢复：请检查 OCR 引擎配置")
            return False
        except Exception as e:
            logger.error(f"OCR 引擎恢复失败: {e}")
            return False
    
    def _recover_file_operation(self, error: OCRError) -> bool:
        """
        恢复文件操作错误
        
        Args:
            error: OCR 错误
            
        Returns:
            是否恢复成功
        """
        try:
            # 尝试创建必要的目录
            import os
            # 从错误消息中提取路径
            if "不存在" in error.message:
                # 尝试创建目录
                path = error.message.split(":")[-1].strip()
                if path:
                    dir_path = os.path.dirname(path)
                    if dir_path and not os.path.exists(dir_path):
                        os.makedirs(dir_path, exist_ok=True)
                        return True
        except Exception as e:
            logger.error(f"文件操作恢复失败: {e}")
        return False
    
    def _recover_config(self, error: OCRError) -> bool:
        """
        恢复配置错误
        
        Args:
            error: OCR 错误
            
        Returns:
            是否恢复成功
        """
        try:
            from .config import get_config_manager
            config = get_config_manager()
            # 尝试重新加载配置
            config._load()
            return True
        except Exception as e:
            logger.error(f"配置恢复失败: {e}")
            return False
    
    def register_callback(self, error_type: ErrorType, callback: Callable[[OCRError], None]):
        """
        注册错误回调
        
        Args:
            error_type: 错误类型
            callback: 回调函数
        """
        if callback not in self.error_callbacks[error_type]:
            self.error_callbacks[error_type].append(callback)
    
    def unregister_callback(self, error_type: ErrorType, callback: Callable[[OCRError], None]):
        """
        注销错误回调
        
        Args:
            error_type: 错误类型
            callback: 回调函数
        """
        if callback in self.error_callbacks[error_type]:
            self.error_callbacks[error_type].remove(callback)
    
    def handle_error(self, error: OCRError):
        """
        处理错误
        
        Args:
            error: OCR 错误
        """
        # 记录错误统计
        self.error_stats[error.error_type] += 1
        
        # 记录错误日志
        timestamp_str = error.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        if error.original_error:
            logger.error(f"[{error.error_type.value}] [{timestamp_str}] {error.message}", exc_info=error.original_error)
        else:
            logger.error(f"[{error.error_type.value}] [{timestamp_str}] {error.message}")
        
        # 尝试错误恢复
        recovery_success = self.attempt_recovery(error)
        if recovery_success:
            logger.info(f"[{error.error_type.value}] 错误恢复成功")
        
        # 调用注册的回调
        for callback in self.error_callbacks[error.error_type]:
            try:
                callback(error)
            except Exception as e:
                logger.error(f"错误回调执行失败: {e}")
        
        # 调用通用回调
        for callback in self.error_callbacks[ErrorType.UNKNOWN]:
            try:
                callback(error)
            except Exception as e:
                logger.error(f"通用错误回调执行失败: {e}")
    
    def wrap_with_error_handling(self, error_type: ErrorType, message: str):
        """
        装饰器：包装函数，自动处理错误
        
        Args:
            error_type: 错误类型
            message: 错误信息
        """
        def decorator(func):
            def wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except OCRError as e:
                    # 已经是 OCRError，直接处理
                    self.handle_error(e)
                    raise
                except Exception as e:
                    # 转换为 OCRError
                    error = OCRError(error_type, message, e)
                    self.handle_error(error)
                    raise error
            return wrapper
        return decorator
    
    def get_error_stats(self) -> Dict[ErrorType, int]:
        """
        获取错误统计
        
        Returns:
            错误类型到错误数量的映射
        """
        return self.error_stats
    
    def reset_error_stats(self):
        """
        重置错误统计
        """
        for error_type in ErrorType:
            self.error_stats[error_type] = 0


# 全局错误处理器实例
_error_handler = ErrorHandler()


def get_error_handler() -> ErrorHandler:
    """
    获取全局错误处理器实例
    
    Returns:
        错误处理器实例
    """
    return _error_handler


def handle_error(error: OCRError):
    """
    处理错误的便捷函数
    
    Args:
        error: OCR 错误
    """
    get_error_handler().handle_error(error)


def error_handling(error_type: ErrorType, message: str):
    """
    错误处理装饰器的便捷函数
    
    Args:
        error_type: 错误类型
        message: 错误信息
    """
    return get_error_handler().wrap_with_error_handling(error_type, message)


def get_error_stats() -> Dict[ErrorType, int]:
    """
    获取错误统计的便捷函数
    
    Returns:
        错误类型到错误数量的映射
    """
    return get_error_handler().get_error_stats()


def reset_error_stats():
    """
    重置错误统计的便捷函数
    """
    get_error_handler().reset_error_stats()