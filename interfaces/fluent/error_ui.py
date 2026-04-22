# 界面错误处理模块
# 处理界面显示和交互相关的错误

from typing import Optional, Dict, Callable
from qfluentwidgets import InfoBar, InfoBarPosition, MessageBox, MessageDialog
from PySide6.QtWidgets import QWidget
from core.error_handler import OCRError, ErrorType
from datetime import datetime
import logging

# 配置日志
logger = logging.getLogger(__name__)


class ErrorUIDisplay:
    """界面错误显示类"""
    
    def __init__(self):
        """初始化界面错误显示类"""
        # 错误统计
        self.error_stats: Dict[ErrorType, int] = {}
        for error_type in ErrorType:
            self.error_stats[error_type] = 0
        
        # 错误恢复策略
        self.recovery_strategies: Dict[ErrorType, Callable[[OCRError, QWidget], bool]] = {}
        self._init_recovery_strategies()
    
    def _init_recovery_strategies(self):
        """初始化错误恢复策略"""
        # 为常见错误类型添加恢复策略
        self.recovery_strategies[ErrorType.OCR_ENGINE] = self._recover_ocr_engine
        self.recovery_strategies[ErrorType.FILE_OPERATION] = self._recover_file_operation
        self.recovery_strategies[ErrorType.CONFIG] = self._recover_config
    
    def get_error_stats(self) -> Dict[ErrorType, int]:
        """
        获取错误统计
        
        Returns:
            错误类型到错误数量的映射
        """
        return self.error_stats
    
    def reset_error_stats(self):
        """
        重置错误统计
        """
        for error_type in ErrorType:
            self.error_stats[error_type] = 0
    
    def _recover_ocr_engine(self, error: OCRError, parent: QWidget) -> bool:
        """
        恢复 OCR 引擎错误
        
        Args:
            error: OCR 错误
            parent: 父窗口
            
        Returns:
            是否恢复成功
        """
        try:
            from core.ocr_engine import get_ocr_engine
            ocr_engine = get_ocr_engine()
            # 尝试重新初始化 OCR 引擎
            success = ocr_engine.initialize()
            if success:
                self.show_success_info_bar(parent, "恢复成功", "OCR 引擎已重新初始化")
            return success
        except Exception as e:
            logger.error(f"OCR 引擎恢复失败: {e}")
            return False
    
    def _recover_file_operation(self, error: OCRError, parent: QWidget) -> bool:
        """
        恢复文件操作错误
        
        Args:
            error: OCR 错误
            parent: 父窗口
            
        Returns:
            是否恢复成功
        """
        try:
            # 尝试创建必要的目录
            import os
            # 从错误消息中提取路径
            if "不存在" in error.message:
                # 尝试创建目录
                path = error.message.split(":")[-1].strip()
                if path:
                    dir_path = os.path.dirname(path)
                    if dir_path and not os.path.exists(dir_path):
                        os.makedirs(dir_path, exist_ok=True)
                        self.show_success_info_bar(parent, "恢复成功", f"已创建目录: {dir_path}")
                        return True
        except Exception as e:
            logger.error(f"文件操作恢复失败: {e}")
        return False
    
    def _recover_config(self, error: OCRError, parent: QWidget) -> bool:
        """
        恢复配置错误
        
        Args:
            error: OCR 错误
            parent: 父窗口
            
        Returns:
            是否恢复成功
        """
        try:
            from core.config import get_config_manager
            config = get_config_manager()
            # 尝试重新加载配置
            config._load()
            self.show_success_info_bar(parent, "恢复成功", "配置已重新加载")
            return True
        except Exception as e:
            logger.error(f"配置恢复失败: {e}")
            return False
    
    def attempt_recovery(self, error: OCRError, parent: QWidget) -> bool:
        """
        尝试从错误中恢复
        
        Args:
            error: OCR 错误
            parent: 父窗口
            
        Returns:
            是否恢复成功
        """
        strategy = self.recovery_strategies.get(error.error_type)
        if strategy:
            try:
                return strategy(error, parent)
            except Exception as e:
                logger.error(f"错误恢复策略执行失败: {e}")
        return False
    
    def show_error_info_bar(self, parent: QWidget, title: str, content: str, duration: int = 5000):
        """
        显示错误信息条
        
        Args:
            parent: 父窗口
            title: 标题
            content: 内容
            duration: 显示时长（毫秒）
        """
        InfoBar.error(
            title=title,
            content=content,
            orient=parent.parent().layout().direction() if hasattr(parent.parent(), 'layout') else None,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=duration,
            parent=parent
        )
    
    def show_success_info_bar(self, parent: QWidget, title: str, content: str, duration: int = 3000):
        """
        显示成功信息条
        
        Args:
            parent: 父窗口
            title: 标题
            content: 内容
            duration: 显示时长（毫秒）
        """
        InfoBar.success(
            title=title,
            content=content,
            orient=parent.parent().layout().direction() if hasattr(parent.parent(), 'layout') else None,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=duration,
            parent=parent
        )
    
    def show_warning_info_bar(self, parent: QWidget, title: str, content: str, duration: int = 4000):
        """
        显示警告信息条
        
        Args:
            parent: 父窗口
            title: 标题
            content: 内容
            duration: 显示时长（毫秒）
        """
        InfoBar.warning(
            title=title,
            content=content,
            orient=parent.parent().layout().direction() if hasattr(parent.parent(), 'layout') else None,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=duration,
            parent=parent
        )
    
    def show_message_box(self, parent: QWidget, title: str, content: str) -> bool:
        """
        显示消息框
        
        Args:
            parent: 父窗口
            title: 标题
            content: 内容
        
        Returns:
            用户是否点击了确定按钮
        """
        msg_box = MessageBox(title, content, parent)
        msg_box.yesButton.setText("确定")
        msg_box.cancelButton.setText("取消")
        return msg_box.exec() == MessageBox.Yes
    
    def show_confirm_dialog(self, parent: QWidget, title: str, content: str) -> bool:
        """
        显示确认对话框
        
        Args:
            parent: 父窗口
            title: 标题
            content: 内容
        
        Returns:
            用户是否点击了确定按钮
        """
        msg_box = MessageBox(title, content, parent)
        msg_box.yesButton.setText("确定")
        msg_box.cancelButton.setText("取消")
        return msg_box.exec() == MessageBox.Yes
    
    def show_error_dialog(self, parent: QWidget, title: str, content: str):
        """
        显示错误对话框
        
        Args:
            parent: 父窗口
            title: 标题
            content: 内容
        """
        msg_box = MessageBox(title, content, parent)
        msg_box.yesButton.setText("确定")
        msg_box.cancelButton.hide()
        msg_box.exec()
    
    def handle_error(self, parent: QWidget, error: OCRError):
        """
        处理 OCR 错误并显示相应的界面提示
        
        Args:
            parent: 父窗口
            error: OCR 错误
        """
        # 记录错误统计
        self.error_stats[error.error_type] += 1
        
        # 尝试错误恢复
        recovery_success = self.attempt_recovery(error, parent)
        if recovery_success:
            logger.info(f"[{error.error_type.value}] 错误恢复成功")
            return
        
        # 显示错误信息
        error_title_map = {
            ErrorType.OCR_ENGINE: "OCR 引擎错误",
            ErrorType.CONFIG: "配置错误",
            ErrorType.FILE_OPERATION: "文件操作错误",
            ErrorType.TEMPLATE: "模板错误",
            ErrorType.SCREENSHOT: "截图错误",
            ErrorType.EXPORT: "导出错误",
            ErrorType.ASYNC_TASK: "任务执行错误",
            ErrorType.UNKNOWN: "未知错误"
        }
        
        title = error_title_map.get(error.error_type, "错误")
        content = error.message
        
        if error.original_error:
            content += f"\n\n原始错误: {str(error.original_error)}"
        
        # 添加错误发生时间
        timestamp_str = error.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        content += f"\n\n发生时间: {timestamp_str}"
        
        self.show_error_info_bar(parent, title, content)


