# -*- coding: utf-8 -*-
"""
Excel 数据处理执行器

所有耗时操作通过 TaskManager 异步调用。
直接接收参数，返回可 JSON 序列化的结果。

依赖：pandas>=2.0.0, openpyxl>=3.0.0
"""

import json
import logging
import gc
import io
from typing import List, Dict, Any, Optional, Callable
from dataclasses import asdict

import pandas as pd
import numpy as np

from core.excel_models import PivotConfig, CleanRule, LoadedTable

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────────────────────

def _df_to_json(df: pd.DataFrame) -> str:
    """
    将 DataFrame 序列化为 JSON（orient='split'，最紧凑且可逆）

    使用 'split' 格式：{"columns": [...], "index": [...], "data": [...]}
    比 'records' 更紧凑（index 只存一次），且能完整还原。
    """
    return df.to_json(orient='split', force_ascii=False)


def _json_to_df(df_json: str) -> pd.DataFrame:
    """将 JSON 反序列化为 DataFrame"""
    return pd.read_json(io.StringIO(df_json), orient='split')


# ──────────────────────────────────────────────────────────────
# Excel 加载
# ──────────────────────────────────────────────────────────────

def _load_single_excel(file_path: str,
                       sheet_name: Optional[str] = None,
                       use_columns: Optional[List[str]] = None,
                       nrows: Optional[int] = None) -> Dict[str, Any]:
    """
    加载单个 Excel 文件

    Args:
        file_path:    Excel 文件路径
        sheet_name:   Sheet 名称（None = 第一个 sheet）
        use_columns:  选用的列（None = 全部）
        nrows:        预览行数（None = 全部加载）

    Returns:
        {
            "file_path": str,
            "sheet_name": str,
            "columns": List[str],
            "preview_df_json": str,   # 仅前 nrows 行（预览用）
            "full_df_json": str,       # 完整数据（nrows=None 时与 preview 相同）
            "row_count": int,
            "col_count": int,
        }
    """
    logger.info(f"[Excel] 加载文件: {file_path}")

    # 获取 sheet_name（默认第一个）
    if sheet_name is None:
        xl = pd.ExcelFile(file_path, engine='openpyxl')
        sheet_name = xl.sheet_names[0]
        xl.close()

    # 读取数据
    df = pd.read_excel(
        file_path,
        sheet_name=sheet_name,
        usecols=use_columns if use_columns else None,
        nrows=nrows,
        engine='openpyxl',
    )

    # 清理列名（去除前后空格）
    df.columns = df.columns.str.strip()

    result = {
        "file_path": file_path,
        "sheet_name": sheet_name,
        "columns": list(df.columns),
        "preview_df_json": _df_to_json(df.head(200)),   # 预览最多 200 行
        "full_df_json": _df_to_json(df),
        "row_count": int(len(df)),
        "col_count": int(len(df.columns)),
    }

    logger.info(f"[Excel] 加载完成: {len(df)} 行 × {len(df.columns)} 列")
    return result


def create_excel_load_executor() -> Callable:
    """
    创建 Excel 加载执行器（供 TaskManager 注册）

    Returns:
        执行器函数，签名：
        executor(params, progress_callback, is_interrupted) -> dict
    """
    def executor(params: Dict[str, Any],
                 progress_callback: Callable,
                 is_interrupted: Callable) -> Dict[str, Any]:
        """
        Args:
            params: {
                "file_paths": List[str],
                "sheet_name": Optional[str],    # None = 每个文件用第一个 sheet
                "use_columns": Optional[List[str]],
                "preview_only": bool,           # True = 只加载前 200 行（快速预览）
            }
            progress_callback: 报告进度 (current, total, **kwargs)
            is_interrupted:  检查是否取消 () -> bool

        Returns:
            {
                "tables": List[Dict],   # 每个表的加载结果
                "total_rows": int,
                "total_cols": int,
            }
        """
        file_paths = params.get("file_paths", [])
        sheet_name = params.get("sheet_name")
        use_columns = params.get("use_columns")
        preview_only = params.get("preview_only", True)   # 默认只预览

        if not file_paths:
            raise ValueError("未提供文件路径")

        tables = []
        total = len(file_paths)

        for i, fp in enumerate(file_paths):
            if is_interrupted():
                raise InterruptedError("任务已被取消")

            progress_callback(i + 1, total, filename=fp)

            nrows = 200 if preview_only else None
            table_info = _load_single_excel(
                file_path=fp,
                sheet_name=sheet_name,
                use_columns=use_columns,
                nrows=nrows,
            )
            tables.append(table_info)

        total_rows = sum(t["row_count"] for t in tables)
        total_cols = max((t["col_count"] for t in tables), default=0)

        logger.info(f"[Excel] 全部加载完成: {len(tables)} 个表，共 {total_rows} 行")

        return {
            "tables": tables,
            "total_rows": total_rows,
            "total_cols": total_cols,
        }

    return executor


