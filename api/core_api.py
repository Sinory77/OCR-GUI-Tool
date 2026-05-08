# -*- coding: utf-8 -*-
"""
统一核心功能API
提供统一的接口供界面层调用，实现核心功能与界面的完全分离
可以选择使用本地API服务或直接调用核心功能
"""

import os
import logging
from typing import Dict, Any, Optional, List, Tuple, TYPE_CHECKING
from pathlib import Path

# 为了解决循环导入问题，使用TYPE_CHECKING
if TYPE_CHECKING:
    from core.enhanced_error_handler import ErrorResult

# 尝试导入API适配器，如果API服务器可用则支持API服务模式
try:
    from api_server.adapter import api_adapter
    API_SERVER_AVAILABLE = True
except ImportError:
    API_SERVER_AVAILABLE = False
    api_adapter = None  # 明确设置为None

# 延迟导入核心模块，以避免循环导入
def _import_core_modules():
    """延迟导入核心模块，避免循环导入"""
    from core.ocr_engine import OCREngine
    from core.config import ConfigManager, get_config_manager
    from core.result_manager import ResultManager
    from core.exporter import ResultExporter
    from core.async_worker import BatchOcrWorker
    from core.enhanced_error_handler import (
        EnhancedError, ErrorResult, ErrorType, ErrorCode, 
        error_handling as enhanced_error_handling, get_error_handler,
        create_ocr_engine_error, create_config_error, create_file_error, create_export_error
    )
    
    # 返回导入的模块
    return {
        'OCREngine': OCREngine,
        'ConfigManager': ConfigManager,
        'get_config_manager': get_config_manager,
        'ResultManager': ResultManager,
        'ResultExporter': ResultExporter,
        'BatchOcrWorker': BatchOcrWorker,
        'EnhancedError': EnhancedError,
        'ErrorResult': ErrorResult,
        'ErrorType': ErrorType,
        'ErrorCode': ErrorCode,
        'enhanced_error_handling': enhanced_error_handling,
        'get_error_handler': get_error_handler,
        'create_ocr_engine_error': create_ocr_engine_error,
        'create_config_error': create_config_error,
        'create_file_error': create_file_error,
        'create_export_error': create_export_error
    }


logger = logging.getLogger(__name__)


