"""
异步工作线程模块 - 提供通用的异步任务执行能力
所有耗时操作都应通过 Worker 在后台线程执行
"""
import os
import time
from PySide6.QtCore import (
    QThread, QObject, Signal, QThreadPool, QRunnable, 
    QTimer, QMetaObject, Qt, QElapsedTimer
)
from typing import Callable, Any, Optional, Dict, List, Set
import logging
import traceback

logger = logging.getLogger(__name__)

# 线程池配置
DEFAULT_THREAD_POOL_MAX_THREADS = 4
# 任务优先级
class TaskPriority:
    LOW = 0
    NORMAL = 1
    HIGH = 2

# 任务状态
class TaskStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskSignal(QObject):
    """任务信号包装器 - 用于 QRunnable 的信号发射"""
    progress = Signal(object)  # progress_data
    finished = Signal(object)  # result
    error = Signal(str)  # error_message
    status_changed = Signal(str, str)  # task_id, status


class AsyncTask(QRunnable):
    """
    通用异步任务 - 基于 QRunnable + QThreadPool
    适用于短任务、可并发任务（如缩略图加载、文件扫描等）
    
    使用示例:
        def on_result(result):
            print(f"任务完成: {result}")
        
        task = AsyncTask(
            worker_fn=lambda: heavy_computation(),
            on_finished=on_result,
            on_error=lambda e: print(f"错误: {e}"),
            on_progress=lambda p: print(f"进度: {p}"),
        )
        task.start()
    """
    
    def __init__(
        self,
        worker_fn: Callable,
        on_finished: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        on_progress: Optional[Callable] = None,
        task_id: str = "",
        priority: int = TaskPriority.NORMAL,
        timeout: Optional[int] = None,  # 超时时间（秒）
    ):
        super().__init__()
        self.worker_fn = worker_fn
        self.on_finished = on_finished
        self.on_error = on_error
        self.on_progress = on_progress
        self.task_id = task_id or f"task_{int(time.time() * 1000)}"
        self.priority = priority
        self.timeout = timeout
        self.setAutoDelete(True)
        self._is_cancelled = False
        
        # 信号发射器（用于跨线程安全通信）
        self.signals = TaskSignal()
        
        # 连接信号到回调
        if on_finished:
            self.signals.finished.connect(on_finished)
        if on_error:
            self.signals.error.connect(on_error)
        if on_progress:
            self.signals.progress.connect(on_progress)
    
    def run(self):
        """在线程池中执行任务"""
        timer = QElapsedTimer()
        timer.start()
        
        try:
            logger.debug(f"[AsyncTask] 开始执行: {self.task_id} (优先级: {self.priority})")
            self.signals.status_changed.emit(self.task_id, TaskStatus.RUNNING)
            
            # 执行工作函数，传入进度回调
            def report_progress(data):
                if self._is_cancelled:
                    raise Exception("任务已取消")
                # 检查超时
                if self.timeout and timer.elapsed() > self.timeout * 1000:
                    raise Exception(f"任务超时（{self.timeout}秒）")
                self.signals.progress.emit(data)
            
            result = self.worker_fn(report_progress=report_progress)
            
            # 检查是否被取消
            if self._is_cancelled:
                self.signals.status_changed.emit(self.task_id, TaskStatus.CANCELLED)
                logger.debug(f"[AsyncTask] 任务被取消: {self.task_id}")
                return
            
            # 在主线程中发射完成信号
            self.signals.finished.emit(result)
            self.signals.status_changed.emit(self.task_id, TaskStatus.COMPLETED)
            logger.debug(f"[AsyncTask] 完成: {self.task_id} (耗时: {timer.elapsed()/1000:.2f}秒)")
            
        except Exception as e:
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            logger.error(f"[AsyncTask] 错误: {self.task_id} - {e}")
            self.signals.error.emit(error_msg)
            self.signals.status_changed.emit(self.task_id, TaskStatus.FAILED)
    
    def start(self):
        """启动任务（提交到全局线程池）"""
        QThreadPool.globalInstance().start(self)
    
    def cancel(self):
        """取消任务"""
        self._is_cancelled = True
        logger.debug(f"[AsyncTask] 取消任务: {self.task_id}")