def get_excel_sheet_names(file_path: str) -> List[str]:
    """
    获取 Excel 文件的所有 sheet 名称（同步，快速）

    Args:
        file_path: Excel 文件路径

    Returns:
        sheet 名称列表
    """
    try:
        xl = pd.ExcelFile(file_path, engine='openpyxl')
        names = xl.sheet_names
        xl.close()
        return names
    except Exception as e:
        logger.error(f"[Excel] 获取 sheet 名称失败: {e}")
        return []


def get_excel_column_names(file_path: str,
                           sheet_name: Optional[str] = None,
                           nrows: int = 0) -> List[str]:
    """
    获取指定 sheet 的列名（同步，快速，只读取表头）

    Args:
        file_path:  Excel 文件路径
        sheet_name: Sheet 名称（None = 第一个）
        nrows:      0 = 只读取表头（最快）

    Returns:
        列名列表
    """
    try:
        if sheet_name is None:
            xl = pd.ExcelFile(file_path, engine='openpyxl')
            sheet_name = xl.sheet_names[0]
            xl.close()

        df = pd.read_excel(
            file_path,
            sheet_name=sheet_name,
            nrows=nrows,
            engine='openpyxl',
        )
        return list(df.columns.str.strip())
    except Exception as e:
        logger.error(f"[Excel] 获取列名失败: {e}")
        return []


# ──────────────────────────────────────────────────────────────
# 数据清洗
# ──────────────────────────────────────────────────────────────

def _apply_clean_rules(df: pd.DataFrame,
                       rules: List[CleanRule]) -> pd.DataFrame:
    """
    应用清洗规则列表

    Args:
        df:    原始 DataFrame
        rules:  CleanRule 列表（按顺序执行）

    Returns:
        清洗后的 DataFrame
    """
    result = df.copy()

    for i, rule in enumerate(rules):
        rule_type = rule.rule_type
        col = rule.column
        params = rule.params

        logger.debug(f"[Clean] 应用规则 #{i+1}: {rule_type} (列={col})")

        try:
            if rule_type == "dropna":
                # 删除空值行
                if col:
                    result = result.dropna(subset=[col])
                else:
                    result = result.dropna()

            elif rule_type == "dropdup":
                # 删除重复行
                if col:
                    result = result.drop_duplicates(subset=[col], keep='first')
                else:
                    result = result.drop_duplicates(keep='first')

            elif rule_type == "fillna":
                # 填充空值
                fill_value = params.get("value", 0)
                method = params.get("method", "")   # ffill / bfill

                if method == "ffill":
                    result[col] = result[col].fillna(method='ffill')
                elif method == "bfill":
                    result[col] = result[col].fillna(method='bfill')
                else:
                    result[col] = result[col].fillna(fill_value)

            elif rule_type == "astype":
                # 类型转换
                target_type = params.get("target_type", "str")
                dtype_map = {
                    "int": "Int64",       # 支持空值的可空整数
                    "float": "Float64",    # 支持空值的可空浮点
                    "str": "string",
                    "datetime": "datetime64[ns]",
                    "bool": "boolean",
                }
                pd_dtype = dtype_map.get(target_type, "string")
                result[col] = result[col].astype(pd_dtype)

            elif rule_type == "filter":
                # 行过滤
                op = params.get("op", ">")
                value = params.get("value", 0)
                logic = params.get("logic", "and")   # 预留，当前只处理单列

                if op == ">":
                    result = result[result[col] > value]
                elif op == ">=":
                    result = result[result[col] >= value]
                elif op == "<":
                    result = result[result[col] < value]
                elif op == "<=":
                    result = result[result[col] <= value]
                elif op == "==":
                    result = result[result[col] == value]
                elif op == "!=":
                    result = result[result[col] != value]
                elif op == "contains":
                    result = result[result[col].astype(str).str.contains(str(value), na=False)]
                elif op == "notna":
                    result = result[result[col].notna()]
                elif op == "isna":
                    result = result[result[col].isna()]

            else:
                logger.warning(f"[Clean] 未知规则类型: {rule_type}")

        except Exception as e:
            logger.error(f"[Clean] 规则应用失败 #{i+1} ({rule_type}): {e}")
            # 继续执行其他规则，不中断

    return result.reset_index(drop=True)


