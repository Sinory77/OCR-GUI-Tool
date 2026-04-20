# 性能监控使用指南

## 概述

OCR-GUI-Tool 内置了性能监控模块，可以实时监控和统计各个操作的执行时间和成功率。

## 快速开始

### 1. 基本使用

```python
from core.performance_monitor import get_performance_monitor

# 获取监控实例
monitor = get_performance_monitor()

# 手动记录操作
monitor.start_operation("data_processing")
# ... 执行操作 ...
monitor.end_operation("data_processing", success=True)

# 或直接记录
monitor.record_operation("api_call", duration=0.5, success=True)
```

### 2. 使用上下文管理器（推荐）

```python
from core.performance_monitor import OperationTimer

# 自动计时
with OperationTimer("my_operation"):
    # 执行你的代码
    result = do_something()
```

### 3. 查看统计数据

```python
# 获取总体统计
stats = monitor.get_stats()
print(f"平均耗时: {stats['avg_duration']:.3f}s")
print(f"成功率: {stats['success_rate']:.1f}%")

# 获取特定操作的统计
ocr_stats = monitor.get_operation_stats("ocr_recognize")
print(f"OCR 平均识别时间: {ocr_stats['avg_duration']:.3f}s")

# 获取最近的操作记录
recent = monitor.get_recent_operations(count=10)
for op in recent:
    print(f"{op['operation']}: {op['duration']:.3f}s")
```

### 4. 导出报告

```python
# 生成格式化的性能报告
report = monitor.export_report()
print(report)

# 保存到文件
with open("performance_report.txt", "w", encoding="utf-8") as f:
    f.write(monitor.export_report())
```

## 集成示例

### OCR 引擎集成

性能监控已自动集成到 OCR 引擎中，所有识别操作都会被自动监控：

```python
from core.ocr_engine import get_ocr_engine
from core.performance_monitor import get_performance_monitor

engine = get_ocr_engine()
monitor = get_performance_monitor()

# 执行识别（自动监控）
result = engine.recognize("image.png")

# 查看 OCR 性能统计
ocr_stats = monitor.get_operation_stats("ocr_recognize")
print(f"OCR 识别统计:")
print(f"  次数: {ocr_stats['count']}")
print(f"  平均: {ocr_stats['avg_duration']:.3f}s")
print(f"  最快: {ocr_stats['min_duration']:.3f}s")
print(f"  最慢: {ocr_stats['max_duration']:.3f}s")
```

### 自定义监控

可以在自己的代码中添加性能监控：

```python
from core.performance_monitor import OperationTimer

def process_batch_images(image_paths):
    """批量处理图片"""
    results = []
    
    for image_path in image_paths:
        # 监控单个图片处理
        with OperationTimer("process_single_image", filename=image_path):
            result = engine.recognize(image_path)
            results.append(result)
    
    return results

# 监控整个批量处理
with OperationTimer("batch_processing", count=len(image_paths)):
    results = process_batch_images(image_paths)
```

## API 参考

### PerformanceMonitor

#### 核心方法

```python
# 开始监控
op_id = monitor.start_operation(operation: str, **metadata) -> str

# 结束监控
duration = monitor.end_operation(op_id: str, success: bool = True) -> Optional[float]

# 直接记录
monitor.record_operation(operation: str, duration: float, 
                        success: bool = True, **metadata)

# 获取统计
stats = monitor.get_stats(last_n: Optional[int] = None) -> Dict[str, Any]
op_stats = monitor.get_operation_stats(operation: str) -> Dict[str, Any]
recent = monitor.get_recent_operations(count: int = 10) -> List[Dict]

# 导出报告
report = monitor.export_report() -> str

# 重置
monitor.reset()
```

### OperationTimer

```python
# 基本用法
with OperationTimer("operation_name"):
    do_something()

# 带元数据
with OperationTimer("api_call", url="https://example.com", method="POST"):
    response = requests.post(...)

# 访问耗时
timer = OperationTimer("my_op")
with timer:
    do_work()
print(f"耗时: {timer.duration}s")
```

## 监控指标说明

### 总体统计

- **total_operations**: 总操作数
- **avg_duration**: 平均耗时（秒）
- **min_duration**: 最短耗时（秒）
- **max_duration**: 最长耗时（秒）
- **success_rate**: 成功率（%）
- **total_duration**: 总耗时（秒）

### 按操作类型统计

内置监控的操作类型：
- `ocr_recognize`: OCR 识别操作
- 可以添加自定义操作类型

## 性能优化建议

### 1. 识别慢查询

```python
# 找出最慢的操作
recent = monitor.get_recent_operations(100)
slow_ops = sorted(recent, key=lambda x: x['duration'], reverse=True)[:10]

for op in slow_ops:
    print(f"{op['operation']}: {op['duration']:.3f}s")
```

### 2. 监控成功率

```python
stats = monitor.get_stats()
if stats['success_rate'] < 95:
    logger.warning(f"成功率低于 95%: {stats['success_rate']:.1f}%")
```

### 3. 设置性能阈值告警

```python
def check_performance():
    ocr_stats = monitor.get_operation_stats("ocr_recognize")
    
    if ocr_stats['count'] > 0:
        avg_time = ocr_stats['avg_duration']
        if avg_time > 5.0:  # 超过 5 秒
            logger.warning(f"OCR 识别过慢: {avg_time:.3f}s")
        
        if ocr_stats['success_rate'] < 90:
            logger.warning(f"OCR 成功率过低: {ocr_stats['success_rate']:.1f}%")
```

## 最佳实践

### 1. 在关键路径添加监控

```python
# 好的做法：监控关键操作
with OperationTimer("database_query"):
    data = db.query("SELECT ...")

# 避免：过度监控
for item in small_list:
    with OperationTimer("trivial_operation"):  # 不必要
        pass
```

### 2. 添加有意义的元数据

```python
# 好的做法
with OperationTimer("file_upload", 
                   file_size=file.size,
                   file_type=file.type):
    upload(file)

# 避免：缺少上下文
with OperationTimer("upload"):
    upload(file)
```

### 3. 定期导出报告

```python
# 每天导出一次性能报告
import schedule

def daily_performance_report():
    report = monitor.export_report()
    with open(f"reports/performance_{date.today()}.txt", "w") as f:
        f.write(report)

schedule.every().day.at("23:59").do(daily_performance_report)
```

## 故障排查

### Q1: 统计数据不准确？

确保正确配对 `start_operation` 和 `end_operation`，或使用 `OperationTimer` 上下文管理器。

### Q2: 内存占用过高？

监控器默认保留最近 1000 条记录，可以通过修改 `deque(maxlen=1000)` 调整。

### Q3: 如何禁用监控？

在不需要的环境中不调用监控函数即可，或使用条件判断：

```python
if ENABLE_PERFORMANCE_MONITORING:
    with OperationTimer("my_op"):
        do_work()
else:
    do_work()
```

## 示例输出

```
============================================================
OCR-GUI-Tool 性能监控报告
生成时间: 2024-01-15 14:30:00
============================================================

总体统计:
  总操作数: 156
  平均耗时: 1.234s
  最短耗时: 0.456s
  最长耗时: 3.789s
  成功率: 98.7%
  总耗时: 192.504s

按操作类型统计:
  ocr_recognize:
    次数: 150
    平均: 1.200s
    成功率: 99.3%

最近操作:
  [✓] ocr_recognize - 1.234s - 2024-01-15T14:29:58
  [✓] ocr_recognize - 1.156s - 2024-01-15T14:29:55
  [✗] ocr_recognize - 0.001s - 2024-01-15T14:29:50
============================================================
```