class WorkerThread(QThread):
    """
    工作线程 - 基于 QThread
    适用于长任务、需要状态管理的任务（如 OCR 识别、引擎初始化等）
    
    使用示例:
        class OcrWorker(WorkerThread):
            progress = Signal(int, int, str)
            finished = Signal(dict)
            error = Signal(str)
            
            def run(self):
                try:
                    result = self.ocr_engine.recognize(self.image_path)
                    self.finished.emit(result)
                except Exception as e:
                    self.error.emit(str(e))
        
        worker = OcrWorker(ocr_engine, image_path)
        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        worker.start()
    """
    
    # 通用信号
    progress = Signal(object)  # 进度数据
    finished = Signal(object)  # 结果
    error = Signal(str)  # 错误信息
    started_signal = Signal()  # 开始
    status_changed = Signal(str, str)  # task_id, status
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_running = False
        self._task_name = "worker"
        self._start_time = 0
    
    @property
    def task_name(self) -> str:
        return self._task_name
    
    @task_name.setter
    def task_name(self, name: str):
        self._task_name = name
    
    def run(self):
        """子类应重写此方法实现具体工作"""
        self._start_time = time.time()
        try:
            self._is_running = True
            self.started_signal.emit()
            self.status_changed.emit(self._task_name, TaskStatus.RUNNING)
            logger.debug(f"[WorkerThread] 开始: {self._task_name}")
            
            # 子类应在此执行实际工作
            self.do_work()
            
            elapsed = time.time() - self._start_time
            logger.debug(f"[WorkerThread] 完成: {self._task_name} (耗时: {elapsed:.2f}秒)")
            self.status_changed.emit(self._task_name, TaskStatus.COMPLETED)
        except Exception as e:
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            logger.error(f"[WorkerThread] 错误: {self._task_name} - {e}")
            self.error.emit(error_msg)
            self.status_changed.emit(self._task_name, TaskStatus.FAILED)
        finally:
            self._is_running = False
    
    def do_work(self):
        """子类应重写此方法"""
        pass
    
    def stop(self):
        """安全停止线程"""
        if self.isRunning():
            logger.debug(f"[WorkerThread] 停止: {self._task_name}")
            self.requestInterruption()
            self.quit()
            self.wait(5000)  # 等待最多 5 秒
            if self.isRunning():
                logger.warning(f"[WorkerThread] 强制停止: {self._task_name}")
            else:
                self.status_changed.emit(self._task_name, TaskStatus.CANCELLED)
    
    @property
    def is_running(self) -> bool:
        return self._is_running
    
    def is_interrupted(self) -> bool:
        """检查是否被中断"""
        return self.isInterruptionRequested()
    
    def report_progress(self, data):
        """报告进度"""
        if self.isInterruptionRequested():
            raise Exception("任务已被中断")
        self.progress.emit(data)


class OcrInitWorker(WorkerThread):
    """
    OCR 引擎初始化工作线程
    用于异步初始化 OCR 引擎，避免阻塞 UI
    """
    
    def __init__(self, ocr_engine, exe_path: str, models_path: str, language: str = "简体中文", parent=None):
        super().__init__(parent)
        self.ocr_engine = ocr_engine
        self.exe_path = exe_path
        self.models_path = models_path
        self.language = language
        self.task_name = "ocr_init"
    
    def do_work(self):
        """执行 OCR 引擎初始化"""
        try:
            # 设置引擎路径
            self.ocr_engine.exe_path = self.exe_path
            self.ocr_engine.models_path = self.models_path
            self.ocr_engine.language = self.language
            
            # 初始化引擎
            success = self.ocr_engine.initialize()
            
            if success:
                logger.info("[OcrInitWorker] OCR 引擎初始化成功")
                self.finished.emit({"success": True, "message": "OCR 引擎初始化成功"})
            else:
                logger.error("[OcrInitWorker] OCR 引擎初始化失败")
                self.finished.emit({"success": False, "message": "OCR 引擎初始化失败"})
                
        except Exception as e:
            error_msg = f"OCR 引擎初始化异常: {str(e)}"
            logger.error(f"[OcrInitWorker] {error_msg}", exc_info=True)
            self.error.emit(error_msg)


class OcrRecognizeWorker(WorkerThread):
    """
    OCR 单图识别工作线程
    用于异步执行单图 OCR 识别
    """
    
    def __init__(self, ocr_engine, image_path: str, config=None, parent=None):
        super().__init__(parent)
        self.ocr_engine = ocr_engine
        self.image_path = image_path
        self.config = config
        self.task_name = f"ocr_recognize_{os.path.basename(image_path)}"
    
    def do_work(self):
        """执行单图 OCR 识别（支持超长图自动切片）"""
        try:
            # 进度回调函数
            def progress_callback(current, total):
                if self.is_interrupted():
                    raise Exception("任务已被中断")
                self.report_progress({
                    "current": current,
                    "total": total,
                    "file_path": self.image_path,
                    "filename": os.path.basename(self.image_path)
                })
            
            # 传入配置对象和进度回调，实现实时读取切片参数和进度反馈
            result = self.ocr_engine.recognize_auto(
                self.image_path, 
                config=self.config,
                progress_callback=progress_callback
            )
            self.finished.emit(result)
        except Exception as e:
            error_msg = f"OCR 识别异常: {str(e)}"
            logger.error(f"[OcrRecognizeWorker] {error_msg}", exc_info=True)
            self.error.emit(error_msg)


