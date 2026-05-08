# 性能监控说明

> ⚠️ **注意**: 本文档描述的性能监控功能已在项目清理中移除。
> 
> 如果需要重新添加性能监控功能，请参考本目录下的历史版本或重新创建 `core/performance_monitor.py` 模块。

## 当前状态

性能监控模块 (`performance_monitor.py`) 已从项目中移除。

如需重新集成，请参考以下设计：

## 推荐实现方案

### 1. 基本架构

```python
# core/performance_monitor.py
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from collections import deque
import time
import logging

logger = logging.getLogger(__name__)

@dataclass
class Operation:
    operation: str
    duration: float
    success: bool
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, max_records: int = 1000):
        self._records: deque = deque(maxlen=max_records)
    
    def record(self, operation: str, duration: float, 
               success: bool = True, **metadata) -> None:
        """记录操作"""
        op = Operation(operation, duration, success, metadata=metadata)
        self._records.append(op)
        logger.debug(f"[PERF] {operation}: {duration:.3f}s")
    
    def get_stats(self, operation: Optional[str] = None) -> Dict[str, Any]:
        """获取统计信息"""
        # 实现统计逻辑
        pass
    
    def export_report(self) -> str:
        """导出报告"""
        # 生成格式化报告
        pass
```

### 2. 集成方式

```python
# 在 ocr_engine.py 中集成
from core.performance_monitor import get_monitor

def recognize(self, image_path: str):
    start = time.time()
    try:
        result = self._do_recognize(image_path)
        duration = time.time() - start
        get_monitor().record("ocr_recognize", duration, True)
        return result
    except Exception as e:
        duration = time.time() - start
        get_monitor().record("ocr_recognize", duration, False)
        raise
```

### 3. 使用示例

```python
from core.performance_monitor import get_monitor

monitor = get_monitor()

# 获取统计
stats = monitor.get_stats()
print(f"平均耗时: {stats['avg_duration']:.3f}s")
print(f"成功率: {stats['success_rate']:.1f}%")

# 导出报告
report = monitor.export_report()
```

## 替代方案

如果需要轻量级的性能监控，可以直接使用 Python 的 `time` 模块：

```python
import time
import logging

logger = logging.getLogger(__name__)

def timed(func):
    """简单的装饰器实现性能监控"""
    def wrapper(*args, **kwargs):
        start = time.time()
        try:
            result = func(*args, **kwargs)
            logger.info(f"{func.__name__}: {time.time() - start:.3f}s")
            return result
        except Exception as e:
            logger.error(f"{func.__name__} failed in {time.time() - start:.3f}s")
            raise
    return wrapper
```

## 后续建议

如需完整的性能监控功能：

1. 重新创建 `core/performance_monitor.py`
2. 在关键操作中添加监控点
3. 添加可视化界面（设置页面）
4. 实现性能告警机制

---

**最后更新**: 2026-05-08
