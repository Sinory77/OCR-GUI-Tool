"""
OCR服务层
封装现有的OCR核心功能
"""
import os
import sys
from typing import Dict, Any, List
from pathlib import Path

# 添加项目根目录到Python路径，以便导入现有模块
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 为了解决循环导入问题，使用延迟导入
def get_ocr_components():
    """延迟获取OCR组件，避免循环导入"""
    from core.ocr_engine import OCREngine
    from core.config import ConfigManager, get_config_manager
    from core.result_manager import ResultManager
    from core.template_manager import TemplateManager
    from core.exporter import ResultExporter as Exporter
    from core.text_parser import TextParser
    from core.screenshot import ScreenshotManager
    
    # 获取模板管理器
    from core.template_manager import get_template_manager
    template_manager = get_template_manager()
    
    # 获取或创建默认模板
    templates = template_manager.get_all_templates()
    if templates:
        default_template = templates[0]  # 使用第一个模板
    else:
        # 创建一个默认模板
        default_template = template_manager.create_template("默认模板")
    
    config_manager = get_config_manager()
    
    # 从配置管理器获取OCR引擎参数
    exe_path = config_manager.get_ocr_exe_path()
    models_path = config_manager.get_models_path()
    language = config_manager.get_language()
    
    ocr_engine = OCREngine(
        exe_path=exe_path,
        models_path=models_path,
        language=language
    )
    
    return {
        'config_manager': config_manager,
        'ocr_engine': ocr_engine,
        'result_manager': ResultManager(),
        'template_manager': TemplateManager(),
        'exporter': Exporter(),
        'text_parser': TextParser(template=default_template),
        'screenshot_manager': ScreenshotManager()
    }


class OCRService:
    """OCR服务类"""
    
    def __init__(self):
        # 延迟加载组件，避免循环导入
        components = get_ocr_components()
        self.config_manager = components['config_manager']
        self.ocr_engine = components['ocr_engine']
        self.result_manager = components['result_manager']
        self.template_manager = components['template_manager']
        self.exporter = components['exporter']
        self.text_parser = components['text_parser']
        self.screenshot_manager = components['screenshot_manager']
    
    def initialize_engine(self) -> Dict[str, Any]:
        """初始化OCR引擎"""
        try:
            success = self.ocr_engine.initialize()
            if success:
                return {
                    "success": True,
                    "message": "OCR引擎初始化成功",
                    "data": {
                        "engine_initialized": True,
                        "engine_info": self.ocr_engine.get_engine_info()
                    }
                }
            else:
                return {
                    "success": False,
                    "message": "OCR引擎初始化失败",
                    "data": {
                        "engine_initialized": False
                    }
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"初始化引擎失败: {str(e)}",
                "data": None
            }
    
    def recognize_single_image(self, image_path: str) -> Dict[str, Any]:
        """识别单张图片"""
        try:
            # 验证输入
            if not os.path.exists(image_path):
                return {
                    "success": False,
                    "message": f"图片路径不存在: {image_path}",
                    "data": None
                }
            
            # 使用OCR引擎执行识别
            result = self.ocr_engine.recognize(image_path)
            
            # 保存结果到历史记录
            self.result_manager.add_result(image_path, result)
            
            return {
                "success": True,
                "message": "识别成功",
                "data": result
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"识别失败: {str(e)}",
                "data": None
            }
    
    def recognize_batch_images(self, image_paths: List[str]) -> Dict[str, Any]:
        """批量识别图片"""
        try:
            results = []
            success_count = 0
            fail_count = 0
            
            for image_path in image_paths:
                try:
                    if not os.path.exists(image_path):
                        result = {
                            "file_path": image_path,
                            "success": False,
                            "error": "文件不存在",
                            "data": None
                        }
                    else:
                        # 执行单张图片识别
                        ocr_result = self.ocr_engine.recognize(image_path)
                        result = {
                            "file_path": image_path,
                            "success": ocr_result.get("success", False),
                            "error": None if ocr_result.get("success", False) else "OCR识别失败",
                            "data": ocr_result
                        }
                        
                        # 保存到历史记录
                        self.result_manager.add_result(image_path, ocr_result)
                        
                        if ocr_result.get("success", False):
                            success_count += 1
                        else:
                            fail_count += 1
                    
                    results.append(result)
                except Exception as e:
                    result = {
                        "file_path": image_path,
                        "success": False,
                        "error": str(e),
                        "data": None
                    }
                    results.append(result)
                    fail_count += 1
            
            return {
                "success": True,
                "message": f"批量识别完成，成功: {success_count}, 失败: {fail_count}",
                "data": {
                    "results": results,
                    "total": len(image_paths),
                    "success_count": success_count,
                    "fail_count": fail_count
                }
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"批量识别失败: {str(e)}",
                "data": None
            }
    
    def get_config(self) -> Dict[str, Any]:
        """获取配置"""
        try:
            config = self.config_manager.get_all_config()
            return {
                "success": True,
                "message": "获取配置成功",
                "data": config
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"获取配置失败: {str(e)}",
                "data": None
            }
    
    def update_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """更新配置"""
        try:
            for key, value in config_data.items():
                self.config_manager.set(key, value)
            
            return {
                "success": True,
                "message": "更新配置成功",
                "data": self.config_manager.get_all_config()
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"更新配置失败: {str(e)}",
                "data": None
            }
    
    def get_templates(self) -> Dict[str, Any]:
        """获取模板列表"""
        try:
            templates = self.template_manager.get_all_templates()
            return {
                "success": True,
                "message": "获取模板成功",
                "data": templates
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"获取模板失败: {str(e)}",
                "data": None
            }
    
    def export_results(self, export_format: str, output_path: str, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """导出结果"""
        try:
            success = self.exporter.export(export_format, output_path, results)
            if success:
                return {
                    "success": True,
                    "message": f"导出成功: {output_path}",
                    "data": {
                        "output_path": output_path,
                        "format": export_format
                    }
                }
            else:
                return {
                    "success": False,
                    "message": "导出失败",
                    "data": None
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"导出失败: {str(e)}",
                "data": None
            }
    
    def parse_text(self, text: str, template_id: str = None) -> Dict[str, Any]:
        """解析文本"""
        try:
            if template_id:
                parsed_data = self.text_parser.parse_with_template(text, template_id)
            else:
                parsed_data = self.text_parser.parse(text)
            
            return {
                "success": True,
                "message": "文本解析成功",
                "data": parsed_data
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"文本解析失败: {str(e)}",
                "data": None
            }
    
    def take_screenshot(self, region: Dict[str, int] = None) -> Dict[str, Any]:
        """截图"""
        try:
            image_path, width, height = self.screenshot_manager.capture(region=region)
            if image_path:
                return {
                    "success": True,
                    "message": "截图成功",
                    "data": {
                        "image_path": image_path,
                        "width": width,
                        "height": height
                    }
                }
            else:
                return {
                    "success": False,
                    "message": "截图失败",
                    "data": None
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"截图失败: {str(e)}",
                "data": None
            }