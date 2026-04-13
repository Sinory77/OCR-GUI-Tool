# ///////////////////////////////////////////////////////////////
#
# PyDracula PaddleOCR Edition
# 基于 PyDracula 模板 + PaddleOCR 核心
#
# ///////////////////////////////////////////////////////////////

import sys
import os
import platform
import threading

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

# IMPORT / GUI AND MODULES AND WIDGETS
# ///////////////////////////////////////////////////////////////
from modules import *
from widgets import *
os.environ["QT_FONT_DPI"] = "96" # FIX Problem for High DPI and Scale above 100%

# SET AS GLOBAL WIDGETS
# ///////////////////////////////////////////////////////////////
widgets = None

class RecognizeThread(QThread):
    """OCR 识别线程"""
    finished = pyqtSignal(dict, dict)
    progress = pyqtSignal(str)

    def __init__(self, ocr_engine, image_path):
        super().__init__()
        self.ocr_engine = ocr_engine
        self.image_path = image_path

    def run(self):
        try:
            self.progress.emit("\u8bc6\u522b\u4e2d...")
            result = self.ocr_engine.recognize(self.image_path)
            display_result = {
                'success': result.get('success', False),
                'texts': result.get('texts', []),
                'text_count': result.get('text_count', 0),
                'full_text': result.get('full_text', '')
            }
            self.finished.emit(display_result, result)
        except Exception as e:
            self.finished.emit({
                'success': False,
                'texts': [],
                'text_count': 0,
                'full_text': '',
                'error': str(e)
            }, {'code': -1, 'data': str(e)})


