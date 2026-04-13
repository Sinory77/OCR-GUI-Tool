"""逐步调试 MainWindow"""
import sys
import os
sys.path.insert(0, r"c:/Users/Sinory/Desktop/测试用/识别工具/OCR-GUI-Tool")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from qfluentwidgets import setTheme, Theme

print("1. Setting theme...")
setTheme(Theme.AUTO)

print("2. Creating app...")
app = QApplication(sys.argv)

try:
    print("3. Importing MainWindow...")
    from interfaces.fluent.main_window import MainWindow

    print("4. Creating MainWindow instance...")
    window = MainWindow()

    print("5. Showing window...")
    window.show()

    print("6. Starting exec...")
    sys.exit(app.exec())
except Exception as e:
    print(f"Exception: {e}")
    import traceback
    traceback.print_exc()
