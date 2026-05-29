# 项目记忆 — OCR-GUI-Tool

> 从 `.workbuddy/memory/` 合并迁移，整合关键架构决策、技术约定与开发历史。
> 最后更新: 2026-05-29

---

## 项目概况

- **名称**: OCR-GUI-Tool
- **定位**: 基于 PaddleOCR-json 的桌面 OCR 批量识别工具
- **技术栈**: Python 3.13+ / PySide6 / qfluentwidgets / pandas / openpyxl
- **仓库**: https://github.com/Sinory77/OCR-GUI-Tool

---

## 四层架构

```
界面层 (UI Layer)
    ↓ 调用接口
CoreAPI (纯接口层)
    ↓ 提交任务
TaskManager (统一调度层)
    ↓ 调度执行
执行器 (核心功能层)
    ↓ 返回结果 → TaskManager → CoreAPI → UI
```

**铁律**: 核心层完全不操作界面代码，只执行功能、推送信息。UI 层只通过 API 调用，不包含业务逻辑。

---

## 推送机制（2026-05-22）

核心模块主动推送变更通知（Push），非 UI 轮询（Pull）。

| 机制 | 用途 | 生命周期 |
|------|------|---------|
| API 回调 | 请求→响应 | 任务结束即销毁 |
| EventBus | 自发推送 | 持续存在 |

事件频道: `engine:status`, `engine:event`, `result:event`, `template:event`

---

## 功能模块

### OCR 引擎 (`core/ocr_engine.py`)
- 引擎: PaddleOCR-json，通过 stdin/stdout 通信
- **不可修改**: `api/PPOCR_api.py`（官方接口）

### 导出 (`core/exporter.py`)
- 格式: TXT / JSON / Excel
- Excel: openpyxl write_only 模式提升大文件性能

### 模板管理 (`core/template_manager.py`)
- 基于模板的结构化字段提取
- 模板持久化: JSON 文件存储

### Excel 数据透视 (`core/excel_processor.py`)
- CleanRule / PivotConfig / LoadedTable 数据模型
- DataFrame 线程安全传递: JSON orient='split'
- 大表渲染: QAbstractTableModel 虚拟滚动

### 检疫证查询 (`core/cert_query.py`) — 2026-05-29 新增
- 调用 scahi.org.cn API 查询动物检疫合格证明
- 7 种证书类型: 动物A证 / A证外省 / B证 / 产品A证 / A证外省 / B证 / 产品证
- 请求必须带 Referer + 浏览器 User-Agent + Accept header

---

## 引擎生命周期

### 优雅关闭
1. 向 stdin 写入 `exit\n`（官方推荐方式）
2. 等待最多 5 秒
3. 超时后 `taskkill /F /T` 强杀

### 紧急清理
`atexit` / `sys.excepthook` / 信号触发 → `emergency_cleanup()` → `taskkill /F /T`

### 关闭标志
`_shutting_down` / `_global_shutting_down` 防止重试逻辑在关闭期间重启引擎。

---

## UI 约定

- 框架: qfluentwidgets，严格按官方 Demo 风格
- StateToolTip: `setState(True)` 自动淡出，无需手动 close
- ListWidget: 禁用 `ItemIsDragEnabled` 避免阻塞双击信号
- 日志: `TimedRotatingFileHandler` 按天滚动 7 天，`logs/runtime.log`

---

## 用户偏好

- 语言: 简体中文
- 修改代码前必须说明改动，获授权后执行
- 三方接口文件（如 PPOCR_api.py）禁止修改
- 复杂功能先讨论架构方案
- 日志查文件，控制台最小化输出

---

## 开发历史要点

### 2026-05-27
- StateToolTip 不消失修复: `_on_ocr_complete` 直接操作实例 + `setState(True)`
- result_manager.py 抽取 `_set_cache()` 统一缓存写入入口

### 2026-05-28
- 文件列表双击识别修复: 移除 `ItemIsDragEnabled` 标志
- 重新解析修复: 缓存数据结构解包 `cached.get('result', {})`
- 导出格式修复: "EXCEL" → "Excel"，按钮文字同步
- 历史记录-缓存同步: `clear_history()` 清理缓存

### 2026-05-29
- 检疫证查询页面实现
- API 473 错误: 需要 Referer + User-Agent + Accept 三个 header
- 类型3（B证）字段扩展到 24 个，处理不同证书类型的数据结构差异
- 耳标号发现: 网站 JS 对 EarTags 做排序+区间压缩，标签为"畜禽标识号"
