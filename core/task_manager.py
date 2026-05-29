# -*- coding: utf-8 -*-
"""
任务调度器 - 核心层统一任务管理
所有耗时任务（OCR识别、导出等）都通过这里调度
"""

import logging
import uuid
import threading
import queue
import time
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from PySide6.QtCore import QObject, Signal, QThread, QThreadPool, QRunnable
from .log_context import LogContext

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """任务类型枚举"""
    OCR_SINGLE = "ocr_single"           # 单图OCR识别
    OCR_BATCH = "ocr_batch"             # 批量OCR识别
    OCR_INIT = "ocr_init"               # OCR引擎初始化
    OCR_SHUTDOWN = "ocr_shutdown"       # OCR引擎关闭（资源回收）
    EXPORT = "export"                   # 导出结果
    SCAN_DIRECTORY = "scan_directory"   # 扫描目录
    CUSTOM = "custom"                   # 自定义任务
    # Excel 数据处理
    EXCEL_LOAD = "excel_load"           # 加载 Excel 文件
    EXCEL_CLEAN = "excel_clean"         # 数据清洗
    EXCEL_PIVOT = "excel_pivot"        # 透视表生成
    EXCEL_EXPORT = "excel_export"       # 导出 Excel 结果
    # 重新解析（使用不同模板解析已有识别结果）
    OCR_REPARSE = "ocr_reparse"         # 重新解析识别结果


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"       # 等待中
    RUNNING = "running"       # 执行中
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"         # 失败
    CANCELLED = "cancelled"   # 已取消


@dataclass
class Task:
    """任务数据类"""
    task_id: str
    task_type: TaskType
    params: Dict[str, Any]
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Any = None
    error: Optional[str] = None

    def __post_init__(self):
        if isinstance(self.task_type, str):
            self.task_type = TaskType(self.task_type)


@dataclass
class TaskResult:
    """任务结果数据类"""
    task_id: str
    success: bool
    data: Any = None
    error: Optional[str] = None
    progress: Optional[Dict] = None


class TaskCallback:
    """任务回调封装"""

    def __init__(self,
                 on_progress: Optional[Callable] = None,
                 on_complete: Optional[Callable] = None,
                 on_error: Optional[Callable] = None,
                 on_cancel: Optional[Callable] = None):
        self.on_progress = on_progress
        self.on_complete = on_complete
        self.on_error = on_error
        self.on_cancel = on_cancel

    def progress(self, task_id: str, current: int, total: int, **kwargs):
        if self.on_progress:
            try:
                self.on_progress(TaskResult(
                    task_id=task_id,
                    success=True,
                    progress={"current": current, "total": total, **kwargs}
                ))
            except Exception as e:
                logger.warning(f"[TaskCallback] progress callback error: {e}")

    def complete(self, task_id: str, data: Any):
        logger.debug(f"[TaskCallback] complete 被调用: task_id={task_id}, data 类型={type(data)}")
        if self.on_complete:
            try:
                self.on_complete(TaskResult(task_id=task_id, success=True, data=data))
                logger.debug(f"[TaskCallback] on_complete 调用完成")
            except Exception as e:
                logger.warning(f"[TaskCallback] complete callback error: {e}")

    def error(self, task_id: str, error_msg: str):
        if self.on_error:
            try:
                self.on_error(TaskResult(task_id=task_id, success=False, error=error_msg))
            except Exception as e:
                logger.warning(f"[TaskCallback] error callback error: {e}")

    def cancel(self, task_id: str):
        if self.on_cancel:
            try:
                self.on_cancel(TaskResult(task_id=task_id, success=False, error="任务已取消"))
            except Exception as e:
                logger.warning(f"[TaskCallback] cancel callback error: {e}")


