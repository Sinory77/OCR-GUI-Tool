# PyQt6 主界面

import os
import threading
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QFileDialog, QMessageBox,
    QSplitter, QFrame, QStatusBar, QMenuBar, QMenu, QListWidget, QListWidgetItem,
    QGraphicsOpacityEffect, QGraphicsDropShadowEffect, QComboBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve, QRect, QRectF, QPoint, QEvent, QTimer
from PyQt6.QtGui import QPixmap, QDragEnterEvent, QDropEvent, QFont, QAction, QPainter, QPen, QColor, QRegion, QCursor, QPainterPath, QBrush
from PyQt6.QtGui import QGuiApplication


class RecognizeThread(QThread):
    """OCR 识别线程"""
    finished = pyqtSignal(dict, dict)  # (display_result, raw_result)

    def __init__(self, ocr_engine, image_path):
        super().__init__()
        self.ocr_engine = ocr_engine
        self.image_path = image_path

    def run(self):
        try:
            result = self.ocr_engine.recognize(self.image_path)
            # 原始结果用于历史记录
            raw_result = result
            # 简化结果用于显示
            display_result = {
                'success': result.get('success', False),
                'texts': result.get('texts', []),
                'text_count': result.get('text_count', 0),
                'full_text': result.get('full_text', '')
            }
            self.finished.emit(display_result, raw_result)
        except Exception as e:
            self.finished.emit({
                'success': False,
                'texts': [],
                'text_count': 0,
                'full_text': '',
                'error': str(e)
            }, {
                'code': -1,
                'data': str(e)
            })


class RoundedMenu(QMenu):
    """真正的圆角弹出菜单 - 继承 QMenu 方案"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Popup)
        self.radius = 12
        
        # 添加阴影效果
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)        # 模糊程度
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 50))  # 半透明黑
        self.setGraphicsEffect(shadow)
        
    def paintEvent(self, event):
        """绘制圆角背景"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 圆角背景
        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), self.radius, self.radius)
        
        # 绘制边框
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QColor("#e0e0e0"))
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), self.radius, self.radius)
        
        # 保留原生绘制
        super().paintEvent(event)


