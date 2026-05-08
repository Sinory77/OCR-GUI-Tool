"""
异步工作线程模块 - 提供通用的异步任务执行能力
所有耗时操作都应通过 Worker 在后台线程执行
"""
import os
import time
import threading
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


class AsyncTask(QRunnable):
    """
    通用异步任务 - 基于 QRunnable + QThreadPool
    适用于短任务、可并发任务（如缩略图加载、文件扫描等）
    
    使用示例:
        def on_result(result):
            print(f"任务完成: {result}")
        
        def on_progress(progress_data):
            print(f"进度: {progress_data}")
        
        task = AsyncTask(
            work_func=lambda: time.sleep(1) or "完成",
            on_finished=on_result,
            on_error=lambda e: print(f"错误: {e}"),
            on_progress=on_progress
        )
        thread_pool.start(task)
    """
    
    def __init__(self, work_func: Callable, on_finished: Optional[Callable] = None, 
                 on_error: Optional[Callable] = None, on_progress: Optional[Callable] = None):
        super().__init__()
        self.work_func = work_func
        self.on_finished = on_finished
        self.on_error = on_error
        self.on_progress = on_progress
    
    def run(self):
        """执行任务"""
        try:
            result = self.work_func()
            if self.on_finished:
                self.on_finished(result)
        except Exception as e:
            if self.on_error:
                self.on_error(str(e))


class WorkerThread(QThread):
    """
    工作线程基类 - 基于 QThread
    适用于长任务、不可并发任务（如 OCR 识别、文件处理等）
    
    信号:
        started_signal: 线程启动
        finished: 任务完成
        error: 任务出错
        progress: 进度更新
        status_changed: 状态变化
    """
    
    started_signal = Signal()
    finished = Signal(object)  # result
    error = Signal(str)  # error_message
    progress = Signal(object)  # progress_data
    status_changed = Signal(str, str)  # task_name, status
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_running = False
        self._task_name = "unnamed_task"
        self._start_time = 0
    
    @property
    def task_name(self):
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
            elapsed = time.time() - self._start_time
            logger.error(f"[WorkerThread] 错误: {self._task_name} (耗时: {elapsed:.2f}秒)", exc_info=True)
            self.status_changed.emit(self._task_name, TaskStatus.FAILED)
            self.error.emit(str(e))
        finally:
            self._is_running = False
    
    def do_work(self):
        """子类应重写此方法"""
        pass
    
    def stop(self, wait_ms: int = 1000):
        """安全停止线程
        
        Args:
            wait_ms: 等待线程退出的最长毫秒数（0 = 仅发请求，不等待）
                     建议传入正值让调用方确认线程已退出，避免僵尸线程。
        """
        if self.isRunning():
            logger.debug(f"[WorkerThread] 停止: {self._task_name}")
            self.requestInterruption()
            if wait_ms > 0:
                # 等待线程结束，但不阻塞太久
                self.wait(wait_ms)
        else:
            logger.debug(f"[WorkerThread] 未运行，跳过停止: {self._task_name}")
    
    @property
    def is_running(self) -> bool:
        return self._is_running
    
    def is_interrupted(self) -> bool:
        """检查是否被中断"""
        return self.isInterruptionRequested()
    
    def report_progress(self, data):
        """报告进度"""
        self.progress.emit(data)


