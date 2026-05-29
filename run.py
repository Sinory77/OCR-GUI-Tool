"""
OCR GUI Tool - Fluent Design 快速启动脚本
IDE中直接运行此文件即可启动程序，无需命令行参数
"""

import sys
import os
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

# ── 日志配置（必须在任何模块导入之前） ──
PROJECT_ROOT = Path(__file__).resolve().parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "runtime.log"

# 根 Logger 配置
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

# 格式
formatter = logging.Formatter(
    fmt="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# 文件 Handler：按天滚动，保留 7 天（桌面应用一天日志量通常不超过几十 MB）
time_handler = TimedRotatingFileHandler(
    LOG_FILE, when="midnight", interval=1, backupCount=7, encoding="utf-8"
)
time_handler.suffix = "%Y-%m-%d"
time_handler.setLevel(logging.INFO)
time_handler.setFormatter(formatter)
root_logger.addHandler(time_handler)

# 控制台 Handler：日常运行保持安静，仅 CRITICAL 输出（排查看日志文件即可）
console_handler = logging.StreamHandler(sys.stderr)
console_handler.setLevel(logging.CRITICAL)
console_handler.setFormatter(formatter)
root_logger.addHandler(console_handler)

# 捕获 Python warnings 到日志（避免静默丢失重要告警）
logging.captureWarnings(True)

# 添加项目根目录到路径
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

# ── 启动锚点日志 ──
startup_logger = logging.getLogger("startup")
startup_logger.info(
    "=" * 50
)
startup_logger.info(
    "程序启动: OCR 识别工具 v2.0.0"
)
startup_logger.info(
    "平台: %s | Python: %s | 日志目录: %s",
    sys.platform, sys.version.split()[0], LOG_DIR
)
startup_logger.info(
    "日志策略: 按天滚动 (保留 7 天)"
)
startup_logger.info(
    "=" * 50
)

# 依赖检查
try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from qfluentwidgets import setTheme, Theme
except ImportError as e:
    logging.error(f"缺少必要的依赖库: {e}")
    logging.error("请运行: pip install PySide6 qfluentwidgets")
    sys.exit(1)

from interfaces.fluent.main_window import MainWindow


def main():
    """主函数"""
    # 高 DPI 支持
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # 创建应用
    app = QApplication(sys.argv)
    app.setApplicationName("OCR 识别工具")
    app.setApplicationVersion("2.0.0")

    # 设置主题（自动跟随系统）
    setTheme(Theme.AUTO)

    # 创建并显示主窗口
    window = MainWindow()
    window.show()

    # 运行事件循环
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