class TaskExecutor(QRunnable):
    """
    任务执行器 - QRunnable 实现
    在后台线程中执行具体任务
    """

    class Signals(QObject):
        """Qt 信号"""
        progress = Signal(str, int, int, dict)  # task_id, current, total, extra
        complete = Signal(str, object)           # task_id, result
        error = Signal(str, str)                  # task_id, error_msg
        cancelled = Signal(str)                   # task_id

    def __init__(self, task: Task, executor_map: Dict[TaskType, Callable]):
        super().__init__()
        self.task = task
        self.executor_map = executor_map
        self._is_cancelled = False
        self.signals = self.Signals()  # 实例属性，每个任务独立信号
        # 不设置 setAutoDelete(True)，由 TaskManager 手动管理生命周期
        # 避免 PySide6 中 QRunnable 被自动销毁时导致内部 QObject 信号源被删除

    def run(self):
        """执行任务"""
        _task_start = time.time()
        try:
            self.task.status = TaskStatus.RUNNING
            self.task.started_at = time.time()
            logger.info("[TaskExecutor] 开始执行任务: %s, 类型: %s",
                        self.task.task_id, self.task.task_type.value)

            # 检查是否已取消
            if self._is_cancelled:
                self.task.status = TaskStatus.CANCELLED
                try:
                    self.signals.cancelled.emit(self.task.task_id)
                except RuntimeError:
                    pass
                return

            # 获取对应的执行器
            executor = self.executor_map.get(self.task.task_type)
            if not executor:
                raise ValueError(f"未找到任务类型的执行器: {self.task.task_type}")

            # 创建进度回调
            def progress_callback(current: int, total: int, **kwargs):
                if self._is_cancelled:
                    raise InterruptedError("任务已被取消")
                try:
                    self.signals.progress.emit(self.task.task_id, current, total, kwargs)
                except RuntimeError:
                    # Signal source has been deleted，忽略以避免崩溃
                    pass

            # 创建中断检查函数
            def is_interrupted() -> bool:
                return self._is_cancelled

            # 执行任务
            result = executor(
                self.task.params,
                progress_callback=progress_callback,
                is_interrupted=is_interrupted
            )

            # 检查是否被取消
            if self._is_cancelled:
                self.task.status = TaskStatus.CANCELLED
                logger.debug(f"[TaskExecutor] 任务被取消: {self.task.task_id}")
                try:
                    self.signals.cancelled.emit(self.task.task_id)
                except RuntimeError:
                    pass
            else:
                self.task.result = result
                self.task.status = TaskStatus.COMPLETED
                self.task.completed_at = time.time()
                logger.debug(f"[TaskExecutor] 任务完成，发送 complete 信号: {self.task.task_id}, result 类型={type(result)}")
                try:
                    self.signals.complete.emit(self.task.task_id, result)
                except RuntimeError:
                    pass

            logger.info("[TaskExecutor] 任务完成: %s, 状态: %s, 耗时: %.1fs",
                       self.task.task_id, self.task.status.value, time.time() - _task_start)

        except InterruptedError:
            self.task.status = TaskStatus.CANCELLED
            try:
                self.signals.cancelled.emit(self.task.task_id)
            except RuntimeError:
                pass
            logger.info("[TaskExecutor] 任务已取消: %s, 耗时: %.1fs",
                       self.task.task_id, time.time() - _task_start)

        except Exception as e:
            self.task.status = TaskStatus.FAILED
            self.task.error = str(e)
            self.task.completed_at = time.time()
            try:
                self.signals.error.emit(self.task.task_id, str(e))
            except RuntimeError:
                pass
            logger.error("[TaskExecutor] 任务失败: %s, 类型: %s, 错误: %s, 耗时: %.1fs",
                        self.task.task_id, self.task.task_type.value, e, time.time() - _task_start,
                        exc_info=True)

    def cancel(self):
        """请求取消任务"""
        self._is_cancelled = True


