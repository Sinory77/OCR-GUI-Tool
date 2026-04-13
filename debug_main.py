"""调试 MainWindow"""
import sys
import os
sys.path.insert(0, r"c:/Users/Sinory/Desktop/测试用/识别工具/OCR-GUI-Tool")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from qfluentwidgets import setTheme, Theme

print("Setting up...")
setTheme(Theme.AUTO)

print("Creating app...")
app = QApplication(sys.argv)

print("Creating MainWindow...")
window = __import__('interfaces.fluent.main_window', fromlist=['MainWindow']).MainWindow()

print("Showing window...")
window.show()

print("Starting exec...")
sys.exit(app.exec())