class OcrRecognizeWorker(WorkerThread):
    """
    OCR 单图识别工作线程
    用于异步执行单图 OCR 识别
    """
    
    # 取消信号（与 BatchOcrWorker 保持一致）
    cancelled = Signal()
    
    def __init__(self, ocr_engine, image_path: str, config=None, parent=None):
        super().__init__(parent)
        self.ocr_engine = ocr_engine
        self.image_path = image_path
        self.config = config
        self.task_name = f"ocr_recognize_{os.path.basename(image_path)}"
    
    def do_work(self):
        """执行单图 OCR 识别（支持超长图自动切片）"""
        # 标记任务是否被中断
        is_cancelled = False
        
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
            
            # 中断检查函数
            def is_interrupted():
                return self.isInterruptionRequested()
            
            # 检查中断状态，确保在执行识别之前能够响应中断请求
            if self.isInterruptionRequested():
                logger.info("[OcrRecognizeWorker] 任务被中断")
                is_cancelled = True
                return
            
            # 传入配置对象、进度回调和中断检查函数
            result = self.ocr_engine.recognize_auto(
                self.image_path, 
                config=self.config,
                progress_callback=progress_callback,
                is_interrupted=is_interrupted
            )
            
            # 检查中断状态，确保在发送完成信号之前能够响应中断请求
            if self.isInterruptionRequested():
                logger.info("[OcrRecognizeWorker] 任务被中断，发送 cancelled 信号")
                # 直接发送信号，Qt 会自动将信号传递到接收对象的线程
                self.cancelled.emit()
                return
            
            self.finished.emit(result)
        except Exception as e:
            error_msg = f"OCR 识别异常: {str(e)}"
            # 检查是否是中断异常
            if "中断" in str(e) or self.isInterruptionRequested():
                logger.info(f"[OcrRecognizeWorker] 任务被中断: {error_msg}")
                # 直接发送信号，Qt 会自动将信号传递到接收对象的线程
                self.cancelled.emit()
            else:
                # 只有在线程未被中断时才发送错误信号
                if not self.isInterruptionRequested():
                    logger.error(f"[OcrRecognizeWorker] {error_msg}", exc_info=True)
                    self.error.emit(error_msg)


class APIBasedOcrRecognizeWorker(WorkerThread):
    """
    基于 CoreAPI 的 OCR 单图识别工作线程
    用于异步执行单图 OCR 识别，使用 CoreAPI 进行错误处理
    """
    
    # 取消信号（与 BatchOcrWorker 保持一致）
    cancelled = Signal()
    
    def __init__(self, core_api, image_path: str, config=None, parent=None):
        super().__init__(parent)
        self.core_api = core_api
        self.image_path = image_path
        self.config = config
        self.task_name = f"api_ocr_recognize_{os.path.basename(image_path)}"
    
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
            
            # 中断检查函数
            def is_interrupted():
                return self.isInterruptionRequested()
            
            # 检查中断状态，确保在执行识别之前能够响应中断请求
            if self.isInterruptionRequested():
                logger.info("[APIBasedOcrRecognizeWorker] 任务被中断")
                self.cancelled.emit()
                return
            
            # 使用 CoreAPI 进行识别
            result = self.core_api.recognize_single_image_async(
                self.image_path,
                progress_callback=progress_callback,
                is_interrupted=is_interrupted
            )
            
            # 检查中断状态，确保在发送完成信号之前能够响应中断请求
            if self.isInterruptionRequested():
                logger.info("[APIBasedOcrRecognizeWorker] 任务被中断，发送 cancelled 信号")
                self.cancelled.emit()
                return
            
            # 如果 CoreAPI 返回 ErrorResult，我们需要从中提取实际结果
            if hasattr(result, 'success') and hasattr(result, 'data'):
                if result.success:
                    self.finished.emit(result.data)  # 发送实际数据
                else:
                    # 如果有错误，发送错误信号
                    error_msg = result.error.message if result.error else "识别失败"
                    self.error.emit(error_msg)
            else:
                # 兼容旧格式
                self.finished.emit(result)
                
        except Exception as e:
            error_msg = f"OCR 识别异常: {str(e)}"
            # 检查是否是中断异常
            if "中断" in str(e) or self.isInterruptionRequested():
                logger.info(f"[APIBasedOcrRecognizeWorker] 任务被中断: {error_msg}")
                self.cancelled.emit()
            else:
                # 只有在线程未被中断时才发送错误信号
                if not self.isInterruptionRequested():
                    logger.error(f"[APIBasedOcrRecognizeWorker] {error_msg}", exc_info=True)
                    self.error.emit(error_msg)


