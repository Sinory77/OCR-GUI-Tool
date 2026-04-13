# PaddleOCR-json GUI Tool
# 统一入口 - 支持选择界面类型
#
# 使用方式:
#   python main.py               # 默认 Tkinter 界面
#   python main.py --ui tkinter # Tkinter 界面
#   python main.py --ui web     # pywebview Web 界面

import sys
import os
import argparse

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)
os.chdir(project_root)


def run_tkinter():
    """运行 Tkinter 界面"""
    from interfaces.tkinter_ui import main as tkinter_main
    tkinter_main()


def run_web():
    """运行 pywebview Web 界面"""
    try:
        import webview
    except ImportError:
        print("错误: 运行 Web 界面需要安装 pywebview")
        print("运行: pip install pywebview")
        print()
        print("或者使用 Tkinter 界面: python main.py --ui tkinter")
        sys.exit(1)

    from interfaces.web_ui import main as web_main
    web_main()


def run_pyqt6():
    """运行 PyQt6 界面"""
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        print("错误: 运行 PyQt6 界面需要安装 PyQt6")
        print("运行: pip install PyQt6")
        print()
        print("或者使用 Tkinter 界面: python main.py --ui tkinter")
        sys.exit(1)

    from interfaces.pyqt6_ui.qt6_ui import MainWindow

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


def run_pydracula():
    """运行 PyQt6 界面（与 --ui pyqt6 相同）"""
    run_pyqt6()


def run_pyside6():
    """运行 PySide6 Dracula 风格界面"""
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("错误: 运行 PySide6 界面需要安装 PySide6")
        print("运行: pip install PySide6")
        sys.exit(1)

    pyside6_dir = os.path.join(project_root, 'interfaces', 'pyside6_dracula')
    sys.path.insert(0, pyside6_dir)

    from interfaces.pyside6_dracula.main import MainWindow

    app = QApplication(sys.argv)
    window = MainWindow()
    sys.exit(app.exec())


def run_fluent():
    """运行 Fluent Design 风格界面"""
    try:
        from PySide6.QtWidgets import QApplication
        from qfluentwidgets import setTheme, Theme
    except ImportError:
        print("错误: 运行 Fluent 界面需要安装 PySide6 和 PySide6-Fluent-Widgets")
        print("运行: pip install PySide6 PySide6-Fluent-Widgets")
        sys.exit(1)

    from qfluentwidgets.common import setFont
    from interfaces.fluent.main_window import MainWindow as FluentMainWindow

    app = QApplication(sys.argv)

    # 设置应用信息
    app.setApplicationName("OCR 识别工具")
    app.setApplicationVersion("2.0.0")

    # 跟随系统主题
    setTheme(Theme.AUTO)

    window = FluentMainWindow()
    sys.exit(app.exec())


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='PaddleOCR-json 识别工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python main.py              # 使用 Tkinter 界面（默认）
  python main.py --ui tkinter # 使用 Tkinter 界面
  python main.py --ui web     # 使用 pywebview Web 界面
  python main.py --ui pyqt6   # 使用 PyQt6 界面
  python main.py --ui pyside6 # 使用 PySide6 界面
  python main.py --ui fluent  # 使用 Fluent Design 界面（推荐）

注意: Web 界面需要安装 pywebview，PyQt6/PySide6 界面需要安装对应依赖
      Fluent 界面需要安装 PySide6 和 PySide6-Fluent-Widgets


"""
    )

    parser.add_argument(
        '--ui',
        choices=['tkinter', 'web', 'pyqt6', 'pyside6', 'fluent'],
        default='tkinter',
        help='选择界面类型: tkinter, web, pyqt6, pyside6 或 fluent (默认: tkinter)'
    )

    args = parser.parse_args()

    if args.ui == 'web':
        print("启动 Web 界面...")
        run_web()
    elif args.ui == 'pyqt6':
        print("启动 PyQt6 界面...")
        run_pyqt6()
    elif args.ui == 'pyside6':
        print("启动 PySide6 界面...")
        run_pyside6()
    elif args.ui == 'fluent':
        print("启动 Fluent Design 界面...")
        run_fluent()
    else:
        print("启动 Tkinter 界面...")
        run_tkinter()


if __name__ == "__main__":
    main()
