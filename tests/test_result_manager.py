"""
结果管理器单元测试
"""
import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.result_manager import ResultManager, get_result_manager


class TestResultManager:
    """结果管理器测试类"""

    @pytest.fixture
    def temp_history_file(self):
        """创建临时历史记录文件"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump([], f)
            temp_path = f.name
        
        yield temp_path
        
        # 清理
        Path(temp_path).unlink(missing_ok=True)

    @pytest.fixture
    def result_manager(self, temp_history_file):
        """创建结果管理器实例"""
        with patch('core.result_manager.HISTORY_FILE', Path(temp_history_file)):
            # 重置单例
            import core.result_manager
            core.result_manager._result_manager = None
            
            manager = ResultManager(history_file=temp_history_file)
            yield manager
            
            # 清理
            core.result_manager._result_manager = None

    def test_initialization(self, result_manager):
        """测试初始化"""
        assert result_manager.history == []
        assert result_manager.current_results == {}

    def test_add_result_success(self, result_manager):
        """测试添加成功的识别结果"""
        ocr_result = {
            "code": 100,
            "data": [
                {"text": "第一行文本", "score": 0.95},
                {"text": "第二行文本", "score": 0.92}
            ]
        }
        
        entry = result_manager.add_result("test_image.png", ocr_result)
        
        assert entry["success"] is True
        assert entry["filename"] == "test_image.png"
        assert "第一行文本" in entry["text"]
        assert len(result_manager.history) == 1

    def test_add_result_failure(self, result_manager):
        """测试添加失败的识别结果"""
        ocr_result = {
            "code": 200,
            "data": "图片路径不存在"
        }
        
        entry = result_manager.add_result("nonexistent.png", ocr_result)
        
        assert entry["success"] is False
        assert len(result_manager.history) == 1

    def test_get_history(self, result_manager):
        """测试获取历史记录"""
        # 添加多条记录
        for i in range(5):
            result_manager.add_result(f"image_{i}.png", {
                "code": 100,
                "data": [{"text": f"Text {i}", "score": 0.9}]
            })
        
        history = result_manager.get_history()
        assert len(history) == 5
        # 验证从新到旧的顺序
        assert history[0]["filename"] == "image_4.png"

    def test_get_history_with_limit(self, result_manager):
        """测试获取限制数量的历史记录"""
        for i in range(10):
            result_manager.add_result(f"image_{i}.png", {
                "code": 100,
                "data": [{"text": f"Text {i}", "score": 0.9}]
            })
        
        history = result_manager.get_history(limit=3)
        assert len(history) == 3

    def test_delete_history(self, result_manager):
        """测试删除历史记录"""
        for i in range(3):
            result_manager.add_result(f"image_{i}.png", {
                "code": 100,
                "data": [{"text": f"Text {i}", "score": 0.9}]
            })
        
        # 删除第一条（显示顺序，即最新的）
        success = result_manager.delete_history(0)
        assert success is True
        assert len(result_manager.history) == 2

    def test_delete_history_invalid_index(self, result_manager):
        """测试删除无效索引的历史记录"""
        success = result_manager.delete_history(999)
        assert success is False

    def test_clear_history(self, result_manager):
        """测试清空历史记录"""
        for i in range(5):
            result_manager.add_result(f"image_{i}.png", {
                "code": 100,
                "data": [{"text": f"Text {i}", "score": 0.9}]
            })
        
        result_manager.clear_history()
        assert len(result_manager.history) == 0

    def test_get_combined_text(self, result_manager):
        """测试获取合并文本"""
        result_manager.add_result("image1.png", {
            "code": 100,
            "data": [{"text": "Line 1", "score": 0.9}]
        })
        result_manager.add_result("image2.png", {
            "code": 100,
            "data": [{"text": "Line 2", "score": 0.8}]
        })
        
        combined = result_manager.get_combined_text()
        assert "Line 1" in combined
        assert "Line 2" in combined

    def test_format_result_for_display_success(self, result_manager):
        """测试格式化成功的识别结果"""
        ocr_result = {
            "code": 100,
            "data": [
                {"text": "Hello", "score": 0.95},
                {"text": "World", "score": 0.92}
            ]
        }
        
        formatted = result_manager.format_result_for_display(ocr_result)
        
        assert formatted["success"] is True
        assert formatted["count"] == 2
        assert "Hello" in formatted["text"]

    def test_format_result_for_display_failure(self, result_manager):
        """测试格式化失败的识别结果"""
        ocr_result = {
            "code": 200,
            "data": "图片路径不存在"
        }
        
        formatted = result_manager.format_result_for_display(ocr_result)
        
        assert formatted["success"] is False
        assert formatted["error_code"] == 200

    def test_history_storage_limit(self, temp_history_file):
        """测试历史记录存储上限"""
        from core.config import get_config_manager
        config = get_config_manager()
        original_limit = config.get_history_storage_limit()
        
        try:
            # 设置较小的上限
            config.set_history_storage_limit(3)
            
            manager = ResultManager(history_file=temp_history_file)
            
            # 添加超过上限的记录
            for i in range(5):
                manager.add_result(f"image_{i}.png", {
                    "code": 100,
                    "data": [{"text": f"Text {i}", "score": 0.9}]
                })
            
            # 验证只保留了最近的 3 条
            assert len(manager.history) == 3
        finally:
            # 恢复原始限制
            config.set_history_storage_limit(original_limit)


class TestGetResultManager:
    """测试全局结果管理器获取函数"""

    def test_get_result_manager_singleton(self):
        """测试全局结果管理器是单例"""
        import core.result_manager
        core.result_manager._result_manager = None
        
        manager1 = get_result_manager()
        manager2 = get_result_manager()
        assert manager1 is manager2
        
        # 清理
        core.result_manager._result_manager = None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
