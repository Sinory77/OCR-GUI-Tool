"""
导出器单元测试
"""
import pytest
import json
import tempfile
import os
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.exporter import ResultExporter, get_exporter


class TestResultExporter:
    """结果导出器测试类"""

    @pytest.fixture
    def exporter(self):
        """创建导出器实例"""
        return ResultExporter()

    @pytest.fixture
    def sample_ocr_result(self):
        """示例 OCR 识别结果"""
        return {
            "code": 100,
            "data": [
                {"text": "第一行文本", "score": 0.95, "box": [[0, 0], [100, 0], [100, 20], [0, 20]]},
                {"text": "第二行文本", "score": 0.92, "box": [[0, 30], [100, 30], [100, 50], [0, 50]]}
            ]
        }

    @pytest.fixture
    def temp_output_dir(self):
        """创建临时输出目录"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    def test_add_result(self, exporter, sample_ocr_result):
        """测试添加识别结果"""
        exporter.add_result("test.png", sample_ocr_result)
        
        assert len(exporter.results) == 1
        assert len(exporter.image_paths) == 1
        assert exporter.image_paths[0] == "test.png"

    def test_clear(self, exporter, sample_ocr_result):
        """测试清空结果"""
        exporter.add_result("test.png", sample_ocr_result)
        exporter.clear()
        
        assert len(exporter.results) == 0
        assert len(exporter.image_paths) == 0

    def test_export_txt(self, exporter, sample_ocr_result, temp_output_dir):
        """测试导出为 TXT"""
        exporter.add_result("test.png", sample_ocr_result)
        
        output_file = os.path.join(temp_output_dir, "test.txt")
        result_path = exporter.export_txt(output_file)
        
        assert result_path == output_file
        assert Path(output_file).exists()
        
        # 验证内容
        with open(output_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert "第一行文本" in content
        assert "第二行文本" in content

    def test_export_json(self, exporter, sample_ocr_result, temp_output_dir):
        """测试导出为 JSON"""
        exporter.add_result("test.png", sample_ocr_result)
        
        output_file = os.path.join(temp_output_dir, "test.json")
        result_path = exporter.export_json(output_file)
        
        assert result_path == output_file
        assert Path(output_file).exists()
        
        # 验证内容
        with open(output_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        assert data["total_images"] == 1
        assert len(data["results"]) == 1

    def test_export_json_without_details(self, exporter, sample_ocr_result, temp_output_dir):
        """测试导出 JSON 不包含详细信息"""
        exporter.add_result("test.png", sample_ocr_result)
        
        output_file = os.path.join(temp_output_dir, "test.json")
        exporter.export_json(output_file, include_details=False)
        
        with open(output_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 验证没有包含 box 信息
        if data["results"] and data["results"][0].get("texts"):
            assert "box" not in data["results"][0]["texts"][0]

    def test_export_excel(self, exporter, sample_ocr_result, temp_output_dir):
        """测试导出为 Excel"""
        try:
            import openpyxl
        except ImportError:
            pytest.skip("openpyxl 未安装")
        
        exporter.add_result("test.png", sample_ocr_result)
        
        output_file = os.path.join(temp_output_dir, "test.xlsx")
        result_path = exporter.export_excel(output_file)
        
        assert result_path == output_file
        assert Path(output_file).exists()

    def test_export_single_txt(self, exporter, sample_ocr_result, temp_output_dir):
        """测试导出单个结果为 TXT"""
        output_file = exporter.export(
            sample_ocr_result,
            "TXT",
            filename="single_test",
            output_dir=temp_output_dir
        )
        
        assert output_file is not None
        assert Path(output_file).exists()
        
        with open(output_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert "第一行文本" in content

    def test_export_single_json(self, exporter, sample_ocr_result, temp_output_dir):
        """测试导出单个结果为 JSON"""
        output_file = exporter.export(
            sample_ocr_result,
            "JSON",
            filename="single_test",
            output_dir=temp_output_dir
        )
        
        assert output_file is not None
        assert Path(output_file).exists()

    def test_export_single_excel(self, exporter, sample_ocr_result, temp_output_dir):
        """测试导出单个结果为 Excel"""
        try:
            import openpyxl
        except ImportError:
            pytest.skip("openpyxl 未安装")
        
        output_file = exporter.export(
            sample_ocr_result,
            "Excel",
            filename="single_test",
            output_dir=temp_output_dir
        )
        
        assert output_file is not None
        assert Path(output_file).exists()

    def test_export_invalid_format(self, exporter, sample_ocr_result, temp_output_dir):
        """测试导出无效格式"""
        output_file = exporter.export(
            sample_ocr_result,
            "INVALID",
            output_dir=temp_output_dir
        )
        
        assert output_file is None

    def test_export_empty_result(self, exporter, temp_output_dir):
        """测试导出空结果"""
        output_file = exporter.export(
            {},
            "TXT",
            output_dir=temp_output_dir
        )
        
        assert output_file is None

    def test_get_combined_text(self, exporter, sample_ocr_result):
        """测试获取合并文本"""
        exporter.add_result("test1.png", sample_ocr_result)
        exporter.add_result("test2.png", {
            "code": 100,
            "data": [{"text": "第三行", "score": 0.9}]
        })
        
        combined = exporter.get_combined_text()
        assert "第一行文本" in combined
        assert "第二行文本" in combined
        assert "第三行" in combined

    def test_export_failed_ocr(self, exporter, temp_output_dir):
        """测试导出失败的 OCR 结果"""
        failed_result = {
            "code": 200,
            "data": "图片路径不存在"
        }
        
        exporter.add_result("nonexistent.png", failed_result)
        
        output_file = os.path.join(temp_output_dir, "failed.txt")
        result_path = exporter.export_txt(output_file)
        
        assert result_path == output_file
        
        with open(output_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert "200" in content


class TestGetExporter:
    """测试全局导出器获取函数"""

    def test_get_exporter_singleton(self):
        """测试全局导出器是单例"""
        import core.exporter
        core.exporter._exporter = None
        
        exporter1 = get_exporter()
        exporter2 = get_exporter()
        assert exporter1 is exporter2
        
        # 清理
        core.exporter._exporter = None

    def test_reset_exporter(self):
        """测试重置导出器"""
        import core.exporter
        core.exporter._exporter = None
        
        exporter1 = get_exporter()
        exporter1.add_result("test.png", {"code": 100, "data": []})
        
        new_exporter = core.exporter.reset_exporter()
        assert new_exporter is not exporter1
        assert len(new_exporter.results) == 0
        
        # 清理
        core.exporter._exporter = None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
