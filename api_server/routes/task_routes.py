"""
任务相关API路由
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from ..tasks.task_manager import task_manager
from ..utils.response import APIResponse, format_task_result
from ..utils.exceptions import TaskNotFoundException

router = APIRouter(prefix="/task", tags=["task"])


@router.get("/{task_id}")
async def get_task_status(task_id: str) -> Dict[str, Any]:
    """查询任务状态"""
    task_info = task_manager.get_task_info(task_id)
    if not task_info:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    return APIResponse.success(format_task_result(task_info))


@router.post("/submit")
async def submit_task(module: str, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """提交异步任务"""
    # 这是一个通用的任务提交接口，具体实现将在主API中定义
    # 这里只是一个占位符
    raise HTTPException(status_code=501, detail="Generic task submission not implemented here")


@router.delete("/{task_id}")
async def cancel_task(task_id: str) -> Dict[str, Any]:
    """取消任务"""
    success = task_manager.cancel_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found or cannot be cancelled")
    
    return APIResponse.success({"task_id": task_id}, "Task cancelled successfully")


@router.get("/")
async def list_all_tasks() -> Dict[str, Any]:
    """列出所有任务"""
    all_tasks = task_manager.get_all_tasks()
    formatted_tasks = {tid: format_task_result(info) for tid, info in all_tasks.items()}
    
    return APIResponse.success(formatted_tasks, "All tasks retrieved successfully")