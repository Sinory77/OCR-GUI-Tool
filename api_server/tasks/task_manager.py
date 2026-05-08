"""
异步任务管理器
负责管理所有异步任务的生命周期
"""
import uuid
import threading
import time
from enum import Enum
from typing import Dict, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, Future
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"      # 待处理
    RUNNING = "running"      # 运行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 执行失败
    CANCELLED = "cancelled"  # 已取消


class TaskInfo:
    """任务信息类"""
    def __init__(self, task_id: str, func: Callable, args: tuple = (), kwargs: dict = None):
        self.task_id = task_id
        self.func = func
        self.args = args
        self.kwargs = kwargs or {}
        self.status = TaskStatus.PENDING
        self.created_at = datetime.now()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.result: Any = None
        self.error: Optional[str] = None
        self.future: Optional[Future] = None
        self._lock = threading.Lock()

    def update_status(self, status: TaskStatus):
        """更新任务状态"""
        with self._lock:
            self.status = status
            if status == TaskStatus.RUNNING:
                self.started_at = datetime.now()
            elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                self.completed_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        with self._lock:
            return {
                'task_id': self.task_id,
                'status': self.status.value,
                'created_at': self.created_at.isoformat() if self.created_at else None,
                'started_at': self.started_at.isoformat() if self.started_at else None,
                'completed_at': self.completed_at.isoformat() if self.completed_at else None,
                'result': self.result,
                'error': self.error,
                'has_result': self.result is not None,
                'has_error': self.error is not None
            }


class TaskManager:
    """全局任务管理器"""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._tasks: Dict[str, TaskInfo] = {}
            self._executor = ThreadPoolExecutor(max_workers=10)  # 线程池大小可配置
            self._lock = threading.RLock()  # 可重入锁
            self._timeout_seconds = 3600  # 任务超时时间（秒）
            self._initialized = True

    def submit_task(self, func: Callable, *args, **kwargs) -> str:
        """提交异步任务"""
        task_id = str(uuid.uuid4())
        
        with self._lock:
            task_info = TaskInfo(task_id, func, args, kwargs)
            self._tasks[task_id] = task_info

        # 提交到线程池执行
        future = self._executor.submit(self._execute_task, task_id, func, args, kwargs)
        
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].future = future

        logger.info(f"Submitted task {task_id}")
        return task_id

    def _execute_task(self, task_id: str, func: Callable, args: tuple, kwargs: dict):
        """执行任务的实际方法"""
        try:
            # 获取任务信息并更新状态
            with self._lock:
                if task_id not in self._tasks:
                    logger.warning(f"Task {task_id} not found in tasks registry")
                    return
                
                task_info = self._tasks[task_id]
                task_info.update_status(TaskStatus.RUNNING)

            # 执行任务
            result = func(*args, **kwargs)

            # 更新结果
            with self._lock:
                if task_id in self._tasks:
                    self._tasks[task_id].result = result
                    self._tasks[task_id].update_status(TaskStatus.COMPLETED)

            logger.info(f"Task {task_id} completed successfully")

        except Exception as e:
            # 处理异常
            error_msg = str(e)
            logger.error(f"Task {task_id} failed: {error_msg}")

            with self._lock:
                if task_id in self._tasks:
                    self._tasks[task_id].error = error_msg
                    self._tasks[task_id].update_status(TaskStatus.FAILED)

    def get_task_info(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务信息"""
        with self._lock:
            if task_id not in self._tasks:
                return None
            return self._tasks[task_id].to_dict()

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        with self._lock:
            if task_id not in self._tasks:
                return False
            
            task_info = self._tasks[task_id]
            if task_info.future and not task_info.future.done():
                # 尝试取消任务（注意：这只是尝试取消还未开始的任务）
                cancelled = task_info.future.cancel()
                if cancelled:
                    task_info.update_status(TaskStatus.CANCELLED)
                    logger.info(f"Task {task_id} cancelled")
                return cancelled
            else:
                # 任务已经开始执行或已完成，无法取消
                return False

    def cleanup_completed_tasks(self, max_age_seconds: int = 3600) -> int:
        """清理已完成的任务"""
        current_time = time.time()
        completed_tasks = []

        with self._lock:
            for task_id, task_info in self._tasks.items():
                if task_info.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                    if task_info.completed_at:
                        age = (datetime.now() - task_info.completed_at).total_seconds()
                        if age > max_age_seconds:
                            completed_tasks.append(task_id)

            # 删除过期任务
            for task_id in completed_tasks:
                del self._tasks[task_id]

        logger.info(f"Cleaned up {len(completed_tasks)} completed tasks")
        return len(completed_tasks)

    def get_all_tasks(self) -> Dict[str, Dict[str, Any]]:
        """获取所有任务信息"""
        with self._lock:
            return {task_id: task_info.to_dict() for task_id, task_info in self._tasks.items()}

    def shutdown(self, wait: bool = True):
        """关闭任务管理器"""
        self._executor.shutdown(wait=wait)
        logger.info("TaskManager shut down")


# 全局任务管理器实例
task_manager = TaskManager()