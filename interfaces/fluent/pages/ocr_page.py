"""
OCR 识别页面
支持拖拽/选择图片、OCR识别、结果显示、复制和导出
"""

import os
import tempfile
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFileDialog, QMessageBox,
    QMenu, QFrame, QListWidget, QListWidgetItem,
    QAbstractItemView, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractScrollArea
)
from qfluentwidgets import TextBrowser, IndeterminateProgressBar, TableWidget
from PySide6.QtCore import Qt, Signal, QThread, QSize, QTimer
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QPixmap
from qfluentwidgets import (
    CardWidget, PrimaryPushButton, PushButton,
    ComboBox, MessageDialog, InfoBar, InfoBarPosition,
    StateToolTip, SubtitleLabel, BodyLabel,
    setTheme, Theme, RoundMenu, Action, DropDownPushButton
)
from qfluentwidgets.common.icon import FluentIcon
from PySide6.QtGui import QPainter, QColor, QPen


def _create_status_dot(color: str) -> 'QPixmap':
    """创建指定颜色的圆点图标"""
    pixmap = QPixmap(16, 16)
    pixmap.fill(QColor(0, 0, 0, 0))  # 透明背景
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(QPen(QColor(color).darker(130), 1))
    painter.drawEllipse(2, 2, 12, 12)
    painter.end()
    
    return pixmap


def _get_file_thumbnail(file_path: str, size: int = 60) -> 'QPixmap':
    """获取文件缩略图"""
    pixmap = QPixmap(file_path)
    if pixmap.isNull():
        # 返回占位图
        placeholder = QPixmap(size, size)
        placeholder.fill(QColor(200, 200, 200))
        return placeholder
    return pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)


