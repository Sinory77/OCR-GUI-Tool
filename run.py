"""
OCR GUI Tool - Fluent Design 快速启动脚本
IDE中直接运行此文件即可启动程序，无需命令行参数
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

# 依赖检查
try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from qfluentwidgets import setTheme, Theme
except ImportError as e:
    print(f"[错误] 缺少必要的依赖库: {e}")
    print("请运行: pip install PySide6 qfluentwidgets")
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