class TaskManager(QObject):
    """
    任务管理器 - 核心层统一任务调度
    使用 QThreadPool 管理所有后台任务
    """

    # Qt 信号
    task_created = Signal(str, str)      # task_id, task_type
    task_progress = Signal(str, int, int, dict)  # task_id, current, total, extra
    task_completed = Signal(str, object)  # task_id, result
    task_failed = Signal(str, str)        # task_id, error_msg
    task_cancelled = Signal(str)          # task_id
    all_tasks_completed = Signal()        # 所有任务完成

    _instance = None
    _instance_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> 'TaskManager':
        """获取单例实例"""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def __init__(self, max_workers: int = 4):
        super().__init__()
        # 单例模式，禁止外部创建
        if TaskManager._instance is not None and TaskManager._instance is not self:
            raise RuntimeError("TaskManager 是单例，请使用 get_instance() 获取实例")

        self._tasks: Dict[str, Task] = {}
        self._executors: Dict[str, TaskExecutor] = {}
        self._callbacks: Dict[str, TaskCallback] = {}
        self._task_lock = threading.RLock()

        # 使用 QThreadPool 管理线程
        self._thread_pool = QThreadPool.globalInstance()
        self._thread_pool.setMaxThreadCount(max_workers)

        # 执行器映射：TaskType -> executor_function
        self._executor_map: Dict[TaskType, Callable] = {}

        logger.info(f"[TaskManager] 初始化完成，最大并发: {max_workers}")

    def register_executor(self, task_type: TaskType, executor: Callable):
        """
        注册任务执行器

        Args:
            task_type: 任务类型
            executor: 执行器函数，签名为:
                      def executor(params: Dict, progress_callback: Callable, is_interrupted: Callable) -> Any
        """
        self._executor_map[task_type] = executor
        logger.info(f"[TaskManager] 注册执行器: {task_type.value}")

    def submit_task(self,
                   task_type: TaskType,
                   params: Dict[str, Any],
                   callback: Optional[TaskCallback] = None,
                   task_id: Optional[str] = None) -> str:
        """
        提交任务

        Args:
            task_type: 任务类型
            params: 任务参数
            callback: 回调函数
            task_id: 任务ID（可选，不提供则自动生成）

        Returns:
            任务ID
        """
        if task_type not in self._executor_map:
            raise ValueError(f"未注册的任务类型: {task_type.value}，请先调用 register_executor()")

        # 生成任务ID
        if not task_id:
            task_id = f"{task_type.value}_{uuid.uuid4().hex[:8]}"

        # 创建任务
        task = Task(
            task_id=task_id,
            task_type=task_type,
            params=params
        )

        with self._task_lock:
            self._tasks[task_id] = task
            if callback:
                self._callbacks[task_id] = callback

        # 创建执行器
        executor = TaskExecutor(task, self._executor_map)

        # 连接信号
        executor.signals.progress.connect(self._on_progress)
        executor.signals.complete.connect(self._on_complete)
        executor.signals.error.connect(self._on_error)
        executor.signals.cancelled.connect(self._on_cancelled)

        with self._task_lock:
            self._executors[task_id] = executor

        # 提交到线程池
        self._thread_pool.start(executor)

        logger.info(f"[TaskManager] 提交任务: {task_id}, 类型: {task_type.value}")
        self.task_created.emit(task_id, task_type.value)

        return task_id

    def cancel_task(self, task_id: str) -> bool:
        """
        取消任务

        Args:
            task_id: 任务ID

        Returns:
            是否成功取消
        """
        with self._task_lock:
            if task_id not in self._executors:
                logger.warning(f"[TaskManager] 任务不存在: {task_id}")
                return False

            executor = self._executors[task_id]
            executor.cancel()

            logger.info(f"[TaskManager] 请求取消任务: {task_id}")
            return True

    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """获取任务状态"""
        with self._task_lock:
            if task_id in self._tasks:
                return self._tasks[task_id].status
            return None

    def get_task_result(self, task_id: str) -> Optional[Any]:
        """获取任务结果"""
        with self._task_lock:
            if task_id in self._tasks:
                return self._tasks[task_id].result
            return None

    def get_all_tasks(self) -> List[Task]:
        """获取所有任务"""
        with self._task_lock:
            return list(self._tasks.values())

    def get_pending_tasks(self) -> List[Task]:
        """获取等待中的任务"""
        with self._task_lock:
            return [t for t in self._tasks.values() if t.status == TaskStatus.PENDING]

    def get_running_tasks(self) -> List[Task]:
        """获取正在执行的任务"""
        with self._task_lock:
            return [t for t in self._tasks.values() if t.status == TaskStatus.RUNNING]

    def clear_completed_tasks(self):
        """清理已完成的任务记录"""
        with self._task_lock:
            completed_ids = [
                tid for tid, t in self._tasks.items()
                if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
            ]
            for tid in completed_ids:
                del self._tasks[tid]
                self._executors.pop(tid, None)
                self._callbacks.pop(tid, None)
            logger.info(f"[TaskManager] 清理了 {len(completed_ids)} 个已完成任务")

    # ==================== 内部信号处理 ====================

    def _on_progress(self, task_id: str, current: int, total: int, extra: dict):
        """进度更新"""
        self.task_progress.emit(task_id, current, total, extra)

        # 调用回调
        with self._task_lock:
            callback = self._callbacks.get(task_id)

        if callback:
            callback.progress(task_id, current, total, **extra)

    def _on_complete(self, task_id: str, result: Any):
        """任务完成"""
        logger.debug(f"[TaskManager] _on_complete 被调用: task_id={task_id}, result 类型={type(result)}")
        self.task_completed.emit(task_id, result)

        # 调用回调
        with self._task_lock:
            callback = self._callbacks.pop(task_id, None)

        logger.debug(f"[TaskManager] _on_complete: callback={'存在' if callback else '不存在'}")
        if callback:
            callback.complete(task_id, result)
            logger.debug(f"[TaskManager] _on_complete: callback.complete 调用完成")

        # 检查是否所有任务都完成
        self._check_all_completed()

        # 清理 executor 引用，避免内存泄漏
        with self._task_lock:
            self._executors.pop(task_id, None)

    def _on_error(self, task_id: str, error_msg: str):
        """任务失败"""
        # 记录更详细的错误上下文
        with self._task_lock:
            task = self._tasks.get(task_id)
            task_type = task.task_type.value if task else "unknown"
        logger.warning("[TaskManager] 任务失败: %s (类型: %s) — %s", task_id, task_type, error_msg)
        
        self.task_failed.emit(task_id, error_msg)

        # 调用回调
        with self._task_lock:
            callback = self._callbacks.pop(task_id, None)

        if callback:
            callback.error(task_id, error_msg)

        # 检查是否所有任务都完成
        self._check_all_completed()

        # 清理 executor 引用，避免内存泄漏
        with self._task_lock:
            self._executors.pop(task_id, None)

    def _on_cancelled(self, task_id: str):
        """任务取消"""
        self.task_cancelled.emit(task_id)

        # 调用回调
        with self._task_lock:
            callback = self._callbacks.pop(task_id, None)

        if callback:
            callback.cancel(task_id)

        # 检查是否所有任务都完成
        self._check_all_completed()

        # 清理 executor 引用，避免内存泄漏
        with self._task_lock:
            self._executors.pop(task_id, None)

    def _check_all_completed(self):
        """检查是否所有任务都完成"""
        with self._task_lock:
            has_active = any(
                t.status in (TaskStatus.PENDING, TaskStatus.RUNNING)
                for t in self._tasks.values()
            )

        if not has_active:
            logger.info("[TaskManager] 所有任务已完成")
            self.all_tasks_completed.emit()


