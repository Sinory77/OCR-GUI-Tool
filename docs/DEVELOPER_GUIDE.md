# 开发者指南

## 目录

- [开发环境设置](#开发环境设置)
- [项目结构](#项目结构)
- [代码规范](#代码规范)
- [测试指南](#测试指南)
- [贡献流程](#贡献流程)
- [常见问题](#常见问题)

---

## 开发环境设置

### 1. 克隆仓库

```bash
git clone https://github.com/Sinory77/OCR-GUI-Tool.git
cd OCR-GUI-Tool
```

### 2. 创建虚拟环境

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 3. 安装依赖

```bash
# 生产依赖
pip install -r requirements.txt

# 开发依赖（包含测试和代码质量工具）
pip install -r requirements-dev.txt
```

### 4. 验证安装

```bash
# 运行测试
pytest tests/ -v

# 检查代码格式
black --check core/ tests/

# 类型检查
mypy core/ --ignore-missing-imports
```

---

## 项目结构

```
OCR-GUI-Tool/
├── core/                    # 核心业务逻辑层
│   ├── __init__.py
│   ├── config.py           # 配置管理
│   ├── ocr_engine.py       # OCR 引擎封装
│   ├── screenshot.py       # 截图功能
│   ├── result_manager.py   # 结果与历史管理
│   ├── exporter.py         # 导出功能
│   ├── template_manager.py # 模板管理器
│   ├── text_parser.py      # 文本解析器
│   ├── async_worker.py     # 异步工作线程
│   ├── deduplication.py    # 去重功能
│   ├── error_handler.py    # 错误处理
│   └── enhanced_error_handler.py  # 增强错误处理
│
├── interfaces/              # 界面层
│   └── fluent/             # Fluent Design UI
│       ├── main_window.py
│       ├── ui_utils.py
│       ├── ui_config.py
│       ├── error_ui.py
│       ├── components/
│       │   └── screenshot_window.py
│       └── pages/
│           ├── ocr_page.py
│           ├── history_page.py
│           ├── template_page.py
│           └── settings_page.py
│
├── api/                     # API 接口层
│   ├── __init__.py
│   ├── PPOCR_api.py
│   ├── core_api.py
│   └── ocr_api.py
│
├── api_server/              # API 服务端（可选）
│   ├── main.py
│   ├── adapter.py
│   ├── client.py
│   ├── routes/
│   ├── services/
│   ├── tasks/
│   └── utils/
│
├── tests/                   # 单元测试
│   ├── test_config.py
│   ├── test_result_manager.py
│   ├── test_exporter.py
│   ├── test_error_handler.py
│   ├── test_error_ui.py
│   └── test_data_*.txt
│
├── templates/               # 解析模板
│   └── *.json
│
├── config/                  # 配置目录
│   ├── config.json
│   └── ui_config.json
│
├── docs/                    # 文档
│
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
└── README.md
```

### 架构原则

1. **分层架构**: Core 层不依赖任何 UI 框架
2. **单一职责**: 每个模块只负责一个功能领域
3. **依赖注入**: 通过参数传递依赖，避免硬编码
4. **接口隔离**: 提供清晰的公共 API，隐藏实现细节

---

## 代码规范

### 1. 命名规范

```python
# 类名：大驼峰命名法 (PascalCase)
class ResultManager:
    pass

# 函数和变量：小写 + 下划线
def get_config_value():
    my_variable = 42

# 常量：全大写 + 下划线
MAX_RETRY_COUNT = 3
DEFAULT_LANGUAGE = "简体中文"

# 私有成员：前导下划线
def _internal_helper():
    pass
```

### 2. 类型注解

所有公共函数和方法必须添加类型注解：

```python
from typing import Dict, List, Optional, Any

def process_data(
    items: List[str],
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, int]:
    """处理数据并返回统计信息"""
    return {"count": len(items)}
```

### 3. 文档字符串

使用 Google 风格的 docstring：

```python
def calculate_score(value: float, max_value: float) -> float:
    """
    计算标准化分数
    
    Args:
        value: 原始值
        max_value: 最大值
        
    Returns:
        0-100 之间的标准化分数
        
    Raises:
        ValueError: 当 max_value <= 0 时
    """
    if max_value <= 0:
        raise ValueError("max_value must be positive")
    return (value / max_value) * 100
```

### 4. 错误处理

```python
import logging

logger = logging.getLogger(__name__)

def risky_operation():
    """执行可能有风险的操作"""
    try:
        result = do_something()
        logger.info("操作成功")
        return result
    except FileNotFoundError as e:
        logger.error(f"文件未找到: {e}")
        return None
    except Exception as e:
        logger.error(f"操作失败: {e}", exc_info=True)
        raise
```

### 5. 日志记录

```python
import logging

logger = logging.getLogger(__name__)

# 不同级别的使用
logger.debug("调试信息：变量值 x=%s", x)
logger.info("一般信息：用户登录")
logger.warning("警告：配置文件不存在，使用默认值")
logger.error("错误：数据库连接失败")
logger.critical("严重：系统资源不足")
```

### 6. 代码格式化

使用 Black 自动格式化：

```bash
# 检查格式
black --check core/ tests/

# 自动格式化
black core/ tests/
```

使用 isort 排序导入：

```bash
isort core/ tests/
```

---

## 测试指南

### 1. 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试文件
pytest tests/test_config.py -v

# 运行特定测试函数
pytest tests/test_config.py::TestConfigManager::test_singleton_pattern -v

# 生成覆盖率报告
pytest tests/ --cov=core --cov-report=html
```

### 2. 编写测试

```python
import pytest
from unittest.mock import patch, MagicMock

class TestMyFeature:
    @pytest.fixture
    def setup_data(self):
        """测试夹具"""
        return {"key": "value"}
    
    def test_basic_functionality(self, setup_data):
        """基本功能测试"""
        assert setup_data["key"] == "value"
    
    @patch('module.external_api_call')
    def test_with_mock(self, mock_api):
        """使用 mock 的测试"""
        mock_api.return_value = {"status": "success"}
        result = my_function()
        assert result["status"] == "success"
```

### 3. 测试覆盖目标

- **配置管理**: 90%+ 覆盖率
- **结果管理**: 85%+ 覆盖率
- **导出功能**: 80%+ 覆盖率
- **OCR 引擎**: 75%+ 覆盖率

---

## 贡献流程

### 1. Fork 仓库

在 GitHub 上 fork 项目到你的账户。

### 2. 创建特性分支

```bash
git checkout -b feature/your-feature-name
```

分支命名规范：
- `feature/xxx`: 新功能
- `bugfix/xxx`: Bug 修复
- `docs/xxx`: 文档更新
- `refactor/xxx`: 代码重构

### 3. 提交更改

```bash
git add .
git commit -m "feat: add new export format support"
```

提交消息规范（Conventional Commits）：
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式（不影响功能）
- `refactor`: 代码重构
- `test`: 测试相关
- `chore`: 构建过程或辅助工具变动

### 4. 推送到远程

```bash
git push origin feature/your-feature-name
```

### 5. 创建 Pull Request

1. 确保所有测试通过
2. 更新相关文档
3. 在 PR 中描述变更内容和原因
4. 等待代码审查

---

## 常见问题

### Q1: 如何添加新的页面？

1. 在 `interfaces/fluent/pages/` 下创建新页面
2. 在 `main_window.py` 的 `initNavigation()` 中注册
3. 连接必要的信号

### Q2: 如何调试 OCR 引擎问题？

```python
import logging
logging.basicConfig(level=logging.DEBUG)

from core.ocr_engine import get_ocr_engine

engine = get_ocr_engine()
# 查看详细日志输出
result = engine.recognize("test.png")
```

### Q3: 如何处理配置冲突？

配置文件位于 `config/config.json`，如果遇到问题：

1. 删除 `config/config.json`（会自动重建）
2. 检查路径是否正确
3. 使用 UI 设置页面重新配置

### Q4: 性能优化建议

1. **避免重复初始化**: 使用全局实例获取函数
2. **批量处理**: 使用 `ResultExporter` 批量导出
3. **异步操作**: UI 层使用 QThread 处理耗时操作
4. **缓存**: 配置和模板都有内置缓存

---

## 开发工具推荐

### IDE
- **VS Code**: 轻量级，丰富的插件生态
- **PyCharm**: 专业的 Python IDE

### VS Code 扩展
- Python
- Pylance
- Black Formatter
- isort
- GitLens

### 调试技巧

```python
# 在代码中设置断点
import pdb; pdb.set_trace()

# 或使用 Python 3.7+
breakpoint()
```

---

## 发布流程

### 1. 版本号规范

遵循语义化版本 (SemVer)：`MAJOR.MINOR.PATCH`

- **MAJOR**: 不兼容的 API 变更
- **MINOR**: 向后兼容的功能新增
- **PATCH**: 向后兼容的问题修正

### 2. 发布步骤

```bash
# 1. 更新版本号
# 在合适的位置更新版本号

# 2. 运行所有测试
pytest tests/ -v

# 3. 创建标签
git tag -a v2.1.0 -m "Release version 2.1.0"

# 4. 推送标签
git push origin v2.1.0
```

---

## 联系方式

- **Issues**: [GitHub Issues](https://github.com/Sinory77/OCR-GUI-Tool/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Sinory77/OCR-GUI-Tool/discussions)

感谢你的贡献！
