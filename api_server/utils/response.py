"""
统一响应格式
"""
from typing import Any, Optional, Union
from datetime import datetime
import json


class APIResponse:
    """统一API响应格式"""
    
    @staticmethod
    def success(data: Any = None, message: str = "Success", code: int = 200) -> dict:
        """成功响应"""
        return {
            "success": True,
            "code": code,
            "message": message,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }

    @staticmethod
    def error(message: str = "Error", code: int = 500, data: Any = None) -> dict:
        """错误响应"""
        return {
            "success": False,
            "code": code,
            "message": message,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }

    @staticmethod
    def task_response(task_id: str, message: str = "Task submitted") -> dict:
        """任务提交响应"""
        return {
            "success": True,
            "code": 200,
            "message": message,
            "data": {
                "task_id": task_id
            },
            "timestamp": datetime.now().isoformat()
        }


def format_task_result(task_info: dict) -> dict:
    """格式化任务结果"""
    return {
        "task_id": task_info["task_id"],
        "status": task_info["status"],
        "created_at": task_info["created_at"],
        "started_at": task_info["started_at"],
        "completed_at": task_info["completed_at"],
        "result": task_info["result"] if task_info["has_result"] else None,
        "error": task_info["error"] if task_info["has_error"] else None
    }