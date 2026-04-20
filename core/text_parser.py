"""
文本解析器 - 根据模板规则从 OCR 结果中提取结构化数据
"""
import re
from typing import Dict, List, Optional, Tuple
from core.template_manager import ParseTemplate, ParseRule


class TextParser:
    """文本解析器"""
    
    def __init__(self, template: ParseTemplate):
        """
        初始化解析器
        
        Args:
            template: 解析模板
        """
        self.template = template
    
    def parse(self, text: str) -> Dict[str, str]:
        """
        解析文本，提取字段
        
        Args:
            text: OCR 识别结果文本
            
        Returns:
            字段名 -> 字段值的字典，提取失败的字段值为空字符串
        """
        result = {}
        
        for rule in self.template.rules:
            value = self._apply_rule(text, rule)
            result[rule.name] = value
        
        return result
    
    def _apply_rule(self, text: str, rule: ParseRule) -> str:
        """
        应用单条规则提取字段值
        
        Args:
            text: 原始文本
            rule: 解析规则
            
        Returns:
            提取的字段值，失败返回空字符串
        """
        if rule.type == 'keyword':
            return self._extract_by_keyword(text, rule)
        elif rule.type == 'regex':
            return self._extract_by_regex(text, rule.pattern)
        elif rule.type == 'position':
            return self._extract_by_position(text, rule.line, rule.start, rule.end)
        else:
            return ""
    
    def _extract_by_keyword(self, text: str, rule: ParseRule) -> str:
        """
        通过关键词提取字段值
        
        Args:
            text: 原始文本
            rule: 解析规则（包含keyword和配置选项）
            
        Returns:
            提取的字段值
        """
        lines = text.split('\n')
        keyword = rule.keyword
        ignore_spaces = rule.ignore_spaces
        use_next_line = rule.use_next_line
        
        # 根据配置决定是否去除空格
        if ignore_spaces:
            keyword_clean = keyword.replace(" ", "")
        else:
            keyword_clean = keyword
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if not line_stripped:
                continue
            
            # 根据配置决定是否去除空格后匹配
            if ignore_spaces:
                line_clean = line_stripped.replace(" ", "")
            else:
                line_clean = line_stripped
            
            # 查找关键词 - 必须完整匹配，不能是部分匹配
            # 例如：关键词"货主"不应该匹配行"货物"
            keyword_pos = line_clean.find(keyword_clean)
            if keyword_pos == -1:
                continue
            
            # 检查是否是完整匹配（关键词后面必须是分隔符或行尾）
            keyword_end_pos = keyword_pos + len(keyword_clean)
            if keyword_end_pos < len(line_clean):
                next_char = line_clean[keyword_end_pos]
                # 关键词后面必须是分隔符或空白
                if next_char not in [':', '：', ' ', '\t', '】', ']', ')', '）']:
                    # 可能是部分匹配，跳过
                    continue
            
            # 使用冒号分割提取值
            after = re.split(r"[：:]\s*", line_stripped, maxsplit=1)
            if len(after) > 1 and after[1].strip():
                val = after[1].strip()
            elif use_next_line and i + 1 < len(lines):
                # 当前行没有值，尝试下一行
                val = lines[i + 1].strip()
            else:
                val = ""
            
            # 去除值中的空格进行比较
            val_clean = val.replace(" ", "")
            
            # 确保值不是关键词本身（且不为空）
            if val_clean and val_clean != keyword_clean:
                return val
        
        return ""
    
    def _extract_by_regex(self, text: str, pattern: str) -> str:
        """
        通过正则表达式提取字段值
        
        Args:
            text: 原始文本
            pattern: 正则表达式模式
            
        Returns:
            提取的字段值（第一个捕获组的内容）
        """
        try:
            match = re.search(pattern, text)
            if match:
                # 如果有捕获组，返回第一个捕获组
                if match.groups():
                    return match.group(1)
                # 否则返回整个匹配
                return match.group(0)
        except re.error:
            pass
        
        return ""
    
    def _extract_by_position(self, text: str, line: int, start: int, end: int) -> str:
        """
        通过位置提取字段值
        
        Args:
            text: 原始文本
            line: 行号（从0开始）
            start: 起始位置
            end: 结束位置（0表示到行尾）
            
        Returns:
            提取的字段值
        """
        lines = text.split('\n')
        
        if line < 0 or line >= len(lines):
            return ""
        
        target_line = lines[line]
        
        if start < 0 or start >= len(target_line):
            return ""
        
        if end <= 0 or end > len(target_line):
            end = len(target_line)
        
        return target_line[start:end].strip()


class TemplateMatcher:
    """模板匹配器 - 自动选择最佳匹配的模板"""
    
    def __init__(self, templates: List[ParseTemplate]):
        """
        初始化匹配器
        
        Args:
            templates: 可用模板列表
        """
        self.templates = templates
    
    def match(self, text: str) -> Tuple[Optional[ParseTemplate], Dict[str, str]]:
        """
        匹配最佳模板并解析文本
        
        Args:
            text: OCR 识别结果文本
            
        Returns:
            (最佳模板, 解析结果)，如果没有匹配则模板为 None
        """
        if not self.templates:
            return None, {}
        
        best_template = None
        best_result = {}
        best_score = 0
        
        for template in self.templates:
            parser = TextParser(template)
            result = parser.parse(text)
            
            # 计算匹配分数（成功提取的字段数）
            score = sum(1 for value in result.values() if value)
            
            # 选择分数最高的模板
            if score > best_score:
                best_score = score
                best_template = template
                best_result = result
        
        return best_template, best_result
    
    def match_with_threshold(self, text: str, min_fields: int = 1) -> Tuple[Optional[ParseTemplate], Dict[str, str]]:
        """
        匹配最佳模板（带阈值）
        
        Args:
            text: OCR 识别结果文本
            min_fields: 最少成功提取字段数，低于此值认为匹配失败
            
        Returns:
            (最佳模板, 解析结果)，如果未达到阈值则模板为 None
        """
        template, result = self.match(text)
        
        if template is None:
            return None, {}
        
        # 检查是否达到阈值
        success_count = sum(1 for value in result.values() if value)
        if success_count < min_fields:
            return None, {}
        
        return template, result