# ==================== 预定义执行器 ====================

def create_ocr_executor(ocr_engine, config_manager, result_manager=None) -> Callable:
    """
    创建 OCR 执行器

    Args:
        ocr_engine: OCR引擎实例
        config_manager: 配置管理器
        result_manager: 结果缓存管理器（可选，传入后自动启用缓存）

    Returns:
        执行器函数
    """

    def ocr_executor(params: Dict,
                     progress_callback: Callable,
                     is_interrupted: Callable) -> List[Dict]:
        """
        OCR 执行器函数
        """
        image_paths = params.get("image_paths", [])
        if isinstance(image_paths, str):
            image_paths = [image_paths]

        config = params.get("config", config_manager)
        template_id = params.get("template_id", None)

        # 加载模板解析器（懒加载，避免顶层 import 开销）
        text_parser = None
        if template_id:
            try:
                from core.template_manager import get_template_manager
                from core.text_parser import TextParser
                tm = get_template_manager()
                template = tm.get_template(template_id)
                if template:
                    text_parser = TextParser(template)
                else:
                    logger.warning(f"[TaskManager] 模板不存在: {template_id}，跳过解析")
            except Exception as e:
                logger.warning(f"[TaskManager] 加载模板失败: {e}，跳过解析")

        results = []
        total = len(image_paths)

        for i, image_path in enumerate(image_paths):
            # 检查中断
            if is_interrupted():
                raise InterruptedError("任务已被取消")

            # ★ 核心改动：先查缓存，命中则跳过引擎
            cached_result = None
            if result_manager:
                try:
                    cached_result = result_manager.get_result(image_path)
                except Exception as e:
                    logger.warning(f"[TaskManager] 读取缓存失败 {image_path}: {e}")

            if cached_result:
                logger.info(f"[TaskManager] 缓存命中，跳过引擎: {image_path.split('/')[-1].split('\\')[-1]}")
                result = cached_result
            else:
                # 缓存未命中，调用引擎
                result = ocr_engine.recognize_auto(
                    image_path,
                    config=config,
                    progress_callback=None,
                    is_interrupted=is_interrupted
                )
                # ★ 识别成功，写入缓存
                if result_manager and result.get("success"):
                    try:
                        result_manager.add_result(image_path, result)
                    except Exception as e:
                        logger.warning(f"[TaskManager] 写入缓存失败 {image_path}: {e}")

            # 先记录结果
            result_item = {
                "file_path": image_path,
                "file_name": image_path.split("\\")[-1] if "\\" in image_path else image_path.split("/")[-1],
                "result": result
            }

            # ★ 新增：用模板解析识别结果
            if text_parser and result.get("success"):
                try:
                    texts = result.get("texts", [])
                    text = "\n".join(texts) if texts else ""
                    result_item["extracted"] = text_parser.parse(text)
                except Exception as e:
                    logger.warning(f"[TaskManager] 解析失败 {image_path}: {e}")
                    result_item["extracted"] = {}

            results.append(result_item)

            # 报告进度（包含已完成的结果，用于实时更新UI）
            progress_callback(
                i + 1,
                total,
                filename=image_path,
                completed=True,
                result=result_item
            )

        return results

    return ocr_executor
    

