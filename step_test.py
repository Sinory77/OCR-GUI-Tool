"""测试 MainWindow 分步"""
import sys
import os
sys.path.insert(0, r"c:/Users/Sinory/Desktop/测试用/识别工具/OCR-GUI-Tool")

print("1. Importing...")
from PySide6.QtWidgets import QApplication
from qfluentwidgets import setTheme, Theme
setTheme(Theme.AUTO)

app = QApplication(sys.argv)
print("2. App created")

print("3. Importing FluentWindow...")
from qfluentwidgets import FluentWindow, NavigationItemPosition, FluentIcon as FIF
print("OK")

print("4. Creating FluentWindow...")
win = FluentWindow()
print("OK")

print("5. Importing pages...")
from interfaces.fluent.pages.ocr_page import OCRPage
from interfaces.fluent.pages.history_page import HistoryPage
from interfaces.fluent.pages.settings_page import SettingsPage
print("OK")

print("6. Creating OCRPage...")
ocr_page = OCRPage(win)
print("OK")

print("7. Creating HistoryPage...")
history_page = HistoryPage(win)
print("OK")

print("8. Creating SettingsPage...")
settings_page = SettingsPage(win)
print("OK")

print("9. Adding subinterfaces...")
win.addSubInterface(ocr_page, FIF.VIEW, "文字识别")
win.addSubInterface(history_page, FIF.HISTORY, "识别历史")
win.addSubInterface(settings_page, FIF.SETTING, "设置")
print("OK")

print("10. Showing window...")
win.show()
print("OK")

print("Starting exec (this will block)...")
sys.exit(app.exec())
