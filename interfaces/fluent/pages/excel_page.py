# -*- coding: utf-8 -*-
"""
Excel 数据清洗 & 透视页面

功能：
- 多表加载与合并
- 数据清洗（去重、空值处理、类型转换、过滤）
- 数据透视（分组聚合、交叉表）
- 透视规则保存/加载（JSON 模板）
- 大表渲染（QAbstractTableModel 虚拟滚动）

架构：UI 只显示和交互，所有数据处理通过 CoreAPI → TaskManager → excel_processor
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidgetItem,
    QAbstractItemView, QFileDialog, QLabel, QComboBox,
    QCheckBox, QListWidget, QListWidgetItem, QMessageBox,
    QProgressDialog, QApplication, QSplitter, QButtonGroup,
)
from PySide6.QtCore import Qt, Signal, QAbstractTableModel, QModelIndex, QSize
from PySide6.QtGui import QFont, QColor

from qfluentwidgets import (
    SubtitleLabel, BodyLabel, CaptionLabel,
    PushButton, PrimaryPushButton, ComboBox, SearchLineEdit,
    ToolButton, TransparentToolButton, StrongBodyLabel,
    PillPushButton, setFont, TogglePushButton, InfoBar, InfoBarPosition,
    Pivot, CardWidget, ScrollArea,
    StateToolTip, FluentIcon as FIF,
)
from qfluentwidgets.components.widgets.button import PushButton
from qfluentwidgets import MessageBox

from api.core_api import get_core_api
from core.excel_models import PivotConfig, CleanRule, LoadedTable

# ──────────────────────────────────────────────────────────────
# 自定义 TableModel（虚拟滚动，支持万级行）
# ──────────────────────────────────────────────────────────────

class ExcelTableModel(QAbstractTableModel):
    """
    用于大表渲染的自定义 TableModel

    使用 QAbstractTableModel 实现虚拟滚动，
    只渲染可见行，万级数据不卡。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._columns = []        # 列名列表
        self._data = []          # 数据行列表 [{"col1": val1, ...}, ...]
        self._row_count = 0

    def load_from_df_json(self, df_json: str):
        """
        从 df_json（orient='split'）加载数据

        Args:
            df_json: pandas DataFrame 的 JSON 字符串（orient='split'）
        """
        import json
        parsed = json.loads(df_json)
        self.beginResetModel()
        self._columns = parsed.get("columns", [])
        # data 是 [[val1, val2, ...], ...] 格式
        raw_data = parsed.get("data", [])
        self._data = raw_data
        self._row_count = len(raw_data)
        self.endResetModel()

    def clear(self):
        self.beginResetModel()
        self._columns = []
        self._data = []
        self._row_count = 0
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return self._row_count

    def columnCount(self, parent=QModelIndex()):
        return len(self._columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()

        if role == Qt.DisplayRole:
            if row < len(self._data) and col < len(self._data[row]):
                val = self._data[row][col]
                return str(val) if val is not None else ""
            return ""

        elif role == Qt.TextAlignmentRole:
            return Qt.AlignLeft | Qt.AlignVCenter

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                if section < len(self._columns):
                    return self._columns[section]
                return f"列{section}"
            else:
                return str(section + 1)
        return None


# ──────────────────────────────────────────────────────────────
# 拖放区域
# ──────────────────────────────────────────────────────────────

class ExcelDropArea(CardWidget):
    """
    Excel 文件拖放区域

    接受 .xlsx / .xls / .csv 文件拖放，
    发射 file_dropped 信号。
    """

    files_dropped = Signal(list)   # List[str]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 20, 16, 20)
        layout.setSpacing(8)

        icon_label = QLabel("📊", self)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setFixedHeight(40)
        layout.addWidget(icon_label)

        hint = BodyLabel("拖放 Excel 文件到此处", self)
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)

        sub = CaptionLabel("支持 .xlsx / .xls / .csv", self)
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("color: gray;")
        layout.addWidget(sub)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        file_paths = []
        for url in event.mimeData().urls():
            fp = url.toLocalFile()
            ext = os.path.splitext(fp)[1].lower()
            if ext in ('.xlsx', '.xls', '.csv'):
                file_paths.append(fp)

        if file_paths:
            self.files_dropped.emit(file_paths)

        event.acceptProposedAction()


# ──────────────────────────────────────────────────────────────
# 主页面
# ──────────────────────────────────────────────────────────────

