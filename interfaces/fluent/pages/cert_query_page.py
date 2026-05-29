# 检疫证查询页面
# 基于 qfluentwidgets Fluent Design 风格
#
# 功能：输入检疫证号 + 选择类型 → 查询 → 表格展示 → 导出 Excel

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QTableWidget, QTableWidgetItem,
    QHeaderView, QFileDialog, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QThread, QTimer, QSize
from PySide6.QtGui import QFont, QColor, QIcon
from qfluentwidgets import (
    CardWidget, PrimaryPushButton, PushButton,
    ComboBox, InfoBar, InfoBarPosition,
    SubtitleLabel, BodyLabel, LineEdit,
    FluentIcon, IndeterminateProgressBar, TableWidget,
)

logger = logging.getLogger(__name__)


class _QueryThread(QThread):
    """异步查询线程，避免阻塞 UI"""
    finished = Signal(object)  # CertQueryResult 或 None（查询出错）
    error = Signal(str)

    def __init__(self, factory_code: str, cert_type: str):
        super().__init__()
        self.factory_code = factory_code
        self.cert_type = cert_type

    def run(self):
        try:
            from core.cert_query import query_cert
            result = query_cert(self.factory_code, self.cert_type)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class CertQueryPage(QWidget):
    """检疫证查询页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("cert_query_page")
        self._query_thread = None
        self._results = []  # 存储查询结果供导出
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ── 标题 ──────────────────────────
        title = SubtitleLabel("动物检疫合格证明 — 公众查询", self)
        title.setStyleSheet("font-size: 20px; font-weight: 600;")
        layout.addWidget(title)

        # ── 查询卡片 ──────────────────────────
        query_card = CardWidget(self)
        query_layout = QVBoxLayout(query_card)
        query_layout.setContentsMargins(20, 16, 20, 16)
        query_layout.setSpacing(12)

        # 查询行
        query_row = QHBoxLayout()
        query_row.setSpacing(12)

        # 类型下拉
        type_label = BodyLabel("证书类型：", self)
        query_row.addWidget(type_label)

        self.combo_type = ComboBox(self)
        self.combo_type.setMinimumWidth(180)
        from core.cert_query import get_cert_types
        cert_types = get_cert_types()
        for ct in cert_types:
            self.combo_type.addItem(ct["name"])
        self.combo_type.setCurrentIndex(0)
        query_row.addWidget(self.combo_type)

        query_row.addSpacing(20)

        # 编号输入
        code_label = BodyLabel("检疫证号：", self)
        query_row.addWidget(code_label)

        self.edit_code = LineEdit(self)
        self.edit_code.setPlaceholderText("请输入10-11位检疫证明印刷号")
        self.edit_code.setMinimumWidth(280)
        self.edit_code.setClearButtonEnabled(True)
        self.edit_code.returnPressed.connect(self._on_query)
        query_row.addWidget(self.edit_code)

        query_row.addSpacing(12)

        # 查询按钮
        self.btn_query = PrimaryPushButton(FluentIcon.SEARCH, "查询", self)
        self.btn_query.setFixedWidth(100)
        self.btn_query.clicked.connect(self._on_query)
        query_row.addWidget(self.btn_query)

        query_row.addStretch()
        query_layout.addLayout(query_row)

        # 提示文字
        hint_label = BodyLabel("请输入检疫证明印刷号或系统生成号码的任意一个进行查询", self)
        hint_label.setStyleSheet("color: #999; font-size: 12px;")
        query_layout.addWidget(hint_label)

        layout.addWidget(query_card)

        # ── 进度条 ──────────────────────────
        self.progress_bar = IndeterminateProgressBar(self)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # ── 结果表格 ──────────────────────────
        result_card = CardWidget(self)
        result_layout = QVBoxLayout(result_card)
        result_layout.setContentsMargins(16, 12, 16, 12)
        result_layout.setSpacing(8)

        # 表格头部
        table_header = QHBoxLayout()
        result_title = SubtitleLabel("查询结果", self)
        table_header.addWidget(result_title)

        self.result_count_label = BodyLabel("", self)
        self.result_count_label.setStyleSheet("color: #666;")
        table_header.addWidget(self.result_count_label)

        table_header.addStretch()

        self.btn_export = PushButton(FluentIcon.SAVE, "导出 Excel", self)
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._on_export)
        table_header.addWidget(self.btn_export)

        result_layout.addLayout(table_header)

        # 表格
        self.result_table = TableWidget(self)
        self.result_table.setColumnCount(3)
        self.result_table.setHorizontalHeaderLabels(["字段", "值", "备注"])
        self.result_table.setColumnWidth(0, 150)
        self.result_table.setColumnWidth(2, 120)
        self.result_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.result_table.setWordWrap(True)
        self.result_table.setMinimumHeight(200)
        result_layout.addWidget(self.result_table)

        layout.addWidget(result_card)

        # ── 底部留白 ──────────────────────────
        layout.addStretch()

    # ─────────────────────── 槽函数 ─────────────────────── #

    def _on_query(self):
        """查询按钮槽函数"""
        factory_code = self.edit_code.text().strip()
        if len(factory_code) < 10:
            InfoBar.warning(
                title="输入错误",
                content="请输入10位或11位检疫证明编号",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )
            return

        # 禁用查询按钮，显示进度条
        self.btn_query.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.start()

        # 清空旧结果
        self._results = []
        self.result_table.setRowCount(0)
        self.result_count_label.setText("")
        self.btn_export.setEnabled(False)

        # 获取类型
        idx = self.combo_type.currentIndex()
        cert_type = str(idx + 1)  # "1" ~ "7"

        # 异步查询
        self._query_thread = _QueryThread(factory_code, cert_type)
        self._query_thread.finished.connect(self._on_query_finished)
        self._query_thread.error.connect(self._on_query_error)
        self._query_thread.start()

    def _on_query_finished(self, result):
        """查询完成"""
        self.btn_query.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.progress_bar.stop()

        if result.success:
            self._display_result(result)
        else:
            InfoBar.warning(
                title="查询结果",
                content=result.error_msg or "未查询到数据",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self,
            )
            self.result_table.setRowCount(0)
            self.result_count_label.setText("（未查到）")

    def _on_query_error(self, error_msg: str):
        """查询出错"""
        self.btn_query.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.progress_bar.stop()
        InfoBar.error(
            title="查询失败",
            content=error_msg,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self,
        )

    def _display_result(self, result):
        """显示查询结果到表格"""
        self._results = [result]
        fields = result.fields

        self.result_table.setRowCount(len(fields))

        for row, (label, value) in enumerate(fields.items()):
            # 字段名
            field_item = QTableWidgetItem(label)
            field_item.setFont(QFont("", -1, QFont.Bold))
            field_item.setBackground(QColor("#F5F7FA"))
            self.result_table.setItem(row, 0, field_item)

            # 值
            value_item = QTableWidgetItem(value)
            value_item.setToolTip(value)
            self.result_table.setItem(row, 1, value_item)

            # 备注
            note = ""
            if label == "检疫证状态":
                note = "✅ 有效" if "有效" in value or "签发" in value else "⚠ " + value
            note_item = QTableWidgetItem(note)
            self.result_table.setItem(row, 2, note_item)

        self.result_count_label.setText(
            f"（{result.cert_type} · {result.factory_code}）"
        )
        self.btn_export.setEnabled(True)
        InfoBar.success(
            title="查询成功",
            content=f"已查到 {result.cert_type} 相关信息",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self,
        )

    def _on_export(self):
        """导出为 Excel"""
        if not self._results:
            InfoBar.warning(
                title="导出失败",
                content="没有可导出的查询结果",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出为 Excel",
            f"检疫证查询结果.xlsx",
            "Excel 文件 (*.xlsx)",
        )

        if file_path:
            from core.cert_query import export_to_excel
            if export_to_excel(self._results, file_path):
                InfoBar.success(
                    title="导出成功",
                    content=f"已保存到: {file_path}",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self,
                )
            else:
                InfoBar.error(
                    title="导出失败",
                    content="保存文件时出错",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=5000,
                    parent=self,
                )
