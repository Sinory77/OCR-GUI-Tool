"""
OCR 识别页面 - 纯 UI 显示版本
仅包含界面创建和显示相关代码，所有功能实现已移除
后续将逐步添加功能
"""

from PySide6.QtCore import Qt, Signal, Slot, QSize, QTimer, QPoint
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QListWidget, QListWidgetItem,
    QAbstractItemView, QTableWidget, QTableWidgetItem,
    QHeaderView, QScrollArea, QSizePolicy
)
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QPixmap, QPainter, QColor, QPen, QIcon, QMouseEvent, QWheelEvent
from qfluentwidgets import TextBrowser, IndeterminateProgressBar, TableWidget, ListWidget, ScrollArea
from qfluentwidgets import (
    CardWidget, PrimaryPushButton, PushButton, ToolButton,
    ComboBox, InfoBar, InfoBarPosition,
    SubtitleLabel, BodyLabel, StateToolTip,
    RoundMenu, Action, DropDownPushButton
)
from qfluentwidgets.common.icon import FluentIcon


def _create_status_dot(color: str) -> QPixmap:
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


def _get_file_thumbnail(file_path: str, size: int = 60) -> QPixmap:
    """获取文件缩略图"""
    pixmap = QPixmap(file_path)
    if pixmap.isNull():
        # 返回占位图
        placeholder = QPixmap(size, size)
        placeholder.fill(QColor(200, 200, 200))
        return placeholder
    return pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)


class DropArea(QFrame):
    """拖放区域组件（纯 UI 版本）"""
    
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
        """放下文件或文件夹（处理拖放）"""
        self.setStyleSheet("""
            QFrame {
                background-color: rgba(240, 240, 240, 0.5);
                border: 2px dashed #aaa;
                border-radius: 8px;
            }
        """)
        
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            
            # 获取所有拖放的文件路径，交由 CoreAPI 分类处理
            file_paths = [url.toLocalFile() for url in urls]
            
            from api.core_api import get_core_api
            core_api = get_core_api()
            classified = core_api.classify_dropped_paths(file_paths)
            
            if classified['folder_images']:
                self.folder_dropped.emit(classified['folder_images'])
            
            if classified['image_files']:
                if len(classified['image_files']) > 1:
                    self.folder_dropped.emit(classified['image_files'])
                else:
                    self.file_dropped.emit(classified['image_files'][0])
        
        event.acceptProposedAction()