class CoreAPI:
    """
    统一核心功能API类
    封装所有核心功能，供界面层调用
    支持API服务模式和直接调用模式
    """
    
    def __init__(self, use_api_service: bool = False):
        """
        初始化核心API
        
        Args:
            use_api_service: 是否使用API服务模式
        """
        self.use_api_service = use_api_service and API_SERVER_AVAILABLE
        
        if self.use_api_service:
            logger.info("Using API service mode")
            self._init_api_service()
        else:
            logger.info("Using direct call mode")
            self._init_direct_call()
    
    def _init_api_service(self):
        """初始化API服务模式"""
        # 使用API适配器
        self.api_adapter = api_adapter
    
    def _init_direct_call(self):
        """初始化直接调用模式"""
        # 延迟导入核心模块
        core_modules = _import_core_modules()
        
        get_config_manager = core_modules['get_config_manager']
        OCREngine = core_modules['OCREngine']
        ResultManager = core_modules['ResultManager']
        ResultExporter = core_modules['ResultExporter']
        BatchOcrWorker = core_modules['BatchOcrWorker']
        get_error_handler = core_modules['get_error_handler']
        
        self.config_manager = get_config_manager()
        
        # 从配置管理器获取OCR引擎参数
        exe_path = self.config_manager.get_ocr_exe_path()
        models_path = self.config_manager.get_models_path()
        language = self.config_manager.get_language()
        
        self.ocr_engine = OCREngine(
            exe_path=exe_path,
            models_path=models_path,
            language=language
        )
        self.result_manager = ResultManager()
        self.result_exporter = ResultExporter()
        self.error_handler = get_error_handler()
        
        # 保存错误处理模块
        self._error_modules = core_modules
        # 保存核心组件，用于按需创建batch_worker
        self._core_components = {
            'ocr_engine': self.ocr_engine,
            'result_manager': self.result_manager
        }
        
        # 验证OCR引擎配置
        if not self.ocr_engine.check_config():
            logger.warning("OCR引擎配置不完整，请先配置引擎路径和模型路径")
    
    # ==================== OCR 识别相关 API ====================
    
    def recognize_single_image(self, image_path: str) -> 'ErrorResult':
        """
        识别单张图片
        
        Args:
            image_path: 图片路径
            
        Returns:
            ErrorResult 包含成功状态和数据或错误信息
        """
        if self.use_api_service:
            # 使用API服务模式
            return self.api_adapter.recognize_single_image(image_path)
        else:
            # 使用直接调用模式
            try:
                # 获取错误处理模块
                error_modules = self._error_modules
                ErrorResult = error_modules['ErrorResult']
                EnhancedError = error_modules['EnhancedError']
                ErrorType = error_modules['ErrorType']
                
                # 验证输入
                if not image_path or not os.path.exists(image_path):
                    error = EnhancedError(
                        type=ErrorType.FILE_ERROR,
                        message="图片路径不存在",
                        details={"file_path": image_path}
                    )
                    return ErrorResult.error_result(error)
                
                # 执行识别
                result = self.ocr_engine.recognize(image_path)
                
                if result.get("success", False):
                    return ErrorResult.success_result(result)
                else:
                    error = EnhancedError(
                        type=ErrorType.OCR_ENGINE_ERROR,
                        message=result.get("message", "OCR识别失败"),
                        details={"file_path": image_path, "raw_result": result}
                    )
                    return ErrorResult.error_result(error)
            except Exception as e:
                error = EnhancedError(
                    type=ErrorType.OCR_ENGINE_ERROR,
                    message=f"识别过程异常: {str(e)}",
                    details={"file_path": image_path, "exception": str(e)}
                )
                return ErrorResult.error_result(error)
    
    def recognize_auto_slice(self, image_path: str, progress_callback=None, is_interrupted=None) -> 'ErrorResult':
        """
        自动识别（支持超长图切片）
        
        Args:
            image_path: 图片路径
            progress_callback: 进度回调函数
            is_interrupted: 中断检查函数
            
        Returns:
            ErrorResult 包含成功状态和数据或错误信息
        """
        try:
            # 获取错误处理模块
            error_modules = self._error_modules
            ErrorResult = error_modules['ErrorResult']
            EnhancedError = error_modules['EnhancedError']
            ErrorType = error_modules['ErrorType']
            create_file_error = error_modules['create_file_error']
            create_ocr_engine_error = error_modules['create_ocr_engine_error']
            
            if not image_path or not os.path.exists(image_path):
                error = create_file_error(f"图片文件不存在: {image_path}", {"file_path": image_path})
                return ErrorResult.error_result(error)
            
            if not self.ocr_engine.check_config():
                error = create_ocr_engine_error("OCR引擎未正确配置，请先配置引擎路径和模型路径")
                return ErrorResult.error_result(error)
            
            # 执行自动识别（支持切片）
            result = self.ocr_engine.recognize_auto(
                image_path, 
                progress_callback=progress_callback,
                is_interrupted=is_interrupted
            )
            
            logger.info(f"自动识别完成: {image_path}")
            return ErrorResult.success_result(result)
            
        except Exception as e:
            logger.error(f"自动识别失败: {str(e)}")
            cancelled = "中断" in str(e) or (is_interrupted and is_interrupted())
            error_details = {"file_path": image_path, "cancelled": cancelled}
            error = create_ocr_engine_error(f"自动识别失败: {str(e)}", error_details)
            return ErrorResult.error_result(error)
    
    def create_batch_worker(self, file_paths: List[str], config: Optional[Dict] = None) -> Any:
        """
        创建批量识别工作线程
        
        Args:
            file_paths: 文件路径列表
            config: 配置参数
            
        Returns:
            批量识别工作线程实例
        """
        if self.use_api_service:
            # 使用API服务模式，返回API适配器的批量识别方法
            return self.api_adapter.recognize_batch_images_async(file_paths)
        else:
            # 使用直接调用模式
            if config is None:
                config = {}
            
            worker = BatchOcrWorker(
                ocr_engine=self.ocr_engine,
                file_paths=file_paths,
                config=config
            )
            
            return worker
    
    def create_api_based_batch_worker(self, file_paths: List[str], config: Optional[Dict] = None):
        """
        创建基于CoreAPI的批量识别工作线程
        
        Args:
            file_paths: 文件路径列表
            config: 配置参数
            
        Returns:
            APIBasedBatchOcrWorker 实例
        """
        if config is None:
            config = {}
        
        from core.async_worker import APIBasedBatchOcrWorker
        worker = APIBasedBatchOcrWorker(
            core_api=self,
            file_paths=file_paths,
            config=config
        )
        
        return worker
    
    # ==================== 配置管理相关 API ====================
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            配置值
        """
        return self.config_manager.get(key, default)
    
    def set_config(self, key: str, value: Any) -> bool:
        """
        设置配置值
        
        Args:
            key: 配置键
            value: 配置值
            
        Returns:
            是否设置成功
        """
        return self.config_manager.set(key, value)
    
    def get_ocr_config(self) -> Dict[str, Any]:
        """
        获取OCR相关配置
        
        Returns:
            OCR配置字典
        """
        return {
            "ocr_exe_path": self.config_manager.get_ocr_exe_path(),
            "models_path": self.config_manager.get_models_path(),
            "language": self.config_manager.get_language(),
            "confidence_threshold": self.config_manager.get_confidence_threshold(),
            "auto_detect": self.config_manager.get_auto_detect(),
            "long_image_mode": self.config_manager.get_long_image_mode(),
            "slice_height": self.config_manager.get_slice_height(),
            "slice_overlap": self.config_manager.get_slice_overlap(),
        }
    
    def set_ocr_config(self, config: Dict[str, Any]) -> bool:
        """
        设置OCR相关配置
        
        Args:
            config: OCR配置字典
            
        Returns:
            是否设置成功
        """
        try:
            # 批量设置配置
            for key, value in config.items():
                if hasattr(self.config_manager, f'set_{key}'):
                    setter = getattr(self.config_manager, f'set_{key}')
                    setter(value)
            
            return True
        except Exception as e:
            logger.error(f"设置OCR配置失败: {str(e)}")
            return False
    
    def check_ocr_config(self) -> bool:
        """
        检查OCR引擎配置是否完整
        
        Returns:
            配置是否完整
        """
        return self.ocr_engine.check_config()
    
    def auto_detect_paths(self) -> Dict[str, Any]:
        """
        自动检测OCR引擎路径
        
        Returns:
            检测结果字典
        """
        return self.config_manager.auto_detect_paths()
    
    # ==================== 结果管理相关 API ====================
    
    def get_history_results(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        获取历史识别结果
        
        Args:
            limit: 限制数量
            
        Returns:
            历史结果列表
        """
        return self.result_manager.get_history(limit)
    
    def get_history_by_date(self, date_str: str) -> List[Dict[str, Any]]:
        """
        按日期获取历史结果

        Args:
            date_str: 日期字符串 (YYYY-MM-DD)

        Returns:
            历史结果列表
        """
        # 过滤出指定日期的历史记录
        all_history = self.result_manager.get_history(limit=None)  # 获取全部
        return [
            item for item in all_history
            if item.get('time', '').startswith(date_str)
        ]
    
    def delete_history_item(self, item_id: str) -> bool:
        """
        删除历史记录项（按显示顺序索引删除）

        Args:
            item_id: 记录ID（此参数已废弃，改为按索引删除）

        Returns:
            是否删除成功
        """
        # item_id 在历史页面中实际传的是显示顺序索引（从新到旧）
        try:
            index = int(item_id) if item_id else -1
            return self.result_manager.delete_history(index)
        except (ValueError, TypeError):
            logger.warning(f"删除历史记录项失败：无效的索引 {item_id}")
            return False
    
    def delete_history_by_index(self, index: int) -> bool:
        """
        按索引删除历史记录（显示顺序索引，从新到旧）

        Args:
            index: 显示顺序索引（0 = 最新）

        Returns:
            是否删除成功
        """
        return self.result_manager.delete_history(index)
    
    def clear_all_history(self) -> bool:
        """
        清空所有历史记录
        
        Returns:
            是否清空成功
        """
        return self.result_manager.clear_all()
    
    def export_history(self, export_format: str, file_path: str) -> 'ErrorResult':
        """
        导出历史记录
        
        Args:
            export_format: 导出格式 ("TXT", "JSON", "Excel")
            file_path: 输出文件路径
            
        Returns:
            ErrorResult 包含成功状态和数据或错误信息
        """
        try:
            # 获取错误处理模块
            error_modules = self._error_modules
            ErrorResult = error_modules['ErrorResult']
            create_export_error = error_modules['create_export_error']
            
            # 验证导出格式
            supported_formats = ["TXT", "JSON", "Excel", "CSV"]
            if export_format.upper() not in supported_formats:
                error = create_export_error(f"不支持的导出格式: {export_format}", {"format": export_format})
                return ErrorResult.error_result(error)
            
            # 验证输出路径
            output_dir = os.path.dirname(file_path)
            if output_dir and not os.path.exists(output_dir):
                error = create_export_error(f"输出目录不存在: {output_dir}", {"output_path": file_path})
                return ErrorResult.error_result(error)
            
            history_items = self.result_manager.get_history(limit=None)
            exporter = ResultExporter()
            exporter.load_from_history(history_items)
            success = exporter.export(export_format, file_path)
            
            if success:
                logger.info(f"历史记录导出成功: {file_path}")
                return ErrorResult.success_result({"export_path": file_path, "format": export_format})
            else:
                error = create_export_error("导出失败，可能是文件写入权限问题", {"output_path": file_path})
                return ErrorResult.error_result(error)
                
        except Exception as e:
            logger.error(f"导出历史记录失败: {str(e)}")
            error = create_export_error(f"导出历史记录失败: {str(e)}", {"output_path": file_path})
            return ErrorResult.error_result(error)
    
    def export_batch_results(self, batch_results: List[Dict], export_format: str, file_path: str) -> 'ErrorResult':
        """
        导出批量识别结果
        
        Args:
            batch_results: 批量识别结果列表
            export_format: 导出格式 ("TXT", "JSON", "Excel")
            file_path: 输出文件路径
            
        Returns:
            ErrorResult 包含成功状态和数据或错误信息
        """
        if self.use_api_service:
            # 使用API服务模式
            return self.api_adapter.export_results(export_format, file_path, batch_results)
        else:
            # 使用直接调用模式
            try:
                # 获取错误处理模块
                error_modules = self._error_modules
                ErrorResult = error_modules['ErrorResult']
                create_export_error = error_modules['create_export_error']
                
                # 验证导出格式
                supported_formats = ["TXT", "JSON", "Excel", "CSV"]
                if export_format.upper() not in supported_formats:
                    error = create_export_error(f"不支持的导出格式: {export_format}", {"format": export_format})
                    return ErrorResult.error_result(error)
                
                # 验证输出路径
                output_dir = os.path.dirname(file_path)
                if output_dir and not os.path.exists(output_dir):
                    error = create_export_error(f"输出目录不存在: {output_dir}", {"output_path": file_path})
                    return ErrorResult.error_result(error)
                
                # 从批量结果中提取实际的识别结果
                results_for_export = []
                for item in batch_results:
                    result = item.get('result', {})
                    if result:
                        # 构造导出所需的数据格式
                        export_item = {
                            'file_path': item.get('file_path', ''),
                            'result': result,
                            'texts': result.get('texts', []),
                            'boxes': result.get('boxes', []),
                            'code': result.get('code', 100),
                            'time': item.get('time', '')  # 如果有时间信息
                        }
                        results_for_export.append(export_item)
                
                exporter = ResultExporter(results_for_export)
                success = exporter.export(export_format, file_path)
                
                if success:
                    logger.info(f"批量结果导出成功: {file_path}")
                    return ErrorResult.success_result({"export_path": file_path, "format": export_format})
                else:
                    error = create_export_error("导出失败，可能是文件写入权限问题", {"output_path": file_path})
                    return ErrorResult.error_result(error)
                    
            except Exception as e:
                logger.error(f"导出批量结果失败: {str(e)}")
                error = create_export_error(f"导出批量结果失败: {str(e)}", {"output_path": file_path})
                return ErrorResult.error_result(error)
    
    # ==================== 文件处理相关 API ====================
    
    def validate_image_file(self, file_path: str) -> Tuple[bool, str]:
        """
        验证图片文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            (是否有效, 错误信息)
        """
        if not os.path.exists(file_path):
            return False, "文件不存在"
        
        if not os.path.isfile(file_path):
            return False, "路径不是文件"
        
        # 检查文件扩展名
        valid_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp', '.tiff', '.tif'}
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in valid_extensions:
            return False, f"不支持的文件格式: {ext}"
        
        # 检查文件大小（限制在100MB以内）
        file_size = os.path.getsize(file_path)
        if file_size > 100 * 1024 * 1024:  # 100MB
            return False, "文件过大（超过100MB）"
        
        return True, ""
    
    def scan_directory_images(self, directory: str, recursive: bool = True) -> List[str]:
        """
        扫描目录中的图片文件
        
        Args:
            directory: 目录路径
            recursive: 是否递归扫描子目录
            
        Returns:
            图片文件路径列表
        """
        if not os.path.exists(directory) or not os.path.isdir(directory):
            return []
        
        image_files = []
        valid_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp', '.tiff', '.tif'}
        
        if recursive:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if os.path.splitext(file)[1].lower() in valid_extensions:
                        image_files.append(os.path.join(root, file))
        else:
            for file in os.listdir(directory):
                file_path = os.path.join(directory, file)
                if os.path.isfile(file_path) and os.path.splitext(file)[1].lower() in valid_extensions:
                    image_files.append(file_path)
        
        return sorted(image_files)
    
    # ==================== 系统相关 API ====================
    
    def update_ocr_language(self, language: str) -> bool:
        """
        更新OCR引擎语言设置
        
        Args:
            language: 语言设置
            
        Returns:
            是否更新成功
        """
        try:
            # 更新配置
            self.config_manager.set_language(language)
            
            # 如果引擎已初始化，尝试更新引擎语言设置
            if self.ocr_engine._initialized:
                # 重新初始化引擎以应用新语言设置
                self.ocr_engine.cleanup()
                self.ocr_engine.initialize()
            
            return True
        except Exception as e:
            logger.error(f"更新OCR语言设置失败: {str(e)}")
            return False

    def get_system_info(self) -> Dict[str, Any]:
        """
        获取系统信息
        
        Returns:
            系统信息字典
        """
        import platform
        import psutil
        
        return {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_count": psutil.cpu_count(),
            "memory_total": psutil.virtual_memory().total,
            "memory_available": psutil.virtual_memory().available,
            "disk_usage": psutil.disk_usage('.').percent,
            "ocr_engine_available": self.ocr_engine.check_config(),
        }
    
    def cleanup_resources(self):
        """
        清理资源
        """
        # 清理资源
        if hasattr(self.ocr_engine, 'cleanup'):
            self.ocr_engine.cleanup()
        
        # 清理结果管理器资源
        self.result_manager.save_history()  # 保存当前结果
    
    def recognize_single_image_async(self, image_path: str, progress_callback=None, is_interrupted=None) -> 'ErrorResult':
        """
        异步识别单张图片（适用于工作线程）
        
        Args:
            image_path: 图片路径
            progress_callback: 进度回调函数
            is_interrupted: 中断检查函数
            
        Returns:
            ErrorResult 包含成功状态和数据或错误信息
        """
        if self.use_api_service:
            # 使用API服务模式
            return self.api_adapter.recognize_single_image_async(image_path)
        else:
            # 使用直接调用模式
            try:
                # 获取错误处理模块
                error_modules = self._error_modules
                ErrorResult = error_modules['ErrorResult']
                create_file_error = error_modules['create_file_error']
                create_ocr_engine_error = error_modules['create_ocr_engine_error']
                
                # 验证输入参数
                if not image_path or not os.path.exists(image_path):
                    error = create_file_error(f"图片文件不存在: {image_path}", {"file_path": image_path})
                    return ErrorResult.error_result(error)
                
                if not self.ocr_engine.check_config():
                    error = create_ocr_engine_error("OCR引擎未正确配置，请先配置引擎路径和模型路径")
                    return ErrorResult.error_result(error)
                
                # 执行识别（使用 recognize_auto 支持超长图切片，传入 config_manager 读取切片参数）
                result = self.ocr_engine.recognize_auto(
                    image_path,
                    config=self.config_manager,
                    progress_callback=progress_callback,
                    is_interrupted=is_interrupted
                )
                
                logger.info(f"单图异步识别完成: {image_path}")
                return ErrorResult.success_result(result)
                
            except Exception as e:
                logger.error(f"单图异步识别失败: {str(e)}")
                error = create_ocr_engine_error(f"单图异步识别失败: {str(e)}", {"file_path": image_path})
                return ErrorResult.error_result(error)


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