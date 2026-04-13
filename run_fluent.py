"""
OCR GUI Tool - Fluent Design 风格启动脚本
基于 PySide6 + qfluentwidgets 构建
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from qfluentwidgets import setTheme, Theme, setFont

from interfaces.fluent.main_window import MainWindow


def main():
    """主函数"""
    # 启用高 DPI 缩放
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # 创建应用
    app = QApplication(sys.argv)

    # 设置应用属性
    app.setApplicationName("OCR 识别工具")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("OCR-GUI-Tool")

    # 设置主题
    setTheme(Theme.AUTO)

    # 设置字体
    setFont(app)

    # 创建并显示主窗口
    window = MainWindow()
    window.show()

    # 运行应用
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