def create_ocr_shutdown_executor(ocr_engine) -> Callable:
    """
    创建 OCR 关闭执行器（资源回收）
    
    Args:
        ocr_engine: OCR引擎实例
    
    Returns:
        执行器函数
    """
    
    def ocr_shutdown_executor(params: Dict,
                              progress_callback: Callable,
                              is_interrupted: Callable) -> Dict:
        """
        OCR 关闭执行器函数
        
        Args:
            params: 参数字典（可以为空）
            progress_callback: 进度回调
            is_interrupted: 中断检查 () -> bool
        
        Returns:
            {"success": bool, "message": str}
        """
        try:
            progress_callback(0, 1, stage="正在关闭 OCR 引擎...")
            
            # 调用 OCR 引擎的 shutdown() 方法
            ocr_engine.shutdown()
            
            progress_callback(1, 1, stage="OCR 引擎已关闭")
            
            return {
                "success": True,
                "message": "OCR 引擎已关闭，资源已回收"
            }
            
        except Exception as e:
            logger.error(f"[TaskManager] OCR 关闭执行器异常: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"关闭 OCR 引擎失败: {str(e)}"
            }
    
    return ocr_shutdown_executor
    

def create_export_executor(exporter) -> Callable:
    """
    创建导出执行器

    Args:
        exporter: 导出器实例

    Returns:
        执行器函数
    """

    def export_executor(params: Dict,
                       progress_callback: Callable,
                       is_interrupted: Callable) -> Dict:
        """
        导出执行器函数
        
        Args:
            params: 参数字典，包含:
                   - format: 导出格式
                   - file_path: 输出文件路径
                   - results: 要导出的结果列表
            progress_callback: 进度回调
            is_interrupted: 中断检查
            
        Returns:
            导出结果
        """
        export_format = params.get("format", "TXT")
        file_path = params.get("file_path")
        results = params.get("results", [])
        column_headers = params.get("column_headers", None)
        include_original_text = params.get("include_original_text", True)  # 新增：读取参数
        
        progress_callback(1, 3, stage="准备导出")
        
        if is_interrupted():
            raise InterruptedError("任务已被取消")
        
        progress_callback(2, 3, stage="正在导出")
        
        # 调用 export_batch，传递 results 列表和 column_headers
        # export_batch 支持三种格式，输出结构优化，支持动态列
        result_file_path = exporter.export_batch(
            results, 
            export_format, 
            file_path, 
            column_headers=column_headers,
            include_original_text=include_original_text  # 新增：传递参数
        )
        
        progress_callback(3, 3, stage="导出完成")
        
        return {
            "success": result_file_path is not None,
            "file_path": result_file_path or file_path,
            "format": export_format,
            "count": len(results)
        }

    return export_executor


def create_scan_executor() -> Callable:
    """创建目录扫描执行器"""

    def scan_executor(params: Dict,
                     progress_callback: Callable,
                     is_interrupted: Callable) -> List[str]:
        """
        扫描执行器函数
        
        Args:
            params: 参数字典，包含:
                   - directory: 目录路径
                   - recursive: 是否递归
            progress_callback: 进度回调
            is_interrupted: 中断检查
            
        Returns:
            文件路径列表
        """
        import os
        from pathlib import Path

        directory = params.get("directory", "")
        recursive = params.get("recursive", True)

        if not directory or not os.path.exists(directory):
            return []

        progress_callback(1, 2, stage="扫描中")

        if is_interrupted():
            raise InterruptedError("任务已被取消")

        valid_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp', '.tiff', '.tif'}
        image_files = []

        if recursive:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if Path(file).suffix.lower() in valid_extensions:
                        image_files.append(os.path.join(root, file))
        else:
            for file in os.listdir(directory):
                file_path = os.path.join(directory, file)
                if os.path.isfile(file_path) and Path(file).suffix.lower() in valid_extensions:
                    image_files.append(file_path)

        image_files.sort()

        progress_callback(2, 2, stage="扫描完成", count=len(image_files))

        return image_files

    return scan_executor


