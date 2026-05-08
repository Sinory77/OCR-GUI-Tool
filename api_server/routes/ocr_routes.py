"""
OCR相关API路由
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
from ..tasks.task_manager import task_manager
from ..services.ocr_service import OCRService
from ..utils.response import APIResponse, format_task_result

router = APIRouter(prefix="/ocr", tags=["ocr"])

# 创建OCR服务实例
ocr_service = OCRService()


@router.post("/initialize")
async def initialize_ocr() -> Dict[str, Any]:
    """初始化OCR引擎"""
    result = ocr_service.initialize_engine()
    return result


@router.post("/recognize/single")
async def recognize_single(image_path: str) -> Dict[str, Any]:
    """识别单张图片"""
    result = ocr_service.recognize_single_image(image_path)
    return result


@router.post("/recognize/single_async")
async def recognize_single_async(image_path: str) -> Dict[str, Any]:
    """异步识别单张图片"""
    task_id = task_manager.submit_task(ocr_service.recognize_single_image, image_path)
    return APIResponse.task_response(task_id, "Single image recognition task submitted")


@router.post("/recognize/batch")
async def recognize_batch(image_paths: List[str]) -> Dict[str, Any]:
    """批量识别图片"""
    result = ocr_service.recognize_batch_images(image_paths)
    return result


@router.post("/recognize/batch_async")
async def recognize_batch_async(image_paths: List[str]) -> Dict[str, Any]:
    """异步批量识别图片"""
    task_id = task_manager.submit_task(ocr_service.recognize_batch_images, image_paths)
    return APIResponse.task_response(task_id, "Batch recognition task submitted")


@router.get("/config")
async def get_config() -> Dict[str, Any]:
    """获取配置"""
    result = ocr_service.get_config()
    return result


@router.post("/config")
async def update_config(config_data: Dict[str, Any]) -> Dict[str, Any]:
    """更新配置"""
    result = ocr_service.update_config(config_data)
    return result


@router.get("/templates")
async def get_templates() -> Dict[str, Any]:
    """获取模板"""
    result = ocr_service.get_templates()
    return result


@router.post("/export")
async def export_results(export_format: str, output_path: str, results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """导出结果"""
    result = ocr_service.export_results(export_format, output_path, results)
    return result


@router.post("/parse_text")
async def parse_text(text: str, template_id: str = None) -> Dict[str, Any]:
    """解析文本"""
    result = ocr_service.parse_text(text, template_id)
    return result


@router.post("/screenshot")
async def take_screenshot(region: Dict[str, int] = None) -> Dict[str, Any]:
    """截图"""
    result = ocr_service.take_screenshot(region)
    return result