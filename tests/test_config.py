"""
配置管理器单元测试
"""
import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# 导入被测试模块
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import ConfigManager, get_config_manager, LANGUAGES


class TestConfigManager:
    """配置管理器测试类"""

    @pytest.fixture
    def temp_config_file(self):
        """创建临时配置文件"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({
                "language": "English",
                "auto_copy": True,
                "confidence_threshold": 75
            }, f)
            temp_path = f.name
        
        yield temp_path
        
        # 清理
        Path(temp_path).unlink(missing_ok=True)

    @pytest.fixture
    def config_manager(self, temp_config_file):
        """创建配置管理器实例"""
        with patch('core.config.CONFIG_FILE', Path(temp_config_file)):
            # 重置单例
            ConfigManager._instance = None
            manager = ConfigManager()
            yield manager
            # 清理
            ConfigManager._instance = None

    def test_singleton_pattern(self):
        """测试单例模式"""
        ConfigManager._instance = None
        manager1 = ConfigManager()
        manager2 = ConfigManager()
        assert manager1 is manager2
        ConfigManager._instance = None

    def test_load_config(self, config_manager):
        """测试加载配置"""
        assert config_manager.get("language") == "English"
        assert config_manager.get("auto_copy") is True
        assert config_manager.get("confidence_threshold") == 75

    def test_get_default_values(self, config_manager):
        """测试获取默认值"""
        # 测试不存在的键返回 None
        assert config_manager.get("nonexistent_key") is None
        
        # 测试不存在的键返回默认值
        assert config_manager.get("nonexistent_key", "default") == "default"

    def test_set_and_save(self, config_manager, temp_config_file):
        """测试设置和保存配置"""
        result = config_manager.set("test_key", "test_value")
        assert result is True
        
        # 重新加载验证
        with open(temp_config_file, 'r', encoding='utf-8') as f:
            saved_data = json.load(f)
        
        assert saved_data["test_key"] == "test_value"

    def test_get_language_valid(self, config_manager):
        """测试获取有效语言"""
        lang = config_manager.get_language()
        assert lang in LANGUAGES

    def test_set_language_invalid(self, config_manager):
        """测试设置无效语言"""
        result = config_manager.set_language("InvalidLanguage")
        assert result is False

    def test_set_confidence_threshold_valid(self, config_manager):
        """测试设置有效的置信度阈值"""
        result = config_manager.set_confidence_threshold(80)
        assert result is True
        assert config_manager.get_confidence_threshold() == 80

    def test_set_confidence_threshold_invalid(self, config_manager):
        """测试设置无效的置信度阈值"""
        # 超出范围
        result = config_manager.set_confidence_threshold(150)
        assert result is False
        
        # 负数
        result = config_manager.set_confidence_threshold(-10)
        assert result is False

    def test_validate_path_safe(self, config_manager):
        """测试路径验证 - 安全路径"""
        from core.config import ROOT_DIR
        safe_path = str(ROOT_DIR / "test.txt")
        # 注意：validate_path 检查路径是否在根目录下，不检查文件是否存在
        assert config_manager.validate_path(safe_path) is True

    def test_validate_path_unsafe(self, config_manager):
        """测试路径验证 - 不安全路径"""
        unsafe_path = "C:\\Windows\\System32\\test.txt"
        assert config_manager.validate_path(unsafe_path) is False


class TestGetConfigManager:
    """测试全局配置管理器获取函数"""

    def test_get_config_manager_singleton(self):
        """测试全局配置管理器是单例"""
        from core.config import _config_manager
        # 重置
        import core.config
        core.config._config_manager = None
        
        manager1 = get_config_manager()
        manager2 = get_config_manager()
        assert manager1 is manager2
        
        # 清理
        core.config._config_manager = None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
