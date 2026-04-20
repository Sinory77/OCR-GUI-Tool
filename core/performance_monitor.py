"""
性能监控模块 - 监控和统计 OCR 识别性能
"""
import time
import logging
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """性能指标数据类"""
    operation: str                    # 操作名称
    start_time: float                 # 开始时间戳
    end_time: float = 0.0            # 结束时间戳
    duration: float = 0.0            # 耗时（秒）
    success: bool = True             # 是否成功
    metadata: Dict[str, Any] = field(default_factory=dict)  # 额外元数据
    
    def complete(self, success: bool = True):
        """完成计时"""
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        self.success = success


class PerformanceMonitor:
    """性能监控器 - 单例模式"""
    
    _instance: Optional['PerformanceMonitor'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        # 存储性能数据
        self._metrics: deque[PerformanceMetrics] = deque(maxlen=1000)
        self._current_operations: Dict[str, PerformanceMetrics] = {}
        self._lock = threading.Lock()
        
        # 统计数据
        self._stats = {
            'total_operations': 0,
            'successful_operations': 0,
            'failed_operations': 0,
            'total_duration': 0.0,
        }
        
        logger.info("性能监控器已初始化")
    
    def start_operation(self, operation: str, **metadata) -> str:
        """
        开始监控一个操作
        
        Args:
            operation: 操作名称
            **metadata: 额外的元数据
            
        Returns:
            操作 ID
        """
        op_id = f"{operation}_{id(threading.current_thread())}_{time.time()}"
        
        metrics = PerformanceMetrics(
            operation=operation,
            start_time=time.time(),
            metadata=metadata
        )
        
        with self._lock:
            self._current_operations[op_id] = metrics
        
        logger.debug(f"[性能监控] 开始: {operation} (ID: {op_id})")
        return op_id
    
    def end_operation(self, op_id: str, success: bool = True) -> Optional[float]:
        """
        结束监控一个操作
        
        Args:
            op_id: 操作 ID
            success: 是否成功
            
        Returns:
            操作耗时（秒），如果找不到操作则返回 None
        """
        with self._lock:
            if op_id not in self._current_operations:
                logger.warning(f"[性能监控] 未找到操作 ID: {op_id}")
                return None
            
            metrics = self._current_operations.pop(op_id)
        
        metrics.complete(success)
        
        with self._lock:
            self._metrics.append(metrics)
            self._stats['total_operations'] += 1
            if success:
                self._stats['successful_operations'] += 1
            else:
                self._stats['failed_operations'] += 1
            self._stats['total_duration'] += metrics.duration
        
        logger.info(
            f"[性能监控] 完成: {metrics.operation} | "
            f"耗时: {metrics.duration:.3f}s | "
            f"状态: {'成功' if success else '失败'}"
        )
        
        return metrics.duration
    
    def record_operation(self, operation: str, duration: float, 
                        success: bool = True, **metadata):
        """
        直接记录一个操作的性能数据
        
        Args:
            operation: 操作名称
            duration: 耗时（秒）
            success: 是否成功
            **metadata: 额外元数据
        """
        metrics = PerformanceMetrics(
            operation=operation,
            start_time=time.time() - duration,
            end_time=time.time(),
            duration=duration,
            success=success,
            metadata=metadata
        )
        
        with self._lock:
            self._metrics.append(metrics)
            self._stats['total_operations'] += 1
            if success:
                self._stats['successful_operations'] += 1
            else:
                self._stats['failed_operations'] += 1
            self._stats['total_duration'] += duration
        
        logger.info(
            f"[性能监控] 记录: {operation} | "
            f"耗时: {duration:.3f}s | "
            f"状态: {'成功' if success else '失败'}"
        )
    
    def get_stats(self, last_n: Optional[int] = None) -> Dict[str, Any]:
        """
        获取性能统计
        
        Args:
            last_n: 只统计最近 N 个操作，None 表示全部
            
        Returns:
            统计信息字典
        """
        with self._lock:
            if last_n:
                metrics_list = list(self._metrics)[-last_n:]
            else:
                metrics_list = list(self._metrics)
        
        if not metrics_list:
            return {
                'total_operations': 0,
                'avg_duration': 0,
                'min_duration': 0,
                'max_duration': 0,
                'success_rate': 0,
            }
        
        durations = [m.duration for m in metrics_list]
        successful = sum(1 for m in metrics_list if m.success)
        
        return {
            'total_operations': len(metrics_list),
            'avg_duration': sum(durations) / len(durations),
            'min_duration': min(durations),
            'max_duration': max(durations),
            'success_rate': successful / len(metrics_list) * 100,
            'total_duration': sum(durations),
        }
    
    def get_operation_stats(self, operation: str) -> Dict[str, Any]:
        """
        获取特定操作的统计信息
        
        Args:
            operation: 操作名称
            
        Returns:
            该操作的统计信息
        """
        with self._lock:
            metrics_list = [m for m in self._metrics if m.operation == operation]
        
        if not metrics_list:
            return {
                'operation': operation,
                'count': 0,
                'avg_duration': 0,
                'min_duration': 0,
                'max_duration': 0,
                'success_rate': 0,
            }
        
        durations = [m.duration for m in metrics_list]
        successful = sum(1 for m in metrics_list if m.success)
        
        return {
            'operation': operation,
            'count': len(metrics_list),
            'avg_duration': sum(durations) / len(durations),
            'min_duration': min(durations),
            'max_duration': max(durations),
            'success_rate': successful / len(metrics_list) * 100,
        }
    
    def get_recent_operations(self, count: int = 10) -> List[Dict[str, Any]]:
        """
        获取最近的操作记录
        
        Args:
            count: 返回数量
            
        Returns:
            操作记录列表
        """
        with self._lock:
            recent = list(self._metrics)[-count:]
        
        return [
            {
                'operation': m.operation,
                'duration': m.duration,
                'success': m.success,
                'timestamp': datetime.fromtimestamp(m.start_time).isoformat(),
                'metadata': m.metadata,
            }
            for m in reversed(recent)
        ]
    
    def reset(self):
        """重置所有统计数据"""
        with self._lock:
            self._metrics.clear()
            self._current_operations.clear()
            self._stats = {
                'total_operations': 0,
                'successful_operations': 0,
                'failed_operations': 0,
                'total_duration': 0.0,
            }
        logger.info("[性能监控] 统计数据已重置")
    
    def export_report(self) -> str:
        """
        导出性能报告
        
        Returns:
            格式化的报告文本
        """
        stats = self.get_stats()
        recent = self.get_recent_operations(20)
        
        report_lines = [
            "=" * 60,
            "OCR-GUI-Tool 性能监控报告",
            f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 60,
            "",
            "总体统计:",
            f"  总操作数: {stats['total_operations']}",
            f"  平均耗时: {stats['avg_duration']:.3f}s",
            f"  最短耗时: {stats['min_duration']:.3f}s",
            f"  最长耗时: {stats['max_duration']:.3f}s",
            f"  成功率: {stats['success_rate']:.1f}%",
            f"  总耗时: {stats['total_duration']:.3f}s",
            "",
        ]
        
        # 按操作类型统计
        with self._lock:
            operations = set(m.operation for m in self._metrics)
        
        if operations:
            report_lines.append("按操作类型统计:")
            for op in sorted(operations):
                op_stats = self.get_operation_stats(op)
                report_lines.append(f"  {op}:")
                report_lines.append(f"    次数: {op_stats['count']}")
                report_lines.append(f"    平均: {op_stats['avg_duration']:.3f}s")
                report_lines.append(f"    成功率: {op_stats['success_rate']:.1f}%")
            report_lines.append("")
        
        # 最近操作
        if recent:
            report_lines.append("最近操作:")
            for op in recent[:10]:
                status = "✓" if op['success'] else "✗"
                report_lines.append(
                    f"  [{status}] {op['operation']} - "
                    f"{op['duration']:.3f}s - "
                    f"{op['timestamp']}"
                )
        
        report_lines.append("=" * 60)
        
        return "\n".join(report_lines)


# 上下文管理器支持
class OperationTimer:
    """操作计时器上下文管理器"""
    
    def __init__(self, operation: str, monitor: Optional[PerformanceMonitor] = None, **metadata):
        self.operation = operation
        self.monitor = monitor or get_performance_monitor()
        self.metadata = metadata
        self.op_id: Optional[str] = None
        self.duration: Optional[float] = None
    
    def __enter__(self):
        self.op_id = self.monitor.start_operation(self.operation, **self.metadata)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        success = exc_type is None
        self.duration = self.monitor.end_operation(self.op_id, success)
        return False  # 不抑制异常


# 全局性能监控实例
_perf_monitor: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> PerformanceMonitor:
    """获取全局性能监控实例
    
    Returns:
        性能监控器实例
    """
    global _perf_monitor
    if _perf_monitor is None:
        _perf_monitor = PerformanceMonitor()
    return _perf_monitor


def reset_performance_monitor():
    """重置全局性能监控器"""
    global _perf_monitor
    if _perf_monitor:
        _perf_monitor.reset()
    _perf_monitor = PerformanceMonitor()
    return _perf_monitor
