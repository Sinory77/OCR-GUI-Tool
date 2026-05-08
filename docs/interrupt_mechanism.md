# -*- coding: utf-8 -*-
"""
OCR-GUI-Tool 中断机制完善说明文档

## 概述

本文档说明 OCR-GUI-Tool 项目中的中断机制设计与实现。

## 当前中断机制分析

### 1. 中断流程

```
UI层 -> 工作线程 -> OCR引擎 -> 响应中断
```

### 2. 当前实现

- **UI层**: `btn_cancel.clicked` -> `_cancel_recognition` -> `worker.requestInterruption()`
- **工作线程**: `isInterruptionRequested()` 检查中断标志
- **OCR引擎**: `is_interrupted()` 回调函数检查中断状态

### 3. 状态管理

中断状态通过 QThread 的 `requestInterruption()` 和 `isInterruptionRequested()` 管理：

```python
# 请求中断
worker.requestInterruption()

# 检查中断状态（在工作线程中）
if worker.isInterruptionRequested():
    # 处理中断
    return
```

## 完善后的中断机制

### 1. 线程安全的 UI 更新

- 使用 `QTimer.singleShot` 确保 UI 操作在主线程执行
- 避免直接跨线程操作 UI 组件

```python
# 错误示例（跨线程操作）
self.state_tooltip.show()

# 正确示例
QTimer.singleShot(0, lambda: self.state_tooltip.show())
```

### 2. 改进的中断检查

- 在所有长时间操作中增加中断检查点
- 使用回调函数模式确保中断状态及时传递

```python
def recognition_with_interrupt(self, callback):
    for i, image in enumerate(images):
        if self.isInterruptionRequested():
            return
        result = self.process_image(image)
        callback(result)
```

### 3. 状态管理优化

- 使用锁保护共享状态变量
- 明确区分不同的中断状态

## 使用场景

### 批量识别中断

1. 用户点击"中断"按钮
2. 设置中断标志
3. 当前任务完成后停止
4. 清理状态，返回列表视图

### 界面响应

中断操作不应阻塞 UI 线程，所有耗时操作都应在工作线程中执行。

## 注意事项

1. **及时检查**: 在循环中定期检查中断状态
2. **清理资源**: 中断时确保释放已分配的资源
3. **状态同步**: UI 状态应与实际中断状态保持一致

## 总结

中断机制设计要点：

1. ✅ 所有 StateToolTip 操作都在主线程中执行
2. ✅ 使用信号槽机制确保线程安全
3. ✅ 在关键位置增加了中断检查点
4. ✅ 避免了跨线程的 UI 操作
5. ✅ 实现了软中断（等待当前任务完成后停止后续任务）

中断机制现已稳定可靠，可正常用于批量识别等长时间操作的中断控制。
