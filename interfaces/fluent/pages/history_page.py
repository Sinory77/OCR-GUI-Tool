"""
历史记录页面
使用 qfluentwidgets 官方控件
"""

import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Qt, Signal, QSize, QAbstractListModel
from qfluentwidgets import (
    CardWidget, PushButton, PrimaryPushButton,
    SubtitleLabel, BodyLabel, InfoBar, InfoBarPosition,
    FluentIcon, ListView, TextEdit, ListItemDelegate,
    MessageBox
)
from ..ui_utils import create_message_box


class HistoryModel(QAbstractListModel):
    """历史记录数据模型"""

    def __init__(self, history_data=None, parent=None):
        super().__init__(parent)
        self.history_data = history_data or []

    def rowCount(self, parent=None):
        return len(self.history_data)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        if row < 0 or row >= len(self.history_data):
            return None

        item = self.history_data[row]

        if role == Qt.DisplayRole:
            filename = item.get('filename', '未知')
            text = item.get('text', '')
            preview = text[:30] + '...' if len(text) > 30 else text
            if not preview:
                preview = "(无识别内容)"
            time = item.get('time', '')
            return f"{filename} - {preview}\n{time}"

        elif role == Qt.UserRole:
            return row

        elif role == Qt.ToolTipRole:
            return f"路径: {item.get('path', '')}\n\n{item.get('text', '')}"

        elif role == Qt.SizeHintRole:
            return QSize(0, 60)

        return None

    def updateData(self, history_data):
        """更新数据"""
        self.beginResetModel()
        self.history_data = history_data
        self.endResetModel()


class HistoryPage(QWidget):
    """历史记录页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.current_index = -1

        self.initUI()
        self.loadHistory()

    def initUI(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # 标题栏
        title_layout = QHBoxLayout()
        title_layout.addWidget(SubtitleLabel("识别历史", self))
        title_layout.addStretch()

        # 清空按钮
        self.btn_clear = PushButton(FluentIcon.DELETE, "清空历史", self)
        self.btn_clear.clicked.connect(self.clearHistory)
        title_layout.addWidget(self.btn_clear)

        main_layout.addLayout(title_layout)

        # 内容区域
        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        # 左侧 - 历史列表
        left_card = CardWidget(self)
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(8)

        # 列表标题
        list_header = QHBoxLayout()
        list_header.addWidget(BodyLabel("历史记录", self))
        self.history_count = BodyLabel("(0 条)", self)
        list_header.addWidget(self.history_count)
        list_header.addStretch()
        left_layout.addLayout(list_header)

        # 历史列表
        self.history_model = HistoryModel([], self)
        self.history_list = ListView(self)
        self.history_list.setModel(self.history_model)
        self.history_list.setItemDelegate(ListItemDelegate(self.history_list))
        self.history_list.clicked.connect(self.onItemClicked)
        left_layout.addWidget(self.history_list, 1)

        content_layout.addWidget(left_card, 1)

        # 右侧 - 详情面板
        right_card = CardWidget(self)
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(8)

        # 详情标题
        right_layout.addWidget(BodyLabel("识别详情", self))

        # 图片信息
        info_layout = QHBoxLayout()
        info_layout.addWidget(BodyLabel("图片: ", self))
        self.img_path_label = BodyLabel("-", self)
        self.img_path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.img_path_label.setWordWrap(True)
        info_layout.addWidget(self.img_path_label, 1)
        right_layout.addLayout(info_layout)

        # 识别结果
        self.result_text = TextEdit(self)
        self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText("点击左侧列表查看详情...")
        right_layout.addWidget(self.result_text, 1)

        # 操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_copy = PushButton(FluentIcon.COPY, "复制结果", self)
        self.btn_copy.clicked.connect(self.copyResult)
        self.btn_copy.setEnabled(False)
        btn_layout.addWidget(self.btn_copy)

        self.btn_view = PrimaryPushButton(FluentIcon.VIEW, "重新识别", self)
        self.btn_view.clicked.connect(self.recognizeAgain)
        self.btn_view.setEnabled(False)
        btn_layout.addWidget(self.btn_view)

        self.btn_delete = PushButton(FluentIcon.DELETE, "删除", self)
        self.btn_delete.clicked.connect(self.deleteCurrent)
        self.btn_delete.setEnabled(False)
        btn_layout.addWidget(self.btn_delete)

        right_layout.addLayout(btn_layout)

        content_layout.addWidget(right_card, 2)

        main_layout.addLayout(content_layout, 1)

    def loadHistory(self):
        """加载历史记录"""
        # 检查 result_manager 是否已初始化
        if not hasattr(self.main_window, 'result_manager') or not self.main_window.result_manager:
            return
        
        history = self.main_window.result_manager.get_history()
        self.history_model.updateData(history)
        self.history_count.setText(f"({len(history)} 条)")

        if len(history) == 0:
            self.result_text.setPlaceholderText("暂无历史记录")

    def onItemClicked(self, index):
        """点击列表项"""
        row = index.row()
        history = self.main_window.result_manager.get_history()

        if 0 <= row < len(history):
            self.current_index = row
            item = history[row]

            # 显示详情
            self.img_path_label.setText(item.get('path', '-'))
            self.result_text.setPlainText(item.get('text', ''))

            # 启用按钮
            self.btn_copy.setEnabled(True)
            self.btn_view.setEnabled(True)
            self.btn_delete.setEnabled(True)

    def copyResult(self):
        """复制结果"""
        history = self.main_window.result_manager.get_history()
        if 0 <= self.current_index < len(history):
            item = history[self.current_index]
            text = item.get('text', '')
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

    def recognizeAgain(self):
        """重新识别"""
        history = self.main_window.result_manager.get_history()
        if 0 <= self.current_index < len(history):
            item = history[self.current_index]
            image_path = item.get('path')
            if os.path.exists(image_path):
                # 切换到 OCR 页面
                self.main_window.stackedWidget.setCurrentWidget(self.main_window.ocr_page)
                self.main_window.navigationInterface.setCurrentItem("ocr_page")

                # 加载图片
                self.main_window.ocr_page.loadImage(image_path)
                self.main_window.ocr_page.startOCR()
            else:
                InfoBar.error(
                    title="文件不存在",
                    content=f"图片文件已不存在: {image_path}",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )

    def deleteCurrent(self):
        """删除当前项"""
        if self.current_index >= 0:
            if self.main_window.result_manager.delete_history(self.current_index):
                InfoBar.success(
                    title="已删除",
                    content="历史记录已删除",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )

                self.current_index = -1
                self.result_text.clear()
                self.img_path_label.setText("-")
                self.btn_copy.setEnabled(False)
                self.btn_view.setEnabled(False)
                self.btn_delete.setEnabled(False)

                self.loadHistory()

    def clearHistory(self):
        """清空所有历史"""
        message_box = create_message_box(
            "确认清空",
            "确定要清空所有历史记录吗？此操作不可撤销。",
            self.window()
        )
        if message_box.exec():
            self.main_window.result_manager.clear_history()

            InfoBar.success(
                title="已清空",
                content="所有历史记录已清空",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )

            self.current_index = -1
            self.result_text.clear()
            self.img_path_label.setText("-")
            self.btn_copy.setEnabled(False)
            self.btn_view.setEnabled(False)
            self.btn_delete.setEnabled(False)
            self.loadHistory()