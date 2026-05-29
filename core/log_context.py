# -*- coding: utf-8 -*-
"""
结构化日志上下文模块

提供线程安全的日志上下文注入能力，允许在关键入口处包装日志记录，
自动为后续所有日志添加结构化字段（task_id、file_name 等），方便排查问题。

用法：
    from core.log_context import LogContext

    with LogContext(task_id="ocr_abc123", file_name="test.png"):
        logger.info("开始识别")  # → [task_id=ocr_abc123][file=test.png] 开始识别

线程安全：每个线程有独立的上下文栈，互不干扰。
"""

import logging
import threading
from contextlib import contextmanager
from typing import Dict, Optional, Any

# ── 线程本地存储 ──
_thread_local = threading.local()


def _get_context_stack() -> list:
    """获取当前线程的上下文栈（延迟初始化）"""
    if not hasattr(_thread_local, "context_stack"):
        _thread_local.context_stack = []
    return _thread_local.context_stack


class ContextFilter(logging.Filter):
    """日志过滤器：自动将线程上下文注入到 LogRecord 的自定义字段"""

    def filter(self, record: logging.LogRecord) -> bool:
        context = get_current_context()
        if context:
            parts = []
            for key, value in context.items():
                parts.append("[%s=%s]" % (key, value))
            record.context_prefix = "".join(parts) + " "
        else:
            record.context_prefix = ""
        return True


def get_current_context() -> Dict[str, Any]:
    """获取当前线程的上下文合并结果

    Returns:
        上下文字典（所有已入栈的上下文合并结果）
    """
    stack = _get_context_stack()
    merged: Dict[str, Any] = {}
    for ctx in stack:
        merged.update(ctx)
    return merged


@contextmanager
def LogContext(**kwargs):
    """线程安全的日志上下文管理器

    自动注入指定的键值对到当前线程的日志记录中。
    支持嵌套——内层覆盖外层的同名字段。

    Args:
        **kwargs: 要注入的键值对，如 task_id="xxx", file_name="test.png"

    Example:
        with LogContext(task_id="ocr_abc123"):
            logger.info("任务开始")  # 自动添加 [task_id=ocr_abc123] 前缀
    """
    stack = _get_context_stack()
    stack.append(kwargs)
    try:
        yield
    finally:
        stack.pop()


def log_with_context(logger: logging.Logger, level: int, msg: str, *args, **kwargs):
    """带线程上下文的手动日志记录方法（备选方案）

    Args:
        logger: logging.Logger 实例
        level: 日志级别 (logging.INFO 等)
        msg: 日志消息
        *args: 消息格式化参数
        **kwargs: 额外参数（会传给 logger.log）
    """
    context = get_current_context()
    if context:
        prefix = "".join("[%s=%s]" % (k, v) for k, v in context.items())
        msg = "%s %s" % (prefix, msg)
    logger.log(level, msg, *args, **kwargs)


# ── 模块初始化：注册过滤器 ──
# 在导入时自动注册到根 logger，确保全局生效
_root_logger = logging.getLogger()
# 避免重复注册
if not any(isinstance(f, ContextFilter) for f in _root_logger.filters):
    _root_logger.addFilter(ContextFilter())
