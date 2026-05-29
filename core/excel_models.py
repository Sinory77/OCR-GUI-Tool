# -*- coding: utf-8 -*-
"""
Excel 数据模型定义

定义透视配置、清洗规则、表数据等核心数据结构。
PivotConfig 可序列化为 JSON 模板，复用 template_manager.py 的模式。
"""

import uuid
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
from datetime import datetime


@dataclass
class CleanRule:
    """
    清洗规则

    rule_type 取值：
      - "dropna":     删除空值行（需指定 column）
      - "dropdup":    删除重复行（可选依据列，空=全部列）
      - "fillna":     填充空值（需指定 column + params["value"]）
      - "astype":     类型转换（需指定 column + params["target_type"]）
      - "filter":     行过滤（需指定 column + params{"op": ">", "value": 0}）
    """
    rule_type: str = "dropna"
    column: str = ""                       # 目标列名
    params: Dict[str, Any] = field(default_factory=dict)
    # params 示例：
    #   fillna:  {"value": 0} 或 {"method": "ffill"}
    #   astype:  {"target_type": "int"}  # int | float | str | datetime
    #   filter:  {"op": ">", "value": 100, "logic": "and"}  # op: >|>=|<|<=|==|!=|contains

    def to_dict(self) -> dict:
        return {
            "rule_type": self.rule_type,
            "column": self.column,
            "params": self.params,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CleanRule":
        return cls(
            rule_type=d.get("rule_type", "dropna"),
            column=d.get("column", ""),
            params=d.get("params", {}),
        )


@dataclass
class PivotConfig:
    """
    透视配置 —— 可序列化为 JSON 模板

    保存为 templates/excel_pivot/{id}.json，
    加载时反序列化为 PivotConfig 对象。
    """
    id: str = ""
    name: str = ""
    description: str = ""
    created_at: str = ""
    updated_at: str = ""

    # 数据源
    source_files: List[str] = field(default_factory=list)   # Excel 文件路径列表
    sheet_names: List[str] = field(default_factory=list)    # 每个文件选用的 sheet（与 source_files 长度一致）
    use_columns: List[str] = field(default_factory=list)    # 选用的列（空=全部）
    row_filters: List[Dict[str, Any]] = field(default_factory=list)
    # row_filters 示例: [{"column": "金额", "op": ">", "value": 0}]

    # 清洗规则
    clean_rules: List[CleanRule] = field(default_factory=list)

    # 透视配置
    row_field: str = ""               # 行维度列名
    col_field: str = ""               # 列维度列名（空=不交叉）
    value_field: str = ""             # 值字段列名
    agg_func: str = "sum"            # 聚合函数: sum|count|avg|min|max|mean|std

    # 多表合并配置
    merge_keys: List[str] = field(default_factory=list)   # 横向合并的键列

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source_files": self.source_files,
            "sheet_names": self.sheet_names,
            "use_columns": self.use_columns,
            "row_filters": self.row_filters,
            "clean_rules": [r.to_dict() for r in self.clean_rules],
            "row_field": self.row_field,
            "col_field": self.col_field,
            "value_field": self.value_field,
            "agg_func": self.agg_func,
            "merge_keys": self.merge_keys,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PivotConfig":
        return cls(
            id=d.get("id", ""),
            name=d.get("name", ""),
            description=d.get("description", ""),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            source_files=d.get("source_files", []),
            sheet_names=d.get("sheet_names", []),
            use_columns=d.get("use_columns", []),
            row_filters=d.get("row_filters", []),
            clean_rules=[CleanRule.from_dict(r) for r in d.get("clean_rules", [])],
            row_field=d.get("row_field", ""),
            col_field=d.get("col_field", ""),
            value_field=d.get("value_field", ""),
            agg_func=d.get("agg_func", "sum"),
            merge_keys=d.get("merge_keys", []),
        )

    def validate(self) -> tuple[bool, str]:
        """
        验证配置有效性

        Returns:
            (is_valid, error_message)
        """
        if not self.id:
            return False, "配置 ID 不能为空"
        if not self.name or not self.name.strip():
            return False, "配置名称不能为空"
        if not self.row_field:
            return False, "请选择行维度字段"
        if not self.value_field:
            return False, "请选择值字段"
        if self.agg_func not in ("sum", "count", "avg", "min", "max", "mean", "std"):
            return False, f"不支持的聚合函数: {self.agg_func}"
        return True, ""


@dataclass
class LoadedTable:
    """
    已加载的表数据（内存中，DataFrame 不序列化）

    注意：DataFrame 对象不跨线程直接传递，
    在线程间使用 JSON 序列化（orient='split'）。
    """
    file_path: str = ""
    sheet_name: str = ""
    columns: List[str] = field(default_factory=list)
    row_count: int = 0
    # DataFrame 不存储在此 dataclass 中，
    # 实际数据由 ExcelProcessor 在内存中管理。
    # 此对象仅用于 UI 显示表摘要信息。
