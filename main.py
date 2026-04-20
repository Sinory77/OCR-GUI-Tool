# PaddleOCR-json GUI Tool
# Fluent Design 主入口
#
# 使用方式:
#   python main.py              # 启动 Fluent 界面
#   python run.py               # 快速启动（推荐用于IDE调试）

import sys
import os

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)
os.chdir(project_root)


def main():
    """主函数 - 启动 Fluent Design 界面"""
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt
        from qfluentwidgets import setTheme, Theme
    except ImportError as e:
        print(f"[错误] 缺少必要的依赖库: {e}")
        print("请运行: pip install PySide6 qfluentwidgets")
        sys.exit(1)

    from interfaces.fluent.main_window import MainWindow

    # 高 DPI 支持
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # 创建应用
    app = QApplication(sys.argv)
    app.setApplicationName("OCR 识别工具")
    app.setApplicationVersion("2.0.0")

    # 跟随系统主题
    setTheme(Theme.AUTO)

    # 创建并显示主窗口
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