class BatchOcrWorker(WorkerThread):
    """
    批量 OCR 识别工作线程
    用于异步执行批量图片 OCR 识别
    """
    # 额外信号：通知 UI 任务被用户取消（区别于 error）
    cancelled = Signal()
    
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
        
        # 检查初始中断状态
        if self.isInterruptionRequested():
            logger.info("[BatchOcrWorker] 启动前已被中断，发送取消信号")
            self.cancelled.emit()
            return
        
        try:
            for i, file_path in enumerate(self.file_paths):
                # ── Umi-OCR风格的中断检查点 ──────────────────────────
                # ① 中断检查：如果标记为停止，直接退出循环
                if self.isInterruptionRequested():
                    logger.info("[BatchOcrWorker] 任务被中断，退出循环并清理")
                    self.cancelled.emit()
                    return
                
                # 发送进度更新
                self.progress.emit({
                    "current": i + 1,
                    "total": total,
                    "filename": os.path.basename(file_path),
                    "file_path": file_path
                })
                
                # ── 为当前文件建立闭包（避免 Python 循环变量捕获 Bug）──
                def make_progress_callback(fp, idx):
                    def progress_callback(current, total_slices):
                        # 在进度回调中也检查中断状态
                        if self.isInterruptionRequested():
                            raise Exception("任务已被中断")
                        self.report_progress({
                            "current": current,
                            "total": total_slices,
                            "batch_current": idx + 1,
                            "batch_total": total,
                            "filename": os.path.basename(fp),
                            "file_path": fp
                        })
                    return progress_callback
                
                def make_is_interrupted():
                    def is_interrupted():
                        # 提供一个可调用的中断检查函数
                        return self.isInterruptionRequested()
                    return is_interrupted
                
                progress_cb = make_progress_callback(file_path, i)
                is_interrupted_fn = make_is_interrupted()
                
                try:
                    # 执行单个文件的 OCR 识别
                    result = self.ocr_engine.recognize_auto(
                        file_path,
                        config=self.config,
                        progress_callback=progress_cb,
                        is_interrupted=is_interrupted_fn
                    )

                    # ★★★ 关键：在任务完成后才检查中断状态 ★★★
                    # PaddleOCR-json 管道模式不支持真正的优雅中断
                    # 必须等待当前任务完成后才能处理中断
                    if self.isInterruptionRequested():
                        logger.info("[BatchOcrWorker] 当前任务完成后检测到中断，停止后续任务")
                        # 不记录这个被取消的任务结果
                        self.cancelled.emit()
                        return

                    # 任务正常完成，记录结果
                    results.append({
                        "file_path": file_path,
                        "file_name": os.path.basename(file_path),
                        "result": result
                    })

                    # 发送单个文件完成的进度更新
                    self.progress.emit({
                        "current": i + 1,
                        "total": total,
                        "filename": os.path.basename(file_path),
                        "file_path": file_path,
                        "completed": True,
                        "result": result
                    })
                    
                except Exception as e:
                    error_msg = f"文件 {file_path} 识别失败: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    
                    # 记录错误结果
                    results.append({
                        "file_path": file_path,
                        "file_name": os.path.basename(file_path),
                        "result": {
                            "code": 999,
                            "data": str(e),
                            "texts": [],
                            "boxes": []
                        }
                    })
                    
                    # 发送错误进度更新
                    self.progress.emit({
                        "current": i + 1,
                        "total": total,
                        "filename": os.path.basename(file_path),
                        "file_path": file_path,
                        "error": str(e)
                    })
                    
                    # 即使单个文件出错，也继续处理下一个文件
                    continue
        
        except Exception as e:
            # 整体错误处理
            error_msg = f"批量 OCR 识别异常: {str(e)}"
            logger.error(error_msg, exc_info=True)
            if not self.isInterruptionRequested():
                self.error.emit(error_msg)
            return
        
        # 所有文件处理完成
        logger.info(f"[BatchOcrWorker] 批量识别完成: {len(results)} 个文件")
        self.finished.emit(results)


