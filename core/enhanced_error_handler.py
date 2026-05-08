# -*- coding: utf-8 -*-
"""
增强版错误处理系统
为CoreAPI提供统一的错误处理机制
"""

import logging
import traceback
from enum import Enum
from typing import Any, Dict, Optional, Callable, Union
from datetime import datetime


logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """错误类型枚举"""
    OCR_ENGINE = "OCR引擎错误"
    CONFIG = "配置错误"
    EXPORT = "导出错误"
    FILE = "文件错误"
    NETWORK = "网络错误"
    PERMISSION = "权限错误"
    VALIDATION = "验证错误"
    TIMEOUT = "超时错误"
    MEMORY = "内存错误"


class ErrorCode(Enum):
    """错误代码枚举"""
    # OCR相关错误
    OCR_ENGINE_NOT_INITIALIZED = 1001
    OCR_INVALID_IMAGE = 1002
    OCR_RECOGNITION_FAILED = 1003
    OCR_ENGINE_TIMEOUT = 1004
    
    # 配置相关错误
    CONFIG_FILE_NOT_FOUND = 2001
    CONFIG_INVALID_FORMAT = 2002
    CONFIG_VALUE_ERROR = 2003
    CONFIG_SAVE_FAILED = 2004
    
    # 文件相关错误
    FILE_NOT_FOUND = 3001
    FILE_PERMISSION_DENIED = 3002
    FILE_INVALID_FORMAT = 3003
    FILE_TOO_LARGE = 3004
    
    # 导出相关错误
    EXPORT_FORMAT_UNSUPPORTED = 4001
    EXPORT_PATH_INVALID = 4002
    EXPORT_FAILED = 4003
    
    # 通用错误
    UNKNOWN_ERROR = 9999
    OPERATION_CANCELLED = 9998


class EnhancedError(Exception):
    """增强错误类，包含更多错误信息"""
    
    def __init__(
        self, 
        message: str, 
        error_type: ErrorType, 
        error_code: ErrorCode,
        details: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.error_code = error_code
        self.details = details or {}
        self.original_exception = original_exception
        self.timestamp = datetime.now()
        self.traceback_info = traceback.format_exc() if original_exception else None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，便于序列化"""
        return {
            'message': self.message,
            'error_type': self.error_type.value,
            'error_code': self.error_code.value,
            'details': self.details,
            'timestamp': self.timestamp.isoformat(),
            'traceback': self.traceback_info
        }


class ErrorResult:
    """标准化错误结果类"""
    
    def __init__(
        self, 
        success: bool = False, 
        data: Optional[Any] = None, 
        error: Optional[EnhancedError] = None,
        warnings: Optional[list] = None
    ):
        self.success = success
        self.data = data or {}
        self.error = error
        self.warnings = warnings or []
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'success': self.success,
            'data': self.data,
            'error': self.error.to_dict() if self.error else None,
            'warnings': self.warnings
        }
    
    @classmethod
    def success_result(cls, data: Any = None, warnings: Optional[list] = None):
        """创建成功结果"""
        return cls(success=True, data=data, warnings=warnings or [])
    
    @classmethod
    def error_result(cls, error: EnhancedError):
        """创建错误结果"""
        return cls(success=False, error=error)


class ErrorHandler:
    """增强版错误处理器"""
    
    def __init__(self):
        self.error_handlers = {}
        self.default_handler = self._default_error_handler
    
    def register_handler(self, error_type: ErrorType, handler_func: Callable):
        """注册特定错误类型的处理函数"""
        self.error_handlers[error_type] = handler_func
    
    def handle_error(
        self, 
        error: Union[EnhancedError, Exception], 
        show_ui: bool = True,
        parent_widget: Optional[object] = None
    ) -> ErrorResult:
        """处理错误"""
        # 如果传入的是普通异常，转换为增强错误
        if not isinstance(error, EnhancedError):
            enhanced_error = EnhancedError(
                message=str(error),
                error_type=ErrorType.UNKNOWN_ERROR,
                error_code=ErrorCode.UNKNOWN_ERROR,
                original_exception=error
            )
        else:
            enhanced_error = error
        
        # 记录日志
        self._log_error(enhanced_error)
        
        # 根据错误类型选择处理函数
        handler = self.error_handlers.get(enhanced_error.error_type, self.default_handler)
        
        # 执行处理
        result = handler(enhanced_error, parent_widget)
        
        # 不再在核心模块中显示UI错误，而是由调用方决定如何处理
        # UI相关的错误显示应该在界面层处理
        
        return ErrorResult.error_result(enhanced_error)
    
    def _default_error_handler(self, error: EnhancedError, parent_widget: Optional[object] = None):
        """默认错误处理器"""
        logger.error(f"Default error handler: {error.message}", exc_info=True)
        return error
    
    def _log_error(self, error: EnhancedError):
        """记录错误日志"""
        logger.error(
            f"Error [{error.error_code.value}] {error.error_type.value}: {error.message}",
            extra={
                'error_code': error.error_code.value,
                'error_type': error.error_type.value,
                'details': error.details,
                'timestamp': error.timestamp.isoformat()
            }
        )


# 全局错误处理器实例
_error_handler_instance = None


def get_error_handler() -> ErrorHandler:
    """获取全局错误处理器实例"""
    global _error_handler_instance
    if _error_handler_instance is None:
        # 直接创建 ErrorHandler 实例，不进行线程检查
        # 这样可以确保在 QApplication 尚未创建时也能正常工作
        _error_handler_instance = ErrorHandler()
    return _error_handler_instance


def error_handling(
    error_type: ErrorType, 
    default_message: str = "操作失败",
    error_code: ErrorCode = ErrorCode.UNKNOWN_ERROR
):
    """装饰器：错误处理装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # 获取错误处理器
                handler = get_error_handler()
                
                # 创建增强错误
                if not isinstance(e, EnhancedError):
                    enhanced_error = EnhancedError(
                        message=f"{default_message}: {str(e)}",
                        error_type=error_type,
                        error_code=error_code,
                        original_exception=e
                    )
                else:
                    enhanced_error = e
                
                # 处理错误
                return handler.handle_error(enhanced_error, show_ui=True)
        
        return wrapper
    return decorator


# 预定义的错误创建函数
def create_ocr_engine_error(message: str, details: Optional[Dict] = None) -> EnhancedError:
    """创建OCR引擎错误"""
    return EnhancedError(
        message=message,
        error_type=ErrorType.OCR_ENGINE,
        error_code=ErrorCode.OCR_ENGINE_NOT_INITIALIZED,
        details=details or {}
    )


def create_config_error(message: str, details: Optional[Dict] = None) -> EnhancedError:
    """创建配置错误"""
    return EnhancedError(
        message=message,
        error_type=ErrorType.CONFIG,
        error_code=ErrorCode.CONFIG_VALUE_ERROR,
        details=details or {}
    )


def create_file_error(message: str, details: Optional[Dict] = None) -> EnhancedError:
    """创建文件错误"""
    return EnhancedError(
        message=message,
        error_type=ErrorType.FILE,
        error_code=ErrorCode.FILE_NOT_FOUND,
        details=details or {}
    )


def create_export_error(message: str, details: Optional[Dict] = None) -> EnhancedError:
    """创建导出错误"""
    return EnhancedError(
        message=message,
        error_type=ErrorType.EXPORT,
        error_code=ErrorCode.EXPORT_FAILED,
        details=details or {}
    )