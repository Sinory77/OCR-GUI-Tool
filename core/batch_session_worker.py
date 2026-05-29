# -*- coding: utf-8 -*-
"""
批量识别会话工作线程 - BatchSession 的异步版本

用于在后台线程中运行 BatchSession，通过信号推送事件
"""

import logging
import threading
import time
from PySide6.QtCore import QThread, Signal, QObject

from core.batch_session import BatchSession

logger = logging.getLogger(__name__)


class BatchSessionWorker(QThread):
    """
    批量识别会话工作线程

    使用信号推送事件，界面层只连接信号即可
    """

    # 信号定义
    # 扫描结果: (folder_path, files_list)
    scan_result = Signal(str, list)

    # 排重结果: (original_count, final_count, duplicates_list)
    dedup_result = Signal(int, int, list)

    # 开始识别: (total_count,)
    recognize_start = Signal(int)

    # 识别进度: (current, total, filename, file_path, is_duplicate, completed, result_dict)
    recognize_progress = Signal(int, int, str, str, bool, bool, object)

    # 识别完成: (success_count, fail_count, skip_count, results_list)
    recognize_complete = Signal(int, int, int, list)

    # 识别错误: (message,)
    recognize_error = Signal(str)

    # 取消: ()
    cancelled = Signal()

    def __init__(self, ocr_engine, config=None, parent=None):
        super().__init__(parent)
        self.ocr_engine = ocr_engine
        self.config = config or {}

        # 内部会话
        self._session: BatchSession = None

        # 取消标志
        self._cancel_requested = False

    def _on_event(self, event):
        """事件回调 - 将事件转换为信号"""
        from core.batch_events import EventType
        
        try:
            etype = event.type
            
            if etype == EventType.SCAN_RESULT:
                self.scan_result.emit(
                    event.data.get('folder_path', ''),
                    event.files
                )

            elif etype == EventType.DEDUP_RESULT:
                # 转换重复文件列表
                duplicates = []
                for d in event.duplicates:
                    duplicates.append({
                        'file_path': d.file_path,
                        'file_name': d.file_name,
                        'reason': d.reason
                    })
                self.dedup_result.emit(
                    event.data.get('original_count', 0),
                    event.data.get('final_count', 0),
                    duplicates
                )

            elif etype == EventType.RECOGNIZE_START:
                self.recognize_start.emit(event.total)

            elif etype == EventType.RECOGNIZE_PROGRESS:
                self.recognize_progress.emit(
                    event.current,
                    event.total,
                    event.filename,
                    event.file_path,
                    event.is_duplicate,
                    event.completed,
                    event.result
                )

            elif etype == EventType.RECOGNIZE_COMPLETE:
                logger.debug(f"[BatchSessionWorker] 收到 RECOGNIZE_COMPLETE，准备 emit recognize_complete: success={event.data.get('success_count',0)}, fail={event.data.get('fail_count',0)}")
                self.recognize_complete.emit(
                    event.data.get('success_count', 0),
                    event.data.get('fail_count', 0),
                    event.data.get('skip_count', 0),
                    event.data.get('results', [])
                )
                logger.debug("[BatchSessionWorker] recognize_complete signal 已 emit")

            elif etype == EventType.RECOGNIZE_ERROR:
                self.recognize_error.emit(event.data.get('message', '未知错误'))

            elif etype == EventType.CANCELLED:
                self.cancelled.emit()
        except Exception as e:
            logger.error(f"[BatchSessionWorker] _on_event 异常: {e}")

    def run(self):
        """在后台线程中运行"""
        if not self._session:
            return

        # 运行会话（在后台线程）
        self._session.start_files(self._file_paths)
        
        # 给 Qt 事件队列一点时间，确保跨线程信号有机会分发到主线程
        time.sleep(0.5)
        logger.info("[BatchSessionWorker] run() 结束，线程即将退出")

    def start_with_files(self, file_paths: list):
        """从文件列表开始"""
        self._file_paths = file_paths

        # 创建会话
        self._session = BatchSession(self.ocr_engine, self.config)
        self._session.set_event_callback(self._on_event)

        # 启动线程
        self.start()

    def start_with_folder(self, folder_path: str, recursive: bool = True):
        """从文件夹开始"""
        # 创建会话
        self._session = BatchSession(self.ocr_engine, self.config)
        self._session.set_event_callback(self._on_event)

        # 在后台线程运行
        def run_in_thread():
            self._session.start(folder_path, recursive)

        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()

    def cancel(self):
        """请求取消"""
        self._cancel_requested = True
        if self._session:
            self._session.cancel()
