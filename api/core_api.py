# -*- coding: utf-8 -*-
"""
统一核心功能API（纯接口版）
提供统一的接口供界面层调用，所有功能通过 TaskManager 任务调度

架构设计：
    界面层 → CoreAPI (纯接口) → TaskManager (统一调度) → 执行器(核心功能) → 结果通过 TaskManager 返回给 CoreAPI → 推送到界面层

CoreAPI 只提供接口，不包含任何功能实现
"""

import logging
import os
import json
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable

from core.task_manager import TaskManager, TaskType, TaskCallback

logger = logging.getLogger(__name__)


class CoreAPI:
    """
    统一核心功能API类（纯接口版）
    所有功能通过 TaskManager 统一调度，不实现任何功能
    """
    
    def __init__(self):
        """初始化核心API"""
        logger.info("CoreAPI 初始化 - 纯接口模式，所有功能通过 TaskManager 调度")
        
        # 初始化核心组件（延迟加载）
        self._ocr_engine = None
        self._config_manager = None
        self._result_manager = None
        self._result_exporter = None
        
        # 跟踪状态（由回调更新）
        self._ocr_engine_status = 'not_initialized'  # 'not_initialized' | 'initializing' | 'ready' | 'error'
        self._ocr_engine_error = None  # 存储初始化错误信息

        # ★ 引擎状态变更通知（核心模块 → 界面层的推送通道）
        self._engine_status_callbacks: List[Callable] = []

        # ★ EventBus：事件频道订阅机制（核心模块 → 界面层的主动推送通道）
        self._event_channels: Dict[str, List[Callable]] = {}
        
        # 状态管理（当前图片路径、批量文件路径等）
        self._current_image_path = None
        self._batch_file_paths = []
        
        # 获取任务管理器单例
        self.task_manager = TaskManager.get_instance()
        
        # ★ 引擎心跳守护：定期检测子进程存活，异常退出时自动重启
        from PySide6.QtCore import QTimer
        self._heartbeat_timer = QTimer()
        self._heartbeat_timer.setInterval(3000)  # 每3秒检测一次
        self._heartbeat_timer.timeout.connect(self._heartbeat_check)
        self._heartbeat_auto_restart = True  # 是否自动重启（用户主动关闭时置False）
        
        # 注册执行器
        self._register_executors()
        
        logger.info("[CoreAPI] 初始化完成，TaskManager 已就绪")
    
    def _register_executors(self):
        """注册任务执行器"""
        from core.task_manager import create_ocr_executor, create_export_executor, create_scan_executor, create_ocr_init_executor, create_ocr_shutdown_executor, create_reparse_executor
        
        # Excel 数据处理执行器
        from core.excel_processor import (
            create_excel_load_executor,
            create_excel_clean_executor,
            create_excel_pivot_executor,
            create_excel_export_executor,
        )
        
        # 延迟导入核心模块
        if self._ocr_engine is None:
            from core.ocr_engine import OCREngine
            from core.config import get_config_manager
            self._config_manager = get_config_manager()
            exe_path = self._config_manager.get_ocr_exe_path()
            models_path = self._config_manager.get_models_path()
            language = self._config_manager.get_language()
            self._ocr_engine = OCREngine(exe_path=exe_path, models_path=models_path, language=language)
        
        if self._result_manager is None:
            from core.result_manager import get_result_manager
            self._result_manager = get_result_manager()
        
        if self._result_exporter is None:
            from core.exporter import ResultExporter
            self._result_exporter = ResultExporter()
        
        # 注册 OCR 执行器
        ocr_executor = create_ocr_executor(self._ocr_engine, self._config_manager, self._result_manager)
        self.task_manager.register_executor(TaskType.OCR_SINGLE, ocr_executor)
        self.task_manager.register_executor(TaskType.OCR_BATCH, ocr_executor)
        
        # 注册 OCR 初始化执行器
        ocr_init_executor = create_ocr_init_executor(self._ocr_engine)
        self.task_manager.register_executor(TaskType.OCR_INIT, ocr_init_executor)
        
        # ★ 新增：注册 OCR 关闭执行器
        ocr_shutdown_executor = create_ocr_shutdown_executor(self._ocr_engine)
        self.task_manager.register_executor(TaskType.OCR_SHUTDOWN, ocr_shutdown_executor)
        
        # 注册导出执行器
        export_executor = create_export_executor(self._result_exporter)
        self.task_manager.register_executor(TaskType.EXPORT, export_executor)
        
        # 注册扫描执行器
        scan_executor = create_scan_executor()
        self.task_manager.register_executor(TaskType.SCAN_DIRECTORY, scan_executor)
        
        # ── Excel 数据处理执行器 ──
        excel_load_executor = create_excel_load_executor()
        self.task_manager.register_executor(TaskType.EXCEL_LOAD, excel_load_executor)
        
        excel_clean_executor = create_excel_clean_executor()
        self.task_manager.register_executor(TaskType.EXCEL_CLEAN, excel_clean_executor)
        
        excel_pivot_executor = create_excel_pivot_executor()
        self.task_manager.register_executor(TaskType.EXCEL_PIVOT, excel_pivot_executor)
        
        excel_export_executor = create_excel_export_executor()
        self.task_manager.register_executor(TaskType.EXCEL_EXPORT, excel_export_executor)
        
        # ★ 新增：注册重新解析执行器
        reparse_executor = create_reparse_executor()
        self.task_manager.register_executor(TaskType.OCR_REPARSE, reparse_executor)
        
        # ★ 注入事件推送能力到核心模块
        if hasattr(self._ocr_engine, 'set_event_emitter'):
            self._ocr_engine.set_event_emitter(self.emit)
            logger.debug("[CoreAPI] 已向 OCREngine 注入事件推送能力")
        if hasattr(self._result_manager, 'set_event_emitter'):
            self._result_manager.set_event_emitter(self.emit)
            logger.debug("[CoreAPI] 已向 ResultManager 注入事件推送能力")
        # TemplateManager 通过 get_template_manager() 获取实例并注入
        from core.template_manager import get_template_manager
        template_mgr = get_template_manager()
        if hasattr(template_mgr, 'set_event_emitter'):
            template_mgr.set_event_emitter(self.emit)
            logger.debug("[CoreAPI] 已向 TemplateManager 注入事件推送能力")

        logger.info("[CoreAPI] 执行器注册完成")
    
    # ==================== 属性访问 ====================
    
    @property
    def config_manager(self):
        """获取配置管理器"""
        return self._config_manager
    
    @property
    def ocr_engine(self):
        """获取 OCR 引擎实例"""
        return self._ocr_engine
    
    @property
    def result_manager(self):
        """获取结果管理器"""
        return self._result_manager
    
    # ==================== 引擎状态推送机制 ====================

    def on_engine_status_changed(self, callback: Callable):
        """注册引擎状态变更回调（核心模块 → 界面层的推送通道）

        Args:
            callback: 回调函数，签名为 callback(status: str, error: Optional[str])
                       status: 'not_initialized' | 'initializing' | 'ready' | 'error'
        """
        if callback not in self._engine_status_callbacks:
            self._engine_status_callbacks.append(callback)
            logger.debug("[CoreAPI] 注册引擎状态回调: %s", callback.__name__ if hasattr(callback, '__name__') else 'anonymous')

    def _set_engine_status(self, status: str, error: Optional[str] = None):
        """设置引擎状态并推送变更通知（内部方法）

        所有 _ocr_engine_status 的修改都必须通过此方法，确保界面层收到推送。
        """
        old_status = self._ocr_engine_status
        self._ocr_engine_status = status
        self._ocr_engine_error = error
        logger.info("[CoreAPI] 引擎状态变更: %s → %s", old_status, status)
        # 推送通知到所有订阅者
        for cb in self._engine_status_callbacks:
            try:
                cb(status, error)
            except Exception as e:
                logger.warning("[CoreAPI] 引擎状态回调异常: %s", e)

    # ==================== 引擎心跳守护 ====================

    def _heartbeat_check(self):
        """引擎心跳检测（定时器回调，主线程执行）
        
        检测引擎子进程是否存活。如果进程意外死亡：
        1. 推送 process_died 事件到 UI
        2. 自动重新初始化引擎
        """
        if self._ocr_engine_status != 'ready':
            return  # 引擎非就绪状态，不检测
        
        if self._ocr_engine is None:
            return
        
        if not self._ocr_engine._is_process_alive():
            logger.warning("[CoreAPI] 心跳检测：引擎子进程已死亡！")
            self._ocr_engine._initialized = False
            self._set_engine_status('not_initialized')
            self.emit("engine:event", type="process_died")
            
            if self._heartbeat_auto_restart:
                logger.info("[CoreAPI] 自动重新初始化引擎...")
                self._heartbeat_timer.stop()
                self.submit_ocr_init_task(
                    on_complete=lambda data: logger.info("[CoreAPI] 引擎自动重启成功"),
                    on_error=lambda msg: logger.error("[CoreAPI] 引擎自动重启失败: %s", msg)
                )

    # ==================== EventBus 事件频道 ====================

    def on(self, channel: str, callback: Callable[[dict], None]) -> None:
        """订阅事件频道

        Args:
            channel: 事件频道名称（如 "engine:event", "result:event", "template:event"）
            callback: 回调函数，签名为 callback(data: dict)
        """
        if channel not in self._event_channels:
            self._event_channels[channel] = []
        if callback not in self._event_channels[channel]:
            self._event_channels[channel].append(callback)
            logger.debug("[CoreAPI] 订阅事件频道 '%s': %s",
                         channel,
                         callback.__name__ if hasattr(callback, '__name__') else 'anonymous')

    def emit(self, channel: str, **data) -> None:
        """向事件频道推送事件

        遍历该频道的所有回调并执行，每个回调用 try/except 包裹，
        防止单个回调异常影响其他订阅者。

        Args:
            channel: 事件频道名称
            **data:  事件数据，作为 dict 传给回调
        """
        callbacks = self._event_channels.get(channel, [])
        if not callbacks:
            return
        # 记录事件推送（结果更新太频繁用 debug 级别，其他用 info 级别）
        event_type = data.get("type", "")
        if channel.startswith("result:"):
            logger.debug("[CoreAPI] EventBus 推送: %s → %s (订阅者: %d)", channel, event_type, len(callbacks))
        else:
            logger.info("[CoreAPI] EventBus 推送: %s → %s (订阅者: %d)", channel, event_type, len(callbacks))
        for cb in callbacks:
            try:
                cb(data)
            except Exception as e:
                logger.warning("[CoreAPI] 事件频道 '%s' 回调异常: %s", channel, e)

    def off(self, channel: str, callback: Callable) -> None:
        """取消订阅事件频道

        Args:
            channel:  事件频道名称
            callback: 要移除的回调函数
        """
        callbacks = self._event_channels.get(channel, [])
        if callback in callbacks:
            callbacks.remove(callback)
            logger.debug("[CoreAPI] 取消订阅事件频道 '%s'", channel)

    # ==================== 状态查询接口 ====================
    
    def is_ocr_engine_ready(self) -> bool:
        """
        检查 OCR 引擎是否已就绪（三重检查：状态标志 + 引擎初始化状态 + 进程存活）
        
        Returns:
            bool: 引擎真正可用返回 True，否则返回 False
        """
        if self._ocr_engine_status != 'ready':
            return False
        # 二次校验：引擎实例确实存在且已初始化
        if self._ocr_engine is None or not self._ocr_engine._initialized:
            return False
        # ★ 三重校验：子进程是否仍在运行（防止用户强杀进程）
        if not self._ocr_engine._is_process_alive():
            logger.warning("[CoreAPI] 引擎子进程已死亡，重置状态")
            self._ocr_engine._initialized = False
            self._set_engine_status('not_initialized')
            # 通过 EventBus 推送进程死亡事件
            self.emit("engine:event", type="process_died")
            return False
        return True
    
    def get_ocr_engine_status(self) -> str:
        """
        获取 OCR 引擎详细状态（含进程存活校验）
        
        Returns:
            str: 'ready' | 'not_initialized' | 'initializing' | 'error'
        """
        # 状态标志说 ready 但需要深层校验
        if self._ocr_engine_status == 'ready':
            if self._ocr_engine is None or not self._ocr_engine._initialized:
                self._set_engine_status('not_initialized')
            elif not self._ocr_engine._is_process_alive():
                logger.warning("[CoreAPI] 引擎子进程已死亡（状态查询时发现），重置状态")
                self._ocr_engine._initialized = False
                self._set_engine_status('not_initialized')
                self.emit("engine:event", type="process_died")
        return self._ocr_engine_status
    
    def get_engine_status_display_info(self, show_notification: bool = False) -> dict:
        """
        获取引擎状态显示信息（供界面层直接使用）
        
        界面层可以直接使用返回的信息更新UI，不需要自己做逻辑判断。
        
        Args:
            show_notification: 是否显示通知（由界面层传入）
            
        Returns:
            dict: 包含状态图标颜色、状态文本、通知信息等
        """
        status = self._ocr_engine_status
        
        if status == 'ready':
            return {
                'icon_color': '#4CAF50',
                'status_text': 'OCR 引擎已就绪',
                'show_notification': show_notification,
                'notification_type': 'success',
                'notification_title': 'OCR 引擎',
                'notification_message': '引擎初始化成功，可以开始识别',
            }
        elif status == 'initializing':
            return {
                'icon_color': '#FFC107',
                'status_text': 'OCR 引擎初始化中...',
                'show_notification': False,  # 初始化中不需要通知
                'notification_type': None,
                'notification_title': None,
                'notification_message': None,
            }
        elif status == 'error':
            error_msg = self._ocr_engine_error or "未知错误"
            return {
                'icon_color': '#F44336',
                'status_text': 'OCR 引擎初始化失败',
                'show_notification': show_notification,
                'notification_type': 'error',
                'notification_title': 'OCR 引擎',
                'notification_message': f'引擎初始化失败: {error_msg}',
            }
        elif status == 'shutting_down':
            return {
                'icon_color': '#FF9800',
                'status_text': 'OCR 引擎正在关闭...',
                'show_notification': False,
                'notification_type': None,
                'notification_title': None,
                'notification_message': None,
            }
        else:  # 'not_initialized'
            return {
                'icon_color': '#9E9E9E',
                'status_text': 'OCR 引擎未初始化',
                'show_notification': show_notification,
                'notification_type': 'warning',
                'notification_title': 'OCR 引擎',
                'notification_message': '引擎未初始化，请先配置',
            }
    
    def get_current_image(self) -> str:
        """
        获取当前选中的图片路径
        
        Returns:
            str: 图片文件路径，如果没有则返回空字符串
        """
        return self._current_image_path or ''
    
    def get_batch_files(self) -> list:
        """
        获取当前批量文件路径列表
        
        Returns:
            list: 文件路径列表
        """
        return self._batch_file_paths
    
    def set_current_image(self, image_path: str):
        """
        设置当前图片路径
        
        Args:
            image_path: 图片文件路径
        """
        self._current_image_path = image_path
    
    def set_batch_files(self, file_paths: list):
        """
        设置批量文件路径列表
        
        Args:
            file_paths: 文件路径列表
        """
        self._batch_file_paths = file_paths
    
    # ==================== TaskManager 统一任务调度接口 ====================
    
    def submit_ocr_init_task(self,
                             on_progress: Optional[Callable] = None,
                             on_complete: Optional[Callable] = None,
                             on_error: Optional[Callable] = None,
                             task_id: Optional[str] = None) -> str:
        """
        提交 OCR 引擎初始化任务
        
        Args:
            on_progress: 进度回调 (TaskResult)
            on_complete: 完成回调 (TaskResult)，data 包含 {"success": bool, "message": str}
            on_error: 错误回调 (TaskResult)
            task_id: 任务ID（可选）
            
        Returns:
            任务ID
        """
        from core.task_manager import TaskCallback
        
        # 更新状态为"初始化中"
        self._set_engine_status('initializing')
        
        # 创建回调包装器，更新状态
        def progress_wrapper(task_result):
            if on_progress:
                progress = task_result.progress or {}
                stage = progress.get('stage', '')
                on_progress(stage)
        
        def complete_wrapper(task_result):
            if task_result.data and task_result.data.get('success'):
                self._set_engine_status('ready')
                # ★ 启动引擎心跳守护
                self._heartbeat_auto_restart = True
                self._heartbeat_timer.start()
                logger.info("[CoreAPI] 引擎心跳守护已启动 (间隔: 3s)")
                if on_complete:
                    on_complete(task_result.data)
            else:
                error_msg = task_result.data.get('message', '未知错误') if task_result.data else '初始化失败'
                self._set_engine_status('error', error_msg)
                if on_error:
                    on_error(error_msg)
        
        def error_wrapper(task_result):
            error_msg = task_result.error or 'OCR引擎初始化异常'
            self._set_engine_status('error', error_msg)
            if on_error:
                on_error(error_msg)
        
        # 创建回调
        callback = TaskCallback(
            on_progress=progress_wrapper,
            on_complete=complete_wrapper,
            on_error=error_wrapper
        )
        
        # 提交任务
        params = {
            "check_config": True
        }
        
        return self.task_manager.submit_task(
            task_type=TaskType.OCR_INIT,
            params=params,
            callback=callback,
            task_id=task_id
        )
    
    def init_ocr_engine(self, on_progress=None, on_complete=None, on_error=None):
        """
        初始化 OCR 引擎（异步）
        
        Args:
            on_progress: 进度回调
            on_complete: 完成回调，接收 {"success": bool, "message": str}
            on_error: 错误回调，接收错误信息
            
        Returns:
            任务ID
        """
        return self.submit_ocr_init_task(
            on_progress=on_progress,
            on_complete=on_complete,
            on_error=on_error
        )
    
    def submit_ocr_task(self,
                       image_paths: str | List[str],
                       on_progress: Optional[Callable] = None,
                       on_complete: Optional[Callable] = None,
                       on_error: Optional[Callable] = None,
                       task_id: Optional[str] = None,
                       template_id: Optional[str] = None) -> str:
        """
        提交 OCR 识别任务（统一接口）
        
        Args:
            image_paths: 单个图片路径或路径列表
            on_progress: 进度回调 (TaskResult)
            on_complete: 完成回调 (TaskResult)
            on_error: 错误回调 (TaskResult)
            task_id: 任务ID（可选）
            template_id: 识别模板ID（可选），提供后自动解析识别结果为结构化字段
            
        Returns:
            任务ID
        """
        from core.task_manager import TaskType, TaskCallback
        
        # 规范化输入
        if isinstance(image_paths, str):
            task_type = TaskType.OCR_SINGLE
        else:
            task_type = TaskType.OCR_BATCH
        
        # 创建回调
        callback = TaskCallback(
            on_progress=on_progress,
            on_complete=on_complete,
            on_error=on_error
        )
        
        # 提交任务
        params = {
            "image_paths": image_paths,
            "config": None,  # 执行器会从 ConfigManager 获取配置
            "template_id": template_id,  # 新增：识别模板ID
        }
        
        return self.task_manager.submit_task(
            task_type=task_type,
            params=params,
            callback=callback,
            task_id=task_id
        )
    
    def submit_export_task(self,
                          export_format: str,
                          file_path: str,
                          results: List[Dict],
                          column_headers: Optional[List[str]] = None,
                          include_original_text: bool = True,
                          on_progress: Optional[Callable] = None,
                          on_complete: Optional[Callable] = None,
                          on_error: Optional[Callable] = None,
                          task_id: Optional[str] = None) -> str:
        """
        提交导出任务
        
        Args:
            export_format: 导出格式 ("TXT", "JSON", "Excel", "CSV")
            file_path: 输出文件路径
            results: 要导出的结果列表
            column_headers: 列头列表（动态列支持，可选）
            include_original_text: 是否包含原始文本（Excel 导出时使用）
            on_progress: 进度回调
            on_complete: 完成回调
            on_error: 错误回调
            task_id: 任务ID（可选）
            
        Returns:
            任务ID
        """
        from core.task_manager import TaskType, TaskCallback
        
        callback = TaskCallback(
            on_progress=on_progress,
            on_complete=on_complete,
            on_error=on_error
        )
        
        params = {
            "format": export_format,
            "file_path": file_path,
            "results": results,
            "column_headers": column_headers,
            "include_original_text": include_original_text,  # 新增参数
        }
        
        return self.task_manager.submit_task(
            task_type=TaskType.EXPORT,
            params=params,
            callback=callback,
            task_id=task_id
        )
    
    def submit_scan_task(self,
                        directory: str,
                        recursive: bool = True,
                        on_progress: Optional[Callable] = None,
                        on_complete: Optional[Callable] = None,
                        on_error: Optional[Callable] = None,
                        task_id: Optional[str] = None) -> str:
        """
        提交目录扫描任务
        
        Args:
            directory: 目录路径
            recursive: 是否递归扫描子目录
            on_progress: 进度回调
            on_complete: 完成回调
            on_error: 错误回调
            task_id: 任务ID（可选）
            
        Returns:
            任务ID
        """
        from core.task_manager import TaskType, TaskCallback
        
        callback = TaskCallback(
            on_progress=on_progress,
            on_complete=on_complete,
            on_error=on_error
        )
        
        params = {
            "directory": directory,
            "recursive": recursive
        }
        
        return self.task_manager.submit_task(
            task_type=TaskType.SCAN_DIRECTORY,
            params=params,
            callback=callback,
            task_id=task_id
        )
    
    # ==================== OCR 关闭任务接口 ====================
    
    def submit_ocr_shutdown_task(self,
                                 on_progress: Optional[Callable] = None,
                                 on_complete: Optional[Callable] = None,
                                 on_error: Optional[Callable] = None,
                                 task_id: Optional[str] = None) -> str:
        """
        提交 OCR 引擎关闭任务（资源回收）
        
        Args:
            on_progress: 进度回调 (TaskResult)
            on_complete: 完成回调 (TaskResult)，data 包含 {"success": bool, "message": str}
            on_error: 错误回调 (TaskResult)
            task_id: 任务ID（可选）
            
        Returns:
            任务ID
        """
        from core.task_manager import TaskCallback
        
        # ★ 停止心跳守护（用户主动关闭，不需要自动重启）
        self._heartbeat_auto_restart = False
        self._heartbeat_timer.stop()
        self._set_engine_status('shutting_down')
        logger.info("[CoreAPI] 引擎心跳守护已停止（用户主动关闭）")
        
        # 创建回调包装器
        def progress_wrapper(task_result):
            if on_progress:
                progress = task_result.progress or {}
                stage = progress.get('stage', '')
                on_progress(stage)
        
        def complete_wrapper(task_result):
            if task_result.data and task_result.data.get('success'):
                if on_complete:
                    on_complete(task_result.data)
            else:
                error_msg = task_result.data.get('message', '关闭失败') if task_result.data else '任务失败'
                if on_error:
                    on_error(error_msg)
        
        def error_wrapper(task_result):
            if on_error:
                on_error(task_result.error or 'OCR关闭任务异常')
        
        # 创建回调
        callback = TaskCallback(
            on_progress=progress_wrapper,
            on_complete=complete_wrapper,
            on_error=error_wrapper
        )
        
        # 提交任务
        params = {}
        
        return self.task_manager.submit_task(
            task_type=TaskType.OCR_SHUTDOWN,
            params=params,
            callback=callback,
            task_id=task_id
        )
    
    def scan_folder(self, folder_path: str, on_progress=None, on_complete=None, on_error=None):
        """
        扫描文件夹（异步）
        
        Args:
            folder_path: 文件夹路径
            on_progress: 进度回调
            on_complete: 完成回调，接收文件列表
            on_error: 错误回调，接收错误信息
            
        Returns:
            任务ID
        """
        return self.submit_scan_task(
            directory=folder_path,
            recursive=self._config_manager.get_scan_subdirs(),
            on_progress=on_progress,
            on_complete=on_complete,
            on_error=on_error
        )
    
    def cancel_task(self, task_id: str) -> bool:
        """
        取消任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否成功取消
        """
        return self.task_manager.cancel_task(task_id)
    
    def get_task_status(self, task_id: str):
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            TaskStatus 或 None
        """
        return self.task_manager.get_task_status(task_id)
    
    def get_running_tasks(self) -> List:
        """获取正在运行的任务列表"""
        return self.task_manager.get_running_tasks()
    
    def clear_completed_tasks(self):
        """清理已完成的任务记录"""
        self.task_manager.clear_completed_tasks()
    
    def connect_task_signals(self,
                            on_progress: Optional[Callable] = None,
                            on_complete: Optional[Callable] = None,
                            on_error: Optional[Callable] = None,
                            on_cancelled: Optional[Callable] = None):
        """
        连接任务管理器全局信号（适用于需要监听所有任务的场景）
        
        Args:
            on_progress: 进度信号回调
            on_complete: 完成信号回调
            on_error: 错误信号回调
            on_cancelled: 取消信号回调
        """
        if on_progress:
            self.task_manager.task_progress.connect(on_progress)
        if on_complete:
            self.task_manager.task_completed.connect(on_complete)
        if on_error:
            self.task_manager.task_failed.connect(on_error)
        if on_cancelled:
            self.task_manager.task_cancelled.connect(on_cancelled)
    
    # ==================== 配置管理相关接口 ====================
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            配置值
        """
        from core.config import get_config_manager
        config_manager = get_config_manager()
        return config_manager.get(key, default)
    
    def set_config(self, key: str, value: Any) -> bool:
        """
        设置配置值
        
        Args:
            key: 配置键
            value: 配置值
            
        Returns:
            是否设置成功
        """
        from core.config import get_config_manager
        config_manager = get_config_manager()
        return config_manager.set(key, value)
    
    def check_ocr_config(self) -> bool:
        """
        检查OCR引擎配置是否完整
        
        Returns:
            配置是否完整
        """
        from core.config import get_config_manager
        config_manager = get_config_manager()
        return config_manager.check_config()
    
    # ==================== 结果管理相关接口 ====================
    
    def get_history_results(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        获取历史识别结果
        
        Args:
            limit: 限制数量
            
        Returns:
            历史结果列表
        """
        from core.result_manager import get_result_manager
        result_manager = get_result_manager()
        return result_manager.get_history(limit)
    
    def clear_all_history(self) -> bool:
        """
        清空所有历史记录
        
        Returns:
            是否清空成功
        """
        from core.result_manager import get_result_manager
        result_manager = get_result_manager()
        return result_manager.clear_all()
    
    def delete_history_by_index(self, index: int) -> bool:
        """
        根据索引删除历史记录
        
        Args:
            index: 历史记录索引
            
        Returns:
            是否删除成功
        """
        from core.result_manager import get_result_manager
        result_manager = get_result_manager()
        return result_manager.delete_history(index)
    
    # ==================== 数据处理（供 UI 层调用） ====================

    def get_ocr_result_display_info(self, result_item: dict) -> dict:
        """将单个 result_item 转换为 UI 显示数据

        Args:
            result_item: 执行器返回的 {"file_path": str, "file_name": str, "result": dict}

        Returns:
            {
                "file_name": str,       # 文件名
                "text": str,            # 识别文本（成功时）或空字符串
                "is_success": bool,     # 是否识别成功
                "error_msg": str,       # 错误信息（失败时）或空字符串
                "extracted_text": str,  # 提取字段文本或空字符串
            }
        """
        ocr_result = result_item.get('result', {}) or {}
        file_name = result_item.get('file_name', '') or os.path.basename(result_item.get('file_path', ''))
        is_success = ocr_result.get('success', False)

        if is_success:
            texts = ocr_result.get('texts', [])
            text = '\n'.join(texts) if texts else ''
            raw_data = ocr_result.get('data', [])
            error_msg = ''
        else:
            text = ''
            raw_data = ocr_result.get('data', '识别失败')
            error_msg = raw_data if isinstance(raw_data, str) else '识别失败'

        # extracted 字段在 result_item 上，不在 ocr_result 里
        extracted = result_item.get('extracted', {})
        if extracted:
            extracted_text = '\n'.join([f"{k}: {v}" for k, v in extracted.items()])
        else:
            extracted_text = ''

        return {
            'file_name': file_name,
            'text': text,
            'is_success': is_success,
            'error_msg': error_msg,
            'extracted_text': extracted_text,
        }

    def get_ocr_summary(self, results: list) -> dict:
        """统计识别结果摘要

        Args:
            results: 执行器返回的 result_item 列表

        Returns:
            {
                "success_count": int,   # 成功数量
                "total_count": int,     # 总数量
                "summary_text": str,    # 摘要文本（如 "成功识别 8/10 个文件"）
            }
        """
        total = len(results)
        success_count = sum(1 for r in results if r.get('result', {}).get('success', False))
        return {
            'success_count': success_count,
            'total_count': total,
            'summary_text': f"成功识别 {success_count}/{total} 个文件",
        }

    def get_ocr_template_names(self) -> Dict[str, str]:
        """
        获取所有 OCR 解析模板 {id: name}（供 UI 下拉框使用）

        Returns:
            模板ID -> 模板名称的字典
        """
        from core.template_manager import get_template_manager
        return get_template_manager().get_template_names()

    def get_export_default_name(self, is_batch: bool, image_path: str = '', ext: str = 'txt') -> str:
        """生成导出默认文件名

        Args:
            is_batch: 是否批量模式
            image_path: 单图模式下的图片路径
            ext: 文件扩展名

        Returns:
            默认文件名字符串
        """
        if is_batch:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            return f"OCR结果_批量_{timestamp}.{ext}"
        elif image_path:
            image_name = os.path.basename(image_path)
            name_without_ext = os.path.splitext(image_name)[0]
            return f"{name_without_ext}_OCR结果.{ext}"
        else:
            return f"OCR结果.{ext}"

    def get_current_filename(self, file_path: str) -> str:
        """从文件路径提取文件名（供 UI 层显示用）

        Args:
            file_path: 完整文件路径

        Returns:
            文件名
        """
        return os.path.basename(file_path)

    def classify_dropped_paths(self, file_paths: list) -> dict:
        """分类拖放的文件路径（供 UI 层调用）

        Args:
            file_paths: 拖放的文件路径列表

        Returns:
            {
                "folder_paths": list,       # 文件夹路径
                "image_files": list,        # 图片文件路径
                "folder_images": list,      # 文件夹中扫描到的图片
                "first_folder": str or None # 第一个文件夹路径
            }
        """
        IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.tif', '.webp', '.ico', '.pdf'}

        folder_paths = [p for p in file_paths if os.path.isdir(p)]
        image_files = [p for p in file_paths if os.path.isfile(p) and os.path.splitext(p)[1].lower() in IMAGE_EXTENSIONS]

        folder_images = []
        first_folder = folder_paths[0] if folder_paths else None
        if first_folder:
            for root, dirs, files in os.walk(first_folder):
                for file in files:
                    if os.path.splitext(file)[1].lower() in IMAGE_EXTENSIONS:
                        folder_images.append(os.path.join(root, file))

        return {
            'folder_paths': folder_paths,
            'image_files': image_files,
            'folder_images': folder_images,
            'first_folder': first_folder,
        }

    def get_export_result_display_info(self, task_result_data) -> dict:
        """从导出任务结果提取 UI 显示信息

        Args:
            task_result_data: 导出任务返回的数据

        Returns:
            {
                "is_success": bool,
                "saved_path": str,
                "error_msg": str,
            }
        """
        if not task_result_data:
            return {'is_success': False, 'saved_path': '', 'error_msg': '导出任务未完成'}

        return {
            'is_success': bool(task_result_data.get('success', False)),
            'saved_path': task_result_data.get('file_path', ''),
            'error_msg': task_result_data.get('message', '导出任务未完成'),
        }

    def get_batch_folder_display_name(self, folder_path: str, file_paths: list) -> str:
        """获取批量模式的文件夹显示名称（供 UI 层显示用）

        Args:
            folder_path: 文件夹路径（可能为空）
            file_paths: 文件路径列表

        Returns:
            显示名称
        """
        if folder_path and os.path.isdir(folder_path):
            return os.path.basename(folder_path)
        elif file_paths:
            common_dir = os.path.dirname(file_paths[0])
            return os.path.basename(common_dir) or common_dir
        else:
            return "多个文件"

    def get_batch_folder_path(self, file_paths: list) -> str:
        """从文件路径列表提取共同目录（供 UI 层使用）

        Args:
            file_paths: 文件路径列表

        Returns:
            共同目录路径
        """
        if file_paths:
            return os.path.dirname(file_paths[0])
        return ""

    # ==================== Excel 数据处理接口 ====================

    # ── 任务提交接口 ──

    def submit_excel_load_task(self,
                               file_paths: List[str],
                               sheet_name: Optional[str] = None,
                               use_columns: Optional[List[str]] = None,
                               preview_only: bool = True,
                               on_progress: Optional[Callable] = None,
                               on_complete: Optional[Callable] = None,
                               on_error: Optional[Callable] = None,
                               task_id: Optional[str] = None) -> str:
        """
        提交 Excel 加载任务

        Args:
            file_paths:     Excel 文件路径列表
            sheet_name:    Sheet 名称（None = 第一个 sheet）
            use_columns:   选用的列（None = 全部）
            preview_only:   True = 只加载前 200 行（快速预览）
            on_progress:   进度回调
            on_complete:   完成回调，接收 {"tables": [...], "total_rows": int}
            on_error:      错误回调
            task_id:       任务ID（可选）

        Returns:
            任务ID
        """
        from core.task_manager import TaskCallback

        callback = TaskCallback(
            on_progress=on_progress,
            on_complete=on_complete,
            on_error=on_error,
        )

        params = {
            "file_paths": file_paths,
            "sheet_name": sheet_name,
            "use_columns": use_columns,
            "preview_only": preview_only,
        }

        return self.task_manager.submit_task(
            task_type=TaskType.EXCEL_LOAD,
            params=params,
            callback=callback,
            task_id=task_id
        )

    def submit_excel_clean_task(self,
                                tables_json: List[str],
                                clean_rules: List[Dict],
                                on_progress: Optional[Callable] = None,
                                on_complete: Optional[Callable] = None,
                                on_error: Optional[Callable] = None,
                                task_id: Optional[str] = None) -> str:
        """
        提交数据清洗任务

        Args:
            tables_json:  已加载表的 full_df_json 列表
            clean_rules: CleanRule 的 dict 列表
            on_progress: 进度回调
            on_complete: 完成回调，接收 {"cleaned_df_json": str, "original_rows": int, ...}
            on_error:    错误回调
            task_id:     任务ID（可选）

        Returns:
            任务ID
        """
        from core.task_manager import TaskCallback

        callback = TaskCallback(
            on_progress=on_progress,
            on_complete=on_complete,
            on_error=on_error,
        )

        params = {
            "tables_json": tables_json,
            "clean_rules": clean_rules,
        }

        return self.task_manager.submit_task(
            task_type=TaskType.EXCEL_CLEAN,
            params=params,
            callback=callback,
            task_id=task_id
        )

    def submit_excel_pivot_task(self,
                                tables_json: List[str],
                                pivot_config: Dict,
                                merge_keys: Optional[List[str]] = None,
                                on_progress: Optional[Callable] = None,
                                on_complete: Optional[Callable] = None,
                                on_error: Optional[Callable] = None,
                                task_id: Optional[str] = None) -> str:
        """
        提交透视表生成任务

        Args:
            tables_json:   已加载表的 full_df_json 列表
            pivot_config:  PivotConfig 的 dict 表示
            merge_keys:    多表合并键列（空=纵向合并）
            on_progress:  进度回调
            on_complete:  完成回调，接收 {"result_df_json": str, "row_count": int, ...}
            on_error:     错误回调
            task_id:      任务ID（可选）

        Returns:
            任务ID
        """
        from core.task_manager import TaskCallback

        callback = TaskCallback(
            on_progress=on_progress,
            on_complete=on_complete,
            on_error=on_error,
        )

        params = {
            "tables_json": tables_json,
            "pivot_config": pivot_config,
            "merge_keys": merge_keys or [],
        }

        return self.task_manager.submit_task(
            task_type=TaskType.EXCEL_PIVOT,
            params=params,
            callback=callback,
            task_id=task_id
        )

    def submit_excel_export_task(self,
                                 result_df_json: str,
                                 file_path: str,
                                 export_format: str = "xlsx",
                                 on_progress: Optional[Callable] = None,
                                 on_complete: Optional[Callable] = None,
                                 on_error: Optional[Callable] = None,
                                 task_id: Optional[str] = None) -> str:
        """
        提交 Excel 导出任务

        Args:
            result_df_json: 透视结果的 df_json 字符串
            file_path:     输出文件路径
            export_format: 导出格式 "xlsx" | "csv"
            on_progress:   进度回调
            on_complete:   完成回调，接收 {"success": bool, "file_path": str, ...}
            on_error:      错误回调
            task_id:       任务ID（可选）

        Returns:
            任务ID
        """
        from core.task_manager import TaskCallback

        callback = TaskCallback(
            on_progress=on_progress,
            on_complete=on_complete,
            on_error=on_error,
        )

        params = {
            "result_df_json": result_df_json,
            "file_path": file_path,
            "format": export_format,
        }

        return self.task_manager.submit_task(
            task_type=TaskType.EXCEL_EXPORT,
            params=params,
            callback=callback,
            task_id=task_id
        )

    # ── 数据处理（供 UI 层同步调用）──

    def get_excel_sheet_names(self, file_path: str) -> List[str]:
        """
        获取 Excel 文件的 sheet 名称列表（同步，快速）

        Args:
            file_path: Excel 文件路径

        Returns:
            sheet 名称列表
        """
        from core.excel_processor import get_excel_sheet_names
        return get_excel_sheet_names(file_path)

    def get_excel_column_names(self, file_path: str,
                               sheet_name: Optional[str] = None,
                               nrows: int = 0) -> List[str]:
        """
        获取指定 sheet 的列名列表（同步，快速）

        Args:
            file_path:   Excel 文件路径
            sheet_name: Sheet 名称（None = 第一个）
            nrows:      0 = 只读取表头

        Returns:
            列名列表
        """
        from core.excel_processor import get_excel_column_names
        return get_excel_column_names(file_path, sheet_name, nrows)

    def get_loaded_tables_info(self, loaded_tables: List[Dict]) -> List[Dict]:
        """
        获取已加载表的信息摘要（供 UI 显示）

        Args:
            loaded_tables: submit_excel_load_task 返回的每个表的 info dict

        Returns:
            [{"file_path": str, "sheet_name": str, "row_count": int, "columns": List[str]}]
        """
        return [
            {
                "file_path": t.get("file_path", ""),
                "sheet_name": t.get("sheet_name", ""),
                "row_count": t.get("row_count", 0),
                "columns": t.get("columns", []),
            }
            for t in loaded_tables
        ]

    def get_clean_result_display_info(self, task_result_data: Dict) -> Dict:
        """
        从清洗任务结果提取 UI 显示信息

        Args:
            task_result_data: 清洗任务返回的数据

        Returns:
            {"original_rows": int, "cleaned_rows": int, "removed_rows": int, "columns": List[str]}
        """
        if not task_result_data:
            return {"original_rows": 0, "cleaned_rows": 0, "removed_rows": 0, "columns": []}

        return {
            "original_rows": task_result_data.get("original_rows", 0),
            "cleaned_rows": task_result_data.get("cleaned_rows", 0),
            "removed_rows": task_result_data.get("removed_rows", 0),
            "columns": task_result_data.get("columns", []),
        }

    def get_pivot_result_display_info(self, task_result_data: Dict) -> Dict:
        """
        从透视任务结果提取 UI 显示信息

        Args:
            task_result_data: 透视任务返回的数据

        Returns:
            {"row_count": int, "col_count": int, "columns": List[str], "result_df_json": str}
        """
        if not task_result_data:
            return {"row_count": 0, "col_count": 0, "columns": [], "result_df_json": ""}

        return {
            "row_count": task_result_data.get("row_count", 0),
            "col_count": task_result_data.get("col_count", 0),
            "columns": task_result_data.get("columns", []),
            "result_df_json": task_result_data.get("result_df_json", ""),
        }

    def get_excel_export_display_info(self, task_result_data: Dict) -> Dict:
        """
        从导出任务结果提取 UI 显示信息

        Args:
            task_result_data: 导出任务返回的数据

        Returns:
            {"is_success": bool, "saved_path": str, "error_msg": str}
        """
        if not task_result_data:
            return {"is_success": False, "saved_path": "", "error_msg": "导出任务未完成"}

        return {
            "is_success": bool(task_result_data.get("success", False)),
            "saved_path": task_result_data.get("file_path", ""),
            "error_msg": "" if task_result_data.get("success") else "导出失败",
        }

    # ── 透视规则模板管理 ──

    def save_pivot_template(self, config: 'PivotConfig') -> bool:
        """
        保存透视配置为模板（JSON 文件）

        Args:
            config: PivotConfig 对象

        Returns:
            是否保存成功
        """
        import json
        import os
        from pathlib import Path

        try:
            # 确保目录存在
            template_dir = Path(__file__).resolve().parent.parent / "templates" / "excel_pivot"
            template_dir.mkdir(parents=True, exist_ok=True)

            # 验证配置
            is_valid, error_msg = config.validate()
            if not is_valid:
                logger.error(f"[CoreAPI] 透视配置验证失败: {error_msg}")
                return False

            # 更新时间戳
            config.updated_at = datetime.now().isoformat()

            # 保存到文件
            file_path = template_dir / f"{config.id}.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(config.to_dict(), f, ensure_ascii=False, indent=2)

            logger.info(f"[CoreAPI] 透视模板已保存: {config.name} ({config.id})")
            return True

        except Exception as e:
            logger.error(f"[CoreAPI] 保存透视模板失败: {e}", exc_info=True)
            return False

    def load_pivot_template(self, template_id: str) -> Optional['PivotConfig']:
        """
        加载透视模板

        Args:
            template_id: 模板 ID

        Returns:
            PivotConfig 对象，失败返回 None
        """
        import json
        from pathlib import Path
        from core.excel_models import PivotConfig

        try:
            template_dir = Path(__file__).resolve().parent.parent / "templates" / "excel_pivot"
            file_path = template_dir / f"{template_id}.json"

            if not file_path.exists():
                logger.warning(f"[CoreAPI] 透视模板不存在: {template_id}")
                return None

            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            return PivotConfig.from_dict(data)

        except Exception as e:
            logger.error(f"[CoreAPI] 加载透视模板失败: {e}", exc_info=True)
            return None

    def get_all_pivot_templates(self) -> List[Dict]:
        """
        获取所有透视模板摘要（供 UI 下拉选择）

        Returns:
            [{"id": str, "name": str, "description": str, "updated_at": str}]
        """
        import json
        from pathlib import Path

        template_dir = Path(__file__).resolve().parent.parent / "templates" / "excel_pivot"
        if not template_dir.exists():
            return []

        results = []
        for fp in template_dir.glob("*.json"):
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                results.append({
                    "id": data.get("id", fp.stem),
                    "name": data.get("name", "未命名"),
                    "description": data.get("description", ""),
                    "updated_at": data.get("updated_at", ""),
                })
            except Exception as e:
                logger.warning(f"[CoreAPI] 读取模板失败 {fp.name}: {e}")

        # 按更新时间倒序
        results.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return results

    def delete_pivot_template(self, template_id: str) -> bool:
        """
        删除透视模板

        Args:
            template_id: 模板 ID

        Returns:
            是否删除成功
        """
        from pathlib import Path

        try:
            template_dir = Path(__file__).resolve().parent.parent / "templates" / "excel_pivot"
            file_path = template_dir / f"{template_id}.json"

            if file_path.exists():
                file_path.unlink()
                logger.info(f"[CoreAPI] 透视模板已删除: {template_id}")
                return True
            else:
                logger.warning(f"[CoreAPI] 透视模板不存在: {template_id}")
                return False

        except Exception as e:
            logger.error(f"[CoreAPI] 删除透视模板失败: {e}", exc_info=True)
            return False

    # ==================== 重新解析 ====================

    def reparse_results(self,
                        results: List[Dict],
                        template_id: str,
                        on_progress: Optional[Callable] = None,
                        on_complete: Optional[Callable] = None,
                        on_error: Optional[Callable] = None,
                        task_id: Optional[str] = None) -> str:
        """
        重新解析识别结果（使用不同的模板，不需要重新识别）

        Args:
            results: 已有识别结果列表（包含 'text' 字段）
            template_id: 识别模板ID
            on_progress: 进度回调
            on_complete: 完成回调，接收重新解析后的结果列表
            on_error: 错误回调
            task_id: 任务ID（可选）

        Returns:
            任务ID
        """
        from core.task_manager import TaskType, TaskCallback

        # 创建回调
        callback = TaskCallback(
            on_progress=on_progress,
            on_complete=on_complete,
            on_error=on_error
        )

        # 提交任务
        params = {
            "results": results,
            "template_id": template_id,
        }

        return self.task_manager.submit_task(
            task_type=TaskType.OCR_REPARSE,
            params=params,
            callback=callback,
            task_id=task_id
        )

    # ==================== 资源清理 ====================

    def cleanup_resources(self):
        """清理所有资源 - 通过 TaskManager 统一调度"""
        logger.info("[CoreAPI] 提交资源清理任务...")
        
        # 提交 OCR 关闭任务（由 TaskManager 统一调度）
        try:
            self.submit_ocr_shutdown_task()
        except Exception as e:
            logger.warning(f"[CoreAPI] 提交 OCR 关闭任务失败: {e}")
        
        logger.info("[CoreAPI] 资源清理任务已提交")


# 全局核心API实例
_core_api_instance = None


def get_core_api() -> CoreAPI:
    """
    获取全局核心API实例
    
    Returns:
        CoreAPI 实例
    """
    global _core_api_instance
    if _core_api_instance is None:
        _core_api_instance = CoreAPI()
    return _core_api_instance