class ExcelPage(QWidget):
    """
    Excel 数据清洗 & 透视主页面

    布局：左右分栏
    - 左侧：数据源、清洗规则、模板管理
    - 右侧：数据预览、透视配置、导出
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self._core_api = None

        # 状态
        self._loaded_tables = []       # List[Dict] — submit_excel_load_task 返回的每个表 info
        self._cleaned_df_json = ""    # 清洗后数据的 df_json
        self._pivot_df_json = ""      # 透视结果的 df_json
        self._current_template_id = ""  # 当前加载的模板 ID

        # 异步任务 ID
        self._load_task_id = ""
        self._clean_task_id = ""
        self._pivot_task_id = ""
        self._export_task_id = ""

        # StateToolTip 引用
        self._load_tooltip = None
        self._clean_tooltip = None
        self._pivot_tooltip = None

        self._init_ui()
        self._connect_signals()

    # ──────────────────────────────────────────────────────
    # UI 初始化
    # ──────────────────────────────────────────────────────

    def _init_ui(self):
        """初始化 UI（左右分栏）"""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 分割器
        self.splitter = QSplitter(Qt.Horizontal, self)
        self.splitter.setHandleWidth(1)
        self.splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: rgba(0, 0, 0, 0.06);
            }
        """)

        # ── 左侧面板 ──────────────────────────────────
        self.left_panel = ScrollArea()
        self.left_panel.setWidgetResizable(True)
        self.left_panel.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(12)

        # 标题
        title = SubtitleLabel("📊 数据透视", left_widget)
        setFont(title, 18)
        left_layout.addWidget(title)

        # 数据源卡片
        self._init_data_source_card(left_widget, left_layout)

        # 清洗规则卡片
        self._init_clean_rules_card(left_widget, left_layout)

        # 模板管理卡片
        self._init_template_card(left_widget, left_layout)

        left_layout.addStretch()
        self.left_panel.setWidget(left_widget)
        self.splitter.addWidget(self.left_panel)

        # ── 右侧工作区 ────────────────────────────────
        self.right_panel = ScrollArea()
        self.right_panel.setWidgetResizable(True)
        self.right_panel.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(12)

        # 数据预览
        self._init_preview_section(right_widget, right_layout)

        # 透视配置
        self._init_pivot_config_card(right_widget, right_layout)

        # 导出面板
        self._init_export_card(right_widget, right_layout)

        right_layout.addStretch()
        self.right_panel.setWidget(right_widget)
        self.splitter.addWidget(self.right_panel)

        # 设置分割比例（左 1 : 右 2）
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 2)
        main_layout.addWidget(self.splitter)

        # 状态栏
        self.status_bar = QHBoxLayout()
        self.status_bar.setContentsMargins(16, 8, 16, 8)
        self.status_label = BodyLabel("就绪", self)
        self.status_bar.addWidget(self.status_label)
        self.status_bar.addStretch()
        main_layout.addLayout(self.status_bar)

    def _init_data_source_card(self, parent, layout):
        """数据源卡片"""
        card = CardWidget(parent)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(8)

        # 标题
        title_row = QHBoxLayout()
        title_row.addWidget(StrongBodyLabel("数据源", card))
        self.data_source_count = CaptionLabel("(0 个文件)", card)
        self.data_source_count.setStyleSheet("color: gray;")
        title_row.addWidget(self.data_source_count)
        title_row.addStretch()

        # 添加文件按钮
        self.btn_add_file = PushButton(FIF.ADD, "添加文件", card)
        self.btn_add_file.setFixedWidth(100)
        title_row.addWidget(self.btn_add_file)
        card_layout.addLayout(title_row)

        # 拖放区域
        self.drop_area = ExcelDropArea(card)
        self.drop_area.setFixedHeight(80)
        card_layout.addWidget(self.drop_area)

        # 文件列表
        self.file_list = QListWidget(card)
        self.file_list.setMaximumHeight(120)
        card_layout.addWidget(self.file_list)

        # Sheet 选择
        sheet_row = QHBoxLayout()
        sheet_row.addWidget(BodyLabel("工作表:", card))
        self.sheet_combo = ComboBox(card)
        self.sheet_combo.setPlaceholderText("选择 sheet")
        self.sheet_combo.setFixedWidth(150)
        sheet_row.addWidget(self.sheet_combo)
        sheet_row.addStretch()

        # 刷新列按钮
        self.btn_refresh_columns = TransparentToolButton(FIF.SYNC, card)
        self.btn_refresh_columns.setToolTip("刷新列名")
        sheet_row.addWidget(self.btn_refresh_columns)
        card_layout.addLayout(sheet_row)

        # 列选择器（复选框列表）
        self.column_list = QListWidget(card)
        self.column_list.setMaximumHeight(100)
        # 允许复选
        self.column_list.itemChanged.connect(self._on_column_check_changed)
        card_layout.addWidget(self.column_list)

        # 加载按钮
        self.btn_load = PrimaryPushButton("加载数据", card)
        self.btn_load.clicked.connect(self._on_load_data)
        card_layout.addWidget(self.btn_load)

        layout.addWidget(card)

    def _init_clean_rules_card(self, parent, layout):
        """清洗规则卡片"""
        card = CardWidget(parent)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(8)

        # 标题
        title_row = QHBoxLayout()
        title_row.addWidget(StrongBodyLabel("清洗规则", card))
        self.clean_rule_count_label = CaptionLabel("(0 条规则)", card)
        self.clean_rule_count_label.setStyleSheet("color: gray;")
        title_row.addWidget(self.clean_rule_count_label)
        title_row.addStretch()

        # 添加规则按钮
        self.btn_add_clean_rule = PushButton(FIF.ADD, "添加规则", card)
        self.btn_add_clean_rule.setFixedWidth(100)
        title_row.addWidget(self.btn_add_clean_rule)
        card_layout.addLayout(title_row)

        # 规则类型选择
        rule_type_row = QHBoxLayout()
        rule_type_row.addWidget(BodyLabel("规则类型:", card))
        self.clean_rule_type = ComboBox(card)
        self.clean_rule_type.addItem("删除空值行", "dropna")
        self.clean_rule_type.addItem("删除重复行", "dropdup")
        self.clean_rule_type.addItem("填充空值", "fillna")
        self.clean_rule_type.addItem("类型转换", "astype")
        self.clean_rule_type.addItem("行过滤", "filter")
        self.clean_rule_type.setCurrentIndex(0)
        self.clean_rule_type.setFixedWidth(120)
        rule_type_row.addWidget(self.clean_rule_type)

        # 目标列
        rule_type_row.addWidget(BodyLabel("列:", card))
        self.clean_rule_column = ComboBox(card)
        self.clean_rule_column.setPlaceholderText("选择列")
        self.clean_rule_column.setFixedWidth(120)
        rule_type_row.addWidget(self.clean_rule_column)
        rule_type_row.addStretch()
        card_layout.addLayout(rule_type_row)

        # 规则参数（动态显示）
        self.clean_rule_params_label = BodyLabel("", card)
        self.clean_rule_params_label.setWordWrap(True)
        self.clean_rule_params_label.setStyleSheet("color: gray; font-size: 12px;")
        card_layout.addWidget(self.clean_rule_params_label)

        # 规则列表
        self.clean_rule_list = QListWidget(card)
        self.clean_rule_list.setMaximumHeight(100)
        card_layout.addWidget(self.clean_rule_list)

        # 删除规则按钮
        self.btn_remove_clean_rule = PushButton(FIF.DELETE, "删除选中规则", card)
        self.btn_remove_clean_rule.clicked.connect(self._on_remove_clean_rule)
        card_layout.addWidget(self.btn_remove_clean_rule)

        # 应用清洗按钮
        self.btn_apply_clean = PrimaryPushButton("应用清洗", card)
        self.btn_apply_clean.clicked.connect(self._on_apply_clean)
        card_layout.addWidget(self.btn_apply_clean)

        layout.addWidget(card)

    def _init_template_card(self, parent, layout):
        """模板管理卡片"""
        card = CardWidget(parent)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(8)

        # 标题
        title_row = QHBoxLayout()
        title_row.addWidget(StrongBodyLabel("透视模板", card))
        title_row.addStretch()

        # 保存模板按钮
        self.btn_save_template = PushButton(FIF.SAVE, "保存为模板", card)
        self.btn_save_template.setFixedWidth(110)
        title_row.addWidget(self.btn_save_template)
        card_layout.addLayout(title_row)

        # 加载模板
        template_row = QHBoxLayout()
        template_row.addWidget(BodyLabel("加载模板:", card))
        self.template_combo = ComboBox(card)
        self.template_combo.setPlaceholderText("选择模板")
        self.template_combo.setFixedWidth(180)
        template_row.addWidget(self.template_combo)

        self.btn_load_template = PushButton(FIF.DOWNLOAD, "加载", card)
        self.btn_load_template.setFixedWidth(80)
        template_row.addWidget(self.btn_load_template)

        self.btn_delete_template = PushButton(FIF.DELETE, "删除", card)
        self.btn_delete_template.setFixedWidth(80)
        template_row.addWidget(self.btn_delete_template)
        template_row.addStretch()
        card_layout.addLayout(template_row)

        layout.addWidget(card)

    def _init_preview_section(self, parent, layout):
        """数据预览区域"""
        # 标题
        preview_header = QHBoxLayout()
        preview_header.addWidget(StrongBodyLabel("数据预览", parent))
        self.preview_shape_label = CaptionLabel("", parent)
        self.preview_shape_label.setStyleSheet("color: gray;")
        preview_header.addWidget(self.preview_shape_label)
        preview_header.addStretch()

        # 刷新预览按钮
        self.btn_refresh_preview = TransparentToolButton(FIF.SYNC, parent)
        self.btn_refresh_preview.setToolTip("刷新预览")
        preview_header.addWidget(self.btn_refresh_preview)
        layout.addLayout(preview_header)

        # TableView + Model（虚拟滚动）
        from PySide6.QtWidgets import QTableView
        self.preview_table = QTableView(parent)
        self.preview_model = ExcelTableModel(self.preview_table)
        self.preview_table.setModel(self.preview_model)

        # 表格样式
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.preview_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.preview_table.horizontalHeader().setStretchLastSection(True)
        self.preview_table.setMinimumHeight(250)
        layout.addWidget(self.preview_table)

    def _init_pivot_config_card(self, parent, layout):
        """透视配置面板"""
        card = CardWidget(parent)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(12)

        # 标题
        card_layout.addWidget(SubtitleLabel("⚙️ 透视配置", card))

        # 行维度
        row_layout = QHBoxLayout()
        row_layout.addWidget(BodyLabel("行维度:", card))
        self.row_field_combo = ComboBox(card)
        self.row_field_combo.setPlaceholderText("选择行字段")
        self.row_field_combo.setFixedWidth(150)
        row_layout.addWidget(self.row_field_combo)
        row_layout.addStretch()
        card_layout.addLayout(row_layout)

        # 列维度（可选）
        col_layout = QHBoxLayout()
        col_layout.addWidget(BodyLabel("列维度:", card))
        self.col_field_combo = ComboBox(card)
        self.col_field_combo.setPlaceholderText("无（不交叉）")
        self.col_field_combo.setFixedWidth(150)
        col_layout.addWidget(self.col_field_combo)
        col_layout.addStretch()
        card_layout.addLayout(col_layout)

        # 值字段
        val_layout = QHBoxLayout()
        val_layout.addWidget(BodyLabel("值字段:", card))
        self.value_field_combo = ComboBox(card)
        self.value_field_combo.setPlaceholderText("选择值字段")
        self.value_field_combo.setFixedWidth(150)
        val_layout.addWidget(self.value_field_combo)

        val_layout.addWidget(BodyLabel("聚合:", card))
        self.agg_func_combo = ComboBox(card)
        self.agg_func_combo.addItem("求和 (sum)", "sum")
        self.agg_func_combo.addItem("计数 (count)", "count")
        self.agg_func_combo.addItem("平均值 (avg)", "avg")
        self.agg_func_combo.addItem("最小值 (min)", "min")
        self.agg_func_combo.addItem("最大值 (max)", "max")
        self.agg_func_combo.addItem("标准差 (std)", "std")
        self.agg_func_combo.setCurrentIndex(0)
        self.agg_func_combo.setFixedWidth(130)
        val_layout.addWidget(self.agg_func_combo)
        val_layout.addStretch()
        card_layout.addLayout(val_layout)

        # 多表合并键
        merge_layout = QHBoxLayout()
        merge_layout.addWidget(BodyLabel("合并键列:", card))
        self.merge_keys_edit = SearchLineEdit(card)
        self.merge_keys_edit.setPlaceholderText("多表横向合并时填写，逗号分隔（可选）")
        merge_layout.addWidget(self.merge_keys_edit)
        merge_layout.addStretch()
        card_layout.addLayout(merge_layout)

        # 按钮行
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.btn_generate_pivot = PrimaryPushButton("生成透视表", card)
        self.btn_generate_pivot.clicked.connect(self._on_generate_pivot)
        btn_layout.addWidget(self.btn_generate_pivot)

        self.btn_save_pivot_config = PushButton("保存配置", card)
        self.btn_save_pivot_config.clicked.connect(self._on_save_pivot_config)
        btn_layout.addWidget(self.btn_save_pivot_config)

        btn_layout.addStretch()
        card_layout.addLayout(btn_layout)

        layout.addWidget(card)

    def _init_export_card(self, parent, layout):
        """导出面板"""
        card = CardWidget(parent)
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(16, 12, 16, 12)

        card_layout.addWidget(StrongBodyLabel("导出结果:", parent))

        self.btn_export_excel = PrimaryPushButton("导出 Excel", card)
        self.btn_export_excel.clicked.connect(self._on_export_excel)
        card_layout.addWidget(self.btn_export_excel)

        self.btn_export_csv = PushButton("导出 CSV", card)
        self.btn_export_csv.clicked.connect(self._on_export_csv)
        card_layout.addWidget(self.btn_export_csv)

        card_layout.addStretch()
        layout.addWidget(card)

    # ──────────────────────────────────────────────────────
    # 信号连接
    # ──────────────────────────────────────────────────────

    def _connect_signals(self):
        """连接信号"""
        # 文件操作
        self.drop_area.files_dropped.connect(self._on_files_dropped)
        self.btn_add_file.clicked.connect(self._on_add_file)
        self.btn_refresh_columns.clicked.connect(self._on_refresh_columns)

        # Sheet 选择变化
        self.sheet_combo.currentTextChanged.connect(self._on_sheet_changed)

        # 清洗规则
        self.btn_add_clean_rule.clicked.connect(self._on_add_clean_rule)
        self.clean_rule_type.currentIndexChanged.connect(self._on_clean_rule_type_changed)

        # 模板
        self.btn_save_template.clicked.connect(self._on_save_template)
        self.btn_load_template.clicked.connect(self._on_load_template)
        self.btn_delete_template.clicked.connect(self._on_delete_template)
        self.template_combo.currentTextChanged.connect(self._on_template_combo_changed)

        # 预览刷新
        self.btn_refresh_preview.clicked.connect(self._on_refresh_preview)

    # ──────────────────────────────────────────────────────
    # 属性访问
    # ──────────────────────────────────────────────────────

    @property
    def core_api(self):
        """延迟获取 CoreAPI 实例"""
        if self._core_api is None:
            self._core_api = get_core_api()
        return self._core_api

    # ──────────────────────────────────────────────────────
    # 文件操作
    # ──────────────────────────────────────────────────────

    def _on_files_dropped(self, file_paths: List[str]):
        """拖放文件"""
        self._add_files_to_list(file_paths)

    def _on_add_file(self):
        """点击添加文件按钮"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "选择 Excel 文件",
            "",
            "Excel 文件 (*.xlsx *.xls);;CSV 文件 (*.csv);;所有文件 (*)",
        )
        if file_paths:
            self._add_files_to_list(file_paths)

    def _add_files_to_list(self, file_paths: List[str]):
        """将文件添加到列表"""
        for fp in file_paths:
            # 检查是否已存在
            exists = False
            for i in range(self.file_list.count()):
                if self.file_list.item(i).data(Qt.UserRole) == fp:
                    exists = True
                    break
            if not exists:
                item = QListWidgetItem(os.path.basename(fp))
                item.setData(Qt.UserRole, fp)
                item.setToolTip(fp)
                self.file_list.addItem(item)

        self._update_file_count()
        self._update_sheet_list()

    def _update_file_count(self):
        """更新文件计数"""
        count = self.file_list.count()
        self.data_source_count.setText(f"({count} 个文件)")

    def _update_sheet_list(self):
        """更新 Sheet 下拉框（取第一个文件的 sheet 列表）"""
        if self.file_list.count() == 0:
            self.sheet_combo.clear()
            return

        first_fp = self.file_list.item(0).data(Qt.UserRole)
        sheet_names = self.core_api.get_excel_sheet_names(first_fp)
        self.sheet_combo.clear()
        self.sheet_combo.addItem("(默认) 第一个 sheet", None)
        for sn in sheet_names:
            self.sheet_combo.addItem(sn, sn)

    def _on_sheet_changed(self, text: str):
        """Sheet 选择变化，刷新列名"""
        self._on_refresh_columns()

    def _on_refresh_columns(self):
        """刷新列名列表"""
        if self.file_list.count() == 0:
            return

        first_fp = self.file_list.item(0).data(Qt.UserRole)
        sheet_name = self.sheet_combo.currentData()
        if sheet_name is None and self.sheet_combo.count() > 1:
            sheet_name = self.sheet_combo.itemData(1)

        columns = self.core_api.get_excel_column_names(first_fp, sheet_name)

        # 更新列选择器
        self.column_list.clear()
        for col in columns:
            item = QListWidgetItem(col)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            item.setData(Qt.UserRole, col)
            self.column_list.addItem(item)

        # 更新清洗规则列下拉
        self.clean_rule_column.clear()
        for col in columns:
            self.clean_rule_column.addItem(col, col)

        # 更新透视配置下拉
        self.row_field_combo.clear()
        self.col_field_combo.clear()
        self.value_field_combo.clear()
        self.col_field_combo.addItem("(无)", "")
        for col in columns:
            self.row_field_combo.addItem(col, col)
            self.col_field_combo.addItem(col, col)
            self.value_field_combo.addItem(col, col)

    def _get_selected_columns(self) -> List[str]:
        """获取选中的列名"""
        result = []
        for i in range(self.column_list.count()):
            item = self.column_list.item(i)
            if item.checkState() == Qt.Checked:
                result.append(item.data(Qt.UserRole))
        return result

    def _on_column_check_changed(self, item: QListWidgetItem):
        """列复选框状态变化"""
        # 当前列选择变化时，可以在此处触发联动逻辑
        # 暂时不做额外操作，由加载按钮统一读取
        pass

    # ──────────────────────────────────────────────────────
    # 数据加载
    # ──────────────────────────────────────────────────────

    def _on_load_data(self):
        """加载数据按钮"""
        if self.file_list.count() == 0:
            InfoBar.warning(title="提示", content="请先添加 Excel 文件", parent=self)
            return

        file_paths = [
            self.file_list.item(i).data(Qt.UserRole)
            for i in range(self.file_list.count())
        ]

        sheet_name = self.sheet_combo.currentData()
        use_columns = self._get_selected_columns()

        # 显示进度提示
        self._load_tooltip = StateToolTip(
            "加载数据",
            f"正在加载 {len(file_paths)} 个文件...",
            self
        )
        self._load_tooltip.show()

        def on_progress(msg: str):
            if self._load_tooltip:
                # msg 是 "current/total" 格式
                self._load_tooltip.setContent(f"正在加载... {msg}")

        def on_complete(result):
            if self._load_tooltip:
                self._load_tooltip.setContent("加载完成！")
                self._load_tooltip.hide()
                self._load_tooltip = None
            self._on_load_complete(result)

        def on_error(error_msg: str):
            if self._load_tooltip:
                self._load_tooltip.hide()
                self._load_tooltip = None
            InfoBar.error(title="加载失败", content=error_msg, parent=self)
            self._restore_status_bar()

        self._load_task_id = self.core_api.submit_excel_load_task(
            file_paths=file_paths,
            sheet_name=sheet_name,
            use_columns=use_columns if use_columns else None,
            preview_only=True,
            on_progress=on_progress,
            on_complete=on_complete,
            on_error=on_error,
        )

        self.status_label.setText("正在加载数据...")

    def _on_load_complete(self, task_result):
        """加载完成回调"""
        data = task_result.data
        if not data:
            InfoBar.error(title="错误", content="加载数据失败", parent=self)
            return

        self._loaded_tables = data.get("tables", [])
        total_rows = data.get("total_rows", 0)
        total_cols = data.get("total_cols", 0)

        # 更新预览（显示第一个表的 preview）
        if self._loaded_tables:
            first_table = self._loaded_tables[0]
            df_json = first_table.get("preview_df_json", "")
            if df_json:
                self.preview_model.load_from_df_json(df_json)

        # 更新形状标签
        self.preview_shape_label.setText(f"({total_rows} 行 × {total_cols} 列)")

        # 更新状态栏
        self.status_label.setText(f"已加载 {len(self._loaded_tables)} 个表，共 {total_rows} 行")

        InfoBar.success(
            title="加载完成",
            content=f"成功加载 {len(self._loaded_tables)} 个表，共 {total_rows} 行",
            parent=self,
            position=InfoBarPosition.TOP,
        )

    # ──────────────────────────────────────────────────────
    # 清洗规则
    # ──────────────────────────────────────────────────────

    def _on_clean_rule_type_changed(self, index: int):
        """清洗规则类型变化，更新参数提示"""
        rule_type = self.clean_rule_type.currentData()
        hints = {
            "dropna": "删除包含空值的行。请选择目标列（空=检查所有列）。",
            "dropdup": "删除重复行。请选择依据列（空=检查所有列）。",
            "fillna": "填充空值。请在「参数」中输入填充值，或选择方法。",
            "astype": "类型转换。请在「参数」中选择目标类型。",
            "filter": "行过滤。请在「参数」中设置过滤条件。",
        }
        self.clean_rule_params_label.setText(hints.get(rule_type, ""))

    def _on_add_clean_rule(self):
        """添加清洗规则"""
        rule_type = self.clean_rule_type.currentData()
        column = self.clean_rule_column.currentData()

        if not column and rule_type in ("dropna", "fillna", "astype", "filter"):
            InfoBar.warning(title="提示", content="请先选择目标列", parent=self)
            return

        # 构建规则 dict
        params = {}
        if rule_type == "fillna":
            params = {"value": 0}   # 默认填充 0
        elif rule_type == "astype":
            params = {"target_type": "str"}  # 默认转字符串
        elif rule_type == "filter":
            params = {"op": ">", "value": 0}

        rule_dict = {
            "rule_type": rule_type,
            "column": column,
            "params": params,
        }

        # 添加到列表
        display_text = f"{rule_type} → {column or '全部'}"
        item = QListWidgetItem(display_text)
        item.setData(Qt.UserRole, rule_dict)
        self.clean_rule_list.addItem(item)

        self._update_clean_rule_count()

        InfoBar.success(title="已添加", content=f"规则: {display_text}", parent=self)

    def _on_remove_clean_rule(self):
        """删除选中的清洗规则"""
        row = self.clean_rule_list.currentRow()
        if row >= 0:
            self.clean_rule_list.takeItem(row)
            self._update_clean_rule_count()

    def _update_clean_rule_count(self):
        """更新清洗规则计数"""
        count = self.clean_rule_list.count()
        self.clean_rule_count_label.setText(f"({count} 条规则)")

    def _get_clean_rules(self) -> List[Dict]:
        """获取所有清洗规则 dict 列表"""
        result = []
        for i in range(self.clean_rule_list.count()):
            item = self.clean_rule_list.item(i)
            result.append(item.data(Qt.UserRole))
        return result

    def _on_apply_clean(self):
        """应用清洗规则"""
        if not self._loaded_tables:
            InfoBar.warning(title="提示", content="请先加载数据", parent=self)
            return

        clean_rules = self._get_clean_rules()
        if not clean_rules:
            InfoBar.warning(title="提示", content="请先添加清洗规则", parent=self)
            return

        # 准备参数：每个表的 full_df_json
        tables_json = [t.get("full_df_json", "") for t in self._loaded_tables]

        def on_progress(msg: str):
            pass  # 清洗一般很快，不需要进度提示

        def on_complete(result):
            self._on_clean_complete(result)

        def on_error(error_msg: str):
            InfoBar.error(title="清洗失败", content=error_msg, parent=self)

        self._clean_task_id = self.core_api.submit_excel_clean_task(
            tables_json=tables_json,
            clean_rules=clean_rules,
            on_progress=on_progress,
            on_complete=on_complete,
            on_error=on_error,
        )

        self.status_label.setText("正在清洗数据...")

    def _on_clean_complete(self, task_result):
        """清洗完成回调"""
        data = task_result.data
        if not data:
            return

        self._cleaned_df_json = data.get("cleaned_df_json", "")
        original_rows = data.get("original_rows", 0)
        cleaned_rows = data.get("cleaned_rows", 0)
        removed = data.get("removed_rows", 0)

        # 更新预览
        if self._cleaned_df_json:
            self.preview_model.load_from_df_json(self._cleaned_df_json)

        self.status_label.setText(
            f"清洗完成：{original_rows} → {cleaned_rows} 行（移除 {removed} 行）"
        )

        InfoBar.success(
            title="清洗完成",
            content=f"原始 {original_rows} 行 → 清洗后 {cleaned_rows} 行（移除 {removed} 行）",
            parent=self,
            position=InfoBarPosition.TOP,
        )

    # ──────────────────────────────────────────────────────
    # 透视表生成
    # ──────────────────────────────────────────────────────

    def _on_generate_pivot(self):
        """生成透视表"""
        # 确定数据源：如果已清洗则用清洗后的，否则用原始
        tables_json = []
        if self._cleaned_df_json:
            tables_json = [self._cleaned_df_json]
        elif self._loaded_tables:
            tables_json = [t.get("full_df_json", "") for t in self._loaded_tables]
        else:
            InfoBar.warning(title="提示", content="请先加载数据", parent=self)
            return

        # 获取透视配置
        row_field = self.row_field_combo.currentData()
        col_field = self.col_field_combo.currentData() or ""
        value_field = self.value_field_combo.currentData()
        agg_func = self.agg_func_combo.currentData()

        if not row_field or not value_field:
            InfoBar.warning(title="提示", content="请选择行维度和值字段", parent=self)
            return

        # 构建 pivot_config dict
        pivot_config = {
            "id": self._current_template_id or "",
            "name": "临时配置",
            "description": "",
            "created_at": "",
            "updated_at": "",
            "source_files": [],
            "sheet_names": [],
            "use_columns": self._get_selected_columns(),
            "row_filters": [],
            "clean_rules": self._get_clean_rules(),
            "row_field": row_field,
            "col_field": col_field,
            "value_field": value_field,
            "agg_func": agg_func,
            "merge_keys": [],
        }

        # 合并键
        merge_keys_str = self.merge_keys_edit.text().strip()
        merge_keys = [k.strip() for k in merge_keys_str.split(",") if k.strip()] if merge_keys_str else []

        # 显示进度
        self._pivot_tooltip = StateToolTip(
            "生成透视表",
            "正在处理...",
            self
        )
        self._pivot_tooltip.show()

        def on_progress(msg: str):
            if self._pivot_tooltip:
                self._pivot_tooltip.setContent(f"正在生成透视表... {msg}")

        def on_complete(result):
            if self._pivot_tooltip:
                self._pivot_tooltip.setContent("透视完成！")
                self._pivot_tooltip.hide()
                self._pivot_tooltip = None
            self._on_pivot_complete(result)

        def on_error(error_msg: str):
            if self._pivot_tooltip:
                self._pivot_tooltip.hide()
                self._pivot_tooltip = None
            InfoBar.error(title="透视失败", content=error_msg, parent=self)

        self._pivot_task_id = self.core_api.submit_excel_pivot_task(
            tables_json=tables_json,
            pivot_config=pivot_config,
            merge_keys=merge_keys,
            on_progress=on_progress,
            on_complete=on_complete,
            on_error=on_error,
        )

        self.status_label.setText("正在生成透视表...")

    def _on_pivot_complete(self, task_result):
        """透视完成回调"""
        data = task_result.data
        if not data:
            return

        self._pivot_df_json = data.get("result_df_json", "")
        row_count = data.get("row_count", 0)
        col_count = data.get("col_count", 0)

        # 更新预览（显示透视结果）
        if self._pivot_df_json:
            self.preview_model.load_from_df_json(self._pivot_df_json)

        self.status_label.setText(f"透视完成：{row_count} 行 × {col_count} 列")

        InfoBar.success(
            title="透视完成",
            content=f"生成透视表：{row_count} 行 × {col_count} 列",
            parent=self,
            position=InfoBarPosition.TOP,
        )

    def _on_save_pivot_config(self):
        """保存当前透视配置（快捷方式，调用模板保存）"""
        self._on_save_template()

    # ──────────────────────────────────────────────────────
    # 导出
    # ──────────────────────────────────────────────────────

    def _on_export_excel(self):
        """导出为 Excel"""
        self._export_result("xlsx")

    def _on_export_csv(self):
        """导出为 CSV"""
        self._export_result("csv")

    def _export_result(self, fmt: str):
        """导出结果"""
        if not self._pivot_df_json:
            InfoBar.warning(title="提示", content="请先生成透视表", parent=self)
            return

        # 默认文件名
        default_name = f"透视结果.{fmt}"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出结果",
            default_name,
            "Excel 文件 (*.xlsx);;CSV 文件 (*.csv);;所有文件 (*)",
        )

        if not file_path:
            return

        def on_progress(msg: str):
            pass

        def on_complete(result):
            self._on_export_complete(result)

        def on_error(error_msg: str):
            InfoBar.error(title="导出失败", content=error_msg, parent=self)

        self._export_task_id = self.core_api.submit_excel_export_task(
            result_df_json=self._pivot_df_json,
            file_path=file_path,
            export_format=fmt,
            on_progress=on_progress,
            on_complete=on_complete,
            on_error=on_error,
        )

        self.status_label.setText(f"正在导出到 {file_path}...")

    def _on_export_complete(self, task_result):
        """导出完成回调"""
        data = task_result.data
        if not data or not data.get("success"):
            InfoBar.error(title="导出失败", content=data.get("error_msg", "未知错误"), parent=self)
            return

        file_path = data.get("file_path", "")
        row_count = data.get("row_count", 0)

        self.status_label.setText(f"导出完成：{file_path}")

        InfoBar.success(
            title="导出成功",
            content=f"已导出 {row_count} 行到：{file_path}",
            parent=self,
            position=InfoBarPosition.TOP,
        )

    # ──────────────────────────────────────────────────────
    # 模板管理
    # ──────────────────────────────────────────────────────

    def _on_save_template(self):
        """保存当前配置为模板"""
        # 获取当前透视配置
        row_field = self.row_field_combo.currentData()
        col_field = self.col_field_combo.currentData() or ""
        value_field = self.value_field_combo.currentData()
        agg_func = self.agg_func_combo.currentData()

        if not row_field or not value_field:
            InfoBar.warning(title="提示", content="请先配置透视参数", parent=self)
            return

        # 生成模板
        from datetime import datetime
        import uuid

        config = PivotConfig(
            id=uuid.uuid4().hex[:8],
            name=f"透视模板 {datetime.now().strftime('%m-%d %H:%M')}",
            description="",
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            source_files=[],
            sheet_names=[],
            use_columns=self._get_selected_columns(),
            row_filters=[],
            clean_rules=[CleanRule.from_dict(r) for r in self._get_clean_rules()],
            row_field=row_field,
            col_field=col_field,
            value_field=value_field,
            agg_func=agg_func,
            merge_keys=[],
        )

        if self.core_api.save_pivot_template(config):
            self._current_template_id = config.id
            self._refresh_template_combo()
            InfoBar.success(title="保存成功", content=f"模板「{config.name}」已保存", parent=self)
        else:
            InfoBar.error(title="保存失败", content="保存模板失败", parent=self)

    def _on_load_template(self):
        """加载选中的模板"""
        template_id = self.template_combo.currentData()
        if not template_id:
            InfoBar.warning(title="提示", content="请先选择模板", parent=self)
            return

        config = self.core_api.load_pivot_template(template_id)
        if not config:
            InfoBar.error(title="错误", content="加载模板失败", parent=self)
            return

        self._current_template_id = config.id

        # 恢复 UI（选中对应的下拉选项）
        self._restore_pivot_ui_from_config(config)

        InfoBar.success(title="加载成功", content=f"模板「{config.name}」已加载", parent=self)

    def _restore_pivot_ui_from_config(self, config: PivotConfig):
        """从 PivotConfig 恢复 UI 状态"""
        # 行维度
        idx = self.row_field_combo.findData(config.row_field)
        if idx >= 0:
            self.row_field_combo.setCurrentIndex(idx)

        # 列维度
        idx = self.col_field_combo.findData(config.col_field)
        if idx >= 0:
            self.col_field_combo.setCurrentIndex(idx)

        # 值字段
        idx = self.value_field_combo.findData(config.value_field)
        if idx >= 0:
            self.value_field_combo.setCurrentIndex(idx)

        # 聚合函数
        idx = self.agg_func_combo.findData(config.agg_func)
        if idx >= 0:
            self.agg_func_combo.setCurrentIndex(idx)

        # 清洗规则
        self.clean_rule_list.clear()
        for rule in config.clean_rules:
            rule_dict = rule.to_dict()
            display_text = f"{rule.rule_type} → {rule.column or '全部'}"
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, rule_dict)
            self.clean_rule_list.addItem(item)
        self._update_clean_rule_count()

    def _on_delete_template(self):
        """删除选中的模板"""
        template_id = self.template_combo.currentData()
        if not template_id:
            InfoBar.warning(title="提示", content="请先选择模板", parent=self)
            return

        msg = QMessageBox.question(
            self,
            "确认删除",
            "确定要删除当前选中的模板吗？",
            QMessageBox.Yes | QMessageBox.No,
        )

        if msg == QMessageBox.Yes:
            if self.core_api.delete_pivot_template(template_id):
                self._current_template_id = ""
                self._refresh_template_combo()
                InfoBar.success(title="已删除", content="模板已删除", parent=self)
            else:
                InfoBar.error(title="删除失败", content="删除模板失败", parent=self)

    def _on_template_combo_changed(self, text: str):
        """模板下拉变化（什么都不做，等用户点「加载」）"""
        pass

    def _refresh_template_combo(self):
        """刷新模板下拉框"""
        self.template_combo.clear()
        self.template_combo.addItem("(选择模板...)", "")

        templates = self.core_api.get_all_pivot_templates()
        for t in templates:
            self.template_combo.addItem(f"{t['name']}", t["id"])

    # ──────────────────────────────────────────────────────
    # 预览刷新
    # ──────────────────────────────────────────────────────

    def _on_refresh_preview(self):
        """刷新预览"""
        if self._pivot_df_json:
            self.preview_model.load_from_df_json(self._pivot_df_json)
        elif self._cleaned_df_json:
            self.preview_model.load_from_df_json(self._cleaned_df_json)
        elif self._loaded_tables:
            first_table = self._loaded_tables[0]
            df_json = first_table.get("preview_df_json", "")
            if df_json:
                self.preview_model.load_from_df_json(df_json)

    # ──────────────────────────────────────────────────────
    # 状态栏
    # ──────────────────────────────────────────────────────

    def _restore_status_bar(self):
        """恢复状态栏（清洗/透视完成后）"""
        self.status_label.setText("就绪")

    # ──────────────────────────────────────────────────────
    # 页面显示时刷新
    # ──────────────────────────────────────────────────────

    def showEvent(self, event):
        """页面显示时刷新模板列表"""
        super().showEvent(event)
        self._refresh_template_combo()