class BatchOcrWorker(WorkerThread):
    """
    批量 OCR 识别工作线程
    用于异步执行批量图片 OCR 识别
    """
    
    def __init__(self, ocr_engine, file_paths: list, config=None, parent=None):
        super().__init__(parent)
        self.ocr_engine = ocr_engine
        self.file_paths = file_paths
        self.config = config
        self.task_name = "batch_ocr"
    
    def do_work(self):
        """执行批量 OCR 识别（支持超长图自动切片）"""
        results = []
        total = len(self.file_paths)
        
        for i, file_path in enumerate(self.file_paths):
            # 检查是否被中断
            if self.isInterruptionRequested():
                logger.info("[BatchOcrWorker] 任务被中断")
                break
            
            try:
                # 发送进度更新
                self.progress.emit({
                    "current": i + 1,
                    "total": total,
                    "filename": os.path.basename(file_path),
                    "file_path": file_path
                })
                
                # 执行识别（传入配置对象，实现实时读取切片参数）
                result = self.ocr_engine.recognize_auto(file_path, config=self.config)
                
                # 添加文件信息
                result["file_path"] = file_path
                result["file_name"] = os.path.basename(file_path)
                
                results.append(result)
                
                # 发送单个完成信号
                self.finished.emit({
                    "index": i,
                    "file_path": file_path,
                    "result": result
                })
                
            except Exception as e:
                error_msg = f"文件 {os.path.basename(file_path)} 识别异常: {str(e)}"
                logger.error(f"[BatchOcrWorker] {error_msg}", exc_info=True)
                self.error.emit(error_msg)
        
        # 发送全部完成信号
        self.finished.emit({
            "all_finished": True,
            "results": results,
            "total": total
        })


class FolderScanWorker(WorkerThread):
    """
    文件夹扫描工作线程
    用于异步扫描文件夹中的图片文件
    """
    
    def __init__(self, folder_path: str, recursive: bool = True, parent=None):
        super().__init__(parent)
        self.folder_path = folder_path
        self.recursive = recursive
        self.task_name = "folder_scan"
        
        # 支持的图片扩展名
        self.IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp', '.tiff', '.tif'}
    
    def _is_image_file(self, file_path: str) -> bool:
        """检查文件是否是图片"""
        ext = os.path.splitext(file_path)[1].lower()
        return ext in self.IMAGE_EXTENSIONS
    
    def do_work(self):
        """执行文件夹扫描"""
        try:
            image_files = []
            
            if self.recursive:
                # 递归扫描子目录
                for root, dirs, files in os.walk(self.folder_path):
                    if self.isInterruptionRequested():
                        break
                    for file in files:
                        file_path = os.path.join(root, file)
                        if self._is_image_file(file_path):
                            image_files.append(file_path)
            else:
                # 仅扫描当前目录
                for file in os.listdir(self.folder_path):
                    if self.isInterruptionRequested():
                        break
                    file_path = os.path.join(self.folder_path, file)
                    if os.path.isfile(file_path) and self._is_image_file(file_path):
                        image_files.append(file_path)
            
            # 排序并返回
            image_files = sorted(set(image_files))
            
            self.progress.emit({
                "scanning": False,
                "count": len(image_files)
            })
            
            self.finished.emit({
                "folder_path": self.folder_path,
                "image_files": image_files,
                "count": len(image_files)
            })
            
        except Exception as e:
            error_msg = f"文件夹扫描异常: {str(e)}"
            logger.error(f"[FolderScanWorker] {error_msg}", exc_info=True)
            self.error.emit(error_msg)


