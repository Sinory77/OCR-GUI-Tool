"""测试 MainWindow"""
import sys
import os
import traceback
sys.path.insert(0, r"c:/Users/Sinory/Desktop/测试用/识别工具/OCR-GUI-Tool")

try:
    print("Importing QApplication...")
    from PySide6.QtWidgets import QApplication
    print("OK")

    print("Setting theme...")
    from qfluentwidgets import setTheme, Theme, setFont
    setTheme(Theme.AUTO)
    print("OK")

    print("Creating app...")
    app = QApplication(sys.argv)
    print("OK")

    print("Creating MainWindow...")
    window = __import__('interfaces.fluent.main_window', fromlist=['MainWindow']).MainWindow()
    print("MainWindow created!")

    print("Showing...")
    window.show()
    print("Starting exec...")
    sys.exit(app.exec())
except Exception as e:
    print(f"Exception: {e}")
    traceback.print_exc()
