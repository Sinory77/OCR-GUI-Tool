"""最小化测试"""
import sys
import os
sys.path.insert(0, r"c:/Users/Sinory/Desktop/测试用/识别工具/OCR-GUI-Tool")

print("Importing QApplication...")
from PySide6.QtWidgets import QApplication
print("OK")

print("Creating app...")
app = QApplication([])
print("OK")

print("Importing FluentWindow...")
from qfluentwidgets import FluentWindow
print("OK")

print("Creating FluentWindow...")
win = FluentWindow()
print("OK")

print("Importing OCRPage...")
from interfaces.fluent.pages.ocr_page import OCRPage
print("OK")

print("Creating OCRPage...")
page = OCRPage()
print("OCRPage created!")

page.setObjectName("test_page")
print("Set objectName!")

win.addSubInterface(page, None, "Test")
print("Added to window!")

win.show()
print("Showing window...")
sys.exit(app.exec())
