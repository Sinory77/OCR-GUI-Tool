"""
全局异常处理器
"""
import logging
from typing import Dict, Any
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from datetime import datetime

logger = logging.getLogger(__name__)


class GlobalExceptionHandler:
    """全局异常处理器"""
    
    @staticmethod
    def handle_exception(request: Request, exc: Exception) -> JSONResponse:
        """处理异常"""
        error_info = {
            "url": str(request.url),
            "method": request.method,
            "timestamp": datetime.now().isoformat(),
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
        }
        
        logger.error(f"Unhandled exception: {error_info}", exc_info=True)
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "code": 500,
                "message": f"Internal server error: {str(exc)}",
                "data": None,
                "timestamp": datetime.now().isoformat()
            }
        )


class TaskTimeoutException(Exception):
    """任务超时异常"""
    def __init__(self, task_id: str, timeout_seconds: int):
        self.task_id = task_id
        self.timeout_seconds = timeout_seconds
        super().__init__(f"Task {task_id} timed out after {timeout_seconds} seconds")


class TaskNotFoundException(Exception):
    """任务不存在异常"""
    def __init__(self, task_id: str):
        self.task_id = task_id
        super().__init__(f"Task {task_id} not found")


# 注册全局异常处理器
async def global_exception_handler(request: Request, exc: Exception):
    return GlobalExceptionHandler.handle_exception(request, exc)