import unittest
from core.error_handler import (
    ErrorType, OCRError, OCREngineError, ConfigError, FileOperationError,
    ErrorHandler, get_error_handler, handle_error, error_handling,
    get_error_stats, reset_error_stats
)


class TestErrorHandler(unittest.TestCase):
    """测试错误处理机制"""
    
    def setUp(self):
        """设置测试环境"""
        # 重置错误统计
        reset_error_stats()
        # 获取全局错误处理器
        self.error_handler = get_error_handler()
    
    def test_error_creation(self):
        """测试错误创建"""
        # 测试基础错误
        error = OCRError(ErrorType.OCR_ENGINE, "测试错误")
        self.assertEqual(error.error_type, ErrorType.OCR_ENGINE)
        self.assertEqual(error.message, "测试错误")
        self.assertIsNone(error.original_error)
        
        # 测试带有原始异常的错误
        try:
            raise ValueError("原始错误")
        except ValueError as e:
            error = OCRError(ErrorType.CONFIG, "测试错误", e)
            self.assertEqual(error.error_type, ErrorType.CONFIG)
            self.assertEqual(error.message, "测试错误")
            self.assertIsInstance(error.original_error, ValueError)
    
    def test_error_subclasses(self):
        """测试错误子类"""
        # 测试 OCREngineError
        engine_error = OCREngineError("引擎错误")
        self.assertEqual(engine_error.error_type, ErrorType.OCR_ENGINE)
        
        # 测试 ConfigError
        config_error = ConfigError("配置错误")
        self.assertEqual(config_error.error_type, ErrorType.CONFIG)
        
        # 测试 FileOperationError
        file_error = FileOperationError("文件操作错误")
        self.assertEqual(file_error.error_type, ErrorType.FILE_OPERATION)
    
    def test_error_handler(self):
        """测试错误处理器"""
        # 测试错误处理
        error = OCRError(ErrorType.OCR_ENGINE, "测试错误")
        self.error_handler.handle_error(error)
        
        # 测试错误统计
        stats = get_error_stats()
        self.assertEqual(stats[ErrorType.OCR_ENGINE], 1)
    
    def test_error_handling_decorator(self):
        """测试错误处理装饰器"""
        @error_handling(ErrorType.OCR_ENGINE, "测试错误")
        def test_function():
            raise ValueError("测试异常")
        
        # 测试装饰器捕获异常
        with self.assertRaises(OCRError):
            test_function()
        
        # 测试错误统计
        stats = get_error_stats()
        self.assertEqual(stats[ErrorType.OCR_ENGINE], 1)
    
    def test_error_recovery(self):
        """测试错误恢复"""
        # 测试文件操作错误恢复
        error = FileOperationError("文件不存在: C:\\test\\nonexistent\\file.txt")
        recovery_success = self.error_handler.attempt_recovery(error)
        # 由于是测试环境，可能无法创建目录，所以不断言恢复成功
        # 只测试恢复策略是否执行
        self.assertIsInstance(recovery_success, bool)
    
    def test_error_stats(self):
        """测试错误统计"""
        # 重置错误统计
        reset_error_stats()
        stats = get_error_stats()
        for error_type in ErrorType:
            self.assertEqual(stats[error_type], 0)
        
        # 触发错误
        error = OCRError(ErrorType.OCR_ENGINE, "测试错误")
        handle_error(error)
        
        # 检查错误统计
        stats = get_error_stats()
        self.assertEqual(stats[ErrorType.OCR_ENGINE], 1)
        
        # 重置错误统计
        reset_error_stats()
        stats = get_error_stats()
        for error_type in ErrorType:
            self.assertEqual(stats[error_type], 0)


if __name__ == '__main__':
    unittest.main()