class MainWindow(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)

        # SET AS GLOBAL WIDGETS
        # ///////////////////////////////////////////////////////////////
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        global widgets
        widgets = self.ui

        # USE CUSTOM TITLE BAR | USE AS "False" FOR MAC OR LINUX
        # ///////////////////////////////////////////////////////////////
        Settings.ENABLE_CUSTOM_TITLE_BAR = True

        # APP NAME
        # ///////////////////////////////////////////////////////////////
        title = "PaddleOCR \u8bc6\u522b\u5de5\u5177"
        description = "\u57fa\u4e8e PaddleOCR \u7684\u56fe\u5f62\u754c\u9762\u8bc6\u522b\u5de5\u5177 - PyDracula \u98ce\u683c"
        self.setWindowTitle(title)
        widgets.titleRightInfo.setText(description)

        # OCR ENGINE STATE
        # ///////////////////////////////////////////////////////////////
        self.ocr_engine = None
        self.result_manager = None
        self.exporter = None
        self.current_image_path = None
        self.current_result = None
        self.recognize_thread = None
        self._batch_files = []
        self._batch_index = 0

        # INIT CORE MODULES
        self.init_core_modules()

        # CONNECT SIGNALS
        self._connect_signals()

        # TOGGLE MENU
        # ///////////////////////////////////////////////////////////////
        widgets.toggleButton.clicked.connect(lambda: UIFunctions.toggleMenu(self, True))

        # SET UI DEFINITIONS
        # ///////////////////////////////////////////////////////////////
        UIFunctions.uiDefinitions(self)

        # BUTTONS CLICK
        # ///////////////////////////////////////////////////////////////

        # LEFT MENUS - MAIN NAVIGATION
        widgets.btn_home.clicked.connect(self.buttonClick)
        widgets.btn_widgets.clicked.connect(self.buttonClick)
        widgets.btn_new.clicked.connect(self.buttonClick)
        widgets.btn_save.clicked.connect(self.buttonClick)

        # OCR PAGE BUTTONS
        widgets.ocr_btn_open.clicked.connect(self.open_file_dialog)
        widgets.ocr_btn_screenshot.clicked.connect(self.screenshot_recognition)
        widgets.ocr_btn_recognize.clicked.connect(self.start_recognition)
        widgets.ocr_btn_copy.clicked.connect(self.copy_result)
        widgets.ocr_btn_export.clicked.connect(self.show_export_menu)
        widgets.ocr_btn_clear.clicked.connect(self.clear_all)
        widgets.ocr_history_list.itemDoubleClicked.connect(self.view_history)

        # IMAGE DROP SUPPORT
        widgets.ocr_image_label.dragEnterEvent = self._drag_enter
        widgets.ocr_image_label.dropEvent = self._drop
        widgets.ocr_image_label.mousePressEvent = lambda e: self.open_file_dialog()

        # EXTRA LEFT BOX
        def openCloseLeftBox():
            UIFunctions.toggleLeftBox(self, True)
        widgets.toggleLeftBox.clicked.connect(openCloseLeftBox)
        widgets.extraCloseColumnBtn.clicked.connect(openCloseLeftBox)

        # EXTRA RIGHT BOX
        def openCloseRightBox():
            UIFunctions.toggleRightBox(self, True)
        widgets.settingsTopBtn.clicked.connect(openCloseRightBox)

        # INIT OCR ENGINE
        self.init_ocr_engine()

        # SHOW APP
        # ///////////////////////////////////////////////////////////////
        self.show()

        # SET OCR PAGE AS DEFAULT
        widgets.stackedWidget.setCurrentWidget(widgets.ocr_page)
        widgets.btn_home.setStyleSheet(UIFunctions.selectMenu(widgets.btn_home.styleSheet()))

        # UPDATE STATUS
        widgets.titleRightInfo.setText("\u5f00\u542f PyDracula PaddleOCR...")

    def _drag_enter(self, event):
        """拖拽进入"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def _drop(self, event):
        """拖拽放下"""
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp')):
                self.load_image(file_path)

    def _connect_signals(self):
        """连接信号"""
        pass

    def init_core_modules(self):
        """初始化核心模块"""
        try:
            from core import get_result_manager, get_exporter
            self.result_manager = get_result_manager()
            self.exporter = get_exporter()
            self.refresh_history()
        except Exception as e:
            print(f"\u521d\u59cb\u5316\u6838\u5fc3\u6a21\u5757\u5931\u8d25: {e}")

    def init_ocr_engine(self):
        """初始化 OCR \u5f15\u64ce"""
        def init_thread():
            try:
                from core import get_ocr_engine
                self.ocr_engine = get_ocr_engine()
                success = self.ocr_engine.initialize()
                if success:
                    self.update_status("\u5f15\u64ce\u5df2\u5c31\u7eea")
                else:
                    self.update_status("\u5f15\u64ce\u521d\u59cb\u5316\u5931\u8d25")
            except Exception as e:
                self.update_status(f"\u521d\u59cb\u5316\u9519\u8bef: {e}")

        threading.Thread(target=init_thread, daemon=True).start()

    def update_status(self, text):
        """更新状态栏"""
        widgets.titleRightInfo.setText(text)

    # BUTTONS CLICK
    # Post here your functions for clicked buttons
    # ///////////////////////////////////////////////////////////////
    def buttonClick(self):
        # GET BUTTON CLICKED
        btn = self.sender()
        btnName = btn.objectName()

        # SHOW OCR PAGE (主页 -> OCR 识别)
        if btnName == "btn_home":
            widgets.stackedWidget.setCurrentWidget(widgets.ocr_page)
            UIFunctions.resetStyle(self, btnName)
            btn.setStyleSheet(UIFunctions.selectMenu(btn.styleSheet()))

        # SHOW WIDGETS PAGE
        if btnName == "btn_widgets":
            widgets.stackedWidget.setCurrentWidget(widgets.widgets)
            UIFunctions.resetStyle(self, btnName)
            btn.setStyleSheet(UIFunctions.selectMenu(btn.styleSheet()))

        # SHOW NEW PAGE - HISTORY
        if btnName == "btn_new":
            widgets.stackedWidget.setCurrentWidget(widgets.new_page)
            UIFunctions.resetStyle(self, btnName)
            btn.setStyleSheet(UIFunctions.selectMenu(btn.styleSheet()))

        if btnName == "btn_save":
            # Save -> export
            self.show_export_menu()

    # RESIZE EVENTS
    # ///////////////////////////////////////////////////////////////
    def resizeEvent(self, event):
        # Update Size Grips
        UIFunctions.resize_grips(self)

    # MOUSE CLICK EVENTS
    # ///////////////////////////////////////////////////////////////
    def mousePressEvent(self, event):
        # SET DRAG POS WINDOW
        self.dragPos = event.globalPosition().toPoint()

    # ==================== OCR 功能实现 ====================

    def open_file_dialog(self):
        """打开文件对话框"""
        from PyQt6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getOpenFileName(
            self, '\u9009\u62e9\u56fe\u7247', '',
            '\u56fe\u7247\u6587\u4ef6 (*.png *.jpg *.jpeg *.bmp *.gif *.webp)'
        )
        if file_path:
            self.load_image(file_path)

    def load_image(self, file_path: str):
        """加载图片"""
        self.current_image_path = file_path
        file_name = os.path.basename(file_path)

        pixmap = QPixmap(file_path)
        if pixmap.isNull():
            self.update_status(f"\u52a0\u8f7d\u56fe\u7247\u5931\u8d25: {file_name}")
            return

        # 缩放以适应 label 大小
        scaled = pixmap.scaled(
            widgets.ocr_image_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        widgets.ocr_image_label.setPixmap(scaled)
        widgets.ocr_image_label.setText('')
        widgets.ocr_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        widgets.ocr_image_info.setText(f"\ud83d\udcc4 {file_name}")
        widgets.ocr_btn_recognize.setEnabled(True)
        widgets.ocr_result_text.clear()
        widgets.ocr_stats.setText('')
        self.current_result = None
        self.update_status(f"\u56fe\u7247\u5df2\u52a0\u8f7d: {file_name}")

    def screenshot_recognition(self):
        """截图识别"""
        self.showMinimized()
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(300, self._do_screenshot)

    def _do_screenshot(self):
        """执行截图"""
        from core import capture_screen_to_temp
        temp_path = capture_screen_to_temp()

        self.showNormal()
        self.activateWindow()

        if temp_path:
            self.load_image(temp_path)
            self.start_recognition()
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, '\u9519\u8bef', '\u622a\u56fe\u5931\u8d25')

    def start_recognition(self):
        """开始识别"""
        if not self.current_image_path:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, '\u63d0\u793a', '\u8bf7\u5148\u9009\u62e9\u56fe\u7247')
            return

        if not self.ocr_engine:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, '\u63d0\u793a', '\u5f15\u64ce\u6682\u672a\u5c31\u7eea')
            return

        widgets.ocr_btn_recognize.setEnabled(False)
        widgets.ocr_btn_open.setEnabled(False)
        self.update_status('\u8bc6\u522b\u4e2d...')
        widgets.ocr_result_text.setPlainText('\u6b63\u5728\u8bc6\u522b...')

        self.recognize_thread = RecognizeThread(self.ocr_engine, self.current_image_path)
        self.recognize_thread.finished.connect(self.on_recognize_finished)
        self.recognize_thread.start()

    def on_recognize_finished(self, result: dict, raw_result: dict):
        """识别完成回调"""
        widgets.ocr_btn_recognize.setEnabled(True)
        widgets.ocr_btn_open.setEnabled(True)
        self.current_result = result

        if self.current_image_path:
            self.add_to_history(self.current_image_path, raw_result)

        if result.get('success') and result.get('texts'):
            texts = result['texts']
            full_text = '\n'.join(texts)
            widgets.ocr_result_text.setPlainText(full_text)
            widgets.ocr_stats.setText(f'\u5171\u8bc6\u522b {result["text_count"]} \u4e2a\u6587\u672c\u533a\u57df')
            self.update_status('\u8bc6\u522b\u5b8c\u6210')
            widgets.ocr_btn_export.setEnabled(True)
            widgets.ocr_btn_copy.setEnabled(True)
        else:
            error_msg = result.get('error', '\u672a\u8bc6\u522b\u5230\u6587\u5b57')
            widgets.ocr_result_text.setPlainText(f'\u8bc6\u522b\u5931\u8d25: {error_msg}')
            widgets.ocr_stats.setText('')
            self.update_status('\u8bc6\u522b\u5931\u8d25')

    def clear_all(self):
        """清空所有"""
        self.current_image_path = None
        self.current_result = None
        widgets.ocr_image_label.setText('\n\n\n\u62d6\u62fd\u56fe\u7247\u5230\u6b64\u5904\n\u6216\u70b9\u51fb\u9009\u62e9\u6587\u4ef6\n\n\n')
        widgets.ocr_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        widgets.ocr_image_info.setText('\u672a\u52a0\u8f7d\u56fe\u7247')
        widgets.ocr_result_text.clear()
        widgets.ocr_stats.setText('')
        widgets.ocr_btn_recognize.setEnabled(False)
        widgets.ocr_btn_export.setEnabled(False)
        widgets.ocr_btn_copy.setEnabled(False)
        self.update_status('\u5df2\u6e05\u7a7a')
        self._batch_files = []
        self._batch_index = 0

    def copy_result(self):
        """复制结果"""
        text = widgets.ocr_result_text.toPlainText().strip()
        if text:
            from PyQt6.QtGui import QGuiApplication
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(text)
            self.update_status('\u5df2\u590d\u5236\u5230\u526a\u8d34\u677f')
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, '\u63d0\u793a', '\u6ca1\u6709\u53ef\u590d\u5236\u7684\u5185\u5bb9')

    def show_export_menu(self):
        """显示导出菜单"""
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtCore import QPoint
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: rgb(44, 49, 58);
                color: rgb(221, 221, 221);
                border: 1px solid rgb(68, 71, 90);
                border-radius: 8px;
                padding: 5px;
            }
            QMenu::item {
                padding: 10px 25px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: rgb(189, 147, 249, 60);
            }
        """)
        txt_action = menu.addAction('\ud83d\udcc4 \u5bfc\u51fa\u4e3a TXT')
        json_action = menu.addAction('\ud83d\udccb \u5bfc\u51fa\u4e3a JSON')
        excel_action = menu.addAction('\ud83d\udcca \u5bfc\u51fa\u4e3a Excel')

        action = menu.exec(widgets.ocr_btn_export.mapToGlobal(QPoint(0, widgets.ocr_btn_export.height())))
        if action == txt_action:
            self.export_results('TXT')
        elif action == json_action:
            self.export_results('JSON')
        elif action == excel_action:
            self.export_results('Excel')

    def export_results(self, format_type: str):
        """导出结果"""
        if not self.current_result:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, '\u63d0\u793a', '\u6ca1\u6709\u53ef\u5bfc\u51fa\u7684\u7ed3\u679c')
            return

        from datetime import datetime
        from PyQt6.QtWidgets import QMessageBox

        ext_map = {'TXT': '.txt', 'JSON': '.json', 'Excel': '.xlsx'}
        ext = ext_map.get(format_type, '.txt')

        if self.current_image_path:
            img_name = os.path.splitext(os.path.basename(self.current_image_path))[0]
        else:
            img_name = 'ocr_result'

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{img_name}_{timestamp}{ext}"

        if self.current_image_path:
            output_dir = os.path.dirname(self.current_image_path)
        else:
            output_dir = '.'

        try:
            from core import get_exporter
            exporter = get_exporter()

            if isinstance(self.current_result, dict) and 'texts' in self.current_result:
                result_for_export = {'success': True, 'texts': self.current_result['texts']}
            else:
                result_for_export = self.current_result

            result_path = exporter.export(result_for_export, format_type, filename, output_dir)

            if result_path:
                self.update_status(f'\u5df2\u5bfc\u51fa\u5230: {os.path.basename(result_path)}')
                QMessageBox.information(self, '\u6210\u529f', f'\u5df2\u5bfc\u51fa\u5230:\n{result_path}')
            else:
                QMessageBox.warning(self, '\u9519\u8bef', '\u5bfc\u51fa\u5931\u8d25')
        except Exception as e:
            QMessageBox.critical(self, '\u9519\u8bef', f'\u5bfc\u51fa\u65f6\u51fa\u9519:\n{str(e)}')

    def add_to_history(self, image_path: str, result: dict):
        """添加到历史记录"""
        if self.result_manager and self.exporter:
            self.result_manager.add_result(image_path, result)
            self.exporter.add_result(image_path, result)
            self.refresh_history()

    def refresh_history(self):
        """刷新历史记录"""
        if not self.result_manager:
            return
        widgets.ocr_history_list.clear()
        history = self.result_manager.get_history()
        for entry in history:
            status = "\u2713" if entry.get('success') else "\u2717"
            time_str = entry.get('time', '')[-8:]
            filename = entry.get('filename', '\u672a\u77e5')
            widgets.ocr_history_list.addItem(f"{time_str} {status} {filename}")

    def view_history(self):
        """查看历史记录"""
        current_row = widgets.ocr_history_list.currentRow()
        if current_row < 0:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, '\u63d0\u793a', '\u8bf7\u5148\u9009\u62e9\u4e00\u6761\u5386\u53f2\u8bb0\u5f55')
            return

        history = self.result_manager.get_history()
        index = len(history) - 1 - current_row
        if 0 <= index < len(history):
            entry = history[index]
            self.current_image_path = entry.get('path')

            if entry.get('success'):
                result_text = entry.get('text', '')
                widgets.ocr_result_text.setPlainText(result_text)
                widgets.ocr_stats.setText(f'\u5171 {len(entry.get("full_texts", []))} \u884c')
                widgets.ocr_btn_copy.setEnabled(True)
                widgets.ocr_btn_export.setEnabled(True)
                self.current_result = {'texts': entry.get('full_texts', []), 'success': True}
                self.update_status(f'\u5df2\u52a0\u8f7d\u5386\u53f2: {entry.get("filename", "\u672a\u77e5")}')

                # 加载历史图片
                if self.current_image_path and os.path.exists(self.current_image_path):
                    pixmap = QPixmap(self.current_image_path)
                    if not pixmap.isNull():
                        scaled = pixmap.scaled(
                            widgets.ocr_image_label.size(),
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        widgets.ocr_image_label.setPixmap(scaled)
                        widgets.ocr_image_label.setText('')
                        widgets.ocr_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                        widgets.ocr_image_info.setText(f"\ud83d\udcc4 {entry.get('filename', '')}")
                        widgets.ocr_btn_recognize.setEnabled(True)
            else:
                widgets.ocr_result_text.setPlainText('\u8bc6\u522b\u5931\u8d25')
                widgets.ocr_stats.setText('')


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("icon.ico"))
    window = MainWindow()
    sys.exit(app.exec())
