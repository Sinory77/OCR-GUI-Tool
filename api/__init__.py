"""
统一核心功能API
提供统一的接口供界面层调用
"""

from .core_api import CoreAPI

# 全局API实例
_global_api_instance = None


def get_core_api(use_api_service: bool = False) -> CoreAPI:
    """
    获取核心API实例
    
    Args:
        use_api_service: 是否使用API服务模式
        
    Returns:
        CoreAPI实例
    """
    global _global_api_instance
    if _global_api_instance is None:
        _global_api_instance = CoreAPI(use_api_service=use_api_service)
    return _global_api_instance


__all__ = ['CoreAPI', 'get_core_api']