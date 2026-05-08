"""
去重模块 - OCR 识别去重功能

功能：
- 识别前排重：基于 MD5 哈希的文件级精确去重
- 识别后排重：基于 SimHash 的文本精确去重
- 表格排重：支持表格结构的行列级比对

使用方法：
    from core.deduplication import Deduplicator

    dedup = Deduplicator()

    # 识别前：检查文件是否重复
    if dedup.check_file_duplicate(file_path):
        skip_file()

    # 识别后：检查识别结果是否重复
    if dedup.check_text_duplicate(text):
        skip_result()

    # 表格内容去重
    if dedup.check_table_duplicate(table_data):
        skip_table()

    # 批量完成，清理
    dedup.clear()
"""

import hashlib
import json
import re
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field


class SimHash:
    """SimHash 实现 - 用于海量文本快速去重

    原理：将文本转为64位哈希码，相似文本的哈希码海明距离相近（≤3）
    优势：O(1) 时间复杂度查询海量数据
    """

    def __init__(self, bits: int = 64):
        self.bits = bits
        self.hash_bits = bits

    def _tokenize(self, text: str) -> List[str]:
        """文本分词"""
        # 清理并分词
        text = text.lower().strip()
        # 按非字母数字分割
        tokens = re.findall(r'\w+', text)
        # 过滤太短的词
        return [t for t in tokens if len(t) >= 2]

    def _hash(self, token: str) -> int:
        """单字符哈希"""
        h = hashlib.md5(token.encode('utf-8')).digest()
        return int.from_bytes(h[:8], byteorder='big')

    def compute(self, text: str) -> int:
        """计算文本的 SimHash 值"""
        if not text:
            return 0

        tokens = self._tokenize(text)
        if not tokens:
            return 0

        # 向量初始化
        v = [0] * self.hash_bits

        # 加权
        for token in tokens:
            h = self._hash(token)
            for i in range(self.hash_bits):
                # 获取第 i 位
                bit = (h >> i) & 1
                if bit:
                    v[i] += 1
                else:
                    v[i] -= 1

        # 生成哈希码
        fingerprint = 0
        for i in range(self.hash_bits):
            if v[i] > 0:
                fingerprint |= (1 << i)

        return fingerprint

    def hamming_distance(self, hash1: int, hash2: int) -> int:
        """计算两个哈希的海明距离"""
        x = hash1 ^ hash2
        return bin(x).count('1')

    def is_similar(self, hash1: int, hash2: int, threshold: int = 3) -> bool:
        """判断两个哈希是否相似（海明距离 <= threshold）"""
        return self.hamming_distance(hash1, hash2) <= threshold


@dataclass
class TableStructure:
    """表格结构数据"""
    headers: List[str] = field(default_factory=list)
    rows: List[List[str]] = field(default_factory=list)

    def normalize(self) -> str:
        """归一化表格内容用于比对"""
        parts = []
        parts.append('|'.join(self.headers))
        for row in sorted(self.rows):
            parts.append('|'.join(row))
        return '\n'.join(parts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'headers': self.headers,
            'rows': self.rows
        }


class TableParser:
    """表格解析器 - 从 OCR 文本中识别表格结构"""

    # 表格分隔符模式
    SEPARATORS = ['|', '│', '┌', '┐', '└', '┘', '─', '─', '┼', '├', '┤', '┬', '┴']

    @classmethod
    def is_table_line(cls, line: str) -> bool:
        """判断是否是表格分隔线"""
        line = line.strip()
        if not line:
            return False
        # 包含多个分隔符
        sep_count = sum(1 for c in line if c in cls.SEPARATORS)
        return sep_count >= 3 or '──' in line or '───' in line or '┅' in line

    @classmethod
    def parse(cls, text: str) -> Optional[TableStructure]:
        """从文本中解析表格结构

        支持格式：
        - 标准表格：| 列1 | 列2 |
        - 简单表格：列1  列2
        """
        lines = text.split('\n')
        table_lines = []
        table_start = -1
        table_end = -1

        # 找到表格区域
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue

            # 跳过分隔线
            if cls.is_table_line(stripped):
                if table_start >= 0 and table_end < 0:
                    table_end = i
                continue

            # 表格内容行
            if '|' in stripped or (len(stripped.split()) >= 2 and all(c.isprintable() for c in stripped)):
                if table_start < 0:
                    table_start = i
                table_lines.append(stripped)
                table_end = i + 1

        if len(table_lines) < 2:
            return None  # 至少需要表头和一行数据

        # 解析表格
        table = TableStructure()

        for i, line in enumerate(table_lines):
            cells = cls._parse_row(line)

            if i == 0:
                # 第一行作为表头
                table.headers = cells
            else:
                table.rows.append(cells)

        return table if table.headers else None

    @classmethod
    def _parse_row(cls, line: str) -> List[str]:
        """解析表格行"""
        # 清理并分割
        line = line.strip().strip('|').strip()
        cells = []

        if '|' in line:
            # 标准表格格式
            parts = line.split('|')
            for part in parts:
                cell = part.strip()
                if cell:
                    cells.append(cell)
        else:
            # 简单空格分隔
            parts = re.split(r'\s{2,}', line)
            cells = [p.strip() for p in parts if p.strip()]

        return cells