def create_excel_clean_executor() -> Callable:
    """
    创建数据清洗执行器
    """
    def executor(params: Dict[str, Any],
                 progress_callback: Callable,
                 is_interrupted: Callable) -> Dict[str, Any]:
        """
        Args:
            params: {
                "tables_json": List[str],   # 每个表的 full_df_json
                "clean_rules": List[Dict],  # CleanRule 的 dict 列表
            }

        Returns:
            {
                "cleaned_df_json": str,
                "original_rows": int,
                "cleaned_rows": int,
                "removed_rows": int,
            }
        """
        tables_json = params.get("tables_json", [])
        rules_dicts = params.get("clean_rules", [])

        if not tables_json:
            raise ValueError("未提供数据")

        # 反序列化规则
        rules = [CleanRule.from_dict(r) for r in rules_dicts]

        # 合并所有表（纵向 concat）
        progress_callback(1, 3, stage="合并数据")
        if is_interrupted():
            raise InterruptedError("任务已被取消")

        dfs = [_json_to_df(tj) for tj in tables_json]
        combined = pd.concat(dfs, ignore_index=True) if len(dfs) > 1 else dfs[0]
        original_rows = len(combined)

        progress_callback(2, 3, stage="应用清洗规则")
        if is_interrupted():
            raise InterruptedError("任务已被取消")

        cleaned = _apply_clean_rules(combined, rules)
        cleaned_rows = len(cleaned)

        progress_callback(3, 3, stage="清洗完成")

        # 释放大对象
        del combined
        gc.collect()

        return {
            "cleaned_df_json": _df_to_json(cleaned),
            "original_rows": original_rows,
            "cleaned_rows": cleaned_rows,
            "removed_rows": original_rows - cleaned_rows,
            "columns": list(cleaned.columns),
        }

    return executor


# ──────────────────────────────────────────────────────────────
# 多表合并
# ──────────────────────────────────────────────────────────────

def merge_tables(table_jsons: List[str],
                 merge_keys: Optional[List[str]] = None) -> pd.DataFrame:
    """
    多表合并

    策略：
    - 如果 merge_keys 为空：纵向 concat（所有表结构一致）
    - 如果 merge_keys 非空：按 key 横向 merge（类似 SQL JOIN）

    Args:
        table_jsons: 每个表的 full_df_json
        merge_keys:  横向合并的键列（空=纵向合并）

    Returns:
        合并后的 DataFrame
    """
    dfs = [_json_to_df(tj) for tj in table_jsons]

    if not merge_keys:
        # 纵向合并
        logger.info(f"[Merge] 纵向合并 {len(dfs)} 个表")
        result = pd.concat(dfs, ignore_index=True)
    else:
        # 横向合并（以第一个表为基准，左连接）
        logger.info(f"[Merge] 横向合并 {len(dfs)} 个表，键列: {merge_keys}")
        result = dfs[0]
        for i, df in enumerate(dfs[1:], 1):
            suffix = f"_{i}"
            result = result.merge(
                df,
                on=merge_keys,
                how='left',
                suffixes=('', suffix),
            )

    return result.reset_index(drop=True)


# ──────────────────────────────────────────────────────────────
# 数据透视
# ──────────────────────────────────────────────────────────────