class OcrInitWorker(WorkerThread):
    """
    OCR 引擎初始化工作线程
    用于异步初始化 OCR 引擎
    """
    
    def __init__(self, ocr_engine, exe_path: str, models_path: str, language: str, parent=None):
        super().__init__(parent)
        self.ocr_engine = ocr_engine
        self.exe_path = exe_path
        self.models_path = models_path
        self.language = language
        self.task_name = "ocr_init"
    
    def do_work(self):
        """执行 OCR 引擎初始化"""
        try:
            # 设置 OCR 引擎参数
            self.ocr_engine.exe_path = self.exe_path
            self.ocr_engine.models_path = self.models_path
            
            # 验证路径
            self.ocr_engine._validate_paths()
            
            # 设置语言
            success = self.ocr_engine.set_language(self.language)
            
            if success:
                # 初始化引擎
                init_success = self.ocr_engine.initialize()
                if init_success:
                    logger.info(f"[OcrInitWorker] OCR 引擎初始化成功")
                    self.finished.emit({"success": True, "message": "OCR 引擎初始化成功"})
                else:
                    error_msg = "OCR 引擎初始化失败"
                    logger.error(f"[OcrInitWorker] {error_msg}")
                    self.finished.emit({"success": False, "message": error_msg})
            else:
                error_msg = f"设置语言失败: {self.language}"
                logger.error(f"[OcrInitWorker] {error_msg}")
                self.finished.emit({"success": False, "message": error_msg})
                
        except Exception as e:
            error_msg = f"OCR 引擎初始化异常: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.finished.emit({"success": False, "message": error_msg})


class FolderScanWorker(WorkerThread):
    """
    文件夹扫描工作线程
    用于异步扫描文件夹中的图片文件
    """
    
    def __init__(self, folder_path: str, recursive: bool = True, parent=None):
        super().__init__(parent)
        self.folder_path = folder_path
        self.recursive = recursive
        self.task_name = f"folder_scan_{os.path.basename(folder_path)}"
    
    def do_work(self):
        """执行文件夹扫描"""
        try:
            image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.gif', '.webp'}
            file_paths = []
            
            if self.recursive:
                # 递归扫描
                for root, dirs, files in os.walk(self.folder_path):
                    for file in files:
                        if os.path.splitext(file.lower())[1] in image_extensions:
                            file_paths.append(os.path.join(root, file))
            else:
                # 只扫描当前目录
                for file in os.listdir(self.folder_path):
                    if os.path.isfile(os.path.join(self.folder_path, file)):
                        if os.path.splitext(file.lower())[1] in image_extensions:
                            file_paths.append(os.path.join(self.folder_path, file))
            
            # 按文件名排序
            file_paths.sort()
            
            logger.info(f"[FolderScanWorker] 扫描完成，找到 {len(file_paths)} 个图片文件")
            
            self.finished.emit({
                "image_files": file_paths,
                "count": len(file_paths)
            })
            
        except Exception as e:
            error_msg = f"文件夹扫描异常: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.error.emit(error_msg)


