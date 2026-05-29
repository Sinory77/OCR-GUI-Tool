# -*- coding: utf-8 -*-
"""
批量识别会话 - 核心层统一管理批量识别流程

设计原则：
- 核心层负责所有逻辑（扫描、排重、识别）
- 界面层只接收事件并显示，不做逻辑判断

事件推送：
- scan_result: 文件夹扫描结果
- dedup_result: 排重结果
- recognize_start: 开始识别
- recognize_progress: 识别进度
- recognize_complete: 识别完成
- recognize_error: 识别错误
- cancelled: 任务取消
"""

import os
import logging
from typing import List, Callable, Optional, Dict, Any
from dataclasses import dataclass

from core.batch_events import BatchOCREvent, EventType, DuplicateFile
from core.deduplication import Deduplicator

logger = logging.getLogger(__name__)


class BatchSession:
    """
    批量识别会话 - 核心层大脑

    使用方式：
        def on_event(event: BatchOCREvent):
            # 界面层：只做显示
            if event.type == EventType.RECOGNIZE_PROGRESS:
                status_label.setText(f"正在识别: {event.filename} ({event.current}/{event.total})")

        session = BatchSession(ocr_engine, config)
        session.set_event_callback(on_event)
        session.start(folder_path="...")  # 或 start_files(file_list)
    """

    def __init__(self, ocr_engine, config: Optional[Dict] = None):
        """
        Args:
            ocr_engine: OCR引擎实例
            config: 配置参数
        """
        self.ocr_engine = ocr_engine
        self.config = config or {}

        # 事件回调
        self._event_callback: Optional[Callable] = None

        # 去重器
        self._deduplicator: Optional[Deduplicator] = None

        # 文件列表
        self._all_files: List[str] = []      # 原始文件列表
        self._files_to_process: List[str] = []  # 处理后文件列表（排重后）
        self._duplicates: List[DuplicateFile] = []  # 重复文件

        # 状态
        self._is_running = False
        self._is_cancelled = False

        # 统计
        self._stats = {
            'success': 0,
            'fail': 0,
            'skip': 0,
        }
        self._results: List[Dict] = []

    def set_event_callback(self, callback: Callable[[BatchOCREvent], None]):
        """设置事件回调"""
        self._event_callback = callback

    def _emit(self, event: BatchOCREvent):
        """发送事件到界面层"""
        if self._event_callback:
            self._event_callback(event)

    def _is_interrupted(self) -> bool:
        """检查是否被中断"""
        return self._is_cancelled

    # ─────────────────────── 公开接口 ───────────────────────

    def start(self, folder_path: str, recursive: bool = True):
        """
        从文件夹开始批量识别

        Args:
            folder_path: 文件夹路径
            recursive: 是否递归扫描子文件夹
        """
        logger.info(f"[BatchSession] 开始批量识别: {folder_path}")
        self._is_running = True
        self._is_cancelled = False
        self._stats = {'success': 0, 'fail': 0, 'skip': 0}
        self._results = []

        try:
            # 1. 扫描文件
            self._scan_folder(folder_path, recursive)

            # 2. 预处理（排重）
            self._preprocess()

            # 3. 开始识别
            self._recognize()
        except Exception as e:
            logger.error(f"[BatchSession] 批量识别异常: {e}")
            self._emit(BatchOCREvent.recognize_error(str(e)))
        finally:
            self._is_running = False

    def start_files(self, file_paths: List[str]):
        """
        直接从文件列表开始批量识别

        Args:
            file_paths: 文件路径列表
        """
        logger.info(f"[BatchSession] 开始批量识别: {len(file_paths)} 个文件")
        self._is_running = True
        self._is_cancelled = False
        self._stats = {'success': 0, 'fail': 0, 'skip': 0}
        self._results = []

        try:
            # 直接使用文件列表
            self._all_files = file_paths
            self._emit(BatchOCREvent.scan_result(
                folder_path=os.path.dirname(file_paths[0]) if file_paths else "",
                files=file_paths
            ))

            # 预处理（排重）
            self._preprocess()

            # 开始识别
            self._recognize()
        except Exception as e:
            logger.error(f"[BatchSession] 批量识别异常: {e}")
            self._emit(BatchOCREvent.recognize_error(str(e)))
        finally:
            self._is_running = False

    def cancel(self):
        """请求取消任务"""
        logger.info("[BatchSession] 收到取消请求")
        self._is_cancelled = True

    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._is_running

    # ─────────────────────── 内部方法 ───────────────────────

    def _scan_folder(self, folder_path: str, recursive: bool):
        """扫描文件夹"""
        logger.info(f"[BatchSession] 扫描文件夹: {folder_path}, recursive={recursive}")

        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.gif', '.webp'}
        files = []

        if recursive:
            for root, dirs, filenames in os.walk(folder_path):
                for filename in filenames:
                    ext = os.path.splitext(filename.lower())[1]
                    if ext in image_extensions:
                        files.append(os.path.join(root, filename))
        else:
            for filename in os.listdir(folder_path):
                file_path = os.path.join(folder_path, filename)
                if os.path.isfile(file_path):
                    ext = os.path.splitext(filename.lower())[1]
                    if ext in image_extensions:
                        files.append(file_path)

        # 按文件名排序
        files.sort()

        self._all_files = files
        logger.info(f"[BatchSession] 扫描完成，找到 {len(files)} 个图片文件")

        # 发送扫描结果事件
        self._emit(BatchOCREvent.scan_result(
            folder_path=folder_path,
            files=files
        ))

    def _preprocess(self):
        """预处理：文件级排重"""
        logger.info("[BatchSession] 开始预处理（文件级排重）")

        # 检查是否启用文件排重
        use_file_dedup = self.config.get('file_dedup_enabled', False)

        self._files_to_process = []
        self._duplicates = []

        if use_file_dedup:
            from core.deduplication import Deduplicator
            dedup = Deduplicator()

            for file_path in self._all_files:
                if self._is_interrupted():
                    return

                file_name = os.path.basename(file_path)

                # 检查文件是否重复（基于MD5）
                if dedup.check_file_duplicate(file_path):
                    self._duplicates.append(DuplicateFile(
                        file_path=file_path,
                        file_name=file_name,
                        reason="文件内容重复（MD5）"
                    ))
                    logger.info(f"[BatchSession] 文件重复: {file_name}")
                else:
                    self._files_to_process.append(file_path)

            dedup.clear()
        else:
            self._files_to_process = self._all_files.copy()

        logger.info(f"[BatchSession] 预处理完成: 原始 {len(self._all_files)}, 排重后 {len(self._files_to_process)}, 排除 {len(self._duplicates)}")

        # 发送排重结果事件
        self._emit(BatchOCREvent.dedup_result(
            original_count=len(self._all_files),
            final_count=len(self._files_to_process),
            duplicates=[
                {
                    'file_path': d.file_path,
                    'file_name': d.file_name,
                    'reason': d.reason
                } for d in self._duplicates
            ]
        ))

    def _recognize(self):
        """执行识别"""
        total = len(self._files_to_process)

        if total == 0:
            logger.info("[BatchSession] 没有需要识别的文件")
            self._emit(BatchOCREvent.recognize_complete(
                success_count=0,
                fail_count=0,
                skip_count=0,
                results=[]
            ))
            return

        # 发送开始识别事件
        self._emit(BatchOCREvent.recognize_start(total=total))

        logger.info(f"[BatchSession] 开始识别: {total} 个文件")

        # 初始化文本去重器
        self._deduplicator = Deduplicator()
        use_text_dedup = self.config.get('text_dedup_enabled', False)

        for i, file_path in enumerate(self._files_to_process):
            if self._is_interrupted():
                logger.info("[BatchSession] 识别被中断")
                self._emit(BatchOCREvent.cancelled())
                return

            file_name = os.path.basename(file_path)
            current = i + 1

            # 发送进度事件（识别中）
            self._emit(BatchOCREvent.recognize_progress(
                current=current,
                total=total,
                filename=file_name,
                file_path=file_path,
                is_duplicate=False,
                completed=False
            ))

            try:
                # ── 为当前文件创建闭包 ──
                def make_progress_callback(fp, idx):
                    def progress_callback(current_s, total_slices):
                        if self._is_interrupted():
                            raise Exception("任务已被中断")
                        self._emit(BatchOCREvent.recognize_progress(
                            current=idx + 1,
                            total=total,
                            filename=os.path.basename(fp),
                            file_path=fp,
                            is_duplicate=False,
                            completed=False
                        ))
                    return progress_callback

                def make_is_interrupted():
                    def check():
                        return self._is_interrupted()
                    return check

                # 执行识别
                result = self.ocr_engine.recognize_auto(
                    file_path,
                    config=self.config.get('ocr_config') if isinstance(self.config, dict) else self.config,
                    progress_callback=make_progress_callback(file_path, i),
                    is_interrupted=make_is_interrupted()
                )

                # 检查中断
                if self._is_interrupted():
                    self._emit(BatchOCREvent.cancelled())
                    return

                # ── 处理识别结果 ──
                is_duplicate = False
                skip_reason = ""

                if use_text_dedup and result.get('code') == 100:
                    texts = result.get('texts', [])
                    if texts:
                        full_text = '\n'.join([
                            t.get('text', '') if isinstance(t, dict) else str(t)
                            for t in texts
                        ])
                        if full_text:
                            if self._deduplicator.check_text_duplicate(full_text):
                                is_duplicate = True
                                skip_reason = "文本内容重复"
                                self._stats['skip'] += 1
                                logger.info(f"[BatchSession] 文本重复: {file_name}")

                if is_duplicate:
                    self._results.append({
                        'file_path': file_path,
                        'file_name': file_name,
                        'result': result,
                        'is_duplicate': True,
                        'skip_reason': skip_reason
                    })
                elif result.get('code') == 100:
                    self._stats['success'] += 1
                    self._results.append({
                        'file_path': file_path,
                        'file_name': file_name,
                        'result': result,
                        'is_duplicate': False
                    })
                else:
                    self._stats['fail'] += 1
                    self._results.append({
                        'file_path': file_path,
                        'file_name': file_name,
                        'result': result,
                        'is_duplicate': False
                    })

                # 发送完成事件
                self._emit(BatchOCREvent.recognize_progress(
                    current=current,
                    total=total,
                    filename=file_name,
                    file_path=file_path,
                    is_duplicate=is_duplicate,
                    completed=True,
                    result=result
                ))

            except Exception as e:
                error_msg = f"文件 {file_name} 识别失败: {str(e)}"
                logger.error(f"[BatchSession] {error_msg}")

                self._stats['fail'] += 1
                self._results.append({
                    'file_path': file_path,
                    'file_name': file_name,
                    'result': {
                        'code': 999,
                        'data': str(e),
                        'texts': [],
                        'boxes': []
                    },
                    'is_duplicate': False
                })

                # 发送错误进度
                self._emit(BatchOCREvent.recognize_progress(
                    current=current,
                    total=total,
                    filename=file_name,
                    file_path=file_path,
                    is_duplicate=False,
                    completed=True,
                    result={'code': 999, 'data': str(e)}
                ))

        # 清理去重器
        if self._deduplicator:
            self._deduplicator.clear()
            self._deduplicator = None

        # 发送完成事件
        logger.info(f"[BatchSession] 识别完成: 成功 {self._stats['success']}, 失败 {self._stats['fail']}, 跳过 {self._stats['skip']}")
        self._emit(BatchOCREvent.recognize_complete(
            success_count=self._stats['success'],
            fail_count=self._stats['fail'],
            skip_count=self._stats['skip'],
            results=self._results
        ))
