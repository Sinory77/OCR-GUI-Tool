# -*- coding: utf-8 -*-
"""界面配置管理器 - 管理界面相关的配置

此模块专门处理界面层的配置，与核心业务逻辑配置分离
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

# 配置日志
logger = logging.getLogger(__name__)

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent.parent.resolve()

# 界面配置文件路径
UI_CONFIG_FILE = ROOT_DIR / "config" / "ui_config.json"


class UIConfigManager:
    """界面配置管理器 - 专门管理界面相关的配置
    
    该类负责：
    1. 加载和保存界面配置文件
    2. 提供界面配置的获取和设置方法
    3. 管理界面语言、主题、自动复制等界面相关设置
    """

    _instance: Optional['UIConfigManager'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._config_file = UI_CONFIG_FILE
        self._data = self._load()

    def _load(self) -> Dict[str, Any]:
        """加载界面配置文件
        
        Returns:
            配置字典，如果加载失败则返回默认配置
        """
        if self._config_file.exists():
            try:
                with open(self._config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    logger.info(f"成功加载界面配置文件: {self._config_file}")
                    return config
            except json.JSONDecodeError as e:
                logger.error(f"界面配置文件格式错误: {str(e)}")
            except Exception as e:
                logger.error(f"加载界面配置文件失败: {str(e)}")
        
        return self._get_defaults()

    def _get_defaults(self) -> Dict[str, Any]:
        """获取默认界面配置
        
        Returns:
            默认配置字典
        """
        return {
            "ui_language": "中文",
            "auto_copy": False,
            "theme": "跟随系统",
            "last_export_format": "TXT",  # 记住上次导出格式
            "export_include_original_text": True,  # 导出时是否包含原始文本
        }

    def save(self) -> bool:
        """保存界面配置到文件
        
        Returns:
            是否保存成功
        """
        try:
            # 确保配置目录存在
            self._config_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 确保配置数据中没有不可序列化的对象
            serializable_data = {}
            for key, value in self._data.items():
                # 检查value是否可序列化
                if isinstance(value, (str, int, float, bool, list, dict, type(None))):
                    serializable_data[key] = value
                else:
                    # 尝试转换为字符串
                    try:
                        serializable_data[key] = str(value)
                    except:
                        logger.warning(f"配置项 {key} 无法序列化，跳过保存")
                        continue

            with open(self._config_file, 'w', encoding='utf-8') as f:
                json.dump(serializable_data, f, ensure_ascii=False, indent=4)
            
            logger.info(f"成功保存界面配置到: {self._config_file}")
            return True
        except Exception as e:
            logger.error(f"保存界面配置失败: {str(e)}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            配置值，如果不存在则返回默认值
        """
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> bool:
        """设置配置值并保存
        
        Args:
            key: 配置键
            value: 配置值
            
        Returns:
            是否设置成功
        """
        old_value = self._data.get(key)
        self._data[key] = value
        
        # 保存配置
        success = self.save()
        if success:
            logger.info(f"配置项 {key} 从 '{old_value}' 更新为 '{value}'")
        else:
            # 如果保存失败，回滚更改
            if old_value is None:
                self._data.pop(key, None)
            else:
                self._data[key] = old_value
        
        return success

    def get_ui_language(self) -> str:
        """获取界面语言
        
        Returns:
            界面语言
        """
        return self.get("ui_language", "中文")
    
    def set_ui_language(self, language: str) -> bool:
        """设置界面语言
        
        Args:
            language: 界面语言
            
        Returns:
            是否保存成功
        """
        return self.set("ui_language", language)

    def get_auto_copy(self) -> bool:
        """获取自动复制设置
        
        Returns:
            是否启用自动复制
        """
        return self.get("auto_copy", False)

    def set_auto_copy(self, enabled: bool) -> bool:
        """设置自动复制
        
        Args:
            enabled: 是否启用自动复制
            
        Returns:
            是否保存成功
        """
        return self.set("auto_copy", bool(enabled))

    def get_theme(self) -> str:
        """获取主题设置
        
        Returns:
            主题名称
        """
        return self.get("theme", "跟随系统")
    
    def set_theme(self, theme: str) -> bool:
        """设置主题
        
        Args:
            theme: 主题名称
            
        Returns:
            是否保存成功
        """
        return self.set("theme", theme)
    
    def get_last_export_format(self) -> str:
        """获取上次导出格式
        
        Returns:
            导出格式（"TXT", "JSON", "Excel"）
        """
        return self.get("last_export_format", "TXT")
    
    def set_last_export_format(self, format: str) -> bool:
        """设置上次导出格式
        
        Args:
            format: 导出格式（"TXT", "JSON", "Excel"）
            
        Returns:
            是否保存成功
        """
        return self.set("last_export_format", format.upper())
    
    def get_export_include_original_text(self) -> bool:
        """获取导出时是否包含原始文本
        
        Returns:
            是否包含原始文本
        """
        return self.get("export_include_original_text", True)
    
    def set_export_include_original_text(self, enabled: bool) -> bool:
        """设置导出时是否包含原始文本
        
        Args:
            enabled: 是否包含原始文本
            
        Returns:
            是否保存成功
        """
        return self.set("export_include_original_text", enabled)