class APIBasedBatchOcrWorker(WorkerThread):
    """
    基于 CoreAPI 的批量 OCR 识别工作线程
    用于异步执行批量图片 OCR 识别，使用 CoreAPI 进行错误处理
    """
    # 额外信号：通知 UI 任务被用户取消（区别于 error）
    cancelled = Signal()
    
    def __init__(self, core_api, file_paths: list, config=None, parent=None):
        super().__init__(parent)
        self.core_api = core_api
        self.file_paths = file_paths
        self.config = config
        self.task_name = "api_batch_ocr"
    
    def do_work(self):
        """执行批量 OCR 识别（支持超长图自动切片）"""
        results = []
        total = len(self.file_paths)
        
        # 检查初始中断状态
        if self.isInterruptionRequested():
            logger.info("[APIBasedBatchOcrWorker] 启动前已被中断，发送取消信号")
            self.cancelled.emit()
            return
        
        try:
            for i, file_path in enumerate(self.file_paths):
                # ── Umi-OCR风格的中断检查点 ──────────────────────────
                # ① 中断检查：如果标记为停止，直接退出循环
                if self.isInterruptionRequested():
                    logger.info("[APIBasedBatchOcrWorker] 任务被中断，退出循环并清理")
                    self.cancelled.emit()
                    return
                
                # 发送进度更新
                self.progress.emit({
                    "current": i + 1,
                    "total": total,
                    "filename": os.path.basename(file_path),
                    "file_path": file_path
                })
                
                # ── 为当前文件建立闭包（避免 Python 循环变量捕获 Bug）──
                def make_progress_callback(fp, idx):
                    def progress_callback(current, total_slices):
                        # 在进度回调中也检查中断状态
                        if self.isInterruptionRequested():
                            raise Exception("任务已被中断")
                        self.report_progress({
                            "current": current,
                            "total": total_slices,
                            "batch_current": idx + 1,
                            "batch_total": total,
                            "filename": os.path.basename(fp),
                            "file_path": fp
                        })
                    return progress_callback
                
                def make_is_interrupted():
                    def is_interrupted():
                        # 提供一个可调用的中断检查函数
                        return self.isInterruptionRequested()
                    return is_interrupted
                
                progress_cb = make_progress_callback(file_path, i)
                is_interrupted_fn = make_is_interrupted()
                
                try:
                    # 使用 CoreAPI 进行单个文件识别
                    result = self.core_api.recognize_single_image_async(
                        file_path,
                        progress_callback=progress_cb,
                        is_interrupted=is_interrupted_fn
                    )
                    
                    # 检查中断状态
                    if self.isInterruptionRequested():
                        logger.info("[APIBasedBatchOcrWorker] 任务被中断，退出循环并清理")
                        self.cancelled.emit()
                        return
                    
                    # 处理 CoreAPI 返回的结果
                    if hasattr(result, 'success') and hasattr(result, 'data'):
                        if result.success:
                            final_result = result.data
                        else:
                            # 如果有错误，创建错误结果
                            final_result = {
                                "code": 999,
                                "data": result.error.message if result.error else "识别失败",
                                "texts": [],
                                "boxes": []
                            }
                    else:
                        # 兼容旧格式
                        final_result = result
                    
                    # 记录单个结果
                    results.append({
                        "file_path": file_path,
                        "file_name": os.path.basename(file_path),
                        "result": final_result
                    })
                    
                    # 发送单个文件完成的进度更新
                    self.progress.emit({
                        "current": i + 1,
                        "total": total,
                        "filename": os.path.basename(file_path),
                        "file_path": file_path,
                        "completed": True,
                        "result": final_result
                    })
                    
                except Exception as e:
                    error_msg = f"文件 {file_path} 识别失败: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    
                    # 记录错误结果
                    results.append({
                        "file_path": file_path,
                        "file_name": os.path.basename(file_path),
                        "result": {
                            "code": 999,
                            "data": str(e),
                            "texts": [],
                            "boxes": []
                        }
                    })
                    
                    # 发送错误进度更新
                    self.progress.emit({
                        "current": i + 1,
                        "total": total,
                        "filename": os.path.basename(file_path),
                        "file_path": file_path,
                        "error": str(e)
                    })
                    
                    # 即使单个文件出错，也继续处理下一个文件
                    continue
        
        except Exception as e:
            # 整体错误处理
            error_msg = f"批量 OCR 识别异常: {str(e)}"
            logger.error(error_msg, exc_info=True)
            if not self.isInterruptionRequested():
                self.error.emit(error_msg)
            return
        
        # 所有文件处理完成
        logger.info(f"[APIBasedBatchOcrWorker] 批量识别完成: {len(results)} 个文件")
        self.finished.emit(results)


