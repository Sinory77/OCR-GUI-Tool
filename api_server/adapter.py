"""
API适配器 - 为现有UI提供兼容接口
"""
from typing import Dict, Any, List
from pathlib import Path
import sys

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from api_server.client import api_client
from core.enhanced_error_handler import ErrorResult, EnhancedError, ErrorType


class APIAdapter:
    """
    API适配器 - 为现有UI层提供兼容的接口
    这个适配器将新的API调用转换为旧的同步接口，以便与现有UI代码兼容
    """
    
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.client = api_client
        self.client.base_url = base_url
    
    def initialize_ocr_engine(self) -> ErrorResult:
        """初始化OCR引擎"""
        try:
            response = self.client.initialize_ocr()
            if response.get("success"):
                return ErrorResult.success_result(response.get("data"))
            else:
                error = EnhancedError(
                    type=ErrorType.OCR_ENGINE_ERROR,
                    message=response.get("message", "初始化OCR引擎失败"),
                    details=response.get("data")
                )
                return ErrorResult.error_result(error)
        except Exception as e:
            error = EnhancedError(
                type=ErrorType.OCR_ENGINE_ERROR,
                message=f"初始化OCR引擎异常: {str(e)}"
            )
            return ErrorResult.error_result(error)
    
    def recognize_single_image(self, image_path: str) -> ErrorResult:
        """识别单张图片（同步）"""
        try:
            response = self.client.recognize_single(image_path)
            if response.get("success"):
                return ErrorResult.success_result(response.get("data"))
            else:
                error = EnhancedError(
                    type=ErrorType.OCR_ENGINE_ERROR,
                    message=response.get("message", "单图识别失败"),
                    details={"file_path": image_path}
                )
                return ErrorResult.error_result(error)
        except Exception as e:
            error = EnhancedError(
                type=ErrorType.OCR_ENGINE_ERROR,
                message=f"单图识别异常: {str(e)}",
                details={"file_path": image_path}
            )
            return ErrorResult.error_result(error)
    
    def recognize_single_image_async(self, image_path: str) -> ErrorResult:
        """异步识别单张图片"""
        try:
            response = self.client.recognize_single_async(image_path)
            if response.get("success"):
                task_id = response.get("data", {}).get("task_id")
                return ErrorResult.success_result({
                    "task_id": task_id,
                    "async": True
                })
            else:
                error = EnhancedError(
                    type=ErrorType.OCR_ENGINE_ERROR,
                    message=response.get("message", "异步单图识别提交失败"),
                    details={"file_path": image_path}
                )
                return ErrorResult.error_result(error)
        except Exception as e:
            error = EnhancedError(
                type=ErrorType.OCR_ENGINE_ERROR,
                message=f"异步单图识别提交异常: {str(e)}",
                details={"file_path": image_path}
            )
            return ErrorResult.error_result(error)
    
    def recognize_batch_images(self, image_paths: List[str]) -> ErrorResult:
        """批量识别图片（同步）"""
        try:
            response = self.client.recognize_batch(image_paths)
            if response.get("success"):
                return ErrorResult.success_result(response.get("data"))
            else:
                error = EnhancedError(
                    type=ErrorType.OCR_ENGINE_ERROR,
                    message=response.get("message", "批量识别失败"),
                    details={"file_count": len(image_paths)}
                )
                return ErrorResult.error_result(error)
        except Exception as e:
            error = EnhancedError(
                type=ErrorType.OCR_ENGINE_ERROR,
                message=f"批量识别异常: {str(e)}",
                details={"file_count": len(image_paths)}
            )
            return ErrorResult.error_result(error)
    
    def recognize_batch_images_async(self, image_paths: List[str]) -> ErrorResult:
        """异步批量识别图片"""
        try:
            response = self.client.recognize_batch_async(image_paths)
            if response.get("success"):
                task_id = response.get("data", {}).get("task_id")
                return ErrorResult.success_result({
                    "task_id": task_id,
                    "async": True
                })
            else:
                error = EnhancedError(
                    type=ErrorType.OCR_ENGINE_ERROR,
                    message=response.get("message", "异步批量识别提交失败"),
                    details={"file_count": len(image_paths)}
                )
                return ErrorResult.error_result(error)
        except Exception as e:
            error = EnhancedError(
                type=ErrorType.OCR_ENGINE_ERROR,
                message=f"异步批量识别提交异常: {str(e)}",
                details={"file_count": len(image_paths)}
            )
            return ErrorResult.error_result(error)
    
    def get_config(self) -> ErrorResult:
        """获取配置"""
        try:
            response = self.client.get_config()
            if response.get("success"):
                return ErrorResult.success_result(response.get("data"))
            else:
                error = EnhancedError(
                    type=ErrorType.CONFIG_ERROR,
                    message=response.get("message", "获取配置失败")
                )
                return ErrorResult.error_result(error)
        except Exception as e:
            error = EnhancedError(
                type=ErrorType.CONFIG_ERROR,
                message=f"获取配置异常: {str(e)}"
            )
            return ErrorResult.error_result(error)
    
    def update_config(self, config_data: Dict[str, Any]) -> ErrorResult:
        """更新配置"""
        try:
            response = self.client.update_config(config_data)
            if response.get("success"):
                return ErrorResult.success_result(response.get("data"))
            else:
                error = EnhancedError(
                    type=ErrorType.CONFIG_ERROR,
                    message=response.get("message", "更新配置失败")
                )
                return ErrorResult.error_result(error)
        except Exception as e:
            error = EnhancedError(
                type=ErrorType.CONFIG_ERROR,
                message=f"更新配置异常: {str(e)}"
            )
            return ErrorResult.error_result(error)
    
    def get_templates(self) -> ErrorResult:
        """获取模板"""
        try:
            response = self.client.get_templates()
            if response.get("success"):
                return ErrorResult.success_result(response.get("data"))
            else:
                error = EnhancedError(
                    type=ErrorType.TEMPLATE_ERROR,
                    message=response.get("message", "获取模板失败")
                )
                return ErrorResult.error_result(error)
        except Exception as e:
            error = EnhancedError(
                type=ErrorType.TEMPLATE_ERROR,
                message=f"获取模板异常: {str(e)}"
            )
            return ErrorResult.error_result(error)
    
    def export_results(self, export_format: str, output_path: str, results: List[Dict[str, Any]]) -> ErrorResult:
        """导出结果"""
        try:
            response = self.client.export_results(export_format, output_path, results)
            if response.get("success"):
                return ErrorResult.success_result(response.get("data"))
            else:
                error = EnhancedError(
                    type=ErrorType.EXPORT_ERROR,
                    message=response.get("message", "导出结果失败"),
                    details={"format": export_format, "output_path": output_path}
                )
                return ErrorResult.error_result(error)
        except Exception as e:
            error = EnhancedError(
                type=ErrorType.EXPORT_ERROR,
                message=f"导出结果异常: {str(e)}",
                details={"format": export_format, "output_path": output_path}
            )
            return ErrorResult.error_result(error)
    
    def parse_text(self, text: str, template_id: str = None) -> ErrorResult:
        """解析文本"""
        try:
            response = self.client.parse_text(text, template_id)
            if response.get("success"):
                return ErrorResult.success_result(response.get("data"))
            else:
                error = EnhancedError(
                    type=ErrorType.TEXT_PARSE_ERROR,
                    message=response.get("message", "文本解析失败"),
                    details={"template_id": template_id}
                )
                return ErrorResult.error_result(error)
        except Exception as e:
            error = EnhancedError(
                type=ErrorType.TEXT_PARSE_ERROR,
                message=f"文本解析异常: {str(e)}",
                details={"template_id": template_id}
            )
            return ErrorResult.error_result(error)
    
    def take_screenshot(self, region: Dict[str, int] = None) -> ErrorResult:
        """截图"""
        try:
            response = self.client.take_screenshot(region)
            if response.get("success"):
                return ErrorResult.success_result(response.get("data"))
            else:
                error = EnhancedError(
                    type=ErrorType.SCREENSHOT_ERROR,
                    message=response.get("message", "截图失败")
                )
                return ErrorResult.error_result(error)
        except Exception as e:
            error = EnhancedError(
                type=ErrorType.SCREENSHOT_ERROR,
                message=f"截图异常: {str(e)}"
            )
            return ErrorResult.error_result(error)


# 全局API适配器实例
api_adapter = APIAdapter()