class OCRPage(QWidget):
    """OCR 识别页面（纯 UI 版本）"""
    
    ocr_completed = Signal(str)  # 识别完成信号，传递图片路径
    batch_ocr_completed = Signal()  # 批量识别完成信号
    # StateToolTip 更新信号
    update_tooltip_signal = Signal(str, str)  # (title, content)
    # ★ 进度更新信号（工作线程 → 主线程）
    _progress_signal = Signal(object)  # TaskResult
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.main_window = parent
        self.current_image_path = None
        
        # StateToolTip 实例（用于显示进度提示）
        self._state_tooltip = None
        
        # 批量模式
        self.batch_file_paths = []  # 当前批量文件列表
        self.batch_folder_path = ""  # 当前批量文件夹路径
        self.is_batch_mode = False
        self._last_selected_index = -1  # 记录上次选中的索引
        self._current_task_is_batch = False  # 当前识别任务是否为批量（回调时使用）
        self._current_single_result = None  # 单图识别结果（含提取字段，供导出/复制用）
        
        self.initUI()
        self._connect_signals()
        
        # 加载识别模板列表
        self._template_ids = []  # 与 combo_template 选项一一对应
        self._load_templates()
    
    def _connect_signals(self):
        """连接信号（纯UI交互，无业务逻辑）"""
        # 选择图片按钮
        self.btn_select.clicked.connect(self._on_select_image)
        
        # 批量选择按钮（暂时只连接文件夹选择）
        if self.btn_batch.menu():
            menu = self.btn_batch.menu()
            actions = menu.actions()
            if len(actions) > 0:
                actions[0].triggered.connect(self._on_select_folder)
            if len(actions) > 1:
                actions[1].triggered.connect(self._on_select_multiple_files)
        
        # 截图识别按钮
        self.btn_screenshot.clicked.connect(self._on_screenshot)
        
        # 开始识别按钮
        self.btn_recognize.clicked.connect(self._on_recognize)
        
        # 中断按钮
        self.btn_cancel.clicked.connect(self._on_cancel)
        
        # 复制按钮
        self.btn_copy.clicked.connect(self._on_copy)
        
        # 导出按钮（菜单项和主按钮点击已在 createResultPanel 中绑定）
        # 文件列表选中/双击事件（去掉 ItemIsDragEnabled 后双击信号正常触发）
        self.file_list_widget.itemClicked.connect(self._on_file_selected)
        self.file_list_widget.itemDoubleClicked.connect(self._on_list_double_clicked)
        
        # 返回列表按钮
        self.btn_back_to_list.clicked.connect(self._on_back_to_list)
        
        # 拖放区域信号
        self.drop_area.file_dropped.connect(self._on_file_dropped)
        self.drop_area.folder_dropped.connect(self._on_folder_dropped)
        
        # ★ 进度信号：工作线程 → 主线程 UI 更新
        self._progress_signal.connect(self._do_progress_update)
    
    def _load_templates(self):
        """从 CoreAPI 获取识别模板列表，填充 combo_template 下拉框"""
        from api.core_api import get_core_api
        core_api = get_core_api()
        self.combo_template.clear()
        self._template_ids = []
        # 第 0 项：不使用模板
        self.combo_template.addItem("无模板")
        self._template_ids.append(None)
        # 加载已保存的识别模板
        names = core_api.get_ocr_template_names()
        for tid, name in names.items():
            self.combo_template.addItem(name)
            self._template_ids.append(tid)
    
    def initUI(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # 标题
        title = SubtitleLabel("图片文字识别", self)
        main_layout.addWidget(title)

        # 顶部工具栏（两行：操作按钮 + 参数选项）
        self.toolbar_widget = self.createToolbar()
        main_layout.addWidget(self.toolbar_widget)

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
        
        # 连接进度更新信号到槽函数（必须在所有 UI 初始化完成后）
        self.update_tooltip_signal.connect(self.update_tooltip_slot)
    
    def createToolbar(self):
        """创建工具栏 - 两行布局：第一行操作按钮，第二行参数选项（纯 UI 版本）"""
        toolbar_widget = QWidget(self)
        outer = QVBoxLayout(toolbar_widget)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        # ── 第一行：操作按钮 ──────────────────────────
        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        row1.setSpacing(8)

        # 返回列表按钮（批量预览模式显示）
        self.btn_back_to_list = PushButton(FluentIcon.LEFT_ARROW, "返回列表", self)
        self.btn_back_to_list.setVisible(False)
        row1.addWidget(self.btn_back_to_list)

        # 选择图片
        self.btn_select = PrimaryPushButton(FluentIcon.FOLDER, "选择图片", self)
        row1.addWidget(self.btn_select)

        # 批量选择（带下拉菜单）
        self.btn_batch = DropDownPushButton(FluentIcon.FOLDER_ADD, "批量选择", self)
        menu = RoundMenu()
        menu.addAction(Action(FluentIcon.FOLDER, "选择文件夹"))
        menu.addAction(Action(FluentIcon.PHOTO, "选择多个文件"))
        self.btn_batch.setMenu(menu)
        row1.addWidget(self.btn_batch)

        # 截图识别
        self.btn_screenshot = PushButton(FluentIcon.CAMERA, "截图识别", self)
        row1.addWidget(self.btn_screenshot)

        # 开始识别
        self.btn_recognize = PrimaryPushButton(FluentIcon.SEARCH, "开始识别", self)
        self.btn_recognize.setEnabled(False)
        row1.addWidget(self.btn_recognize)

        # 中断
        self.btn_cancel = PushButton(FluentIcon.CLOSE, "中断", self)
        self.btn_cancel.setEnabled(False)
        row1.addWidget(self.btn_cancel)

        row1.addStretch(1)   # 右侧留白，让按钮靠左
        outer.addLayout(row1)

        # ── 第二行：参数选项 ──────────────────────────
        row2 = QHBoxLayout()
        row2.setContentsMargins(0, 0, 0, 0)
        row2.setSpacing(8)

        # 识别语言
        lang_label = BodyLabel("识别语言:", self)
        row2.addWidget(lang_label)

        self.combo_lang = ComboBox(self)
        self.combo_lang.addItems(["简体中文", "English", "繁体中文", "日本語", "한국어"])
        self.combo_lang.setCurrentText("简体中文")
        self.combo_lang.setMinimumWidth(120)
        row2.addWidget(self.combo_lang)

        row2.addSpacing(24)   # 两个选项组之间留间隔

        # 提取模板
        template_label = BodyLabel("提取模板:", self)
        row2.addWidget(template_label)
        
        self.combo_template = ComboBox(self)
        self.combo_template.setMinimumWidth(140)
        row2.addWidget(self.combo_template)
        
        # 重新解析按钮（识别完成后显示）
        self.btn_reparse = PushButton(FluentIcon.SYNC, "重新解析", self)
        self.btn_reparse.setVisible(False)  # 默认隐藏
        self.btn_reparse.setToolTip("使用当前选中的模板重新解析识别结果（不需要重新识别）")
        self.btn_reparse.clicked.connect(self._on_reparse)
        row2.addWidget(self.btn_reparse)
        
        row2.addStretch(1)   # 右侧留白
        outer.addLayout(row2)

        return toolbar_widget
    
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
        
        # ── 单图预览模式 ──────────────────────────
        # 创建一个容器来包含滚动区域和文件名标签
        self.single_image_container = QWidget(self.preview_stack)
        single_image_layout = QVBoxLayout(self.single_image_container)
        single_image_layout.setContentsMargins(0, 0, 0, 0)
        single_image_layout.setSpacing(8)
        
        # 顶部栏：文件名 + 缩放控制按钮
        top_bar = QWidget(self.single_image_container)
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(0, 0, 0, 0)
        top_bar_layout.setSpacing(8)
        
        # 文件名标签（左对齐）
        self.image_filename_label = BodyLabel("", self.single_image_container)
        self.image_filename_label.setStyleSheet("color: #666; font-size: 12px;")
        self.image_filename_label.setVisible(False)
        top_bar_layout.addWidget(self.image_filename_label)
        
        top_bar_layout.addStretch()
        
        # 缩放控制按钮
        self.btn_zoom_in = ToolButton(FluentIcon.SEARCH, self)
        self.btn_zoom_in.setToolTip("放大")
        self.btn_zoom_in.setFixedSize(32, 32)
        self.btn_zoom_in.clicked.connect(self._on_zoom_in)
        top_bar_layout.addWidget(self.btn_zoom_in)
        
        self.btn_zoom_out = ToolButton(FluentIcon.SEARCH_MIRROR, self)
        self.btn_zoom_out.setToolTip("缩小")
        self.btn_zoom_out.setFixedSize(32, 32)
        self.btn_zoom_out.clicked.connect(self._on_zoom_out)
        top_bar_layout.addWidget(self.btn_zoom_out)
        
        self.btn_zoom_fit = ToolButton(FluentIcon.FIT_PAGE, self)
        self.btn_zoom_fit.setToolTip("适应窗口")
        self.btn_zoom_fit.setFixedSize(32, 32)
        self.btn_zoom_fit.clicked.connect(self._on_zoom_fit)
        top_bar_layout.addWidget(self.btn_zoom_fit)
        
        single_image_layout.addWidget(top_bar)
        
        # 滚动区域（支持缩放和滚动）- 使用 qfluentwidgets 的 ScrollArea
        self.image_scroll_area = ScrollArea(self.single_image_container)
        self.image_scroll_area.setWidgetResizable(True)
        self.image_scroll_area.setStyleSheet("""
            ScrollArea {
                border: none;
                background-color: transparent;
            }
            ScrollArea QScrollBar:vertical, ScrollArea QScrollBar:horizontal {
                background-color: transparent;
            }
        """)
        
        # 图片标签（放在滚动区域中）
        self.image_label = QLabel()
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
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.image_scroll_area.setWidget(self.image_label)
        
        single_image_layout.addWidget(self.image_scroll_area)
        
        preview_layout.addWidget(self.single_image_container)
        
        # ── 批量文件列表模式 ──────────────────────────
        # 批量文件列表模式 - 使用 qfluentwidgets 的 ListWidget（自带 Fluent 风格滚动条）
        self.file_list_widget = ListWidget(self.preview_stack)
        self.file_list_widget.setSpacing(2)
        self.file_list_widget.setIconSize(QSize(64, 64))
        self.file_list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.file_list_widget.setVisible(False)  # 默认隐藏
        # 只设置必要的样式，滚动条由 ListWidget 自动管理
        self.file_list_widget.setStyleSheet("""
            ListWidget {
                border: none;
                background-color: transparent;
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
        
        drop_layout.addWidget(self.preview_stack)
        layout.addWidget(self.drop_area)
        
        # 初始化缩放相关变量
        self._image_original_pixmap = None
        self._image_scale_factor = 1.0
        
        return container
    
    def createResultPanel(self):
        """创建结果面板"""
        card = CardWidget(self)
        layout = QVBoxLayout(card)
        
        # 标题栏
        header = QHBoxLayout()
        header.addWidget(SubtitleLabel("识别结果", self))
        
        # 复制按钮
        self.btn_copy = PushButton(FluentIcon.COPY, "复制", self)
        self.btn_copy.setEnabled(False)
        header.addWidget(self.btn_copy)
        
        # 导出下拉按钮（主按钮直接导出上次格式，下拉切换格式）
        export_menu = RoundMenu(parent=self)
        
        action_txt = Action(FluentIcon.SAVE, "导出为 TXT")
        action_txt.triggered.connect(lambda: self._on_export_with_format("TXT"))
        export_menu.addAction(action_txt)
        
        action_json = Action(FluentIcon.SAVE, "导出为 JSON")
        action_json.triggered.connect(lambda: self._on_export_with_format("JSON"))
        export_menu.addAction(action_json)
        
        action_excel = Action(FluentIcon.SAVE, "导出为 Excel")
        action_excel.triggered.connect(lambda: self._on_export_with_format("Excel"))
        export_menu.addAction(action_excel)
        
        self.btn_export = DropDownPushButton(FluentIcon.SAVE, "导出", self)
        self.btn_export.setMenu(export_menu)
        self.btn_export.clicked.connect(self._on_export_last_format)  # 主按钮：直接导出上次格式
        self.btn_export.setEnabled(False)
        header.addWidget(self.btn_export)
        
        # 优化：更新导出按钮文本（显示上次格式）
        self._update_export_button_text()
        
        layout.addLayout(header)
        
        # 结果表格（批量模式用，3列：文件名/识别内容/提取字段）
        self.result_table = TableWidget(self)
        self.result_table.setColumnCount(3)
        self.result_table.setHorizontalHeaderLabels(["文件名", "识别内容", "提取字段"])
        self.result_table.setColumnWidth(0, 160)
        self.result_table.setColumnWidth(2, 180)
        # 第二列（识别内容）自动拉伸填充剩余空间
        self.result_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Interactive
        )
        self.result_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.result_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Interactive
        )
        # 多行文本自动换行
        self.result_table.setWordWrap(True)
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
    
    def set_engine_initializing(self):
        """设置引擎正在初始化中 - 黄色图标（纯 UI 版本）"""
        self.status_icon.setPixmap(_create_status_dot("#FFC107"))
        self.status_label.setText("OCR 引擎初始化中...")
    
    def set_engine_error(self):
        """设置引擎初始化失败 - 红色图标（纯 UI 版本）"""
        self.status_icon.setPixmap(_create_status_dot("#F44336"))
        self.status_label.setText("引擎初始化失败")
    
    def update_engine_status(self, show_notification: bool = False):
        """更新状态栏引擎状态显示（纯显示，逻辑判断在核心层）"""
        try:
            # 获取 CoreAPI 实例
            from api.core_api import get_core_api
            core_api = get_core_api()
            
            # 获取状态显示信息（逻辑判断在核心层）
            display_info = core_api.get_engine_status_display_info(show_notification)
            
            # 更新状态栏（纯显示，无逻辑判断）
            self.status_icon.setPixmap(_create_status_dot(display_info['icon_color']))
            self.status_label.setText(display_info['status_text'])
            
            # 显示通知（如果有）
            if display_info['show_notification'] and display_info['notification_type']:
                if display_info['notification_type'] == 'success':
                    self._info_bar_success(
                        display_info['notification_title'],
                        display_info['notification_message']
                    )
                elif display_info['notification_type'] == 'warning':
                    self._info_bar_warning(
                        display_info['notification_title'],
                        display_info['notification_message']
                    )
                elif display_info['notification_type'] == 'error':
                    self._info_bar_error(
                        display_info['notification_title'],
                        display_info['notification_message']
                    )
            
        except Exception as e:
            logger.info(f"[OCRPage] 更新引擎状态出错: {e}")
            self.status_icon.setPixmap(_create_status_dot("#F44336"))
            self.status_label.setText("OCR 引擎状态检查失败")
    
    def _update_recognize_button_state(self):
        """根据引擎和图片状态更新识别按钮可用性（纯 UI 版本）"""
        # 纯 UI 版本：按钮状态固定，不动态更新
        # 功能将在后续添加
        pass
    
    @Slot(str, str)
    def update_tooltip_slot(self, title: str, content: str):
        """槽函数：更新 StateToolTip，确保在主线程执行（纯 UI 版本）"""
        # 纯 UI 版本：显示提示框，但不处理功能逻辑
        self._show_state_tooltip(title, content)
    
    def _hide_state_tooltip(self):
        """Hide state tooltip (simplified, match official Demo)"""
        if hasattr(self, '_state_tooltip') and self._state_tooltip:
            try:
                self._state_tooltip.hide()
                self._state_tooltip.deleteLater()
            except:
                pass
            self._state_tooltip = None
    
    def _close_state_tooltip(self):
        """Close state tooltip (simplified, match official Demo)"""
        if hasattr(self, '_state_tooltip') and self._state_tooltip:
            try:
                self._state_tooltip.hide()
                self._state_tooltip.deleteLater()
            except:
                pass
            self._state_tooltip = None
    
    def _show_state_tooltip(self, title: str, content: str, is_done: bool = False):
        """Show StateToolTip (top-right corner, match official Demo)"""
        try:
            if hasattr(self, '_state_tooltip') and self._state_tooltip:
                try:
                    self._state_tooltip.hide()
                    self._state_tooltip.deleteLater()
                except:
                    pass
                self._state_tooltip = None
            
            self._state_tooltip = StateToolTip(title, content, self)
            self._state_tooltip.show()
            
            x = self.width() - self._state_tooltip.width() - 10
            self._state_tooltip.move(x, 30)
            
            if is_done:
                self._state_tooltip.setState(True)
                self._state_tooltip = None  # clear ref only, tooltip auto-dismisses
            
        except Exception as e:
            logger.warning(f"[OCRPage] Show StateToolTip error: {e}")
    
    def _update_state_tooltip(self, title: str, content: str):
        """辅助方法：安全更新 StateToolTip（纯 UI 版本）"""
        # 纯 UI 版本：直接调用显示方法
        self._show_state_tooltip(title, content)
    
    # ─────────────────────── InfoBar 快捷方法（纯 UI 版本）─────────────────────── #
    
    def _info_bar_success(self, title: str, content: str, duration: int = 3000,
                          position=InfoBarPosition.TOP_RIGHT):
        """显示成功提示"""
        InfoBar.success(title=title, content=content, isClosable=True,
                        position=position, duration=duration, parent=self)
    
    def _info_bar_warning(self, title: str, content: str, duration: int = 3000,
                          position=InfoBarPosition.TOP_RIGHT):
        """显示警告提示"""
        InfoBar.warning(title=title, content=content, isClosable=True,
                        position=position, duration=duration, parent=self)
    
    def _info_bar_error(self, title: str, content: str, duration: int = 5000,
                        position=InfoBarPosition.TOP_RIGHT):
        """显示错误提示"""
        InfoBar.error(title=title, content=content, isClosable=True,
                      position=position, duration=duration, parent=self)
    
    def _info_bar_info(self, title: str, content: str, duration: int = 3000,
                       position=InfoBarPosition.TOP_RIGHT, isClosable: bool = True):
        """显示信息提示"""
        InfoBar.info(title=title, content=content, isClosable=isClosable,
                     position=position, duration=duration, parent=self)
    
    def _close_info_bar_by_title(self, title: str):
        """关闭指定标题的 InfoBar"""
        for bar in self.findChildren(InfoBar):
            if getattr(bar, 'title', None) == title:
                bar.close()
    
    # ─────────────────────── 图片选择相关槽函数 ─────────────────────── #
    
    def _on_select_image(self):
        """选择图片按钮槽函数（纯UI交互）"""
        from PySide6.QtWidgets import QFileDialog
        
        # 打开文件对话框（只显示图片文件）
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择图片",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tiff *.tif)"
        )
        
        if file_path:
            # 调用核心层处理（验证逻辑）
            from api.core_api import get_core_api
            core_api = get_core_api()
            core_api.set_current_image(file_path)
            
            # 直接更新UI（纯显示，无逻辑判断）
            self._display_image(file_path)
            self.btn_recognize.setEnabled(True)
            
            # 优化：如果引擎已就绪，自动开始识别
            if core_api.is_ocr_engine_ready():
                QTimer.singleShot(100, self._on_recognize)  # 延迟100ms确保UI更新完成
    
    def _on_select_folder(self):
        """选择文件夹按钮槽函数（批量模式）"""
        from PySide6.QtWidgets import QFileDialog
        
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "选择文件夹",
            ""
        )
        
        if folder_path:
            # 保存文件夹路径
            self.batch_folder_path = folder_path
            
            # 扫描文件夹中的图片（异步）
            from api.core_api import get_core_api
            core_api = get_core_api()
            
            def on_complete(result_data):
                """扫描完成回调"""
                # result_data 是 TaskResult，data 是 List[str]（文件路径列表）
                if result_data and result_data.data:
                    self._enter_batch_mode(result_data.data)
                else:
                    self._info_bar_error("扫描文件夹", "未找到图片文件")
            
            def on_error(error_msg):
                """扫描失败回调"""
                self._info_bar_error("扫描文件夹失败", str(error_msg))
            
            core_api.scan_folder(
                folder_path,
                on_complete=on_complete,
                on_error=on_error
            )
    
    def _on_select_multiple_files(self):
        """选择多个文件按钮槽函数（批量模式）"""
        from PySide6.QtWidgets import QFileDialog
        
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "选择多个图片",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tiff *.tif)"
        )
        
        if file_paths:
            # 保存共同目录路径（通过 CoreAPI 获取）
            from api.core_api import get_core_api
            core_api = get_core_api()
            self.batch_folder_path = core_api.get_batch_folder_path(file_paths)
            
            # 调用核心层处理
            core_api.set_batch_files(file_paths)
            
            # 直接进入批量模式
            self._enter_batch_mode(file_paths)
    
    def _display_image(self, file_path: str, keep_batch_mode: bool = False):
        """显示图片到预览区域（纯UI显示）
        
        Args:
            file_path: 图片文件路径
            keep_batch_mode: 是否保持批量模式（用于从列表预览图片时）
        """
        # 如果不是从批量列表预览，则退出批量模式
        if not keep_batch_mode and self.is_batch_mode:
            self._exit_batch_mode()
        
        # 切换图片时清除上一张的识别结果
        self._clear_ocr_results()
        
        # 加载图片
        pixmap = QPixmap(file_path)
        if pixmap.isNull():
            self._info_bar_error("显示图片失败", "无法加载图片文件")
            return
        
        # 保存原始 pixmap 和文件路径
        self._image_original_pixmap = pixmap
        self.current_image_path = file_path
        
        # 显示文件名
        from api.core_api import get_core_api
        core_api = get_core_api()
        self.image_filename_label.setText(core_api.get_current_filename(file_path))
        self.image_filename_label.setVisible(True)
        
        # 重置缩放比例
        self._image_scale_factor = 1.0
        self._update_image_display()
        
        # 显示文件路径（tooltip）
        self.image_label.setToolTip(file_path)
        
        # 显示单图预览，隐藏列表
        self.single_image_container.setVisible(True)
        self.file_list_widget.setVisible(False)
        self.batch_header.setVisible(False)
        
        # 在单图预览时显示"返回列表"按钮（如果保持了批量模式）
        if keep_batch_mode and self.batch_file_paths:
            self.btn_back_to_list.setVisible(True)
        
        # 自动适应窗口显示
        QTimer.singleShot(0, self._on_zoom_fit)
    
    def _update_image_display(self):
        """根据缩放比例更新图片显示"""
        if self._image_original_pixmap is None:
            return
        
        # 计算缩放后的尺寸
        original_size = self._image_original_pixmap.size()
        new_width = int(original_size.width() * self._image_scale_factor)
        new_height = int(original_size.height() * self._image_scale_factor)
        
        # 缩放图片
        scaled_pixmap = self._image_original_pixmap.scaled(
            new_width, new_height,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        
        self.image_label.setPixmap(scaled_pixmap)
        self.image_label.resize(scaled_pixmap.size())
    
    def _on_zoom_in(self):
        """放大图片"""
        self._image_scale_factor *= 1.2
        self._update_image_display()
    
    def _on_zoom_out(self):
        """缩小图片"""
        self._image_scale_factor /= 1.2
        # 限制最小缩放比例
        if self._image_scale_factor < 0.1:
            self._image_scale_factor = 0.1
        self._update_image_display()
    
    def _on_zoom_fit(self):
        """适应窗口大小"""
        if self._image_original_pixmap is None:
            return
        
        # 计算适应滚动区域的缩放比例
        scroll_size = self.image_scroll_area.size()
        image_size = self._image_original_pixmap.size()
        
        # 计算宽高比的缩放因子
        width_ratio = scroll_size.width() / image_size.width()
        height_ratio = scroll_size.height() / image_size.height()
        
        # 选择较小的比例以确保图片完全显示
        self._image_scale_factor = min(width_ratio, height_ratio) * 0.95  # 留一点边距
        
        self._update_image_display()
    
    def _enter_batch_mode(self, file_paths: list):
        """进入批量模式（纯UI显示）"""
        from api.core_api import get_core_api
        core_api = get_core_api()
        
        self.is_batch_mode = True
        self.batch_file_paths = file_paths
        
        # 切换显示：显示列表，隐藏单图预览和"返回列表"按钮
        self.single_image_container.setVisible(False)
        self.file_list_widget.setVisible(True)
        self.batch_header.setVisible(True)
        self.btn_back_to_list.setVisible(False)  # 显示列表时隐藏"返回列表"按钮
        
        # 更新文件夹名称标签
        folder_name = core_api.get_batch_folder_display_name(
            self.batch_folder_path, file_paths
        )
        self.batch_folder_label.setText(folder_name)
        
        # 填充文件列表
        self.file_list_widget.clear()
        for file_path in file_paths:
            item = QListWidgetItem()
            item.setText(core_api.get_current_filename(file_path))
            item.setToolTip(file_path)
            
            # 设置缩略图
            thumbnail = _get_file_thumbnail(file_path)
            item.setIcon(QIcon(thumbnail))
            
            # ★ 去掉拖拽标志（ItemIsDragEnabled 会阻止双击信号触发）
            item.setFlags(item.flags() & ~Qt.ItemIsDragEnabled)
            
            self.file_list_widget.addItem(item)
        
        # 更新计数
        self.batch_count_label.setText(f"{len(file_paths)} 个文件")
        
        # 启用识别按钮
        self.btn_recognize.setEnabled(True)
        
        # 优化：如果引擎已就绪，自动开始批量识别
        if core_api.is_ocr_engine_ready():
            QTimer.singleShot(100, self._on_recognize)  # 延迟100ms确保UI更新完成
    
    def _exit_batch_mode(self):
        """退出批量模式（纯UI显示）"""
        self.is_batch_mode = False
        self.batch_file_paths = []
        
        self.single_image_container.setVisible(True)
        self.file_list_widget.setVisible(False)
        self.batch_header.setVisible(False)
        self.btn_back_to_list.setVisible(False)
        self.image_filename_label.setVisible(False)
    
    def _on_file_selected(self, item):
        """文件列表单击事件：仅选中，不预览"""
        # 只更新选中状态，预览留给双击
        pass
    
    def _on_list_double_clicked(self, item):
        """文件列表双击：预览图片并自动开始识别"""
        index = self.file_list_widget.row(item)
        file_path = self.batch_file_paths[index]
        
        # 显示预览（不隐藏列表，保留双击触发区域）
        self._display_image(file_path, keep_batch_mode=True)
        # 切换结果区域为单图文本框模式
        self.result_table.setVisible(False)
        self.result_text.setVisible(True)
        # 延迟开始识别
        QTimer.singleShot(0, self._on_recognize)
    
    def _copy_text_to_clipboard(self, text: str):
        """将文本复制到剪贴板"""
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)
        self._info_bar_success("复制成功", "已复制到剪贴板")
    
    def _on_back_to_list(self):
        """返回列表按钮槽函数"""
        # 直接切换显示，不重新加载数据（数据还在 batch_file_paths 中）
        self.single_image_container.setVisible(False)
        self.file_list_widget.setVisible(True)
        self.batch_header.setVisible(True)
        self.btn_back_to_list.setVisible(False)
    
    def _on_file_dropped(self, file_path: str):
        """处理拖放的单图文件（纯UI交互）"""
        # 调用核心层处理（验证逻辑）
        from api.core_api import get_core_api
        core_api = get_core_api()
        core_api.set_current_image(file_path)
        
        # 直接更新UI
        self._display_image(file_path)
        self.btn_recognize.setEnabled(True)
        
        # 优化：如果引擎已就绪，自动开始识别
        if core_api.is_ocr_engine_ready():
            QTimer.singleShot(100, self._on_recognize)  # 延迟100ms确保UI更新完成
    
    def _on_folder_dropped(self, file_paths: list):
        """处理拖放的文件夹（纯UI交互）"""
        if not file_paths:
            self._info_bar_warning("拖放文件夹", "文件夹中没有图片文件")
            return
        
        # 保存文件夹路径（通过 CoreAPI 获取）
        if file_paths:
            from api.core_api import get_core_api
            core_api = get_core_api()
            self.batch_folder_path = core_api.get_batch_folder_path(file_paths)
        
        # 调用核心层处理
        from api.core_api import get_core_api
        core_api = get_core_api()
        core_api.set_batch_files(file_paths)
        
        # 直接进入批量模式
        self._enter_batch_mode(file_paths)
        
        # 优化：如果引擎已就绪，自动开始批量识别
        if core_api.is_ocr_engine_ready():
            QTimer.singleShot(100, self._on_recognize)  # 延迟100ms确保UI更新完成
    
    # ─────────────────────── 其他槽函数（占位）─────────────────────── #
    
    def _on_screenshot(self):
        """截图识别按钮槽函数（待实现）"""
        self._info_bar_info("提示", "截图识别功能正在开发中...")
    
    def _on_recognize(self):
        """开始识别按钮槽函数（调用核心层API）"""
        from api.core_api import get_core_api
        core_api = get_core_api()
        
        # 检查引擎是否就绪（如果崩溃则自动重新初始化）
        if not core_api.is_ocr_engine_ready():
            status = core_api.get_ocr_engine_status()
            if status == 'not_initialized':
                # 引擎未初始化（可能是进程被强杀），自动触发重新初始化
                self._info_bar_warning("引擎未就绪", "正在重新初始化引擎，请稍后重试...")
                self._show_state_tooltip("初始化引擎", "正在重新初始化 OCR 引擎...")
                
                def on_init_complete(data):
                    self._hide_state_tooltip()
                    if data.get('success'):
                        self._info_bar_success("引擎就绪", "OCR 引擎已重新初始化，可以开始识别")
                        self.update_engine_status()
                        # ★ 初始化成功后自动重试识别
                        self._on_recognize()
                    else:
                        self._info_bar_error("初始化失败", data.get('message', '未知错误'))
                
                def on_init_error(msg):
                    self._hide_state_tooltip()
                    self._info_bar_error("初始化失败", str(msg))
                
                core_api.submit_ocr_init_task(
                    on_complete=on_init_complete,
                    on_error=on_init_error
                )
            else:
                self._info_bar_warning("引擎未就绪", "请等待 OCR 引擎初始化完成")
            return
        
        # 禁用识别按钮，启用取消按钮
        self.btn_recognize.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setVisible(True)
        
        # 定义回调函数
        def on_progress(task_result):
            """进度回调"""
            self._on_ocr_progress(task_result)
        
        def on_complete(task_result):
            """完成回调"""
            self._on_ocr_complete(task_result)
        
        def on_error(task_result):
            """错误回调"""
            self._on_ocr_error(task_result)
        
        # 根据当前界面状态，确定提交给 API 的识别目标
        # 列表视图 → 传批量文件路径（批量识别）
        # 单图预览 → 传当前图片路径（单图识别）
        image_paths = self._get_recognize_target()
        
        if not image_paths:
            self._info_bar_warning("未选择图片", "请先选择要识别的图片")
            self._reset_recognize_ui()
            return
        
        # 记录当前任务类型，供回调使用
        self._current_task_is_batch = isinstance(image_paths, list)
        
        # 读取选中的模板 ID
        idx = self.combo_template.currentIndex()
        template_id = self._template_ids[idx] if idx >= 0 else None
        
        # 批量识别：预设置表格行数，以便实时写入
        if isinstance(image_paths, list):
            self.result_text.setVisible(False)
            self.result_table.setVisible(True)
            self.result_table.setRowCount(len(image_paths))
        
        core_api.submit_ocr_task(
            image_paths,
            on_progress=on_progress,
            on_complete=on_complete,
            on_error=on_error,
            template_id=template_id
        )
        
        # 根据识别类型显示提示
        if isinstance(image_paths, list):
            self._show_state_tooltip("批量识别中", f"共 {len(image_paths)} 个文件")
        else:
            self._show_state_tooltip("识别中", "正在识别图片...")
    
    def _get_recognize_target(self) -> str | list | None:
        """根据当前界面状态，返回应提交给 API 的识别目标
        
        界面状态映射（纯 UI 状态 → API 参数）：
        - 列表视图可见 → 传批量文件路径列表（CoreAPI 自动识别为批量任务）
        - 单图预览视图 → 传当前图片路径字符串（CoreAPI 自动识别为单图任务）
        """
        if self.file_list_widget.isVisible() and self.batch_file_paths:
            return self.batch_file_paths
        elif self.current_image_path:
            return self.current_image_path
        return None
    
    def _on_ocr_progress(self, task_result):
        """OCR识别进度回调（可能来自工作线程，通过信号转到主线程）"""
        self._progress_signal.emit(task_result)
    
    def _do_progress_update(self, task_result):
        """在主线程执行进度 UI 更新"""
        progress = task_result.progress
        current = progress.get('current', 0)
        total = progress.get('total', 0)
        filename = progress.get('filename', '')
        
        if self._current_task_is_batch:
            # 批量识别：StateToolTip 只显示计数
            self._update_state_tooltip("批量识别中", f"已完成 {current}/{total}")
            
            # 状态栏显示当前识别的文件名
            if filename:
                from api.core_api import get_core_api
                core_api = get_core_api()
                display_name = core_api.get_current_filename(filename)
                self.status_label.setText(f"正在识别: {display_name}")
            
            # 同步高亮列表中当前识别的文件
            if filename and hasattr(self, 'batch_file_paths'):
                try:
                    idx = self.batch_file_paths.index(filename)
                    self.file_list_widget.setCurrentRow(idx)
                except ValueError:
                    pass
            
            # 实时写入表格：进度回调携带当前已完成的结果
            progress = task_result.progress or {}
            result_item = progress.get('result', None)
            current = progress.get('current', 0)
            if result_item and self.result_table.isVisible():
                row = current - 1  # current 是 1-based
                self._update_table_row(row, result_item)
        else:
            # 单图识别：更新进度提示
            self._update_state_tooltip(
                "识别中",
                f"识别进度: {current}/{total}"
            )
    
    def _on_ocr_complete(self, task_result):
        """OCR识别完成回调"""
        # 获取识别结果
        results = task_result.data  # List[Dict]
        
        # 更新进度条为100%
        self.progress_bar.setValue(100)
        self.progress_bar.setVisible(False)
        
        # 显示完成状态：更新已有 StateToolTip 并设为完成态
        # ★ 匹配官方 Demo：setState(True) 后 tooltip 会自动消失，不需要手动关闭
        if hasattr(self, '_state_tooltip') and self._state_tooltip:
            self._state_tooltip.setContent('识别完成')
            self._state_tooltip.setState(True)
            self._state_tooltip = None  # 只清引用，tooltip 会自动消失（官方 Demo 用法）
        else:
            # 边界情况：tooltip 已不存在，创建一个并立即完成
            self._show_state_tooltip("识别完成", "已完成全部识别", is_done=True)
        
        # 重置按钮状态
        self._reset_recognize_ui()
        
        if not results:
            self._info_bar_warning("识别失败", "未获取到识别结果")
            return
        
        # ★ 将识别结果存入 ResultManager 缓存（供重新解析等功能使用）
        from core.result_manager import get_result_manager
        result_manager = get_result_manager()
        for item in results:
            file_path = item.get("file_path", "")
            ocr_result = item.get("result", {})
            if file_path and ocr_result:
                result_manager.add_result(file_path, ocr_result)
        
        # 显示结果
        if self._current_task_is_batch:
            # 批量识别：更新表格
            self._display_batch_results(results)
        else:
            # 单图识别：更新文本框，并存储结果供导出/复制使用
            self._current_single_result = results[0] if results else None
            self._display_single_result(self._current_single_result)
        
        # 启用复制和导出按钮
        self.btn_copy.setEnabled(True)
        self.btn_export.setEnabled(True)
        
        # ★ 显示重新解析按钮（识别完成后可以更换模板重新解析）
        self.btn_reparse.setVisible(True)
        
        # 显示成功提示
        if self._current_task_is_batch:
            from api.core_api import get_core_api
            core_api = get_core_api()
            summary = core_api.get_ocr_summary(results)
            self._info_bar_success("识别完成", summary['summary_text'], duration=5000)
        else:
            self._info_bar_success("识别完成", "图片识别成功", duration=5000)
        
        # ★ 强制在 6 秒后关闭"识别完成"的 InfoBar（防止不消失）
        QTimer.singleShot(6000, lambda: self._close_info_bar_by_title("识别完成"))
        
        # 延迟恢复状态栏，让用户看到完成提示
        QTimer.singleShot(2000, self._restore_status_bar)
        
        # ★ 发射识别完成信号，通知 MainWindow 刷新历史记录页面
        if self._current_task_is_batch:
            self.batch_ocr_completed.emit()
        else:
            file_path = results[0].get("file_path", "") if results else ""
            self.ocr_completed.emit(file_path)
        
        # 如果启用了自动复制，则自动复制到剪贴板
        from interfaces.fluent.ui_config import UIConfigManager
        ui_config = UIConfigManager()
        if ui_config.get_auto_copy():
            self._on_copy()
    
    def _on_ocr_error(self, task_result):
        """OCR识别错误回调"""
        # 隐藏进度条和提示
        self._hide_state_tooltip()
        self.progress_bar.setVisible(False)
        
        # 重置按钮状态
        self._reset_recognize_ui()
        
        # 恢复状态栏
        self._restore_status_bar()
        
        # 显示错误提示
        error_msg = task_result.error or "未知错误"
        self._info_bar_error("识别失败", error_msg)
    
    def startOCR(self):
        """公开接口：开始 OCR 识别（供历史记录等外部调用）"""
        self._on_recognize()
    
    def loadImage(self, file_path: str):
        """公开接口：加载图片到预览区（供历史记录等外部调用）"""
        self._display_image(file_path)
    
    def _reset_recognize_ui(self):
        """重置识别相关的UI状态"""
        self.btn_recognize.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress_bar.setVisible(False)
        # 隐藏重新解析按钮
        self.btn_reparse.setVisible(False)
    
    def _restore_status_bar(self):
        """恢复状态栏为引擎就绪状态"""
        self.update_engine_status()

    
    def _clear_ocr_results(self):
        """切换图片时清除上一张的识别结果"""
        # 清除单图文本结果
        self.result_text.clear()
        # 清除批量表格结果
        self.result_table.setRowCount(0)
        # 重置按钮状态
        self.btn_copy.setEnabled(False)
        self.btn_export.setEnabled(False)
        # 隐藏重新解析按钮
        self.btn_reparse.setVisible(False)
    
    def _display_single_result(self, result: dict):
        """显示单图识别结果（纯显示，数据由 CoreAPI 处理）"""
        if not result:
            self.result_text.setPlainText("未获取到识别结果")
            return
        
        from api.core_api import get_core_api
        core_api = get_core_api()
        info = core_api.get_ocr_result_display_info(result)
        
        if info['is_success']:
            self.result_text.setPlainText(info['text'])
        else:
            self.result_text.setPlainText(f"识别失败:\n{info['error_msg']}")
        
        # 切换到文本框显示
        self.result_text.setVisible(True)
        self.result_table.setVisible(False)
    
    def _display_batch_results(self, results: list):
        """显示批量识别结果（纯显示，数据由 CoreAPI 处理）"""
        from api.core_api import get_core_api
        core_api = get_core_api()
        
        # 切换到表格显示
        self.result_text.setVisible(False)
        self.result_table.setVisible(True)
        
        # 清空表格
        self.result_table.setRowCount(0)
        
        # 填充表格
        for row, result in enumerate(results):
            self.result_table.insertRow(row)
            
            info = core_api.get_ocr_result_display_info(result)
            
            # 文件名（第0列）— 一劳永逸：_set_cell 自动设置 tooltip
            self._set_cell(row, 0, info['file_name'])
            
            # 识别内容（第1列）
            if info['is_success']:
                self._set_cell(row, 1, info['text'], store_full=True)
            else:
                self._set_cell(row, 1, f"错误: {info['error_msg']}")
            
            # 提取字段（第2列）— 一劳永逸
            self._set_cell(row, 2, info['extracted_text'])
        
        # 自动调整行高
        for row in range(self.result_table.rowCount()):
            self.result_table.resizeRowToContents(row)
    
    def _set_cell(self, row: int, col: int, text: str, store_full: bool = False):
        """
        设置单元格文本和预览（tooltip）
        以后扩列只需调用此方法，tooltip 自动生效，无需单独设置
        
        Args:
            row: 行号（0-based）
            col: 列号（0-based）
            text: 显示文本（同时作为 tooltip 内容）
            store_full: 是否将完整文本存入 Qt.UserRole（用于需要复制完整文本的列）
        """
        item = QTableWidgetItem(text)
        if store_full:
            item.setData(Qt.UserRole, text)  # 存完整文本（用于复制等场景）
        item.setToolTip(text)  # 预览完整内容
        self.result_table.setItem(row, col, item)
    
    def _update_table_row(self, row: int, result_item: dict):
        """实时更新表格中指定行（供进度回调调用）"""
        from api.core_api import get_core_api
        core_api = get_core_api()
        info = core_api.get_ocr_result_display_info(result_item)
        
        # 第0列：文件名（只写一次，_set_cell 自动设置 tooltip）
        if not self.result_table.item(row, 0):
            self._set_cell(row, 0, info['file_name'])
        
        # 第1列：识别内容（总是更新）
        if info['is_success']:
            self._set_cell(row, 1, info['text'], store_full=True)
        else:
            self._set_cell(row, 1, f"错误: {info['error_msg']}")
        
        # 第2列：提取字段（总是更新）
        self._set_cell(row, 2, info['extracted_text'])
        
        # 实时调整当前行行高
        self.result_table.resizeRowToContents(row)

    def _on_cancel(self):
        """中断按钮槽函数"""
        # 取消当前任务
        from api.core_api import get_core_api
        core_api = get_core_api()
        
        # 获取当前运行的任务并取消
        running_tasks = core_api.get_running_tasks()
        if running_tasks:
            task_id = running_tasks[0].task_id
            core_api.cancel_task(task_id)
            self._info_bar_info("提示", "已取消识别任务")
        
        # 重置UI状态
        self._reset_recognize_ui()
        self._hide_state_tooltip()
    
    def _on_copy(self):
        """复制按钮槽函数（含文件名和提取字段）"""
        from PySide6.QtGui import QGuiApplication
        from api.core_api import get_core_api
        clipboard = QGuiApplication.clipboard()
        core_api = get_core_api()
        
        # 根据当前结果展示控件决定复制来源
        if self.result_table.isVisible():
            # 表格可见：复制表格中所有识别结果（含文件名和提取字段）
            text_list = []
            for row in range(self.result_table.rowCount()):
                file_item = self.result_table.item(row, 0)
                text_item = self.result_table.item(row, 1)
                extracted_item = self.result_table.item(row, 2)
                
                if file_item:
                    file_name = file_item.text()
                    full_text = text_item.data(Qt.UserRole) or (text_item.text() if text_item else '')
                    extracted_text = extracted_item.data(Qt.UserRole) or (extracted_item.text() if extracted_item else '')
                    
                    # 格式化：文件名 + 识别内容 + 提取字段
                    entry = f"【文件: {file_name}】\n"
                    entry += f"【识别内容】\n{full_text}\n"
                    if extracted_text:
                        entry += f"【提取字段】\n{extracted_text}\n"
                    text_list.append(entry)
            
            if text_list:
                clipboard.setText("\n---\n".join(text_list))
                self._info_bar_success("复制成功", f"已复制 {len(text_list)} 个识别结果")
            else:
                self._info_bar_warning("复制失败", "没有可复制的识别结果")
        else:
            # 文本框可见：复制文本框内容（含文件名和提取字段）
            text = self.result_text.toPlainText()
            if text:
                file_name = core_api.get_current_filename(self.current_image_path) if self.current_image_path else 'unknown'
                
                # 获取提取字段内容
                extracted_text = ''
                if self._current_single_result and 'extracted' in self._current_single_result:
                    ext = self._current_single_result['extracted']
                    if ext:
                        extracted_text = '\n'.join([f"{k}: {v}" for k, v in ext.items()])
                
                # 格式化：文件名 + 识别内容 + 提取字段
                clipboard_text = f"【文件: {file_name}】\n"
                clipboard_text += f"【识别内容】\n{text}\n"
                if extracted_text:
                    clipboard_text += f"【提取字段】\n{extracted_text}\n"
                
                clipboard.setText(clipboard_text)
                self._info_bar_success("复制成功", "已复制到剪贴板")
            else:
                self._info_bar_warning("复制失败", "没有可复制的识别结果")
    
    def _on_export(self, format: str):
        """导出按钮槽函数"""
        from PySide6.QtWidgets import QFileDialog
        from api.core_api import get_core_api
        core_api = get_core_api()
        
        # ★ 标准化格式名（兼容旧配置中的 "EXCEL" 等变体）
        format = format.strip().upper() if format.strip().upper() in ("TXT", "JSON") else "Excel"
        
        # 获取识别结果
        results = []
        
        # 根据当前结果展示控件决定导出来源
        if self.result_table.isVisible():
            # 表格可见：动态提取所有列
            col_count = self.result_table.columnCount()
            column_headers = []
            for col in range(col_count):
                header_item = self.result_table.horizontalHeaderItem(col)
                header_text = header_item.text() if header_item else f"列{col}"
                column_headers.append(header_text)
            
            for row in range(self.result_table.rowCount()):
                row_data = {}
                for col in range(col_count):
                    item = self.result_table.item(row, col)
                    text = item.data(Qt.UserRole) or (item.text() if item else '')
                    row_data[column_headers[col]] = text
                results.append(row_data)
            
            # 存储列头，供导出使用
            self._export_column_headers = column_headers
        else:
            # 文本框可见：从文本框获取结果，并获取提取字段
            text = self.result_text.toPlainText()
            if text:
                file_name = core_api.get_current_filename(self.current_image_path) if self.current_image_path else 'unknown'
                # 从存储的单图结果中获取提取字段
                extracted_text = ''
                if self._current_single_result and 'extracted' in self._current_single_result:
                    ext = self._current_single_result['extracted']
                    if ext:
                        extracted_text = '\n'.join([f"{k}: {v}" for k, v in ext.items()])
                results.append({
                    'file_name': file_name,
                    'text': text,
                    'extracted_text': extracted_text
                })
        
        if not results:
            self._info_bar_warning("导出失败", "没有可导出的识别结果")
            return
        
        # 选择保存路径
        format_filter = {
            "TXT": "文本文件 (*.txt)",
            "JSON": "JSON 文件 (*.json)",
            "Excel": "Excel 文件 (*.xlsx)"
        }
        
        ext = format.lower() if format != 'Excel' else 'xlsx'
        is_batch = self.result_table.isVisible() and self.result_table.rowCount() > 1
        default_name = core_api.get_export_default_name(
            is_batch=is_batch,
            image_path=self.current_image_path,
            ext=ext
        )
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"导出为 {format}",
            default_name,
            format_filter.get(format, "所有文件 (*.*)")
        )
        
        if file_path:
            # 读取配置：是否包含原始文本
            from interfaces.fluent.ui_config import UIConfigManager
            ui_config = UIConfigManager()
            include_original_text = ui_config.get_export_include_original_text()
            
            # 调用核心层导出API
            core_api = get_core_api()
            
            def on_complete(task_result):
                """导出完成回调"""
                from interfaces.fluent.ui_config import UIConfigManager
                info = core_api.get_export_result_display_info(task_result.data)
                if info['is_success']:
                    # 保存导出格式（优化：记住上次格式）
                    ui_config = UIConfigManager()
                    ui_config.set_last_export_format(format)
                    self._update_export_button_text()  # ★ 刷新按钮文本
                    self._info_bar_success("导出成功", f"结果已保存到: {info['saved_path'] or file_path}")
                else:
                    self._info_bar_error("导出失败", info['error_msg'])
            
            def on_error(task_result):
                self._info_bar_error("导出失败", task_result.error or "未知错误")
            
            core_api.submit_export_task(
                export_format=format,
                file_path=file_path,
                results=results,
                column_headers=getattr(self, '_export_column_headers', None),
                include_original_text=include_original_text,  # 新增参数
                on_complete=on_complete,
                on_error=on_error
            )
            
            self._info_bar_info("提示", f"正在导出为 {format}...")

    def _on_export_with_format(self, format: str):
        """下拉菜单选择格式时调用"""
        from interfaces.fluent.ui_config import UIConfigManager
        # ★ 标准化后立即保存，确保按钮刷新读到最新值
        normalized = "Excel" if format.upper() not in ("TXT", "JSON") else format.upper()
        UIConfigManager().set_last_export_format(normalized)
        self._update_export_button_text()
        self._on_export(normalized)
    
    def _on_export_last_format(self):
        """主按钮点击时调用：使用上次格式导出"""
        from interfaces.fluent.ui_config import UIConfigManager
        ui_config = UIConfigManager()
        last_format = ui_config.get_last_export_format()
        # ★ 兼容旧配置
        if last_format and last_format.upper() not in ("TXT", "JSON"):
            last_format = "Excel"
        
        # 调用导出
        self._on_export(last_format)

    def _update_export_button_text(self):
        """更新导出按钮文本（显示上次使用的格式）"""
        from interfaces.fluent.ui_config import UIConfigManager
        ui_config = UIConfigManager()
        last_format = ui_config.get_last_export_format()
        # ★ 兼容旧配置
        if last_format and last_format.upper() not in ("TXT", "JSON"):
            last_format = "Excel"
        
        # 根据格式设置按钮文本
        format_display = {
            "TXT": "导出为 TXT",
            "JSON": "导出为 JSON",
            "Excel": "导出为 Excel",
        }
        button_text = format_display.get(last_format, "导出")
        self.btn_export.setText(button_text)

    def _on_reparse(self):
        """重新解析按钮槽函数：使用当前选中的模板重新解析识别结果（使用缓存）"""
        from api.core_api import get_core_api
        from core.result_manager import get_result_manager
        import os
        
        core_api = get_core_api()
        result_manager = get_result_manager()
        
        # 读取选中的模板 ID
        idx = self.combo_template.currentIndex()
        template_id = self._template_ids[idx] if idx >= 0 else None
        
        if not template_id:
            self._info_bar_warning("重新解析", "请先选择一个识别模板")
            return
        
        # ★ 从 ResultManager 缓存读取结果
        cached_results = result_manager.get_current_results()  # dict: image_path -> ocr_result
        
        if not cached_results:
            self._info_bar_warning("重新解析", "没有可重新解析的识别结果")
            return
        
        # 转换为 reparse_results() 期望的格式
        # ★ current_results 存的是 {'result': ocr_result, 'image_hash': str}，需要解包
        results = []
        for image_path, cached in cached_results.items():
            ocr_result = cached.get('result', {})
            # 提取文本
            text = ""
            if ocr_result.get('code') == 100 and ocr_result.get('data'):
                texts = [line.get('text', '') for line in ocr_result['data'] if isinstance(line, dict)]
                text = '\n'.join(texts)
            
            results.append({
                'file_path': image_path,
                'file_name': os.path.basename(image_path),
                'text': text,
                'result': ocr_result,  # ★ 保留原始结果，get_ocr_result_display_info 需要
            })
        
        # 判断是批量模式还是单图模式
        is_batch = len(cached_results) > 1
        
        # 调用核心层重新解析
        def on_complete(task_result):
            """重新解析完成回调"""
            if task_result.data:
                # 更新 UI 显示
                if is_batch:
                    self._display_batch_results(task_result.data)
                else:
                    # 单图模式
                    if task_result.data and len(task_result.data) > 0:
                        self._current_single_result = task_result.data[0]
                        self._display_single_result(self._current_single_result)
                
                self._info_bar_success("重新解析完成", f"已使用模板重新解析 {len(results)} 个结果")
        
        def on_error(task_result):
            self._info_bar_error("重新解析失败", task_result.error or "未知错误")
        
        core_api.reparse_results(
            results,
            template_id=template_id,
            on_complete=on_complete,
            on_error=on_error
        )