class DropArea(QFrame):
    """拖放区域组件"""
    
    # 信号：文件路径 或 文件路径列表
    file_dropped = Signal(str)  # 单个文件
    folder_dropped = Signal(list)  # 文件夹内的图片列表
    
    # 支持的图片扩展名
    IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp', '.tiff', '.tif'}
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(280)
        self.setMinimumWidth(400)
        
        # 默认样式 - 虚线边框
        self.setStyleSheet("""
            QFrame {
                background-color: rgba(240, 240, 240, 0.5);
                border: 2px dashed #aaa;
                border-radius: 8px;
            }
        """)
    
    def _is_image_file(self, file_path: str) -> bool:
        """检查文件是否是图片"""
        ext = os.path.splitext(file_path)[1].lower()
        return ext in self.IMAGE_EXTENSIONS
    
    def _scan_folder_for_images(self, folder_path: str) -> list:
        """扫描文件夹获取所有图片文件（由父组件控制是否递归）"""
        # 通过父组件获取配置
        scan_subdirs = True
        parent = self.parent()
        while parent:
            if hasattr(parent, 'config'):
                scan_subdirs = parent.config.get_scan_subdirs()
                break
            parent = parent.parent()
        
        image_files = []
        
        if scan_subdirs:
            # 递归扫描子目录
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    if self._is_image_file(file_path):
                        image_files.append(file_path)
        else:
            # 仅扫描当前目录
            for file in os.listdir(folder_path):
                file_path = os.path.join(folder_path, file)
                if os.path.isfile(file_path) and self._is_image_file(file_path):
                    image_files.append(file_path)
        
        return sorted(image_files)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """拖拽进入"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet("""
                QFrame {
                    background-color: rgba(0, 120, 212, 0.1);
                    border: 2px dashed #0078d4;
                    border-radius: 8px;
                }
            """)
    
    def dragLeaveEvent(self, event):
        """拖拽离开"""
        self.setStyleSheet("""
            QFrame {
                background-color: rgba(240, 240, 240, 0.5);
                border: 2px dashed #aaa;
                border-radius: 8px;
            }
        """)
    
    def dropEvent(self, event: QDropEvent):
        """放下文件或文件夹（支持多文件拖入）"""
        self.setStyleSheet("""
            QFrame {
                background-color: rgba(240, 240, 240, 0.5);
                border: 2px dashed #aaa;
                border-radius: 8px;
            }
        """)
        
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if not urls:
                return
            
            all_images = []
            has_folder = False
            
            for url in urls:
                path = url.toLocalFile()
                
                if os.path.isdir(path):
                    # 文件夹：扫描其中的图片
                    has_folder = True
                    images = self._scan_folder_for_images(path)
                    all_images.extend(images)
                elif self._is_image_file(path):
                    # 单个图片文件
                    all_images.append(path)
            
            # 去重并排序
            all_images = sorted(set(all_images))
            
            if not all_images:
                InfoBar.warning(
                    title="未找到图片",
                    content="拖入的文件中没有找到图片文件",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self.parent().parent()
                )
                return
            
            # 只有一个图片文件 → 预览模式
            if len(all_images) == 1 and not has_folder:
                self.file_dropped.emit(all_images[0])
            else:
                # 多个文件或包含文件夹 → 列表模式
                self.folder_dropped.emit(all_images)
            
            event.acceptProposedAction()


class OCRWorker(QThread):
    """OCR 识别工作线程 - 直接复用主线程 OCR 实例"""
    finished = Signal(dict)
    error = Signal(str)
    
    def __init__(self, ocr_engine, image_path):
        super().__init__()
        self.ocr_engine = ocr_engine
        self.image_path = image_path
    
    def run(self):
        try:
            # 直接使用已初始化的 OCR 实例（线程安全）
            result = self.ocr_engine.recognize(self.image_path)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class BatchOCRWorker(QThread):
    """批量 OCR 识别工作线程 - 复用主线程 OCR 实例"""
    progress = Signal(int, int, str)  # 当前进度, 总数, 当前文件名
    finished_one = Signal(str, dict)  # 文件路径, 识别结果
    finished_all = Signal(list)  # 所有结果列表
    error = Signal(str)
    
    def __init__(self, ocr_engine, file_paths):
        super().__init__()
        self.ocr_engine = ocr_engine
        self.file_paths = file_paths
    
    def run(self):
        results = []
        total = len(self.file_paths)
        
        for i, file_path in enumerate(self.file_paths):
            try:
                self.progress.emit(i + 1, total, os.path.basename(file_path))
                result = self.ocr_engine.recognize(file_path)
                
                # 提取纯文本（已在 recognize 中处理）
                texts = result.get("texts", [])
                result["texts"] = texts
                result["success"] = result["code"] == 100
                
                results.append({
                    'path': file_path,
                    'result': result
                })
                self.finished_one.emit(file_path, result)
            except Exception as e:
                self.error.emit(f"{os.path.basename(file_path)}: {str(e)}")
        
        self.finished_all.emit(results)


class OCRPage(QWidget):
    """OCR 识别页面"""
    
    ocr_completed = Signal(str)  # 识别完成信号，传递图片路径
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.current_image_path = None
        self.ocr_result = None
        self.worker = None
        
        # 批量模式
        self.batch_file_paths = []  # 当前批量文件列表
        self.is_batch_mode = False
        self._last_selected_index = -1  # 记录上次选中的索引
        
        # 获取配置管理器
        from core.config import get_config_manager
        self.config = get_config_manager()
        
        self.initUI()
    
    def initUI(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # 标题
        title = SubtitleLabel("图片文字识别", self)
        main_layout.addWidget(title)

        # 顶部工具栏
        toolbar = self.createToolbar()
        main_layout.addLayout(toolbar)

        # 内容区域 - 左侧图片，右侧结果
        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        # 左侧 - 图片预览区
        left_widget = self.createImagePreview()
        content_layout.addWidget(left_widget, 1)

        # 右侧 - 识别结果区
        right_widget = self.createResultPanel()
        content_layout.addWidget(right_widget, 1)

        main_layout.addLayout(content_layout, 1)

        # 状态栏
        self.status_bar = self.createStatusBar()
        main_layout.addLayout(self.status_bar)

    def createToolbar(self):
        """创建工具栏"""
        toolbar = QHBoxLayout()
        
        # 返回列表按钮（批量模式预览时显示）
        self.btn_back_to_list = PushButton(FluentIcon.LEFT_ARROW, "返回列表", self)
        self.btn_back_to_list.clicked.connect(self._return_to_batch_list)
        self.btn_back_to_list.setVisible(False)
        toolbar.addWidget(self.btn_back_to_list)
        
        # 选择文件按钮
        self.btn_select = PrimaryPushButton(FluentIcon.FOLDER, "选择图片", self)
        self.btn_select.clicked.connect(self.selectFile)
        toolbar.addWidget(self.btn_select)
        
        # 批量选择按钮（带下拉菜单）
        self.btn_batch = DropDownPushButton(FluentIcon.FOLDER_ADD, "批量选择", self)
        menu = RoundMenu()
        menu.addAction(Action(FluentIcon.FOLDER, "选择文件夹", triggered=self._select_folder))
        menu.addAction(Action(FluentIcon.PHOTO, "选择多个文件", triggered=self._select_multiple_files))
        self.btn_batch.setMenu(menu)
        toolbar.addWidget(self.btn_batch)
        
        # 截图按钮
        self.btn_screenshot = PushButton(FluentIcon.CAMERA, "截图识别", self)
        self.btn_screenshot.clicked.connect(self.screenshot)
        toolbar.addWidget(self.btn_screenshot)
        
        toolbar.addSpacing(16)
        
        # 识别按钮（自动判断单图/批量）
        self.btn_recognize = PrimaryPushButton(FluentIcon.SEARCH, "开始识别", self)
        self.btn_recognize.clicked.connect(self._on_recognize_clicked)
        self.btn_recognize.setEnabled(False)
        toolbar.addWidget(self.btn_recognize)
        
        # 语言选择
        lang_label = BodyLabel("识别语言:", self)
        toolbar.addWidget(lang_label)
        
        self.combo_lang = ComboBox(self)
        self.combo_lang.addItems(["简体中文", "English", "繁体中文", "日本語", "한국어"])
        self.combo_lang.setCurrentText("简体中文")  # 默认简体中文
        self.combo_lang.setMinimumWidth(120)
        self.combo_lang.currentTextChanged.connect(self.onLanguageChanged)
        toolbar.addWidget(self.combo_lang)
        
        return toolbar
    
    def _return_to_batch_list(self):
        """从预览模式返回批量列表"""
        if hasattr(self, 'batch_file_paths') and self.batch_file_paths:
            self._switch_to_batch_mode(self.batch_file_paths)
            # 如果有之前选中的索引，恢复选中状态
            if hasattr(self, '_last_selected_index') and self._last_selected_index >= 0:
                self.file_list_widget.setCurrentRow(self._last_selected_index)

    def _on_recognize_clicked(self):
        """识别按钮点击 - 自动判断单图/批量"""
        # 统一判断逻辑：检查是否有多张图片
        is_batch = self.is_batch_mode and len(self.batch_file_paths) > 1
        if is_batch:
            # 批量模式
            self.startBatchOCR()
        else:
            # 单图模式
            self.startOCR()

    def _update_recognize_button_text(self):
        """根据模式更新识别按钮文字"""
        if self.is_batch_mode and len(self.batch_file_paths) > 1:
            self.btn_recognize.setText(f"批量识别 ({len(self.batch_file_paths)})")
        else:
            self.btn_recognize.setText("开始识别")
    
    def createImagePreview(self):
        """创建图片预览区域"""
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 8, 0, 0)
        
        # 拖放区域（带虚线边框）
        self.drop_area = DropArea(self)
        drop_layout = QVBoxLayout(self.drop_area)
        drop_layout.setContentsMargins(0, 0, 0, 0)
        
        # 堆叠布局：预览视图 + 列表视图
        self.preview_stack = QWidget(self.drop_area)
        preview_layout = QVBoxLayout(self.preview_stack)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        
        # 单图预览模式
        self.image_label = QLabel(self.preview_stack)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setText("拖拽图片到此处\n或点击上方按钮选择图片\n\n拖入文件夹或多个文件将进入批量模式")
        self.image_label.setStyleSheet("""
            QLabel {
                color: #888;
                font-size: 14px;
                background-color: transparent;
                border: none;
                outline: none;
            }
        """)
        preview_layout.addWidget(self.image_label)
        
        # 批量文件列表模式
        self.file_list_widget = QListWidget(self.preview_stack)
        self.file_list_widget.setSpacing(2)
        self.file_list_widget.setIconSize(QSize(48, 48))
        self.file_list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.file_list_widget.itemClicked.connect(self._on_file_list_item_clicked)
        self.file_list_widget.itemDoubleClicked.connect(self._on_file_list_item_double_clicked)
        self.file_list_widget.setVisible(False)  # 默认隐藏
        self.file_list_widget.setStyleSheet("""
            QListWidget {
                border: none;
                background-color: transparent;
            }
            QListWidget::item {
                padding: 4px;
                border-radius: 4px;
                min-height: 56px;
            }
            QListWidget::item:selected {
                background-color: rgba(0, 120, 212, 0.2);
            }
            QListWidget::item:hover {
                background-color: rgba(0, 0, 0, 0.05);
            }
            QScrollBar:vertical {
                width: 6px;
                background: transparent;
            }
            QScrollBar::handle:vertical {
                background: rgba(0, 0, 0, 0.2);
                border-radius: 3px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(0, 0, 0, 0.3);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar:horizontal {
                height: 6px;
                background: transparent;
            }
            QScrollBar::handle:horizontal {
                background: rgba(0, 0, 0, 0.2);
                border-radius: 3px;
                min-width: 30px;
            }
            QScrollBar::handle:horizontal:hover {
                background: rgba(0, 0, 0, 0.3);
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """)
        
        preview_layout.addWidget(self.file_list_widget)
        
        # 批量模式顶部栏（文件名 + 数量）
        self.batch_header = QWidget(self.preview_stack)
        batch_header_layout = QHBoxLayout(self.batch_header)
        batch_header_layout.setContentsMargins(8, 4, 8, 4)
        
        self.batch_folder_label = BodyLabel("文件夹名称", self.batch_header)
        batch_header_layout.addWidget(self.batch_folder_label)
        
        batch_header_layout.addStretch()
        
        self.batch_count_label = BodyLabel("0 个文件", self.batch_header)
        self.batch_count_label.setStyleSheet("color: #666;")
        batch_header_layout.addWidget(self.batch_count_label)
        
        self.batch_header.setVisible(False)  # 默认隐藏
        preview_layout.addWidget(self.batch_header)
        
        # 移动到堆叠区域最底层
        preview_layout.addWidget(self.image_label, 1)
        preview_layout.addWidget(self.batch_header)
        preview_layout.addWidget(self.file_list_widget, 1)
        
        drop_layout.addWidget(self.preview_stack)
        
        # 连接拖拽信号
        self.drop_area.file_dropped.connect(self._on_single_file_dropped)
        self.drop_area.folder_dropped.connect(self._on_folder_dropped)
        
        layout.addWidget(self.drop_area)
        
        return container
    
    def _on_single_file_dropped(self, file_path: str):
        """单个文件拖入（自动开始识别）"""
        self._switch_to_preview_mode()
        self.loadImage(file_path)
        # 延迟一点让 UI 更新后再开始识别
        QTimer.singleShot(100, self._start_single_ocr)
    
    def _on_folder_dropped(self, file_paths: list):
        """文件夹拖入（仅切换到批量模式，不自动识别）"""
        self._switch_to_batch_mode(file_paths)
    
    def _switch_to_preview_mode(self):
        """切换到单图预览模式"""
        self.is_batch_mode = False
        self.image_label.setVisible(True)
        self.file_list_widget.setVisible(False)
        self.batch_header.setVisible(False)
        # 如果有批量文件列表，显示返回按钮
        self.btn_back_to_list.setVisible(bool(self.batch_file_paths))
        # 更新按钮文字
        self._update_recognize_button_text()
    
    def _switch_to_batch_mode(self, file_paths: list):
        """切换到批量列表模式"""
        # 如果是从预览模式返回，且文件列表已加载过，直接显示列表
        if (hasattr(self, 'batch_file_paths') and 
            self.batch_file_paths == file_paths and
            self.file_list_widget.count() > 0):
            # 快速切换显示，不重新加载
            self._quick_switch_to_batch()
            return
        
        # 首次加载或文件列表变化，重新构建
        self.is_batch_mode = True
        self.batch_file_paths = file_paths
        
        # 隐藏单图预览，显示列表
        self.image_label.setVisible(False)
        self.file_list_widget.setVisible(True)
        self.batch_header.setVisible(True)
        self.btn_back_to_list.setVisible(False)  # 隐藏返回按钮
        
        # 更新批量模式标题
        if file_paths:
            folder = os.path.dirname(file_paths[0])
            folder_name = os.path.basename(folder) or folder
            self.batch_folder_label.setText(f"📁 {folder_name}")
            self.batch_count_label.setText(f"{len(file_paths)} 个文件")
        
        # 清空并填充列表
        self.file_list_widget.clear()
        for file_path in file_paths:
            # 先创建列表项
            file_name = os.path.basename(file_path)
            item = QListWidgetItem(file_name)
            item.setData(Qt.UserRole, file_path)  # 存储完整路径
            
            # 异步加载缩略图
            self._load_list_thumbnail(file_path, item)
            
            self.file_list_widget.addItem(item)
        
        # 恢复选择状态
        self.file_list_widget.setCurrentRow(0)
        self.current_image_path = file_paths[0]
        self.btn_recognize.setEnabled(True)
        self.status_label.setText(f"批量模式: {len(file_paths)} 个文件")
        
        # 更新按钮文字
        self._update_recognize_button_text()
        
        # 批量模式下显示表格
        self.result_text.setVisible(False)
        self.result_table.setVisible(True)
    
    def _quick_switch_to_batch(self):
        """快速切换到批量列表（不清空列表）"""
        self.is_batch_mode = True
        self.image_label.setVisible(False)
        self.file_list_widget.setVisible(True)
        self.batch_header.setVisible(True)
        self.btn_back_to_list.setVisible(False)
        
        # 恢复选择状态
        if self.file_list_widget.count() > 0:
            self.file_list_widget.setCurrentRow(0)
            self.current_image_path = self.batch_file_paths[0]
        
        self.btn_recognize.setEnabled(True)
        self.status_label.setText(f"批量模式: {len(self.batch_file_paths)} 个文件")
        
        # 更新按钮文字
        self._update_recognize_button_text()
    
    def _load_list_thumbnail(self, file_path: str, item: QListWidgetItem):
        """异步加载列表缩略图"""
        def load_thumbnail():
            pixmap = _get_file_thumbnail(file_path, 48)
            if item.listWidget():  # 检查 item 是否还在列表中
                item.setIcon(pixmap)
        
        QTimer.singleShot(0, load_thumbnail)
    
    def _on_file_list_item_clicked(self, item: QListWidgetItem):
        """点击列表项"""
        self.current_image_path = item.data(Qt.UserRole)
        self.result_text.clear()
        self.btn_copy.setEnabled(False)
        self.btn_export.setEnabled(False)
        self.btn_recognize.setEnabled(True)  # 启用识别按钮
    
    def _on_file_list_item_double_clicked(self, item: QListWidgetItem):
        """双击列表项预览并识别"""
        self.current_image_path = item.data(Qt.UserRole)
        # 保存当前选中索引，识别完成后恢复
        self._last_selected_index = self.file_list_widget.currentRow()
        # 切换到预览模式显示这张图
        self._switch_to_preview_mode()
        self.loadImage(self.current_image_path)
        # 自动开始识别
        self.startOCR()
    
    def createResultPanel(self):
        """创建结果面板"""
        card = CardWidget(self)
        layout = QVBoxLayout(card)
        
        # 标题栏
        header = QHBoxLayout()
        header.addWidget(SubtitleLabel("识别结果", self))
        
        # 复制按钮
        self.btn_copy = PushButton(FluentIcon.COPY, "复制", self)
        self.btn_copy.clicked.connect(self.copyResult)
        self.btn_copy.setEnabled(False)
        header.addWidget(self.btn_copy)
        
        # 导出下拉按钮
        export_menu = RoundMenu(parent=self)
        action_txt = Action(FluentIcon.SAVE, "导出为 TXT")
        action_txt.triggered.connect(lambda: self.exportResult("TXT"))
        action_json = Action(FluentIcon.SAVE, "导出为 JSON")
        action_json.triggered.connect(lambda: self.exportResult("JSON"))
        action_excel = Action(FluentIcon.SAVE, "导出为 Excel")
        action_excel.triggered.connect(lambda: self.exportResult("Excel"))
        export_menu.addActions([action_txt, action_json, action_excel])
        
        self.btn_export = DropDownPushButton(FluentIcon.SAVE, "导出", self)
        self.btn_export.setMenu(export_menu)
        self.btn_export.setEnabled(False)
        header.addWidget(self.btn_export)
        
        layout.addLayout(header)
        
        # 结果表格（批量模式用）
        self.result_table = TableWidget(self)
        self.result_table.setColumnCount(2)
        self.result_table.setHorizontalHeaderLabels(["文件名", "识别内容"])
        self.result_table.setColumnWidth(0, 150)
        self.result_table.setVisible(False)  # 初始隐藏
        layout.addWidget(self.result_table)
        
        # 结果文本框（单图模式用）
        self.result_text = TextBrowser(self)
        self.result_text.setPlaceholderText("识别结果将在此处显示...")
        self.result_text.setVisible(True)  # 初始显示文本框
        layout.addWidget(self.result_text)
        
        return card
    
    def createStatusBar(self):
        """创建状态栏"""
        layout = QHBoxLayout()
        
        # 状态图标
        self.status_icon = QLabel(self)
        self.status_icon.setFixedSize(16, 16)
        self.status_icon.setPixmap(_create_status_dot("#888888"))  # 灰色默认
        layout.addWidget(self.status_icon)
        
        # 状态文字
        self.status_label = BodyLabel("就绪", self)
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        
        self.progress_bar = IndeterminateProgressBar(self)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedWidth(200)
        layout.addWidget(self.progress_bar)
        
        return layout

    def update_engine_status(self):
        """由 MainWindow 调用，初始化引擎后更新状态栏"""
        if hasattr(self.main_window, 'ocr_engine'):
            engine = self.main_window.ocr_engine
            if engine._initialized:
                # 绿色 - 已就绪
                self.status_icon.setPixmap(_create_status_dot("#4CAF50"))
                self.status_label.setText("OCR 引擎已就绪")
                InfoBar.success(
                    title="引擎就绪",
                    content="OCR 引擎初始化完成，可以开始识别",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
            else:
                # 红色 - 未就绪
                self.status_icon.setPixmap(_create_status_dot("#F44336"))
                self.status_label.setText("引擎未就绪")

    def set_engine_initializing(self):
        """设置引擎正在初始化中 - 黄色图标"""
        self.status_icon.setPixmap(_create_status_dot("#FFC107"))
        self.status_label.setText("OCR 引擎初始化中...")

    def set_engine_error(self):
        """设置引擎初始化失败 - 红色图标"""
        self.status_icon.setPixmap(_create_status_dot("#F44336"))
        self.status_label.setText("引擎初始化失败")

    def selectFile(self):
        """选择文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择图片",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;所有文件 (*.*)"
        )
        
        if file_path:
            self.loadImage(file_path)
    
    def _select_folder(self):
        """选择文件夹"""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "选择文件夹",
            "",
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )

        if folder_path:
            image_files = self.drop_area._scan_folder_for_images(folder_path)
            if image_files:
                self._switch_to_batch_mode(image_files)
            else:
                InfoBar.warning(
                    title="文件夹为空",
                    content="该文件夹中没有找到图片文件",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )

    def _select_multiple_files(self):
        """选择多个文件"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "批量选择图片",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;所有文件 (*.*)"
        )

        if file_paths:
            self._switch_to_batch_mode(file_paths)
    
    def loadImage(self, file_path):
        """加载图片"""
        if not os.path.exists(file_path):
            InfoBar.error(
                title="错误",
                content="图片文件不存在",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return
        
        self.current_image_path = file_path
        
        # 如果是批量模式，切换到预览模式
        if self.is_batch_mode:
            self._switch_to_preview_mode()
        
        # 显示图片预览
        pixmap = QPixmap(file_path)
        if pixmap.isNull():
            InfoBar.error(
                title="错误",
                content="无法加载图片",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return
        
        # 清除提示文字
        self.image_label.setText("")
        self.image_label.setStyleSheet("border: none; background-color: transparent;")
        
        # 缩放图片以适应显示
        scaled_pixmap = pixmap.scaled(
            self.drop_area.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.image_label.setPixmap(scaled_pixmap)
        
        # 更新状态
        self.status_label.setText(f"已加载: {os.path.basename(file_path)}")
        self.btn_recognize.setEnabled(True)
        self.result_text.clear()
        self.result_table.setRowCount(0)  # 清空表格
        self.btn_copy.setEnabled(False)
        self.btn_export.setEnabled(False)
    
    def onFileDropped(self, file_path: str):
        """处理拖放的文件（保留兼容）"""
        self.loadImage(file_path)
    
    def onLanguageChanged(self, language):
        """切换语言（运行时动态选择，不保存配置）"""
        # 直接应用到引擎
        if hasattr(self.main_window, 'ocr_engine'):
            self.main_window.ocr_engine.set_language(language)
            self.status_label.setText(f"已切换语言: {language}")
    
    def startOCR(self):
        """开始OCR识别（自动判断单图/批量）"""
        if not self.current_image_path:
            InfoBar.warning(
                title="提示",
                content="请先选择或拖入图片",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return
        
        # 检查 main_window
        if not hasattr(self, 'main_window') or not self.main_window:
            InfoBar.error(
                title="错误",
                content="主窗口未初始化",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return
        
        # 检查 OCR 引擎状态
        engine = self.main_window.ocr_engine
        if not engine._initialized:
            if not engine.initialize():
                InfoBar.error(
                    title="引擎初始化失败",
                    content="OCR 引擎无法初始化，请检查配置",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=5000,
                    parent=self
                )
                return
            # 初始化成功，更新状态
            self.update_engine_status()
        
        # 统一判断逻辑：检查是否有多张图片
        is_batch = self.is_batch_mode and len(self.batch_file_paths) > 1
        if is_batch:
            # 批量识别模式
            self._start_batch_ocr()
        else:
            # 单图识别模式
            self._start_single_ocr()
    
    def _start_single_ocr(self):
        """单图OCR识别 - 同步执行（直接调用避免 UI 卡死）"""
        file_name = os.path.basename(self.current_image_path)[:30]
        
        self.state_tooltip = StateToolTip("正在识别", file_name, self)
        self.state_tooltip.move(self.state_tooltip.getSuitablePos())
        self.state_tooltip.show()
        
        self.btn_recognize.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.start()
        
        # 同步执行 OCR
        try:
            engine = self.main_window.ocr_engine
            result = engine.recognize(self.current_image_path)
            self.onOCRFinished(result)
        except Exception as e:
            self.onOCRError(str(e))
    
    def _start_batch_ocr(self):
        """批量OCR识别"""
        self.batch_results = []  # 存储所有识别结果
        self.batch_current_index = 0
        self.batch_total = len(self.batch_file_paths)
        
        # 切换到表格显示
        self.result_text.setVisible(False)
        self.result_table.setVisible(True)
        self.result_table.setRowCount(0)
        
        # 显示进度
        self.state_tooltip = StateToolTip(
            "正在批量识别",
            f"已处理 0/{self.batch_total}",
            self
        )
        self.state_tooltip.move(self.state_tooltip.getSuitablePos())
        self.state_tooltip.show()
        
        self.btn_recognize.setEnabled(False)
        self.btn_select.setEnabled(False)
        self.btn_batch.setEnabled(False)
        self.file_list_widget.setEnabled(False)
        
        # 开始第一个
        self._batch_process_next()
    
    def _batch_process_next(self):
        """处理下一张图片（使用异步避免阻塞UI）"""
        if self.batch_current_index >= self.batch_total:
            # 所有图片处理完成
            self._on_batch_ocr_finished()
            return
        
        # 异步执行，让UI有机会更新
        QTimer.singleShot(10, self._do_batch_process)
    
    def _do_batch_process(self):
        """实际执行批量处理"""
        if self.batch_current_index >= self.batch_total:
            return
        
        file_path = self.batch_file_paths[self.batch_current_index]
        file_name = os.path.basename(file_path)
        
        # 只显示进度行，单行显示更紧凑
        progress_text = f"已处理 {self.batch_current_index}/{self.batch_total}"
        self.state_tooltip.setContent(progress_text)
        
        # 高亮当前项
        self.file_list_widget.setCurrentRow(self.batch_current_index)
        
        # 同步执行 OCR
        try:
            engine = self.main_window.ocr_engine
            result = engine.recognize(file_path)
            self._on_batch_item_finished(result)
        except Exception as e:
            self._on_batch_item_error(str(e))
    
    def _on_batch_item_finished(self, result):
        """批量中单个图片识别完成"""
        file_path = self.batch_file_paths[self.batch_current_index]
        file_name = os.path.basename(file_path)
        
        result_data = {
            'file_path': file_path,
            'file_name': file_name,
            'result': result
        }
        self.batch_results.append(result_data)
        
        # 添加到历史记录
        self.main_window.result_manager.add_result(file_path, result)
        
        # 添加到结果表格
        self._add_result_to_table(file_name, result)
        
        # 添加到历史记录
        self.main_window.result_manager.add_result(file_path, result)
        
        # 下一个
        self.batch_current_index += 1
        self._batch_process_next()
    
    def _on_batch_item_error(self, error_msg):
        """批量中单个图片识别出错"""
        file_path = self.batch_file_paths[self.batch_current_index]
        file_name = os.path.basename(file_path)
        
        # 添加错误结果
        result_data = {
            'file_path': file_path,
            'file_name': file_name,
            'result': {'code': -1, 'data': error_msg}
        }
        self.batch_results.append(result_data)
        
        # 添加到结果表格
        self._add_result_to_table(file_name, {'code': -1, 'data': error_msg})
        
        # 下一个
        self.batch_current_index += 1
        self._batch_process_next()
    
    def _add_result_to_table(self, file_name: str, result: dict):
        """添加结果到表格"""
        row = self.result_table.rowCount()
        self.result_table.insertRow(row)
        
        # 文件名列
        file_item = QTableWidgetItem(file_name)
        file_item.setToolTip(file_name)
        self.result_table.setItem(row, 0, file_item)
        
        # 识别内容列
        if result.get('code') == 100:
            texts = result.get('texts', [])
            content = '\n'.join(texts) if texts else "(未识别到文字)"
        else:
            content = f"识别失败: {result.get('data', '未知错误')}"
        
        content_item = QTableWidgetItem(content)
        content_item.setToolTip(content)
        self.result_table.setItem(row, 1, content_item)
    
    def _append_batch_result_text(self, result_data):
        """追加批量识别结果到文本框"""
        file_name = result_data['file_name']
        result = result_data['result']
        
        # 添加分隔符和文件名
        separator = "=" * 50
        self.result_text.append(f"\n{separator}")
        self.result_text.append(f"📄 {file_name}")
        self.result_text.append(separator)
        
        if result.get('code') == 100:
            texts = result.get('texts', [])
            if texts:
                self.result_text.append('\n'.join(texts))
            else:
                self.result_text.append("(未识别到文字)")
        else:
            self.result_text.append(f"识别失败: {result.get('data', '未知错误')}")
        
        # 滚动到底部
        self.result_text.verticalScrollBar().setValue(
            self.result_text.verticalScrollBar().maximum()
        )
    
    def _on_batch_ocr_finished(self):
        """批量识别全部完成"""
        self.state_tooltip.hide()
        self.btn_recognize.setEnabled(True)
        self.btn_select.setEnabled(True)
        self.btn_batch.setEnabled(True)
        self.file_list_widget.setEnabled(True)
        
        # 统计成功/失败数量
        success_count = sum(1 for r in self.batch_results if r['result'].get('code') == 100)
        fail_count = self.batch_total - success_count
        
        self.status_label.setText(f"批量识别完成: {success_count} 成功, {fail_count} 失败")
        
        # 启用复制和导出
        self.btn_copy.setEnabled(True)
        self.btn_export.setEnabled(True)
        
        # 显示完成提示
        if fail_count > 0:
            InfoBar.warning(
                title="批量识别完成",
                content=f"成功 {success_count} 个，失败 {fail_count} 个",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
        else:
            InfoBar.success(
                title="批量识别完成",
                content=f"已成功识别 {success_count} 张图片",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
        
        self.worker = None
    
    def onOCRFinished(self, result):
        """OCR识别完成（单图模式）"""
        self.state_tooltip.hide()
        self.progress_bar.stop()
        self.progress_bar.setVisible(False)
        self.btn_recognize.setEnabled(True)
        
        # 单图模式切换到文本框显示
        self.result_table.setVisible(False)
        self.result_text.setVisible(True)
        
        self.ocr_result = result
        
        if result.get('code') == 100:
            # 成功
            texts = result.get('texts', [])
            self.result_text.setPlainText('\n'.join(texts))
            
            # 添加到历史记录
            self.main_window.result_manager.add_result(
                self.current_image_path, 
                result
            )
            
            self.status_label.setText(f"识别成功，共 {len(texts)} 行文字")
            self.btn_copy.setEnabled(True)
            self.btn_export.setEnabled(True)
            
            InfoBar.success(
                title="识别成功",
                content=f"已识别 {len(texts)} 行文字",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            
            # 发送完成信号
            self.ocr_completed.emit(self.current_image_path)
        else:
            # 失败
            error_msg = result.get('data', '未知错误')
            self.result_text.setPlainText(f"识别失败: {error_msg}")
            self.status_label.setText(f"识别失败: {error_msg}")
            
            InfoBar.error(
                title="识别失败",
                content=error_msg,
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
        
        self.worker = None
    
    def onOCRError(self, error_msg):
        """OCR识别错误"""
        self.state_tooltip.hide()
        self.progress_bar.stop()
        self.progress_bar.setVisible(False)
        self.btn_recognize.setEnabled(True)
        
        self.result_text.setPlainText(f"识别出错: {error_msg}")
        self.status_label.setText(f"识别出错: {error_msg}")
        
        InfoBar.error(
            title="识别出错",
            content=error_msg,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self
        )
        
        self.worker = None
    
    def copyResult(self):
        """复制结果"""
        text = self.result_text.toPlainText()
        if text:
            # 调用核心层复制到剪贴板
            from core.config import copy_to_clipboard
            if copy_to_clipboard(text):
                InfoBar.success(
                    title="已复制",
                    content="识别结果已复制到剪贴板",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
    
    def exportResult(self, format_type):
        """导出结果"""
        if not self.ocr_result:
            return
        
        # 获取文件名
        base_name = os.path.splitext(os.path.basename(self.current_image_path))[0]
        
        # 打开保存对话框
        filters = {
            "TXT": "文本文件 (*.txt)",
            "JSON": "JSON文件 (*.json)",
            "Excel": "Excel文件 (*.xlsx)"
        }
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"导出为 {format_type}",
            f"{base_name}_识别结果.{format_type.lower()}",
            filters.get(format_type, "")
        )
        
        if file_path:
            result = self.main_window.exporter.export(
                self.ocr_result,
                format_type,
                file_path
            )
            
            if result:
                InfoBar.success(
                    title="导出成功",
                    content=f"已保存到: {result}",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=5000,
                    parent=self
                )
            else:
                InfoBar.error(
                    title="导出失败",
                    content="无法导出文件",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
    
    def startBatchOCR(self):
        """开始批量OCR识别"""
        if not hasattr(self, 'batch_file_paths') or not self.batch_file_paths:
            InfoBar.warning(
                title="提示",
                content="请先批量选择图片",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return
        
        # 检查 main_window
        if not hasattr(self, 'main_window') or not self.main_window:
            InfoBar.error(
                title="错误",
                content="主窗口未初始化",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return
        
        total = len(self.batch_file_paths)
        
        # 切换到表格显示
        self.result_text.setVisible(False)
        self.result_table.setVisible(True)
        self.result_table.setRowCount(0)
        
        # 显示进度提示
        self.state_tooltip = StateToolTip(f"正在批量识别...", f"已处理 0/{total}", self)
        self.state_tooltip.move(self.state_tooltip.getSuitablePos())
        self.state_tooltip.show()
        
        # 禁用按钮
        self.btn_recognize.setEnabled(False)
        self.btn_select.setEnabled(False)
        self.btn_batch.setEnabled(False)
        
        # 启动批量工作线程
        self.batch_worker = BatchOCRWorker(
            self.main_window.ocr_engine,
            self.batch_file_paths
        )
        self.batch_worker.progress.connect(self.onBatchProgress)
        self.batch_worker.finished_one.connect(self.onBatchOneFinished)
        self.batch_worker.finished_all.connect(self.onBatchAllFinished)
        self.batch_worker.error.connect(self.onBatchError)
        self.batch_worker.start()
    
    def onBatchProgress(self, current, total, filename):
        """批量识别进度更新"""
        # 只显示进度行，避免截断
        self.state_tooltip.setContent(f"已处理 {current}/{total}")
    
    def onBatchOneFinished(self, file_path, result):
        """批量识别中单个文件完成"""
        # 添加到历史记录
        self.main_window.result_manager.add_result(file_path, result)
        
        # 添加到结果表格
        file_name = os.path.basename(file_path)
        self._add_result_to_table(file_name, result)
    
    def onBatchAllFinished(self, results):
        """批量识别全部完成"""
        self.state_tooltip.hide()
        
        # 恢复按钮
        self.btn_recognize.setEnabled(True)
        self.btn_select.setEnabled(True)
        self.btn_batch.setEnabled(True)
        
        # 恢复按钮文字
        self._update_recognize_button_text()
        
        # 统计成功数量
        success_count = sum(1 for r in results if r['result'].get('code') == 100)
        
        self.batch_results = results
        self.status_label.setText(f"批量识别完成: {success_count}/{len(results)} 个成功")
        
        InfoBar.success(
            title="批量识别完成",
            content=f"成功 {success_count} 个，失败 {len(results) - success_count} 个",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self
        )
        
        # 询问用户是否导出
        self._ask_export_batch_results()
    
    def onBatchError(self, error_msg):
        """批量识别错误"""
        self.state_tooltip.hide()
        
        InfoBar.error(
            title="识别出错",
            content=error_msg,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self
        )
    
    def _ask_export_batch_results(self):
        """询问用户导出格式"""
        if not hasattr(self, 'batch_results') or not self.batch_results:
            return
        
        from qfluentwidgets import MessageBox
        
        message_box = MessageBox(
            "导出结果",
            "是否导出批量识别结果？",
            self.window()
        )
        if message_box.exec():
            self.exportBatchResults()
    
    def exportBatchResults(self):
        """导出批量识别结果"""
        if not hasattr(self, 'batch_results') or not self.batch_results:
            return
        
        # 让用户选择导出格式
        from qfluentwidgets import MessageBox
        
        message_box = MessageBox("选择导出格式", "请选择导出格式：", self.window())
        message_box.yesButton.setText("TXT 文本")
        message_box.cancelButton.setText("JSON")
        message_box.yesButton.clicked.connect(lambda: self._do_export_batch("TXT"))
        message_box.cancelButton.clicked.connect(lambda: self._do_export_batch("JSON"))
        message_box.yesButton.setFocus()
        message_box.exec()
    
    def _do_export_batch(self, export_format: str):
        """执行批量导出"""
        # 获取导出目录
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "选择导出目录",
            ""
        )
        
        if not dir_path:
            return
        
        success_count = 0
        for item in self.batch_results:
            file_path = item['path']
            result = item['result']
            
            if result.get('code') == 100:
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                ext = "txt" if export_format == "TXT" else "json"
                file_path_out = os.path.join(dir_path, f"{base_name}.{ext}")
                self.main_window.exporter.export(result, export_format, file_path_out)
                success_count += 1
        
        InfoBar.success(
            title="导出完成",
            content=f"已导出 {success_count} 个 {export_format} 文件到: {dir_path}",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self
        )
    
    def screenshot(self):
        """截图识别"""
        # 先截取当前屏幕（主窗口还在，所以会包含主窗口内容）
        try:
            from core.screenshot import capture_screen_to_temp
            bg_path = capture_screen_to_temp()
        except:
            bg_path = None
        
        # 隐藏主窗口
        self.main_window.hide()
        
        # 延迟启动截图窗口，传入背景截图路径
        QTimer.singleShot(100, lambda: self._show_screenshot_window(bg_path))

    def _show_screenshot_window(self, bg_path=None):
        """显示截图窗口"""
        from interfaces.fluent.components.screenshot_window import ScreenShotWindow
        self.screenshot_window = ScreenShotWindow(bg_path)
        self.screenshot_window.screenshot_finished.connect(self._on_screenshot_region)
        self.screenshot_window.screenshot_cancelled.connect(self._on_screenshot_cancelled)
        self.screenshot_window.show()

    def _on_screenshot_region(self, x: int, y: int, width: int, height: int):
        """截图完成回调 - 调用核心层处理"""
        # 先隐藏截图窗口（让屏幕可见）
        if hasattr(self, 'screenshot_window') and self.screenshot_window:
            self.screenshot_window.hide()

        # 显示主窗口
        self.main_window.show()
        self.main_window.activateWindow()

        # 延迟截图，等待屏幕渲染完成（增加延迟确保窗口完全显示）
        def do_screenshot():
            # 调用核心层截图
            from core.screenshot import capture_screen_region
            temp_path = capture_screen_region(x, y, width, height)

            # 关闭截图窗口
            if hasattr(self, 'screenshot_window') and self.screenshot_window:
                self.screenshot_window.close()
                self.screenshot_window = None

            if temp_path and os.path.exists(temp_path):
                self.loadImage(temp_path)

        QTimer.singleShot(300, do_screenshot)

    def _on_screenshot_cancelled(self):
        """截图取消回调"""
        # 关闭截图窗口
        if hasattr(self, 'screenshot_window') and self.screenshot_window:
            self.screenshot_window.close()
            self.screenshot_window = None

        # 显示主窗口
        self.main_window.show()
        self.main_window.activateWindow()