def create_ocr_init_executor(ocr_engine) -> Callable:
    """
    创建 OCR 引擎初始化执行器
    
    Args:
        ocr_engine: OCR引擎实例
        
    Returns:
        执行器函数
    """
    
    def ocr_init_executor(params: Dict,
                         progress_callback: Callable,
                         is_interrupted: Callable) -> Dict:
        """
        OCR 初始化执行器函数
        
        Args:
            params: 参数字典，包含:
                   - check_config: 是否检查配置 (默认 True)
            progress_callback: 进度回调 (current, total, **kwargs)
            is_interrupted: 中断检查 () -> bool
            
        Returns:
            初始化结果字典 {"success": bool, "message": str}
        """
        progress_callback(1, 3, stage="检查配置")
        
        if is_interrupted():
            raise InterruptedError("初始化已被取消")
        
        # 检查配置
        check_config = params.get("check_config", True)
        if check_config:
            if not ocr_engine.check_config():
                return {
                    "success": False,
                    "message": "OCR引擎配置不完整"
                }
        
        progress_callback(2, 3, stage="正在初始化")
        
        if is_interrupted():
            raise InterruptedError("初始化已被取消")
        
        # 执行初始化
        success = ocr_engine.initialize()
        
        progress_callback(3, 3, stage="初始化完成")
        
        if success:
            return {
                "success": True,
                "message": "OCR引擎初始化成功"
            }
        else:
            return {
                "success": False,
                "message": "OCR引擎初始化失败"
            }
    
    return ocr_init_executor

def create_reparse_executor() -> Callable:
    """
    创建重新解析执行器（使用不同模板解析已有识别结果）
    
    Returns:
        执行器函数
    """
    
    def reparse_executor(params: Dict,
                        progress_callback: Callable,
                        is_interrupted: Callable) -> List[Dict]:
        """
        重新解析执行器函数
        
        Args:
            params: 参数字典，包含:
                   - results: 已有识别结果列表（包含 'text' 字段）
                   - template_id: 识别模板ID
            progress_callback: 进度回调 (current, total, **kwargs)
            is_interrupted: 中断检查 () -> bool
            
        Returns:
            重新解析后的结果列表（包含 'extracted' 字段）
        """
        results = params.get("results", [])
        template_id = params.get("template_id", None)
        
        if not template_id:
            raise ValueError("缺少 template_id 参数")
        
        if not results:
            return []
        
        # 加载模板解析器
        try:
            from core.template_manager import get_template_manager
            from core.text_parser import TextParser
            tm = get_template_manager()
            template = tm.get_template(template_id)
            if not template:
                raise ValueError(f"模板不存在: {template_id}")
            text_parser = TextParser(template)
        except Exception as e:
            logger.error(f"[TaskManager] 加载模板失败: {e}", exc_info=True)
            raise
        
        total = len(results)
        parsed_results = []
        
        for i, item in enumerate(results):
            # 检查中断
            if is_interrupted():
                raise InterruptedError("任务已被取消")
            
            # 获取识别文本
            text = item.get("text", "")
            if not text and "result" in item:
                # 兼容另一种数据结构
                result = item.get("result", {})
                if result.get("code") == 100 and result.get("data"):
                    texts = [line.get("text", "") for line in result["data"] if isinstance(line, dict)]
                    text = "\n".join(texts)
            
            # 解析文本
            try:
                extracted = text_parser.parse(text)
                new_item = item.copy()
                new_item["extracted"] = extracted
                parsed_results.append(new_item)
            except Exception as e:
                logger.warning(f"[TaskManager] 解析失败 {item.get('file_name', '')}: {e}")
                new_item = item.copy()
                new_item["extracted"] = {}
                parsed_results.append(new_item)
            
            # 报告进度
            progress_callback(i + 1, total, filename=item.get("file_name", ""))
        
        return parsed_results
    
    return reparse_executor
