"""
API客户端 - 用于UI层调用API服务
"""
import requests
from typing import Dict, Any, List, Optional
import time
from .tasks.task_manager import TaskStatus


class APIClient:
    """API客户端"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """发送HTTP请求"""
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.request(method, url, timeout=30, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "code": 500,
                "message": f"Request failed: {str(e)}",
                "data": None
            }
    
    def initialize_ocr(self) -> Dict[str, Any]:
        """初始化OCR引擎"""
        return self._make_request("POST", "/ocr/initialize")
    
    def recognize_single(self, image_path: str) -> Dict[str, Any]:
        """同步识别单张图片"""
        return self._make_request("POST", "/ocr/recognize/single", json={"image_path": image_path})
    
    def recognize_single_async(self, image_path: str) -> Dict[str, Any]:
        """异步识别单张图片"""
        return self._make_request("POST", "/ocr/recognize/single_async", json={"image_path": image_path})
    
    def recognize_batch(self, image_paths: List[str]) -> Dict[str, Any]:
        """同步批量识别"""
        return self._make_request("POST", "/ocr/recognize/batch", json={"image_paths": image_paths})
    
    def recognize_batch_async(self, image_paths: List[str]) -> Dict[str, Any]:
        """异步批量识别"""
        return self._make_request("POST", "/ocr/recognize/batch_async", json={"image_paths": image_paths})
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        return self._make_request("GET", f"/task/{task_id}")
    
    def wait_for_task_completion(self, task_id: str, timeout: int = 300, interval: float = 1.0) -> Dict[str, Any]:
        """等待任务完成"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status_response = self.get_task_status(task_id)
            
            if not status_response.get("success"):
                return status_response
            
            task_data = status_response.get("data", {})
            status = task_data.get("status")
            
            if status == TaskStatus.COMPLETED.value:
                return {
                    "success": True,
                    "data": task_data.get("result"),
                    "message": "Task completed successfully"
                }
            elif status == TaskStatus.FAILED.value:
                return {
                    "success": False,
                    "data": None,
                    "message": f"Task failed: {task_data.get('error', 'Unknown error')}"
                }
            elif status == TaskStatus.CANCELLED.value:
                return {
                    "success": False,
                    "data": None,
                    "message": "Task was cancelled"
                }
            
            time.sleep(interval)
        
        return {
            "success": False,
            "data": None,
            "message": f"Task {task_id} timed out after {timeout} seconds"
        }
    
    def get_config(self) -> Dict[str, Any]:
        """获取配置"""
        return self._make_request("GET", "/ocr/config")
    
    def update_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """更新配置"""
        return self._make_request("POST", "/ocr/config", json=config_data)
    
    def get_templates(self) -> Dict[str, Any]:
        """获取模板"""
        return self._make_request("GET", "/ocr/templates")
    
    def export_results(self, export_format: str, output_path: str, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """导出结果"""
        return self._make_request("POST", "/ocr/export", json={
            "export_format": export_format,
            "output_path": output_path,
            "results": results
        })
    
    def parse_text(self, text: str, template_id: str = None) -> Dict[str, Any]:
        """解析文本"""
        return self._make_request("POST", "/ocr/parse_text", json={
            "text": text,
            "template_id": template_id
        })
    
    def take_screenshot(self, region: Dict[str, int] = None) -> Dict[str, Any]:
        """截图"""
        return self._make_request("POST", "/ocr/screenshot", json={"region": region})


# 全局API客户端实例
api_client = APIClient()