class ErrorHandlerUI:
    """界面错误处理器"""
    
    def __init__(self, parent: QWidget):
        """
        初始化界面错误处理器
        
        Args:
            parent: 父窗口
        """
        self.parent = parent
        self.error_display = ErrorUIDisplay()
    
    def get_error_stats(self):
        """
        获取错误统计
        
        Returns:
            错误类型到错误数量的映射
        """
        return self.error_display.get_error_stats()
    
    def reset_error_stats(self):
        """
        重置错误统计
        """
        self.error_display.reset_error_stats()
    
    def attempt_recovery(self, error: OCRError) -> bool:
        """
        尝试从错误中恢复
        
        Args:
            error: OCR 错误
            
        Returns:
            是否恢复成功
        """
        return self.error_display.attempt_recovery(error, self.parent)
    
    def handle_ocr_error(self, error: OCRError):
        """
        处理 OCR 错误
        
        Args:
            error: OCR 错误
        """
        self.error_display.handle_error(self.parent, error)
    
    def show_error(self, title: str, message: str):
        """
        显示错误信息
        
        Args:
            title: 标题
            message: 消息
        """
        self.error_display.show_error_info_bar(self.parent, title, message)
    
    def show_success(self, title: str, message: str):
        """
        显示成功信息
        
        Args:
            title: 标题
            message: 消息
        """
        self.error_display.show_success_info_bar(self.parent, title, message)
    
    def show_warning(self, title: str, message: str):
        """
        显示警告信息
        
        Args:
            title: 标题
            message: 消息
        """
        self.error_display.show_warning_info_bar(self.parent, title, message)
    
    def confirm(self, title: str, message: str) -> bool:
        """
        显示确认对话框
        
        Args:
            title: 标题
            message: 消息
        
        Returns:
            用户是否确认
        """
        return self.error_display.show_confirm_dialog(self.parent, title, message)
    
    def alert(self, title: str, message: str):
        """
        显示警告对话框
        
        Args:
            title: 标题
            message: 消息
        """
        self.error_display.show_message_box(self.parent, title, message)