def build_pivot(df: pd.DataFrame,
                 config: PivotConfig) -> pd.DataFrame:
    """
    构建透视表

    Args:
        df:      合并后的 DataFrame
        config:  透视配置

    Returns:
        透视后的 DataFrame（reset_index 后的平面表）
    """
    row_field = config.row_field
    col_field = config.col_field
    value_field = config.value_field
    agg_func = config.agg_func

    if not row_field or not value_field:
        raise ValueError("行维度和值字段不能为空")

    agg_map = {
        "sum": np.sum,
        "count": "count",
        "avg": np.mean,
        "mean": np.mean,
        "min": np.min,
        "max": np.max,
        "std": np.std,
    }
    # 直接使用字符串 agg 名，避免 FutureWarning
    agg_func_str = agg_func if agg_func in agg_map else "sum"

    if col_field:
        # 交叉透视表
        logger.info(f"[Pivot] 交叉透视: index={row_field}, columns={col_field}, values={value_field}, agg={agg_func}")

        pivot = pd.pivot_table(
            df,
            index=row_field,
            columns=col_field,
            values=value_field,
            aggfunc=agg_func_str,
            fill_value=0,
        )

        # 扁平化列名（MultiIndex -> 字符串）
        if isinstance(pivot.columns, pd.MultiIndex):
            pivot.columns = ['_'.join(map(str, col)).strip() for col in pivot.columns.values]

        result = pivot.reset_index()
    else:
        # 单维度分组聚合
        logger.info(f"[Pivot] 单维透视: groupby={row_field}, values={value_field}, agg={agg_func}")

        grouped = df.groupby(row_field)[value_field].agg(agg_func_str)
        result = grouped.reset_index()
        result.columns = [row_field, f"{value_field}_{agg_func}"]

    return result


def create_excel_pivot_executor() -> Callable:
    """
    创建透视表执行器
    """
    def executor(params: Dict[str, Any],
                 progress_callback: Callable,
                 is_interrupted: Callable) -> Dict[str, Any]:
        """
        Args:
            params: {
                "tables_json": List[str],   # 已加载表的 full_df_json 列表
                "pivot_config": Dict,         # PivotConfig 的 dict 表示
                "merge_keys": List[str],     # 合并键（可选）
            }

        Returns:
            {
                "result_df_json": str,
                "row_count": int,
                "col_count": int,
            }
        """
        tables_json = params.get("tables_json", [])
        config_dict = params.get("pivot_config", {})
        merge_keys = params.get("merge_keys", [])

        if not tables_json:
            raise ValueError("未提供数据")

        progress_callback(1, 4, stage="合并数据")
        if is_interrupted():
            raise InterruptedError("任务已被取消")

        # 合并表
        df = merge_tables(tables_json, merge_keys if merge_keys else None)

        progress_callback(2, 4, stage="数据清洗")
        if is_interrupted():
            raise InterruptedError("任务已被取消")

        # 应用清洗规则
        config = PivotConfig.from_dict(config_dict)
        if config.clean_rules:
            df = _apply_clean_rules(df, config.clean_rules)

        progress_callback(3, 4, stage="生成透视表")
        if is_interrupted():
            raise InterruptedError("任务已被取消")

        # 构建透视表
        result_df = build_pivot(df, config)

        progress_callback(4, 4, stage="透视完成")

        # 释放大对象
        del df
        gc.collect()

        logger.info(f"[Pivot] 透视完成: {len(result_df)} 行 × {len(result_df.columns)} 列")

        return {
            "result_df_json": _df_to_json(result_df),
            "row_count": int(len(result_df)),
            "col_count": int(len(result_df.columns)),
            "columns": list(result_df.columns),
        }

    return executor


# ──────────────────────────────────────────────────────────────
# 导出
# ──────────────────────────────────────────────────────────────

def create_excel_export_executor() -> Callable:
    """
    创建导出执行器
    """
    def executor(params: Dict[str, Any],
                 progress_callback: Callable,
                 is_interrupted: Callable) -> Dict[str, Any]:
        """
        Args:
            params: {
                "result_df_json": str,     # 透视结果的 JSON
                "file_path": str,           # 输出文件路径
                "format": str,              # "xlsx" | "csv"
            }

        Returns:
            {"success": bool, "file_path": str, "row_count": int}
        """
        result_df_json = params.get("result_df_json", "")
        file_path = params.get("file_path", "")
        export_format = params.get("format", "xlsx")

        if not result_df_json or not file_path:
            raise ValueError("参数不完整")

        progress_callback(1, 3, stage="解析数据")
        if is_interrupted():
            raise InterruptedError("任务已被取消")

        df = _json_to_df(result_df_json)

        progress_callback(2, 3, stage="写入文件")
        if is_interrupted():
            raise InterruptedError("任务已被取消")

        if export_format == "csv":
            df.to_csv(file_path, index=False, encoding='utf-8-sig')
        else:
            df.to_excel(file_path, index=False, engine='openpyxl')

        progress_callback(3, 3, stage="导出完成")

        return {
            "success": True,
            "file_path": file_path,
            "row_count": int(len(df)),
        }

    return executor
