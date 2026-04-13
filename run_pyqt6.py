# PyQt6 界面独立入口
# 直接运行此文件即可启动 PyQt6 界面

import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)
os.chdir(project_root)

from PyQt6.QtWidgets import QApplication
from interfaces.pyqt6_ui.qt6_ui import MainWindow

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
