#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PySide6 Dracula PaddleOCR Edition - 独立启动脚本

使用方式:
    python run_pyside6_dracula.py

依赖安装:
    pip install PySide6
"""

import sys
import os

# 添加项目根目录到 path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)
os.chdir(project_root)

# 添加 pyside6_dracula 目录到 path（使其 modules/widgets 可以直接 import）
pyside6_dir = os.path.join(project_root, 'interfaces', 'pyside6_dracula')
sys.path.insert(0, pyside6_dir)

try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QIcon
except ImportError:
    print("=" * 50)
    print("错误: 未安装 PySide6")
    print("请运行: pip install PySide6")
    print("=" * 50)
    sys.exit(1)

from interfaces.pyside6_dracula.main import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    icon_path = os.path.join(pyside6_dir, 'icon.ico')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    window = MainWindow()
    sys.exit(app.exec())
