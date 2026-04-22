import unittest
from unittest.mock import Mock, patch
from PySide6.QtWidgets import QWidget
from core.error_handler import OCRError, ErrorType
from interfaces.fluent.error_ui import ErrorUIDisplay, ErrorHandlerUI


class TestErrorUIDisplay(unittest.TestCase):
    """测试界面错误显示类"""
    
    def setUp(self):
        """设置测试环境"""
        self.error_display = ErrorUIDisplay()
        self.parent = Mock(spec=QWidget)
        # 模拟父窗口的父窗口和布局
        self.parent.parent = Mock()
        self.parent.parent.layout = Mock()
        self.parent.parent.layout().direction = Mock(return_value=None)
    
    def test_error_stats_initialization(self):
        """测试错误统计初始化"""
        stats = self.error_display.get_error_stats()
        for error_type in ErrorType:
            self.assertEqual(stats[error_type], 0)
    
    def test_reset_error_stats(self):
        """测试重置错误统计"""
        # 先触发一个错误
        error = OCRError(ErrorType.OCR_ENGINE, "测试错误")
        self.error_display.handle_error(self.parent, error)
        
        # 检查错误统计
        stats = self.error_display.get_error_stats()
        self.assertEqual(stats[ErrorType.OCR_ENGINE], 1)
        
        # 重置错误统计
        self.error_display.reset_error_stats()
        stats = self.error_display.get_error_stats()
        for error_type in ErrorType:
            self.assertEqual(stats[error_type], 0)
    
    def test_handle_error(self):
        """测试处理错误"""
        error = OCRError(ErrorType.OCR_ENGINE, "测试错误")
        
        # 模拟 InfoBar.error 方法
        with patch('interfaces.fluent.error_ui.InfoBar.error') as mock_error:
            self.error_display.handle_error(self.parent, error)
            
            # 检查 InfoBar.error 被调用
            mock_error.assert_called_once()
            
            # 检查错误统计
            stats = self.error_display.get_error_stats()
            self.assertEqual(stats[ErrorType.OCR_ENGINE], 1)
    
    def test_attempt_recovery(self):
        """测试尝试错误恢复"""
        error = OCRError(ErrorType.OCR_ENGINE, "测试错误")
        
        # 模拟 OCR 引擎初始化
        with patch('core.ocr_engine.get_ocr_engine') as mock_get_engine:
            mock_engine = Mock()
            mock_engine.initialize.return_value = True
            mock_get_engine.return_value = mock_engine
            
            # 模拟 InfoBar.success 方法
            with patch('interfaces.fluent.error_ui.InfoBar.success') as mock_success:
                recovery_success = self.error_display.attempt_recovery(error, self.parent)
                
                # 检查恢复成功
                self.assertTrue(recovery_success)
                # 检查 OCR 引擎初始化被调用
                mock_engine.initialize.assert_called_once()
                # 检查成功信息条被显示
                mock_success.assert_called_once()


class TestErrorHandlerUI(unittest.TestCase):
    """测试界面错误处理器"""
    
    def setUp(self):
        """设置测试环境"""
        self.parent = Mock(spec=QWidget)
        self.error_handler = ErrorHandlerUI(self.parent)
    
    def test_get_error_stats(self):
        """测试获取错误统计"""
        stats = self.error_handler.get_error_stats()
        for error_type in ErrorType:
            self.assertEqual(stats[error_type], 0)
    
    def test_reset_error_stats(self):
        """测试重置错误统计"""
        # 先触发一个错误
        error = OCRError(ErrorType.OCR_ENGINE, "测试错误")
        self.error_handler.handle_ocr_error(error)
        
        # 检查错误统计
        stats = self.error_handler.get_error_stats()
        self.assertEqual(stats[ErrorType.OCR_ENGINE], 1)
        
        # 重置错误统计
        self.error_handler.reset_error_stats()
        stats = self.error_handler.get_error_stats()
        for error_type in ErrorType:
            self.assertEqual(stats[error_type], 0)
    
    def test_handle_ocr_error(self):
        """测试处理 OCR 错误"""
        error = OCRError(ErrorType.OCR_ENGINE, "测试错误")
        
        # 模拟 ErrorUIDisplay.handle_error 方法
        with patch.object(self.error_handler.error_display, 'handle_error') as mock_handle_error:
            self.error_handler.handle_ocr_error(error)
            
            # 检查 handle_error 被调用
            mock_handle_error.assert_called_once_with(self.parent, error)
    
    def test_show_error(self):
        """测试显示错误信息"""
        title = "测试错误"
        message = "测试错误消息"
        
        # 模拟 ErrorUIDisplay.show_error_info_bar 方法
        with patch.object(self.error_handler.error_display, 'show_error_info_bar') as mock_show_error:
            self.error_handler.show_error(title, message)
            
            # 检查 show_error_info_bar 被调用
            mock_show_error.assert_called_once_with(self.parent, title, message)
    
    def test_show_success(self):
        """测试显示成功信息"""
        title = "测试成功"
        message = "测试成功消息"
        
        # 模拟 ErrorUIDisplay.show_success_info_bar 方法
        with patch.object(self.error_handler.error_display, 'show_success_info_bar') as mock_show_success:
            self.error_handler.show_success(title, message)
            
            # 检查 show_success_info_bar 被调用
            mock_show_success.assert_called_once_with(self.parent, title, message)
    
    def test_show_warning(self):
        """测试显示警告信息"""
        title = "测试警告"
        message = "测试警告消息"
        
        # 模拟 ErrorUIDisplay.show_warning_info_bar 方法
        with patch.object(self.error_handler.error_display, 'show_warning_info_bar') as mock_show_warning:
            self.error_handler.show_warning(title, message)
            
            # 检查 show_warning_info_bar 被调用
            mock_show_warning.assert_called_once_with(self.parent, title, message)
    
    def test_confirm(self):
        """测试显示确认对话框"""
        title = "测试确认"
        message = "测试确认消息"
        
        # 模拟 ErrorUIDisplay.show_confirm_dialog 方法
        with patch.object(self.error_handler.error_display, 'show_confirm_dialog') as mock_confirm:
            mock_confirm.return_value = True
            result = self.error_handler.confirm(title, message)
            
            # 检查 show_confirm_dialog 被调用
            mock_confirm.assert_called_once_with(self.parent, title, message)
            # 检查返回值
            self.assertTrue(result)
    
    def test_alert(self):
        """测试显示警告对话框"""
        title = "测试警告"
        message = "测试警告消息"
        
        # 模拟 ErrorUIDisplay.show_message_box 方法
        with patch.object(self.error_handler.error_display, 'show_message_box') as mock_alert:
            self.error_handler.alert(title, message)
            
            # 检查 show_message_box 被调用
            mock_alert.assert_called_once_with(self.parent, title, message)


if __name__ == '__main__':
    unittest.main()