class ImageDropWidget(QLabel):
    """支持拖拽图片的组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setMinimumSize(200, 200)
        self._set_placeholder()

    def _set_placeholder(self):
        self.setText('\n\n\n📁\n\n拖拽图片到此处\n或点击选择文件\n\n\n')
        self.setStyleSheet('''
            QLabel {
                border: 2px dashed #ccc;
                border-radius: 10px;
                background-color: white;
                color: #888;
                font-size: 14px;
            }
            QLabel:hover {
                border-color: #007bff;
                background-color: #f0f7ff;
            }
        ''')

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet('''
                QLabel {
                    border: 2px dashed #007bff;
                    border-radius: 10px;
                    background-color: #f0f7ff;
                    color: #007bff;
                    font-size: 14px;
                }
            ''')

    def dragLeaveEvent(self, event):
        self._set_placeholder()

    def dropEvent(self, event: QDropEvent):
        self._set_placeholder()
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp')):
                self.parent().load_image(file_path)


class MainWindow(QMainWindow):
    """主窗口"""
    
    # 子线程更新 UI 的信号
    sig_load_image = pyqtSignal(str)      # 加载图片
    sig_update_status = pyqtSignal(str, str)  # 更新状态 (text, color)
    sig_add_to_history = pyqtSignal(str, dict)  # 添加历史记录
    sig_refresh_history = pyqtSignal()    # 刷新历史列表
    sig_batch_complete = pyqtSignal()     # 批量处理完成
    sig_batch_started = pyqtSignal(list)  # 批量处理开始 (文件列表)
    sig_batch_progress = pyqtSignal(int, int)  # 批量处理进度 (当前索引, 总数)

    def __init__(self):
        super().__init__()
        self.ocr_engine = None
        self.result_manager = None
        self.exporter = None
        self.current_image_path = None
        self.current_result = None  # 当前识别结果，用于导出
        self.recognize_thread = None
        self._batch_count = 0  # 批量处理计数器
        self._batch_files = []  # 批量文件列表
        self._batch_index = 0  # 当前处理索引
        self.setup_ui()
        self._connect_ui_signals()
        self.init_core_modules()
        self.init_ocr_engine()

    def _connect_ui_signals(self):
        """连接 UI 更新信号"""
        self.sig_load_image.connect(self._load_image_slot)
        self.sig_update_status.connect(self._update_status_slot)
        self.sig_add_to_history.connect(self._add_to_history_slot)
        self.sig_refresh_history.connect(self._refresh_history_slot)
        self.sig_batch_complete.connect(self._batch_complete_slot)
        self.sig_batch_started.connect(self._batch_started_slot)
        self.sig_batch_progress.connect(self._batch_progress_slot)

    def setup_ui(self):
        self.setWindowTitle('PaddleOCR 识别工具 v2.0')
        self.setMinimumSize(900, 650)
        self.resize(1000, 750)

        # 创建菜单栏
        self._create_menu_bar()

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # 内容区域
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # 左侧面板
        left_panel = self._create_left_panel()
        # 右侧面板
        right_panel = self._create_right_panel()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setSizes([600, 380])

        content_layout.addWidget(splitter)
        main_layout.addWidget(content, 1)

        # 工具栏
        toolbar = self._create_toolbar()
        main_layout.addWidget(toolbar)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage('就绪')

    def _create_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 10, 0)

        # 图片预览区域
        preview_title = QLabel('图片预览')
        preview_title.setFont(QFont('Microsoft YaHei', 10, QFont.Weight.Bold))
        layout.addWidget(preview_title)

        self.image_label = ImageDropWidget(self)
        self.image_label.mousePressEvent = lambda e: self.open_file_dialog()
        layout.addWidget(self.image_label)

        # 图片信息
        self.image_info_label = QLabel('未加载图片')
        self.image_info_label.setStyleSheet('''
            QLabel {
                padding: 8px;
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 5px;
                font-size: 12px;
                color: #666;
            }
        ''')
        layout.addWidget(self.image_info_label)

        # 文件列表标题
        list_title_layout = QHBoxLayout()
        self.list_title = QLabel('文件列表')
        self.list_title.setFont(QFont('Microsoft YaHei', 10, QFont.Weight.Bold))
        self.list_title.hide()  # 默认隐藏
        list_title_layout.addWidget(self.list_title)
        list_title_layout.addStretch()
        layout.addLayout(list_title_layout)

        # 文件列表
        self.batch_file_list = QListWidget()
        self.batch_file_list.setStyleSheet('''
            QListWidget {
                border: 1px solid #dee2e6;
                border-radius: 5px;
                background-color: white;
                font-size: 12px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-bottom: 1px solid #f0f0f0;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
            }
            QListWidget::item:disabled {
                color: #999;
            }
        ''')
        self.batch_file_list.hide()  # 默认隐藏
        layout.addWidget(self.batch_file_list)

        return panel

    def _create_right_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 0, 0, 0)

        # 上半部分：识别结果
        result_group = QWidget()
        result_layout = QVBoxLayout(result_group)
        result_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel('识别结果')
        title.setFont(QFont('Microsoft YaHei', 10, QFont.Weight.Bold))
        result_layout.addWidget(title)

        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText('识别结果将显示在这里')
        self.result_text.setStyleSheet('''
            QTextEdit {
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 15px;
                background-color: #f8f9fa;
                font-family: "Microsoft YaHei";
                font-size: 13px;
            }
        ''')
        result_layout.addWidget(self.result_text, 1)

        self.stats_label = QLabel('')
        self.stats_label.setStyleSheet('''
            QLabel {
                padding: 8px;
                background-color: #e9ecef;
                border-radius: 5px;
                font-size: 12px;
                color: #666;
            }
        ''')
        result_layout.addWidget(self.stats_label)
        layout.addWidget(result_group, 2)

        # 下半部分：历史记录
        history_group = QWidget()
        history_layout = QVBoxLayout(history_group)
        history_layout.setContentsMargins(0, 10, 0, 0)

        history_title = QLabel('历史记录')
        history_title.setFont(QFont('Microsoft YaHei', 10, QFont.Weight.Bold))
        history_layout.addWidget(history_title)

        # 历史记录列表
        self.history_list = QListWidget()
        self.history_list.setStyleSheet('''
            QListWidget {
                border: 1px solid #dee2e6;
                border-radius: 5px;
                background-color: white;
                font-size: 12px;
            }
        ''')
        self.history_list.itemDoubleClicked.connect(self.view_history)
        history_layout.addWidget(self.history_list, 1)

        # 历史记录按钮
        history_btn_layout = QHBoxLayout()
        history_btn_layout.setContentsMargins(0, 5, 0, 0)

        self.btn_view_history = QPushButton('查看')
        self.btn_view_history.setStyleSheet('''
            QPushButton {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 3px;
                padding: 4px 12px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #e2e6ea; }
        ''')
        self.btn_view_history.clicked.connect(self.view_history)
        history_btn_layout.addWidget(self.btn_view_history)

        self.btn_delete_history = QPushButton('删除')
        self.btn_delete_history.setStyleSheet(self.btn_view_history.styleSheet())
        self.btn_delete_history.clicked.connect(self.delete_history)
        history_btn_layout.addWidget(self.btn_delete_history)

        self.btn_clear_history = QPushButton('清空')
        self.btn_clear_history.setStyleSheet(self.btn_view_history.styleSheet())
        self.btn_clear_history.clicked.connect(self.clear_history)
        history_btn_layout.addWidget(self.btn_clear_history)

        history_layout.addLayout(history_btn_layout)
        layout.addWidget(history_group, 1)

        return panel

    def _create_toolbar(self) -> QWidget:
        toolbar = QWidget()
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(0, 5, 0, 0)

        # 打开图片按钮
        self.btn_open = QPushButton('📂 打开图片')
        self.btn_open.setStyleSheet('''
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #0056b3; }
        ''')
        self.btn_open.clicked.connect(self.open_file_dialog)
        layout.addWidget(self.btn_open)

        # 开始识别按钮
        self.btn_recognize = QPushButton('🔍 开始识别')
        self.btn_recognize.setStyleSheet('''
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #218838; }
            QPushButton:disabled { background-color: #cccccc; }
        ''')
        self.btn_recognize.clicked.connect(self.start_recognition)
        self.btn_recognize.setEnabled(False)
        layout.addWidget(self.btn_recognize)

        # 批量选择按钮
        self.btn_batch = QPushButton('📁 批量选择')
        self.btn_batch.setStyleSheet('''
            QPushButton {
                background-color: #6f42c1;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #5a3d91; }
        ''')
        self.btn_batch.clicked.connect(self.batch_select_images)
        layout.addWidget(self.btn_batch)

        # 截图识别按钮
        self.btn_screenshot = QPushButton('🖼️ 截图识别')
        self.btn_screenshot.setStyleSheet('''
            QPushButton {
                background-color: #fd7e14;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #e8630a; }
        ''')
        self.btn_screenshot.clicked.connect(self.screenshot_recognition)
        layout.addWidget(self.btn_screenshot)

        # 清空按钮
        self.btn_clear = QPushButton('🗑️ 清空')
        self.btn_clear.setStyleSheet('''
            QPushButton {
                background-color: #f8f9fa;
                color: #343a40;
                border: 1px solid #dee2e6;
                border-radius: 5px;
                padding: 8px 16px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #e2e6ea; }
        ''')
        self.btn_clear.clicked.connect(self.clear_all)
        layout.addWidget(self.btn_clear)

        # 复制到剪贴板按钮
        self.btn_copy = QPushButton('📋 复制')
        self.btn_copy.setStyleSheet('''
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #5a6268; }
            QPushButton:disabled { background-color: #cccccc; }
        ''')
        self.btn_copy.clicked.connect(self.copy_result)
        self.btn_copy.setEnabled(False)
        layout.addWidget(self.btn_copy)

        # 语言选择（使用自定义按钮 + 圆角菜单）
        from core import LANGUAGES
        self.current_language = "简体中文"
        
        self.language_btn = QPushButton('🌐 简体中文')
        self.language_btn.setStyleSheet('''
            QPushButton {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 13px;
                font-family: "Microsoft YaHei";
                color: #495057;
                text-align: left;
                min-width: 120px;
            }
            QPushButton:hover {
                border-color: #007bff;
                background-color: white;
            }
        ''')
        
        # 语言选择圆角菜单
        self.language_menu = RoundedMenu(self)
        self.language_menu.setStyleSheet('''
            QMenu {
                background-color: white;
            }
        ''')
        
        for lang in LANGUAGES.keys():
            action = QAction(lang, self)
            action.triggered.connect(lambda checked, l=lang: self._on_language_selected(l))
            self.language_menu.addAction(action)
        
        self.language_btn.setMenu(self.language_menu)
        layout.addWidget(self.language_btn)
        layout.addStretch()

        # 导出按钮
        self.btn_export = QPushButton('💾 导出结果')
        self.btn_export.setStyleSheet('''
            QPushButton {
                background-color: #17a2b8;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #138496; }
            QPushButton:disabled { background-color: #cccccc; }
        ''')
        self.btn_export.setEnabled(False)
        layout.addWidget(self.btn_export)

        # 导出圆角菜单
        self.export_menu = RoundedMenu(self)
        
        action1 = QAction('📄 导出为 TXT', self)
        action1.triggered.connect(lambda: self.export_results('TXT'))
        self.export_menu.addAction(action1)
        
        action2 = QAction('📋 导出为 JSON', self)
        action2.triggered.connect(lambda: self.export_results('JSON'))
        self.export_menu.addAction(action2)
        
        action3 = QAction('📊 导出为 Excel', self)
        action3.triggered.connect(lambda: self.export_results('Excel'))
        self.export_menu.addAction(action3)
        
        # 点击按钮显示菜单
        self.btn_export.clicked.connect(self.show_export_menu)

        layout.addStretch()
        self.status_label = QLabel('就绪')
        self.status_label.setStyleSheet('color: #666; font-size: 13px;')
        layout.addWidget(self.status_label)

        return toolbar

    def _on_language_selected(self, language: str):
        """语言选择回调"""
        self.language_btn.setText(f'🌐 {language}')
        self.on_language_changed(language)

    def _create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu('文件')

        open_action = QAction('打开图片...', self)
        open_action.setShortcut('Ctrl+O')
        open_action.triggered.connect(self.open_file_dialog)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        # 导出子菜单 - 使用圆角样式
        export_menu = QMenu('导出结果', self)
        export_menu.setStyleSheet('''
            QMenu {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 12px;
                padding: 8px 4px;
            }
            QMenu::item {
                padding: 10px 24px;
                font-size: 14px;
                border-radius: 6px;
                margin: 2px 4px;
            }
            QMenu::item:selected {
                background-color: #f0f4f8;
            }
            QMenu::separator {
                height: 1px;
                background-color: #f0f0f0;
                margin: 4px 12px;
            }
        ''')

        export_txt_action = QAction('📄 导出为 TXT', self)
        export_txt_action.triggered.connect(lambda: self.export_results('TXT'))
        export_menu.addAction(export_txt_action)

        export_json_action = QAction('📋 导出为 JSON', self)
        export_json_action.triggered.connect(lambda: self.export_results('JSON'))
        export_menu.addAction(export_json_action)

        export_excel_action = QAction('📊 导出为 Excel', self)
        export_excel_action.triggered.connect(lambda: self.export_results('Excel'))
        export_menu.addAction(export_excel_action)

        file_menu.addMenu(export_menu)

        file_menu.addSeparator()

        exit_action = QAction('退出', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 编辑菜单
        edit_menu = menubar.addMenu('编辑')

        copy_action = QAction('复制结果', self)
        copy_action.setShortcut('Ctrl+C')
        copy_action.triggered.connect(self.copy_result)
        edit_menu.addAction(copy_action)

        clear_action = QAction('清空结果', self)
        clear_action.triggered.connect(self.clear_results)
        edit_menu.addAction(clear_action)

    def export_results(self, format_type):
        """导出识别结果 - 自动导出到图片同目录"""
        if not self.current_result:
            QMessageBox.information(self, '提示', '没有可导出的结果')
            return

        from datetime import datetime

        # 根据格式类型设置扩展名
        ext_map = {'TXT': '.txt', 'JSON': '.json', 'Excel': '.xlsx'}
        ext = ext_map.get(format_type, '.txt')

        # 生成文件名：图片名_时间戳
        if self.current_image_path:
            img_name = os.path.splitext(os.path.basename(self.current_image_path))[0]
        else:
            img_name = 'ocr_result'

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{img_name}_{timestamp}{ext}"

        # 导出到图片同目录
        if self.current_image_path:
            output_dir = os.path.dirname(self.current_image_path)
        else:
            output_dir = '.'

        try:
            from core import get_exporter
            exporter = get_exporter()

            # 将当前结果转换为兼容格式
            if isinstance(self.current_result, dict) and 'texts' in self.current_result:
                result_for_export = {
                    'success': True,
                    'texts': self.current_result['texts']
                }
            else:
                result_for_export = self.current_result

            result_path = exporter.export(result_for_export, format_type, filename, output_dir)

            if result_path:
                self.status_bar.showMessage(f'已导出到: {result_path}')
                QMessageBox.information(self, '成功', f'已导出到:\n{result_path}')
            else:
                QMessageBox.warning(self, '错误', '导出失败')
        except Exception as e:
            QMessageBox.critical(self, '错误', f'导出时出错:\n{str(e)}')

    def init_core_modules(self):
        """初始化核心模块"""
        from core import get_result_manager, get_exporter
        self.result_manager = get_result_manager()
        self.exporter = get_exporter()
        self.sig_refresh_history.emit()

    # ==================== UI 信号槽 ====================
    def _load_image_slot(self, file_path: str):
        """加载图片槽函数"""
        self.current_image_path = file_path
        file_name = os.path.basename(file_path)

        pixmap = QPixmap(file_path)
        if pixmap.isNull():
            self.status_label.setText('图片加载失败')
            return

        scaled_pixmap = pixmap.scaled(
            self.image_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.image_label.setPixmap(scaled_pixmap)
        self.image_label.setText('')

        self.image_info_label.setText(f'已加载: {file_name}')
        self.btn_recognize.setEnabled(True)
        self.result_text.clear()
        self.stats_label.setText('')

    def _update_status_slot(self, text: str, color: str = '#666'):
        """更新状态槽函数"""
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f'color: {color}; font-size: 13px;')

    def _add_to_history_slot(self, image_path: str, result: dict):
        """添加到历史记录槽函数"""
        if not self.result_manager or not self.exporter:
            return
        self.result_manager.add_result(image_path, result)
        self.exporter.add_result(image_path, result)
        # 刷新历史列表
        self._refresh_history_slot()

    def _refresh_history_slot(self):
        """刷新历史列表槽函数"""
        if not self.result_manager:
            return
        self.history_list.clear()
        history = self.result_manager.get_history()
        for entry in history:
            status = "✓" if entry.get('success') else "✗"
            time_str = entry.get('time', '')[-8:]
            filename = entry.get('filename', '未知')
            display_text = f"{time_str} {status} {filename}"
            self.history_list.addItem(display_text)

    def _batch_started_slot(self, file_list: list):
        """批量处理开始槽函数"""
        self._batch_files = file_list
        self._batch_index = 0
        
        # 显示文件列表
        self.batch_file_list.clear()
        self.batch_file_list.show()
        self.list_title.show()
        
        for i, path in enumerate(file_list):
            filename = os.path.basename(path)
            item = QListWidgetItem(f"○ {filename}")
            item.setData(Qt.ItemDataRole.UserRole, path)  # 保存完整路径
            if i == 0:
                item.setFont(QFont('Microsoft YaHei', 12, QFont.Weight.Bold))
            self.batch_file_list.addItem(item)

    def _batch_progress_slot(self, current_index: int, total: int):
        """批量处理进度更新槽函数"""
        if not self._batch_files or current_index >= len(self._batch_files):
            return
        
        # 更新当前文件状态为处理中（高亮）
        current_item = self.batch_file_list.item(current_index)
        if current_item:
            filename = os.path.basename(self._batch_files[current_index])
            current_item.setText(f"🔄 {filename}")
            current_item.setFont(QFont('Microsoft YaHei', 12, QFont.Weight.Bold))
            self.batch_file_list.scrollToItem(current_item)
        
        # 将上一个文件标记为完成
        if current_index > 0:
            prev_item = self.batch_file_list.item(current_index - 1)
            if prev_item:
                filename = os.path.basename(self._batch_files[current_index - 1])
                prev_item.setText(f"✓ {filename}")
                prev_item.setFont(QFont('Microsoft YaHei', 12))

    def _batch_complete_slot(self):
        """批量处理完成槽函数"""
        self._batch_count = 0
        
        # 标记最后一个文件为完成
        if self._batch_files and self._batch_index < len(self._batch_files):
            last_item = self.batch_file_list.item(self._batch_index)
            if last_item:
                filename = os.path.basename(self._batch_files[self._batch_index])
                last_item.setText(f"✓ {filename}")
                last_item.setFont(QFont('Microsoft YaHei', 12))
        
        self.sig_update_status.emit('批量处理完成', '#28a745')

    def init_ocr_engine(self):
        """初始化 OCR 引擎"""
        def init_thread():
            from core import get_ocr_engine
            self.ocr_engine = get_ocr_engine()
            success = self.ocr_engine.initialize()
            if success:
                self.sig_update_status.emit('引擎已就绪', '#28a745')
            else:
                self.sig_update_status.emit('引擎初始化失败', '#dc3545')

        threading.Thread(target=init_thread, daemon=True).start()

    def show_export_menu(self):
        """显示导出圆角菜单"""
        pos = self.btn_export.mapToGlobal(self.btn_export.rect().bottomLeft())
        self.export_menu.popup(pos)

    def open_file_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            '选择图片',
            '',
            '图片文件 (*.png *.jpg *.jpeg *.bmp *.gif *.webp)'
        )
        if file_path:
            self.load_image(file_path)

    def batch_select_images(self):
        """批量选择图片"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            '批量选择图片',
            '',
            '图片文件 (*.png *.jpg *.jpeg *.bmp *.gif *.webp)'
        )
        if file_paths:
            self.process_batch(file_paths)

    def process_batch(self, image_paths):
        """批量处理图片"""
        if not image_paths:
            return

        self._batch_count = len(image_paths)

        def process_thread():
            # 先发送批量开始信号，显示文件列表
            self.sig_batch_started.emit(image_paths)

            for i, path in enumerate(image_paths):
                # 使用信号更新进度（0-based index）
                self.sig_batch_progress.emit(i, len(image_paths))
                
                # 使用信号更新状态
                self.sig_update_status.emit(f'处理中: {i+1}/{len(image_paths)}', '#007bff')

                # 使用信号加载图片（主线程执行）
                self.sig_load_image.emit(path)

                # 更新当前索引
                self._batch_index = i

                # 识别
                if self.ocr_engine:
                    result = self.ocr_engine.recognize(path)
                    # 使用信号添加到历史记录（主线程执行）
                    if result:
                        self.sig_add_to_history.emit(path, result)

                # 最后一张完成后刷新历史列表
                if i == len(image_paths) - 1:
                    self.sig_refresh_history.emit()
                    self.sig_batch_complete.emit()

        threading.Thread(target=process_thread, daemon=True).start()

    def screenshot_recognition(self):
        """截图识别"""
        # 最小化窗口
        self.showMinimized()

        # 延迟执行截图，等待窗口最小化
        QTimer.singleShot(300, self._do_screenshot)

    def _do_screenshot(self):
        """执行截图"""
        from core import capture_screen_to_temp
        temp_path = capture_screen_to_temp()

        # 恢复窗口
        self.showNormal()
        self.activateWindow()

        if temp_path:
            self.load_image(temp_path)
            # 自动开始识别
            self.start_recognition()
        else:
            QMessageBox.warning(self, '错误', '截图失败')

    def on_language_changed(self, language: str):
        """切换语言"""
        if language == self.current_language:
            return

        self.current_language = language
        self.sig_update_status.emit(f'正在切换到 {language}...', '#007bff')

        def switch_thread():
            from core import get_ocr_engine, reset_ocr_engine
            reset_ocr_engine(language=language)
            self.ocr_engine = get_ocr_engine()
            success = self.ocr_engine.initialize()

            if success:
                self.sig_update_status.emit(f'已切换到 {language}', '#28a745')
            else:
                self.sig_update_status.emit('语言切换失败', '#dc3545')

        threading.Thread(target=switch_thread, daemon=True).start()

    def load_image(self, file_path: str):
        """加载图片"""
        self.current_image_path = file_path
        file_name = os.path.basename(file_path)

        pixmap = QPixmap(file_path)
        if pixmap.isNull():
            self.status_label.setText('图片加载失败')
            return

        scaled_pixmap = pixmap.scaled(
            self.image_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.image_label.setPixmap(scaled_pixmap)
        self.image_label.setText('')

        self.image_info_label.setText(f'已加载: {file_name}')
        self.btn_recognize.setEnabled(True)
        self.status_label.setText('图片已加载')
        self.result_text.clear()
        self.stats_label.setText('')

    def start_recognition(self):
        """开始识别"""
        if not self.current_image_path:
            QMessageBox.warning(self, '提示', '请先选择图片')
            return

        if not self.ocr_engine:
            QMessageBox.warning(self, '提示', '引擎尚未初始化完成')
            return

        self.btn_recognize.setEnabled(False)
        self.btn_open.setEnabled(False)
        self.status_label.setText('识别中...')
        self.status_label.setStyleSheet('color: #007bff; font-size: 13px;')
        self.result_text.setHtml('<p style="color:#888;">正在识别...</p>')

        self.recognize_thread = RecognizeThread(self.ocr_engine, self.current_image_path)
        self.recognize_thread.finished.connect(self.on_recognize_finished)
        self.recognize_thread.start()

    def on_recognize_finished(self, result: dict, raw_result: dict):
        """识别完成回调"""
        self.btn_recognize.setEnabled(True)
        self.btn_open.setEnabled(True)

        # 保存结果用于导出
        self.current_result = result

        # 添加到历史记录
        self.add_to_history(self.current_image_path, raw_result)

        if result.get('success') and result.get('texts'):
            texts = result['texts']
            html = ''
            for i, text in enumerate(texts, 1):
                safe_text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                html += f'<p style="padding:8px 12px;margin:5px 0;background:white;border-left:3px solid #007bff;border-radius:3px;">{i}. {safe_text}</p>'

            self.result_text.setHtml(html)
            self.stats_label.setText(f'共识别 {result["text_count"]} 个文本区域')
            self.status_label.setText('识别完成')
            self.status_label.setStyleSheet('color: #28a745; font-size: 13px;')
            # 启用导出按钮
            self.btn_export.setEnabled(True)
            # 启用复制按钮
            self.btn_copy.setEnabled(True)
        else:
            error_msg = result.get('error', '未识别到文字')
            if result.get('error'):
                self.result_text.setHtml(f'<p style="color:#dc3545;">识别失败: {error_msg}</p>')
            else:
                self.result_text.setHtml('<p style="color:#888;">未识别到文字</p>')
            self.stats_label.setText('')
            self.status_label.setText('识别失败')
            self.status_label.setStyleSheet('color: #dc3545; font-size: 13px;')

    def clear_all(self):
        """清空所有"""
        self.current_image_path = None
        self.current_result = None
        self.image_label._set_placeholder()
        self.image_info_label.setText('未加载图片')
        self.result_text.clear()
        self.stats_label.setText('')
        self.btn_recognize.setEnabled(False)
        self.btn_export.setEnabled(False)
        self.btn_copy.setEnabled(False)
        self.status_label.setText('已清空')
        self.status_label.setStyleSheet('color: #666; font-size: 13px;')
        # 清空批量文件列表
        self.batch_file_list.clear()
        self.batch_file_list.hide()
        self.list_title.hide()
        self._batch_files = []
        self._batch_index = 0

    def copy_result(self):
        """复制识别结果到剪贴板"""
        text = self.result_text.toPlainText().strip()
        if text:
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(text)
            self.status_bar.showMessage('已复制到剪贴板')
        else:
            QMessageBox.information(self, '提示', '没有可复制的内容')

    def clear_results(self):
        """清空识别结果"""
        self.result_text.clear()
        self.stats_label.setText('')
        self.btn_export.setEnabled(False)
        self.btn_copy.setEnabled(False)

    def add_to_history(self, image_path, result):
        """添加到历史记录 - 调用 core 模块"""
        if not self.result_manager or not self.exporter:
            return
        self.result_manager.add_result(image_path, result)
        self.exporter.add_result(image_path, result)
        self.refresh_history_list()

    def refresh_history_list(self):
        """刷新历史列表"""
        if not self.result_manager:
            return
        self.history_list.clear()
        history = self.result_manager.get_history()
        for entry in history:
            status = "✓" if entry.get('success') else "✗"
            time_str = entry.get('time', '')[-8:]  # 只显示时间部分
            filename = entry.get('filename', '未知')
            display_text = f"{time_str} {status} {filename}"
            self.history_list.addItem(display_text)

    def view_history(self):
        """查看/加载历史记录到结果区域"""
        current_row = self.history_list.currentRow()
        if current_row < 0:
            QMessageBox.information(self, '提示', '请先选择一条历史记录')
            return

        history = self.result_manager.get_history()
        # 历史列表是从新到旧显示的，所以索引要反转
        index = len(history) - 1 - current_row
        if 0 <= index < len(history):
            entry = history[index]
            # 加载历史记录到当前结果区域
            self.current_image_path = entry.get('path')
            self.current_result = {'texts': entry.get('full_texts', []), 'success': entry.get('success', False)}

            if entry.get('success'):
                result_text = entry.get('text', '')
                # 显示到结果区域
                self.result_text.setPlainText(result_text)
                self.stats_label.setText(f'共 {len(entry.get("full_texts", []))} 行')
                # 启用复制和导出按钮
                self.btn_copy.setEnabled(True)
                self.btn_export.setEnabled(True)
                self.status_bar.showMessage(f'已加载历史记录: {entry.get("filename", "未知")}')
            else:
                self.result_text.setPlainText('识别失败')
                self.stats_label.setText('')
                self.btn_copy.setEnabled(False)
                self.btn_export.setEnabled(False)
                self.status_bar.showMessage('该记录识别失败')

    def delete_history(self):
        """删除历史记录"""
        current_row = self.history_list.currentRow()
        if current_row < 0:
            QMessageBox.information(self, '提示', '请先选择一条历史记录')
            return

        history = self.result_manager.get_history()
        index = len(history) - 1 - current_row
        if self.result_manager.delete_history(index):
            self.refresh_history_list()

    def clear_history(self):
        """清空历史记录"""
        if QMessageBox.question(self, '确认', '确定要清空历史记录吗？') == QMessageBox.StandardButton.Yes:
            if self.result_manager:
                self.result_manager.clear_history()
            from core import reset_exporter
            reset_exporter()
            self.refresh_history_list()
            self.status_bar.showMessage('历史记录已清空')

    def resizeEvent(self, event):
        """窗口大小改变时重新调整图片"""
        super().resizeEvent(event)
        if self.current_image_path and self.image_label.pixmap():
            pixmap = QPixmap(self.current_image_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    self.image_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.image_label.setPixmap(scaled)