class ThumbnailLoadWorker(WorkerThread):
    """
    缩略图加载工作线程
    用于异步加载图片缩略图
    """
    
    def __init__(self, file_path: str, size: int = 48, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.size = size
        self.task_name = f"thumbnail_load_{os.path.basename(file_path)}"
    
    def do_work(self):
        """执行缩略图加载"""
        try:
            from PIL import Image
            import base64
            import io
            
            # 打开图片
            with Image.open(self.file_path) as img:
                # 计算缩放尺寸，保持宽高比
                width, height = img.size
                if width > height:
                    new_width = self.size
                    new_height = int(height * (self.size / width))
                else:
                    new_height = self.size
                    new_width = int(width * (self.size / height))
                
                # 调整图片大小
                resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # 转换为base64编码
                buffer = io.BytesIO()
                resized_img.save(buffer, format='PNG')
                img_base64 = base64.b64encode(buffer.getvalue()).decode()
                
                result = {
                    "success": True,
                    "file_path": self.file_path,
                    "thumbnail_data": img_base64,
                    "size": (new_width, new_height)
                }
                
                logger.info(f"[ThumbnailLoadWorker] 缩略图加载完成: {self.file_path}")
                self.finished.emit(result)
                
        except Exception as e:
            error_msg = f"缩略图加载异常: {str(e)}"
            logger.error(error_msg, exc_info=True)
            # 发送错误结果而不是错误信号，这样调用方可以统一处理
            result = {
                "success": False,
                "file_path": self.file_path,
                "error": str(e)
            }
            self.finished.emit(result)


class AsyncTaskManager:
    """
    异步任务管理器 - 管理多个 AsyncTask 的生命周期
    适用于需要管理大量短期任务的场景
    """
    
    def __init__(self):
        self._workers = {}  # task_id -> worker
        self._lock = threading.RLock()  # 线程安全锁
        self._task_started_callbacks = []
        self._task_finished_callbacks = []
        self._task_error_callbacks = []
    
    def _get_lock(self):
        return self._lock
    
    def register_callback(self, event_type: str, callback: Callable):
        """注册回调函数
        
        Args:
            event_type: 事件类型，可选值: 'started', 'finished', 'error'
            callback: 回调函数
        """
        if event_type == 'started':
            self._task_started_callbacks.append(callback)
        elif event_type == 'finished':
            self._task_finished_callbacks.append(callback)
        elif event_type == 'error':
            self._task_error_callbacks.append(callback)
    
    def submit_task(self, task: AsyncTask, task_id: Optional[str] = None) -> str:
        """提交任务
        
        Args:
            task: 任务对象
            task_id: 任务ID，如果不提供则自动生成
            
        Returns:
            任务ID
        """
        import threading
        import uuid
        
        if not task_id:
            task_id = str(uuid.uuid4())
        
        with self._get_lock():
            self._workers[task_id] = task
        
        # 调用回调函数
        for callback in self._task_started_callbacks:
            try:
                callback(task_id)
            except Exception as e:
                logger.error(f"任务开始回调执行失败: {e}")
        
        task.start()
        logger.debug(f"[AsyncTaskManager] 启动异步任务: {task_id}")
        
        return task_id
    
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
    
    def cleanup(self):
        """清理所有资源"""
        self.stop_all()


# 全局线程池
_thread_pool = None


def get_thread_pool():
    """获取全局线程池"""
    global _thread_pool
    if _thread_pool is None:
        from PySide6.QtCore import QThreadPool
        _thread_pool = QThreadPool.globalInstance()
        _thread_pool.setMaxThreadCount(DEFAULT_THREAD_POOL_MAX_THREADS)
        logger.info(f"[ThreadPool] 初始化，最大线程数: {_thread_pool.maxThreadCount()}")
    return _thread_pool


# 全局任务管理器实例
_task_manager_instance = None

def get_task_manager():
    """获取任务管理器"""
    global _task_manager_instance
    if _task_manager_instance is None:
        # 直接创建 AsyncTaskManager 实例，不进行线程检查
        # 这样可以确保在 QApplication 尚未创建时也能正常工作
        _task_manager_instance = AsyncTaskManager()
    return _task_manager_instance