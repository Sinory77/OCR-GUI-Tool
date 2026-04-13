"""测试脚本"""
import sys
import os
sys.path.insert(0, r"c:/Users/Sinory/Desktop/测试用/识别工具/OCR-GUI-Tool")

try:
    from PySide6.QtWidgets import QApplication
    from interfaces.fluent.pages.ocr_page import OCRPage, OCRWorker
    
    print("Imports OK")
    
    app = QApplication([])
    page = OCRPage()
    print("OCRPage created OK")
    
    # 测试 worker
    worker = OCRWorker(None, "test.png")
    print("OCRWorker created OK")
    
    print("All tests passed!")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