class ThumbnailLoadWorker(WorkerThread):
    """
    缩略图加载工作线程
    用于异步加载图片缩略图
    """
    
    def __init__(self, file_path: str, size: int = 60, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.size = size
        self.task_name = "thumbnail_load"
    
    def do_work(self):
        """加载缩略图"""
        try:
            from PySide6.QtGui import QPixmap
            from PySide6.QtCore import Qt
            
            pixmap = QPixmap(self.file_path)
            if pixmap.isNull():
                # 返回占位图
                placeholder = QPixmap(self.size, self.size)
                placeholder.fill(Qt.GlobalColor.lightGray)
                self.finished.emit({
                    "file_path": self.file_path,
                    "pixmap": placeholder,
                    "success": False
                })
            else:
                scaled_pixmap = pixmap.scaled(
                    self.size, self.size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.finished.emit({
                    "file_path": self.file_path,
                    "pixmap": scaled_pixmap,
                    "success": True
                })
        except Exception as e:
            error_msg = f"缩略图加载异常: {str(e)}"
            logger.error(f"[ThumbnailLoadWorker] {error_msg}", exc_info=True)
            self.error.emit(error_msg)


class ExportWorker(WorkerThread):
    """
    导出工作线程
    用于异步导出识别结果
    """
    
    def __init__(self, exporter, results, format_type: str, output_path: str, parent=None):
        super().__init__(parent)
        self.exporter = exporter
        self.results = results
        self.format_type = format_type
        self.output_path = output_path
        self.task_name = "export"
    
    def do_work(self):
        """执行导出"""
        try:
            # 从完整路径中提取文件名和目录
            output_dir = os.path.dirname(self.output_path)
            filename_with_ext = os.path.basename(self.output_path)
            filename_without_ext = os.path.splitext(filename_with_ext)[0]
            
            # 调用导出方法
            result_path = self.exporter.export(
                self.results,
                self.format_type,
                filename=filename_without_ext,
                output_dir=output_dir if output_dir else None
            )
            
            self.finished.emit({
                "success": result_path is not None,
                "format_type": self.format_type,
                "output_path": result_path if result_path else self.output_path
            })
        except Exception as e:
            error_msg = f"导出异常: {str(e)}"
            logger.error(f"[ExportWorker] {error_msg}", exc_info=True)
            self.error.emit(error_msg)


class BatchExportWorker(WorkerThread):
    """
    批量导出工作线程
    用于异步导出批量识别结果
    """
    
    def __init__(self, exporter, format_type: str, output_path: str, parent=None):
        super().__init__(parent)
        self.exporter = exporter
        self.format_type = format_type
        self.output_path = output_path
        self.task_name = "batch_export"
    
    def do_work(self):
        """执行批量导出"""
        try:
            # 根据格式类型调用不同的导出方法
            result_path = None
            if self.format_type.upper() == "TXT":
                result_path = self.exporter.export_txt(self.output_path)
            elif self.format_type.upper() == "JSON":
                result_path = self.exporter.export_json(self.output_path)
            elif self.format_type.upper() == "EXCEL":
                result_path = self.exporter.export_excel(self.output_path)
            
            self.finished.emit({
                "success": result_path is not None,
                "format_type": self.format_type,
                "output_path": result_path if result_path else self.output_path
            })
        except Exception as e:
            error_msg = f"批量导出异常: {str(e)}"
            logger.error(f"[BatchExportWorker] {error_msg}", exc_info=True)
            self.error.emit(error_msg)


class AsyncTaskManager(QObject):
    """
    异步任务管理器 - 管理所有后台任务
    提供任务生命周期管理、取消、状态查询等功能
    """
    
    # 全局信号
    task_started = Signal(str)  # task_id
    task_finished = Signal(str)  # task_id
    task_error = Signal(str, str)  # task_id, error_message
    task_status_changed = Signal(str, str)  # task_id, status
    all_tasks_finished = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 跟踪所有运行中的线程
        self._workers: Dict[str, WorkerThread] = {}
        self._lock = None  # 延迟初始化
        
        # 配置线程池
        self._configure_thread_pool()
        
        logger.info("[AsyncTaskManager] 初始化完成")
    
    def _configure_thread_pool(self):
        """配置线程池"""
        thread_pool = QThreadPool.globalInstance()
        thread_pool.setMaxThreadCount(DEFAULT_THREAD_POOL_MAX_THREADS)
        logger.info(f"[AsyncTaskManager] 线程池配置完成，最大线程数: {DEFAULT_THREAD_POOL_MAX_THREADS}")
    
    def _get_lock(self):
        """获取线程锁"""
        if self._lock is None:
            import threading
            self._lock = threading.Lock()
        return self._lock
    
    def start_worker(self, task_id: str, worker: WorkerThread):
        """
        启动工作线程
        
        Args:
            task_id: 任务唯一标识
            worker: 工作线程实例
        """
        worker.task_name = task_id
        
        # 连接信号
        worker.finished.connect(lambda r: self._on_worker_finished(task_id, r))
        worker.error.connect(lambda e: self._on_worker_error(task_id, e))
        worker.status_changed.connect(self._on_worker_status_changed)
        
        with self._get_lock():
            # 如果已有同名任务在运行，先停止它
            if task_id in self._workers:
                old_worker = self._workers[task_id]
                if old_worker.isRunning():
                    old_worker.stop()
                del self._workers[task_id]
            
            self._workers[task_id] = worker
        
        self.task_started.emit(task_id)
        worker.start()
        logger.debug(f"[AsyncTaskManager] 启动任务: {task_id}")
    
    def start_async_task(self, task: AsyncTask):
        """
        启动异步任务（基于 QRunnable）
        
        Args:
            task: AsyncTask 实例
        """
        # 连接信号
        task.signals.status_changed.connect(self._on_worker_status_changed)
        task.signals.finished.connect(lambda r: self._on_async_task_finished(task.task_id, r))
        task.signals.error.connect(lambda e: self._on_async_task_error(task.task_id, e))
        
        self.task_started.emit(task.task_id)
        task.start()
        logger.debug(f"[AsyncTaskManager] 启动异步任务: {task.task_id}")
    
    def stop_worker(self, task_id: str):
        """停止指定任务"""
        with self._get_lock():
            if task_id in self._workers:
                worker = self._workers[task_id]
                worker.stop()
                del self._workers[task_id]
                logger.debug(f"[AsyncTaskManager] 停止任务: {task_id}")
    
    def stop_all(self):
        """停止所有任务"""
        with self._get_lock():
            workers = list(self._workers.values())
            self._workers.clear()
        
        for worker in workers:
            worker.stop()
        
        logger.info("[AsyncTaskManager] 已停止所有任务")
    
    def is_running(self, task_id: str) -> bool:
        """检查任务是否正在运行"""
        with self._get_lock():
            if task_id in self._workers:
                return self._workers[task_id].isRunning()
            return False
    
    def get_running_tasks(self) -> list:
        """获取所有运行中的任务 ID"""
        with self._get_lock():
            return [tid for tid, w in self._workers.items() if w.isRunning()]
    
    def get_task_count(self) -> int:
        """获取当前任务数量"""
        with self._get_lock():
            return len(self._workers)
    
    def _on_worker_finished(self, task_id: str, result):
        """工作线程完成回调"""
        with self._get_lock():
            if task_id in self._workers:
                del self._workers[task_id]
        
        self.task_finished.emit(task_id)
        logger.debug(f"[AsyncTaskManager] 任务完成: {task_id}")
        self._check_all_tasks_finished()
    
    def _on_worker_error(self, task_id: str, error_msg: str):
        """工作线程错误回调"""
        with self._get_lock():
            if task_id in self._workers:
                del self._workers[task_id]
        
        self.task_error.emit(task_id, error_msg)
        logger.error(f"[AsyncTaskManager] 任务错误: {task_id} - {error_msg[:100]}")
        self._check_all_tasks_finished()
    
    def _on_async_task_finished(self, task_id: str, result):
        """异步任务完成回调"""
        self.task_finished.emit(task_id)
        logger.debug(f"[AsyncTaskManager] 异步任务完成: {task_id}")
        self._check_all_tasks_finished()
    
    def _on_async_task_error(self, task_id: str, error_msg: str):
        """异步任务错误回调"""
        self.task_error.emit(task_id, error_msg)
        logger.error(f"[AsyncTaskManager] 异步任务错误: {task_id} - {error_msg[:100]}")
        self._check_all_tasks_finished()
    
    def _on_worker_status_changed(self, task_id: str, status: str):
        """任务状态变更回调"""
        self.task_status_changed.emit(task_id, status)
        logger.debug(f"[AsyncTaskManager] 任务状态变更: {task_id} -> {status}")
    
    def _check_all_tasks_finished(self):
        """检查是否所有任务都已完成"""
        with self._get_lock():
            if len(self._workers) == 0:
                self.all_tasks_finished.emit()
                logger.debug("[AsyncTaskManager] 所有任务已完成")
    
    def cleanup(self):
        """清理资源"""
        self.stop_all()
        # 清理线程池
        thread_pool = QThreadPool.globalInstance()
        thread_pool.clear()
        logger.info("[AsyncTaskManager] 清理完成")


# 全局任务管理器实例
_async_task_manager: Optional[AsyncTaskManager] = None


def get_task_manager() -> AsyncTaskManager:
    """获取全局任务管理器"""
    global _async_task_manager
    if _async_task_manager is None:
        _async_task_manager = AsyncTaskManager()
    return _async_task_manager


def reset_task_manager() -> AsyncTaskManager:
    """重置任务管理器"""
    global _async_task_manager
    if _async_task_manager:
        _async_task_manager.cleanup()
    _async_task_manager = AsyncTaskManager()
    return _async_task_manager