class Deduplicator:
    """去重器 - 统一的去重接口"""

    def __init__(self, text_threshold: int = 0, table_threshold: float = 0.95):
        """
        Args:
            text_threshold: SimHash 海明距离阈值，0 表示完全匹配
            table_threshold: 表格内容相似度阈值（0-1）
        """
        self.text_threshold = text_threshold
        self.table_threshold = table_threshold

        # 文件 MD5 集合
        self._file_hashes: Set[str] = set()

        # SimHash 集合
        self._simhash_map: Dict[int, str] = {}  # hash -> original_text (用于完全匹配)

        # 原始文本集合（用于完全匹配）
        self._text_set: Set[str] = set()

        # 表格哈希集合
        self._table_hashes: Set[str] = set()

        # SimHash 计算器
        self._simhasher = SimHash()

        # 统计
        self.stats = {
            'file_checked': 0,
            'file_duplicates': 0,
            'text_checked': 0,
            'text_duplicates': 0,
            'table_checked': 0,
            'table_duplicates': 0,
        }

    def check_file_duplicate(self, file_path: str) -> bool:
        """检查文件是否重复（基于 MD5）

        Args:
            file_path: 文件路径

        Returns:
            True 表示重复，False 表示新文件
        """
        self.stats['file_checked'] += 1

        md5_hash = self._compute_file_md5(file_path)

        if md5_hash in self._file_hashes:
            self.stats['file_duplicates'] += 1
            return True

        self._file_hashes.add(md5_hash)
        return False

    def check_file_hash_duplicate(self, file_hash: str) -> bool:
        """直接使用文件哈希检查重复

        Args:
            file_hash: 已计算好的 MD5 哈希值

        Returns:
            True 表示重复，False 表示新文件
        """
        self.stats['file_checked'] += 1

        if file_hash in self._file_hashes:
            self.stats['file_duplicates'] += 1
            return True

        self._file_hashes.add(file_hash)
        return False

    def check_text_duplicate(self, text: str) -> bool:
        """检查文本是否重复（基于 SimHash + 完全匹配）

        Args:
            text: OCR 识别结果文本

        Returns:
            True 表示重复，False 表示新内容
        """
        self.stats['text_checked'] += 1

        # 归一化文本
        normalized = self._normalize_text(text)
        if not normalized:
            return False

        # 1. 完全匹配优先（最高精度）
        if normalized in self._text_set:
            self.stats['text_duplicates'] += 1
            return True

        # 2. SimHash 精确匹配（threshold=0 表示完全相同）
        if self.text_threshold == 0:
            # 完全匹配模式，只比较 SimHash 是否相同
            text_hash = self._simhasher.compute(normalized)
            for stored_hash, stored_text in self._simhash_map.items():
                if text_hash == stored_hash:
                    # SimHash 相同，再用原始内容确认
                    if self._normalize_text(stored_text) == normalized:
                        self.stats['text_duplicates'] += 1
                        return True
        else:
            # 容差模式（threshold > 0）
            text_hash = self._simhasher.compute(normalized)
            for stored_hash in self._simhash_map.keys():
                if self._simhasher.is_similar(text_hash, stored_hash, self.text_threshold):
                    self.stats['text_duplicates'] += 1
                    return True

        # 不重复，记录
        self._text_set.add(normalized)
        self._simhash_map[self._simhasher.compute(normalized)] = text
        return False

    def check_table_duplicate(self, table_data: TableStructure) -> bool:
        """检查表格是否重复（基于内容比对）

        Args:
            table_data: 表格结构数据

        Returns:
            True 表示重复，False 表示新表格
        """
        self.stats['table_checked'] += 1

        if not table_data.headers or not table_data.rows:
            return False

        # 计算表格哈希
        table_hash = self._compute_table_hash(table_data)

        if table_hash in self._table_hashes:
            self.stats['table_duplicates'] += 1
            return True

        self._table_hashes.add(table_hash)
        return False

    def check_table_from_text(self, text: str) -> Tuple[bool, Optional[TableStructure]]:
        """从文本中解析表格并检查重复

        Args:
            text: 可能包含表格的文本

        Returns:
            (is_duplicate, table_structure)
        """
        table = TableParser.parse(text)
        if table:
            is_dup = self.check_table_duplicate(table)
            return is_dup, table
        return False, None

    def get_stats(self) -> Dict[str, int]:
        """获取去重统计信息"""
        return self.stats.copy()

    def clear(self):
        """清空去重记录"""
        self._file_hashes.clear()
        self._text_set.clear()
        self._simhash_map.clear()
        self._table_hashes.clear()

    def reset_stats(self):
        """重置统计信息"""
        for key in self.stats:
            self.stats[key] = 0

    @staticmethod
    def _compute_file_md5(file_path: str) -> str:
        """计算文件的 MD5 哈希"""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception:
            # 文件读取失败，使用路径哈希
            return hashlib.md5(file_path.encode()).hexdigest()

    @staticmethod
    def _normalize_text(text: str) -> str:
        """归一化文本用于比对"""
        if not text:
            return ""

        # 清理多余空白
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()

        # 移除常见 OCR 错误
        replacements = {
            '０': '0', '１': '1', '２': '2', '３': '3', '４': '4',
            '５': '5', '６': '6', '７': '7', '８': '8', '９': '9',
            '－': '-', '—': '-', '‘': "'", '’': "'", '"': '"', '"': '"',
        }
        for old, new in replacements.items():
            text = text.replace(old, new)

        return text

    @staticmethod
    def _compute_table_hash(table: TableStructure) -> str:
        """计算表格内容的哈希"""
        # 归一化表格内容
        normalized = table.normalize()
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def get_deduplicator() -> Deduplicator:
    """获取去重器单例"""
    return Deduplicator()
