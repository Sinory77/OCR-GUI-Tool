"""
模板管理页面 - 管理 OCR 结果解析模板

功能：
- 模板 CRUD（创建、编辑、删除）
- 规则编辑（关键词/正则/位置）
- 实时预览测试
- 模板导入/导出
- 搜索和筛选
"""
import os
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFileDialog
)
from qfluentwidgets import ScrollArea, ExpandLayout
from PySide6.QtCore import Qt, Signal
from qfluentwidgets import (
    SubtitleLabel, BodyLabel, CaptionLabel,
    PushButton, PrimaryPushButton, LineEdit, TextEdit,
    ComboBox, TableWidget, CardWidget, InfoBar, InfoBarPosition,
    MessageBoxBase, FluentIcon as FIF, CheckBox, SearchLineEdit,
    ToolButton, TransparentToolButton, StrongBodyLabel,
    PillPushButton, setFont, TogglePushButton
)
from qfluentwidgets import MessageBox
from ..ui_utils import create_message_box, setup_chinese_buttons

from core.template_manager import get_template_manager, ParseTemplate, ParseRule
from core.text_parser import TextParser
from api.core_api import CoreAPI


# ──────────────────────────────────────────────────────────────
# 历史选择对话框
# ──────────────────────────────────────────────────────────────

class HistorySelectDialog(MessageBoxBase):
    """历史选择对话框 - 从识别历史中选择测试文本"""

    def __init__(self, parent=None):
        self.selected_text = None
        self.selected_filename = None
        super().__init__(parent)
        # 设置中文按钮
        setup_chinese_buttons(self)
        self._setup_ui()
        self._load_history()

    def _setup_ui(self):
        """设置 UI"""
        self.titleLabel = SubtitleLabel("📜 选择识别历史", self)
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.setSpacing(12)

        # 搜索框
        self.search_input = SearchLineEdit(self)
        self.search_input.setPlaceholderText("搜索文件名...")
        self.search_input.textChanged.connect(self._on_search)
        self.viewLayout.addWidget(self.search_input)

        # 历史列表
        self.history_table = TableWidget(self)
        self.history_table.setColumnCount(3)
        self.history_table.setHorizontalHeaderLabels(["文件名", "时间", "预览"])
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.history_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.history_table.setMinimumHeight(250)
        self.history_table.itemDoubleClicked.connect(self._on_select)
        self.history_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.viewLayout.addWidget(self.history_table)

        # 提示
        hint = CaptionLabel("💡 双击行或点击确定选择", self)
        hint.setStyleSheet("color: gray;")
        self.viewLayout.addWidget(hint)

        # 窗口尺寸
        self.widget.setMinimumWidth(500)

    def _load_history(self):
        """加载历史记录"""
        try:
            api = CoreAPI()
            history = api.get_history_results(limit=100)

            self.all_history = history
            self._display_history(history)
        except Exception as e:
            self.history_table.setRowCount(1)
            self.history_table.setItem(0, 0, QTableWidgetItem(f"加载失败: {str(e)}"))

    def _display_history(self, history):
        """显示历史记录"""
        self.history_table.setRowCount(len(history))
        for i, item in enumerate(history):
            # 文件名
            filename = item.get('filename', '未知')
            self.history_table.setItem(i, 0, QTableWidgetItem(filename))

            # 时间
            time_str = item.get('time', '')[:19] if item.get('time') else ''
            self.history_table.setItem(i, 1, QTableWidgetItem(time_str))

            # 预览（文本前50字）
            text = item.get('text', '')
            preview = text[:50] + '...' if len(text) > 50 else text
            preview_item = QTableWidgetItem(preview)
            preview_item.setForeground(Qt.gray)
            self.history_table.setItem(i, 2, preview_item)

            # 保存完整文本
            self.history_table.item(i, 0).setData(Qt.UserRole, text)
            self.history_table.item(i, 0).setToolTip(text)

    def _on_search(self, text: str):
        """搜索过滤"""
        if not text.strip():
            self._display_history(self.all_history)
            return

        filtered = [h for h in self.all_history
                   if text.lower() in h.get('filename', '').lower()
                   or text.lower() in h.get('text', '').lower()]
        self._display_history(filtered)

    def _on_select(self, item):
        """选择历史项"""
        row = item.row()
        self.selected_text = self.history_table.item(row, 0).data(Qt.UserRole)
        self.selected_filename = self.history_table.item(row, 0).text()
        self.accept()

    def get_selected(self):
        """获取选中的内容"""
        return self.selected_text, self.selected_filename


# ──────────────────────────────────────────────────────────────
# 导入选项对话框
# ──────────────────────────────────────────────────────────────

class ImportOptionsDialog(MessageBoxBase):
    """导入选项对话框 - 处理模板名称冲突"""

    def __init__(self, template_name: str, parent=None):
        self.template_name = template_name
        super().__init__(parent)
        # 设置中文按钮
        setup_chinese_buttons(self)
        self._setup_ui()

    def _setup_ui(self):
        """设置 UI"""
        self.titleLabel = SubtitleLabel("模板冲突", self)
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.setSpacing(12)

        # 提示信息
        hint_text = f"已存在模板「{self.template_name}」，请选择处理方式："
        hint_label = BodyLabel(hint_text, self)
        self.viewLayout.addWidget(hint_label)

        # 选项
        self.option_combo = ComboBox(self)
        self.option_combo.addItem("🔄 覆盖现有模板", "overwrite")
        self.option_combo.addItem("📝 重命名为新模板", "rename")
        self.option_combo.addItem("❌ 取消导入", "cancel")
        self.option_combo.setCurrentIndex(0)
        self.viewLayout.addWidget(self.option_combo)

        # 窗口尺寸
        self.widget.setMinimumWidth(400)

    def get_option(self) -> str:
        """获取选择的选项"""
        return self.option_combo.currentData()


# ──────────────────────────────────────────────────────────────
# 规则编辑对话框
# ──────────────────────────────────────────────────────────────

class RuleEditDialog(MessageBoxBase):
    """规则编辑对话框 - 优化版
    
    改进：
    - 更清晰的布局分组
    - 实时验证提示
    - 更好的占位符文本
    - 支持键盘快捷键（Enter保存，Esc取消）
    """

    def __init__(self, rule: ParseRule = None, parent=None):
        self.rule = rule or ParseRule(name="", type="keyword")
        super().__init__(parent)
        # 设置中文按钮
        setup_chinese_buttons(self)
        self._setup_ui()
        self._setup_shortcuts()
    
    def _setup_shortcuts(self):
        """设置键盘快捷键"""
        # 尝试连接按钮信号
        try:
            # 检查 buttonGroup 是否有 applyButton 属性
            if hasattr(self.buttonGroup, 'applyButton'):
                self.buttonGroup.applyButton.clicked.connect(self.accept)
                self.buttonGroup.cancelButton.clicked.connect(self.reject)
            else:
                # 如果 buttonGroup 是 QFrame，尝试查找子按钮
                from PySide6.QtWidgets import QPushButton
                apply_button = self.buttonGroup.findChild(QPushButton, "applyButton")
                cancel_button = self.buttonGroup.findChild(QPushButton, "cancelButton")
                if apply_button and cancel_button:
                    apply_button.clicked.connect(self.accept)
                    cancel_button.clicked.connect(self.reject)
                else:
                    # 如果找不到按钮，使用默认的 accept/reject 方法
                    pass
        except Exception as e:
            # 如果连接失败，忽略错误
            pass
    
    def _setup_ui(self):
        """设置 UI"""
        self.titleLabel = SubtitleLabel("编辑解析规则", self)
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.setSpacing(16)

        # ── 字段名称 ──
        name_group = QVBoxLayout()
        name_group.setSpacing(6)
        name_label = CaptionLabel("字段名称", self)
        self.name_edit = LineEdit(self)
        self.name_edit.setText(self.rule.name)
        self.name_edit.setPlaceholderText("例如：货主、联系电话、地址")
        self.name_edit.setClearButtonEnabled(True)
        name_group.addWidget(name_label)
        name_group.addWidget(self.name_edit)
        self.viewLayout.addLayout(name_group)

        # ── 规则类型 ──
        type_group = QVBoxLayout()
        type_group.setSpacing(6)
        type_label = CaptionLabel("规则类型", self)
        self.type_combo = ComboBox(self)
        self.type_combo.addItem("🔑 关键词匹配", "keyword")
        self.type_combo.addItem("🔍 正则表达式", "regex")
        self.type_combo.addItem("📍 位置提取", "position")
        type_to_index = {"keyword": 0, "regex": 1, "position": 2}
        self.type_combo.setCurrentIndex(type_to_index.get(self.rule.type, 0))
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        type_group.addWidget(type_label)
        type_group.addWidget(self.type_combo)
        self.viewLayout.addLayout(type_group)

        # ── 关键词输入（keyword 类型）──
        self.keyword_widget = QWidget(self)
        kw_layout = QVBoxLayout(self.keyword_widget)
        kw_layout.setContentsMargins(0, 0, 0, 0)
        kw_layout.setSpacing(6)
        
        kw_label = CaptionLabel("关键词", self.keyword_widget)
        self.keyword_edit = LineEdit(self.keyword_widget)
        self.keyword_edit.setText(self.rule.keyword)
        self.keyword_edit.setPlaceholderText("例如：货主、联系电话")
        self.keyword_edit.setClearButtonEnabled(True)
        
        kw_layout.addWidget(kw_label)
        kw_layout.addWidget(self.keyword_edit)
        self.viewLayout.addWidget(self.keyword_widget)

        # ── 正则表达式输入（regex 类型）──
        self.regex_widget = QWidget(self)
        re_layout = QVBoxLayout(self.regex_widget)
        re_layout.setContentsMargins(0, 0, 0, 0)
        re_layout.setSpacing(6)
        
        re_label = CaptionLabel("正则表达式", self.regex_widget)
        self.regex_edit = LineEdit(self.regex_widget)
        self.regex_edit.setText(self.rule.pattern)
        self.regex_edit.setPlaceholderText(r"例如：联系电话[：:]\s*(\d+)")
        self.regex_edit.setClearButtonEnabled(True)
        
        # 正则提示
        re_hint = BodyLabel("💡 提示：使用括号 () 捕获要提取的内容", self.regex_widget)
        re_hint.setStyleSheet("color: gray; font-size: 12px;")
        
        re_layout.addWidget(re_label)
        re_layout.addWidget(self.regex_edit)
        re_layout.addWidget(re_hint)
        self.viewLayout.addWidget(self.regex_widget)

        # ── 位置输入（position 类型）──
        self.position_widget = QWidget(self)
        pos_layout = QVBoxLayout(self.position_widget)
        pos_layout.setContentsMargins(0, 0, 0, 0)
        pos_layout.setSpacing(6)
        
        pos_label = CaptionLabel("位置参数", self.position_widget)
        pos_row = QHBoxLayout()
        pos_row.setSpacing(12)

        # 行号
        line_col = QVBoxLayout()
        line_col.setSpacing(4)
        line_col.addWidget(BodyLabel("行号", self.position_widget))
        self.line_edit = LineEdit(self.position_widget)
        self.line_edit.setText(str(self.rule.line))
        self.line_edit.setFixedWidth(80)
        line_col.addWidget(self.line_edit)
        pos_row.addLayout(line_col)

        # 起始位置
        start_col = QVBoxLayout()
        start_col.setSpacing(4)
        start_col.addWidget(BodyLabel("起始位置", self.position_widget))
        self.start_edit = LineEdit(self.position_widget)
        self.start_edit.setText(str(self.rule.start))
        self.start_edit.setFixedWidth(80)
        start_col.addWidget(self.start_edit)
        pos_row.addLayout(start_col)

        # 结束位置
        end_col = QVBoxLayout()
        end_col.setSpacing(4)
        end_col.addWidget(BodyLabel("结束位置", self.position_widget))
        self.end_edit = LineEdit(self.position_widget)
        self.end_edit.setText(str(self.rule.end))
        self.end_edit.setFixedWidth(80)
        end_col.addWidget(self.end_edit)
        pos_row.addLayout(end_col)

        pos_row.addStretch()
        pos_layout.addWidget(pos_label)
        pos_layout.addLayout(pos_row)
        self.viewLayout.addWidget(self.position_widget)

        # ── 关键词高级选项（仅 keyword 类型显示）──
        self.keyword_options_widget = QWidget(self)
        opt_layout = QVBoxLayout(self.keyword_options_widget)
        opt_layout.setContentsMargins(0, 8, 0, 0)
        opt_layout.setSpacing(10)

        self.ignore_spaces_check = CheckBox("忽略空格匹配", self)
        self.ignore_spaces_check.setChecked(self.rule.ignore_spaces)
        self.ignore_spaces_check.setToolTip("匹配时去除所有空格，用于处理关键词被分行的情况\n例如：'货 主' 也能匹配 '货主'")
        opt_layout.addWidget(self.ignore_spaces_check)

        self.use_next_line_check = CheckBox("允许下一行取值", self)
        self.use_next_line_check.setChecked(self.rule.use_next_line)
        self.use_next_line_check.setToolTip("当前行没有值时，尝试从下一行提取\n适用于关键词和值不在同一行的情况")
        opt_layout.addWidget(self.use_next_line_check)

        self.viewLayout.addWidget(self.keyword_options_widget)

        # 初始可见性
        self._update_visibility(self.rule.type)

        # 窗口尺寸
        self.widget.setMinimumWidth(520)
    
    # ── 规则类型切换 ──────────────────────────────────────────

    def _on_type_changed(self, _index: int):
        text_to_value = {"🔑 关键词匹配": "keyword", "🔍 正则表达式": "regex", "📍 位置提取": "position"}
        self._update_visibility(text_to_value.get(self.type_combo.currentText(), "keyword"))

    def _update_visibility(self, type_value: str):
        """根据规则类型显示/隐藏对应输入框"""
        self.keyword_widget.setVisible(type_value == "keyword")
        self.regex_widget.setVisible(type_value == "regex")
        self.position_widget.setVisible(type_value == "position")
        self.keyword_options_widget.setVisible(type_value == "keyword")

    # ── 获取结果 ──────────────────────────────────────────────

    def get_rule(self) -> ParseRule:
        """获取编辑后的规则对象"""
        text_to_value = {"🔑 关键词匹配": "keyword", "🔍 正则表达式": "regex", "📍 位置提取": "position"}
        rule_type = text_to_value.get(self.type_combo.currentText(), "keyword")
        
        return ParseRule(
            name=self.name_edit.text().strip(),
            type=rule_type,
            keyword=self.keyword_edit.text().strip(),
            pattern=self.regex_edit.text().strip(),
            line=int(self.line_edit.text() or 0),
            start=int(self.start_edit.text() or 0),
            end=int(self.end_edit.text() or 0),
            ignore_spaces=self.ignore_spaces_check.isChecked(),
            use_next_line=self.use_next_line_check.isChecked()
        )


# ──────────────────────────────────────────────────────────────
# 模板编辑对话框
# ──────────────────────────────────────────────────────────────

class TemplateEditDialog(MessageBoxBase):
    """模板编辑对话框 - 优化版
    
    改进：
    - 更大的默认窗口尺寸
    - 双击规则行即可编辑
    - 更好的表格列宽分配
    - 添加规则数量提示
    """

    def __init__(self, template: ParseTemplate = None, parent=None):
        self.template = template
        super().__init__(parent)
        # 设置中文按钮
        setup_chinese_buttons(self)
        self._setup_ui()
        self._connect_signals()
    
    def _connect_signals(self):
        """连接信号"""
        # 双击表格行编辑规则
        self.rule_table.doubleClicked.connect(self._on_edit_rule)
    
    def _setup_ui(self):
        """设置 UI"""
        title = "编辑模板" if self.template else "新建模板"
        self.titleLabel = SubtitleLabel(title, self)
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.setSpacing(12)

        # ── 模板名称 ──
        name_group = QVBoxLayout()
        name_group.setSpacing(6)
        name_label = CaptionLabel("模板名称 *", self)
        self.name_edit = LineEdit(self)
        self.name_edit.setText(self.template.name if self.template else "")
        self.name_edit.setPlaceholderText("例如：动物检疫证明、报货单")
        self.name_edit.setClearButtonEnabled(True)
        name_group.addWidget(name_label)
        name_group.addWidget(self.name_edit)
        self.viewLayout.addLayout(name_group)

        # ── 模板描述 ──
        desc_group = QVBoxLayout()
        desc_group.setSpacing(6)
        desc_label = CaptionLabel("模板描述", self)
        self.desc_edit = LineEdit(self)
        self.desc_edit.setText(self.template.description if self.template else "")
        self.desc_edit.setPlaceholderText("简要描述该模板适用的文档类型")
        self.desc_edit.setClearButtonEnabled(True)
        desc_group.addWidget(desc_label)
        desc_group.addWidget(self.desc_edit)
        self.viewLayout.addLayout(desc_group)

        # ── 解析规则表格 ──
        rules_header = QHBoxLayout()
        rules_header.addWidget(CaptionLabel("解析规则", self))
        self.rule_count_label = BodyLabel("(0 个规则)", self)
        self.rule_count_label.setStyleSheet("color: gray;")
        rules_header.addWidget(self.rule_count_label)
        rules_header.addStretch()
        self.viewLayout.addLayout(rules_header)

        self.rule_table = TableWidget(self)
        self.rule_table.setColumnCount(3)
        self.rule_table.setHorizontalHeaderLabels(["字段名称", "规则类型", "规则内容"])
        
        # 表格样式
        header = self.rule_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        
        self.rule_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.rule_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.rule_table.setMinimumHeight(220)
        self.rule_table.setMaximumHeight(350)
        self.viewLayout.addWidget(self.rule_table)

        # ── 规则操作按钮 ──
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.btn_add_rule = PrimaryPushButton(FIF.ADD, "添加规则", self)
        self.btn_add_rule.clicked.connect(self._on_add_rule)
        btn_layout.addWidget(self.btn_add_rule)

        self.btn_edit_rule = PushButton(FIF.EDIT, "编辑规则", self)
        self.btn_edit_rule.clicked.connect(self._on_edit_rule)
        btn_layout.addWidget(self.btn_edit_rule)

        self.btn_delete_rule = PushButton(FIF.DELETE, "删除规则", self)
        self.btn_delete_rule.clicked.connect(self._on_delete_rule)
        btn_layout.addWidget(self.btn_delete_rule)

        btn_layout.addStretch()
        self.viewLayout.addLayout(btn_layout)

        # 加载已有规则
        self._load_rules()

        # 窗口尺寸
        self.widget.setMinimumWidth(700)
        self.widget.setMinimumHeight(600)

    # ── 规则表格操作 ──────────────────────────────────────────

    _TYPE_MAP = {
        "keyword": "🔑 关键词", 
        "regex": "🔍 正则", 
        "position": "📍 位置"
    }

    def _load_rules(self):
        """加载规则到表格"""
        if not self.template:
            self.rule_table.setRowCount(0)
            self._update_rule_count()
            return
        
        self.rule_table.setRowCount(len(self.template.rules))
        for i, rule in enumerate(self.template.rules):
            # 字段名称
            name_item = QTableWidgetItem(rule.name)
            name_item.setData(Qt.UserRole, i)  # 存储规则索引
            self.rule_table.setItem(i, 0, name_item)
            
            # 规则类型
            type_text = self._TYPE_MAP.get(rule.type, rule.type)
            type_item = QTableWidgetItem(type_text)
            self.rule_table.setItem(i, 1, type_item)
            
            # 规则内容
            if rule.type == "keyword":
                content = rule.keyword
                if rule.ignore_spaces:
                    content += " (忽略空格)"
                if rule.use_next_line:
                    content += " (允许下一行)"
            elif rule.type == "regex":
                content = rule.pattern[:50] + "..." if len(rule.pattern) > 50 else rule.pattern
            else:
                content = f"行{rule.line}, {rule.start}-{rule.end}"
            
            content_item = QTableWidgetItem(content)
            self.rule_table.setItem(i, 2, content_item)
        
        self._update_rule_count()
    
    def _update_rule_count(self):
        """更新规则数量显示"""
        count = self.rule_table.rowCount()
        self.rule_count_label.setText(f"({count} 个规则)")
        if count == 0:
            self.rule_count_label.setStyleSheet("color: red;")
        else:
            self.rule_count_label.setStyleSheet("color: gray;")

    def _on_add_rule(self):
        """添加新规则"""
        dialog = RuleEditDialog(parent=self)
        if dialog.exec():
            rule = dialog.get_rule()
            if not rule.name:
                InfoBar.warning(title="提示", content="字段名称不能为空", parent=self)
                return
            
            if self.template is None:
                from core.template_manager import get_template_manager
                self.template = get_template_manager().create_template(
                    name=self.name_edit.text().strip() or "未命名",
                    description=self.desc_edit.text().strip()
                )
            
            self.template.rules.append(rule)
            self._load_rules()
            InfoBar.success(title="已添加", content=f"规则 '{rule.name}' 已添加", parent=self)

    def _on_edit_rule(self):
        """编辑选中的规则"""
        row = self.rule_table.currentRow()
        if row < 0 or not self.template or row >= len(self.template.rules):
            InfoBar.warning(title="提示", content="请先选择要编辑的规则", parent=self)
            return
        
        dialog = RuleEditDialog(rule=self.template.rules[row], parent=self)
        if dialog.exec():
            self.template.rules[row] = dialog.get_rule()
            self._load_rules()
            InfoBar.success(title="已更新", content="规则已更新", parent=self)

    def _on_delete_rule(self):
        """删除选中的规则"""
        row = self.rule_table.currentRow()
        if row < 0 or not self.template or row >= len(self.template.rules):
            InfoBar.warning(title="提示", content="请先选择要删除的规则", parent=self)
            return
        
        rule_name = self.template.rules[row].name
        self.template.rules.pop(row)
        self._load_rules()
        InfoBar.success(title="已删除", content=f"规则 '{rule_name}' 已删除", parent=self)

    # ── 获取结果 ──────────────────────────────────────────────

    def get_template(self) -> ParseTemplate:
        """获取编辑后的模板对象"""
        if self.template is None:
            from core.template_manager import get_template_manager
            self.template = get_template_manager().create_template(
                name=self.name_edit.text().strip() or "未命名",
                description=self.desc_edit.text().strip()
            )
        else:
            self.template.name = self.name_edit.text().strip()
            self.template.description = self.desc_edit.text().strip()
        
        return self.template


# ──────────────────────────────────────────────────────────────
# 模板管理主页面
# ──────────────────────────────────────────────────────────────

class TemplatePage(ScrollArea):
    """模板管理页面 - 优化版
    
    改进：
    - 添加搜索功能
    - 添加导入/导出按钮
    - 双击模板行编辑
    - 更好的视觉层次
    - 实时统计信息
    - 官方样式滚动条
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.template_manager = get_template_manager()
        
        # 创建滚动内容部件
        self.scrollWidget = QWidget()
        self.main_layout = QVBoxLayout(self.scrollWidget)
        
        self.initUI()
        self._initWidget()
        self._load_templates()
        self._connect_signals()
    
    def _connect_signals(self):
        """连接信号"""
        # 双击表格行编辑模板
        self.template_table.doubleClicked.connect(self._on_edit_template)
        # 正则测试信号
        self.regex_test_button.clicked.connect(self._on_regex_test)
        # 关键词测试信号
        self.keyword_test_button.clicked.connect(self._on_keyword_test)
        # 添加到模板信号
        self.add_to_template_button.clicked.connect(self._on_add_to_template)
    
    def _initWidget(self):
        """初始化布局（官方样式）"""
        # ScrollArea 设置透明背景，让父窗口主题透过来
        self.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollArea>QWidget>QWidget {
                background-color: transparent;
            }
        """)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setViewportMargins(0, 0, 0, 0)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)

        # scrollWidget 使用透明背景，跟随父窗口主题色
        self.scrollWidget.setStyleSheet("background-color: transparent;")

    def initUI(self):
        """初始化 UI"""
        # 主布局
        self.main_layout.setContentsMargins(24, 24, 24, 24)
        self.main_layout.setSpacing(16)

        # ── 标题栏 ──
        title_row = QHBoxLayout()
        title_label = SubtitleLabel("📋 解析模板管理", self.scrollWidget)
        setFont(title_label, 18)
        title_row.addWidget(title_label)
        title_row.addStretch()
        self.main_layout.addLayout(title_row)

        # ── 搜索栏 ──
        search_card = CardWidget(self.scrollWidget)
        search_layout = QHBoxLayout(search_card)
        search_layout.setContentsMargins(16, 12, 16, 12)
        
        self.search_box = SearchLineEdit(search_card)
        self.search_box.setPlaceholderText("搜索模板名称或描述...")
        self.search_box.setFixedWidth(300)
        self.search_box.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self.search_box)
        
        search_layout.addStretch()
        self.main_layout.addWidget(search_card)

        # ── 模板列表卡片 ──
        list_card = CardWidget(self.scrollWidget)
        list_card_layout = QVBoxLayout(list_card)
        list_card_layout.setContentsMargins(16, 16, 16, 16)
        list_card_layout.setSpacing(12)

        # 表格标题
        table_header = QHBoxLayout()
        table_header.addWidget(StrongBodyLabel("模板列表", list_card))
        self.template_count_label = BodyLabel("(0 个模板)", list_card)
        self.template_count_label.setStyleSheet("color: gray;")
        table_header.addWidget(self.template_count_label)
        table_header.addStretch()
        list_card_layout.addLayout(table_header)

        # 表格
        self.template_table = TableWidget(list_card)
        self.template_table.setColumnCount(4)
        self.template_table.setHorizontalHeaderLabels(["模板名称", "描述", "规则数", "更新时间"])
        
        # 表格样式
        header = self.template_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.template_table.setColumnWidth(2, 80)
        
        self.template_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.template_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.template_table.setMinimumHeight(200)
        self.template_table.itemSelectionChanged.connect(self._on_template_selected)
        list_card_layout.addWidget(self.template_table)

        # 操作按钮行
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.btn_add = PrimaryPushButton(FIF.ADD, "新建模板", list_card)
        self.btn_add.clicked.connect(self._on_add_template)
        btn_layout.addWidget(self.btn_add)

        self.btn_edit = PushButton(FIF.EDIT, "编辑模板", list_card)
        self.btn_edit.setEnabled(False)
        self.btn_edit.clicked.connect(self._on_edit_template)
        btn_layout.addWidget(self.btn_edit)

        self.btn_delete = PushButton(FIF.DELETE, "删除模板", list_card)
        self.btn_delete.setEnabled(False)
        self.btn_delete.clicked.connect(self._on_delete_template)
        btn_layout.addWidget(self.btn_delete)

        btn_layout.addSpacing(16)

        self.btn_import = PushButton(FIF.DOWNLOAD, "导入模板", list_card)
        self.btn_import.clicked.connect(self._on_import_template)
        btn_layout.addWidget(self.btn_import)

        self.btn_export = PushButton(FIF.SHARE, "导出模板", list_card)
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._on_export_template)
        btn_layout.addWidget(self.btn_export)

        self.btn_export_all = PushButton(FIF.SAVE, "批量导出", list_card)
        self.btn_export_all.clicked.connect(self._on_export_all_templates)
        btn_layout.addWidget(self.btn_export_all)

        self.btn_duplicate = PushButton(FIF.COPY, "复制模板", list_card)
        self.btn_duplicate.setEnabled(False)
        self.btn_duplicate.clicked.connect(self._on_duplicate_template)
        btn_layout.addWidget(self.btn_duplicate)

        btn_layout.addStretch()

        self.btn_refresh = TransparentToolButton(FIF.SYNC, list_card)
        self.btn_refresh.setToolTip("刷新模板列表")
        self.btn_refresh.clicked.connect(self._on_refresh_templates)
        btn_layout.addWidget(self.btn_refresh)

        list_card_layout.addLayout(btn_layout)
        self.main_layout.addWidget(list_card)

        # ── 预览测试卡片（可折叠）──
        preview_card = CardWidget(self.scrollWidget)
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(16, 16, 16, 16)
        preview_layout.setSpacing(12)

        # 卡片标题行
        preview_title_row = QHBoxLayout()
        self.preview_toggle = TogglePushButton("🧪 模板预览测试", preview_card)
        self.preview_toggle.setChecked(True)
        self.preview_toggle.setText("🧪 模板预览测试 ▲")
        self.preview_toggle.setToolTip("点击折叠/展开预览测试区域")
        self.preview_toggle.clicked.connect(self._on_preview_toggle)
        preview_title_row.addWidget(self.preview_toggle)

        # 当前选中模板显示
        self.current_template_label = BodyLabel("（未选择模板）", preview_card)
        self.current_template_label.setStyleSheet("color: gray; font-style: italic;")
        preview_title_row.addWidget(self.current_template_label)

        # 测试按钮放到标题行右侧
        self.btn_test = PrimaryPushButton(FIF.SEARCH, "测试解析", preview_card)
        self.btn_test.clicked.connect(self._on_test_parse)
        preview_title_row.addWidget(self.btn_test)

        preview_title_row.addStretch()
        preview_layout.addLayout(preview_title_row)

        # 可折叠的内容区域
        self.preview_content_widget = QWidget(preview_card)
        self.preview_content_layout = QVBoxLayout(self.preview_content_widget)
        self.preview_content_layout.setContentsMargins(0, 0, 0, 0)
        self.preview_content_layout.setSpacing(12)
        preview_layout.addWidget(self.preview_content_widget)

        # 输入区域 - 左右布局
        input_row = QHBoxLayout()
        input_row.setSpacing(16)

        # 左侧：测试输入
        input_group = QVBoxLayout()
        input_group.setSpacing(6)

        # 输入区标题行
        input_header = QHBoxLayout()
        input_header.addWidget(CaptionLabel("测试文本："))
        input_header.addStretch()
        self.btn_from_history = PushButton(FIF.HISTORY, "从历史选择", preview_card)
        self.btn_from_history.clicked.connect(self._on_select_from_history)
        input_header.addWidget(self.btn_from_history)
        input_group.addLayout(input_header)

        self.test_text = TextEdit(preview_card)
        self.test_text.setPlaceholderText("在此粘贴需要解析的文本内容...\n\n例如：\n货主：张三\n联系电话：13800138000")
        self.test_text.setMinimumHeight(120)
        input_group.addWidget(self.test_text)
        input_row.addLayout(input_group, 1)

        # 右侧：解析结果
        result_group = QVBoxLayout()
        result_group.setSpacing(6)

        result_header = QHBoxLayout()
        result_header.addWidget(CaptionLabel("解析结果：", preview_card))
        self.result_count_label = BodyLabel("", preview_card)
        self.result_count_label.setStyleSheet("color: gray;")
        result_header.addWidget(self.result_count_label)
        result_header.addStretch()
        result_group.addLayout(result_header)

        self.test_result = TableWidget(preview_card)
        self.test_result.setColumnCount(2)
        self.test_result.setHorizontalHeaderLabels(["字段", "值"])

        result_header_widget = self.test_result.horizontalHeader()
        result_header_widget.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        result_header_widget.setSectionResizeMode(1, QHeaderView.Stretch)

        self.test_result.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.test_result.setMinimumHeight(120)
        result_group.addWidget(self.test_result)
        input_row.addLayout(result_group, 1)

        self.preview_content_layout.addLayout(input_row)

        # ── 正则表达式测试功能 ──
        regex_test_group = QVBoxLayout()
        regex_test_group.setSpacing(6)
        regex_test_group.addWidget(CaptionLabel("🔍 正则表达式测试：", preview_card))

        # 正则输入和测试按钮
        regex_input_row = QHBoxLayout()
        self.regex_input = LineEdit(preview_card)
        self.regex_input.setPlaceholderText(r"输入正则表达式，例如：联系电话[：:]\s*(\d+)")
        self.regex_input.setClearButtonEnabled(True)
        self.regex_input.textChanged.connect(self._on_regex_changed)
        regex_input_row.addWidget(self.regex_input, 1)

        self.regex_test_button = PushButton(FIF.SEARCH, "测试", preview_card)
        self.regex_test_button.setFixedWidth(80)
        self.regex_test_button.clicked.connect(self._on_regex_test)
        regex_input_row.addWidget(self.regex_test_button)
        regex_test_group.addLayout(regex_input_row)

        # 正则验证状态标签
        self.regex_status_label = BodyLabel("", preview_card)
        self.regex_status_label.setStyleSheet("color: gray;")
        regex_test_group.addWidget(self.regex_status_label)

        # 正则测试结果
        self.regex_result = TextEdit(preview_card)
        self.regex_result.setReadOnly(True)
        self.regex_result.setPlaceholderText("输入正则表达式后，匹配结果将实时显示在这里...")
        self.regex_result.setMinimumHeight(80)
        regex_test_group.addWidget(self.regex_result)
        self.preview_content_layout.addLayout(regex_test_group)

        # ── 关键词搜索功能 ──
        keyword_test_group = QVBoxLayout()
        keyword_test_group.setSpacing(6)

        # 关键词标题行
        keyword_header = QHBoxLayout()
        keyword_header.addWidget(CaptionLabel("🔑 关键词搜索测试："))
        keyword_header.addStretch()
        self.btn_suggest_keywords = PushButton(FIF.DICTIONARY_ADD, "智能生成", preview_card)
        self.btn_suggest_keywords.clicked.connect(self._on_suggest_keywords)
        keyword_header.addWidget(self.btn_suggest_keywords)
        keyword_test_group.addLayout(keyword_header)

        # 关键词输入和测试按钮
        keyword_input_row = QHBoxLayout()
        self.keyword_input = LineEdit(preview_card)
        self.keyword_input.setPlaceholderText("输入关键词，例如：货主")
        self.keyword_input.setClearButtonEnabled(True)
        self.keyword_input.textChanged.connect(self._on_keyword_changed)
        keyword_input_row.addWidget(self.keyword_input, 1)

        self.keyword_test_button = PushButton(FIF.SEARCH, "测试", preview_card)
        self.keyword_test_button.setFixedWidth(80)
        self.keyword_test_button.clicked.connect(self._on_keyword_test)
        keyword_input_row.addWidget(self.keyword_test_button)
        keyword_test_group.addLayout(keyword_input_row)

        # 关键词建议列表
        self.keyword_suggestions = BodyLabel("", preview_card)
        self.keyword_suggestions.setStyleSheet("color: #666;")
        self.keyword_suggestions.setWordWrap(True)
        keyword_test_group.addWidget(self.keyword_suggestions)

        # 关键词测试结果
        self.keyword_result = TextEdit(preview_card)
        self.keyword_result.setReadOnly(True)
        self.keyword_result.setPlaceholderText("输入关键词后，匹配结果将显示在这里...")
        self.keyword_result.setMinimumHeight(80)
        keyword_test_group.addWidget(self.keyword_result)
        self.preview_content_layout.addLayout(keyword_test_group)

        # ── 添加到模板按钮 ──
        self.add_to_template_button = PrimaryPushButton(FIF.ADD, "添加测试规则到模板", preview_card)
        self.add_to_template_button.setEnabled(False)
        self.preview_content_layout.addWidget(self.add_to_template_button)

        self.main_layout.addWidget(preview_card)

    # ── 模板列表操作 ──────────────────────────────────────────

    def _on_preview_toggle(self):
        """预览区折叠/展开切换"""
        is_expanded = self.preview_toggle.isChecked()
        self.preview_content_widget.setVisible(is_expanded)
        self.preview_toggle.setText("🧪 模板预览测试 " + ("▲" if is_expanded else "▼"))

    def _on_select_from_history(self):
        """从识别历史选择"""
        dialog = HistorySelectDialog(self)
        if dialog.exec():
            text, filename = dialog.get_selected()
            if text:
                self.test_text.setPlainText(text)
                InfoBar.success(
                    title="已加载",
                    content=f"已从「{filename}」加载识别内容",
                    position=InfoBarPosition.TOP,
                    parent=self,
                    duration=2000
                )

    def _load_templates(self, templates=None):
        """加载模板到表格
        
        Args:
            templates: 可选的模板列表，默认为所有模板
        """
        if templates is None:
            templates = self.template_manager.get_all_templates()
        
        self.template_table.setRowCount(len(templates))
        for i, tpl in enumerate(templates):
            # 模板名称
            name_item = QTableWidgetItem(tpl.name)
            name_item.setData(Qt.UserRole, tpl.id)
            self.template_table.setItem(i, 0, name_item)
            
            # 描述（限制显示长度）
            desc_text = tpl.description if tpl.description else "-"
            if len(desc_text) > 30:
                display_text = desc_text[:27] + "..."
                desc_item = QTableWidgetItem(display_text)
                desc_item.setToolTip(desc_text)  # 完整内容显示在 tooltip
            else:
                desc_item = QTableWidgetItem(desc_text)
                desc_item.setToolTip(desc_text)
            desc_item.setForeground(Qt.gray)
            self.template_table.setItem(i, 1, desc_item)
            
            # 规则数
            count_item = QTableWidgetItem(str(len(tpl.rules)))
            count_item.setTextAlignment(Qt.AlignCenter)
            self.template_table.setItem(i, 2, count_item)
            
            # 更新时间
            updated = tpl.updated_at[:10] if tpl.updated_at else "-"
            time_item = QTableWidgetItem(updated)
            self.template_table.setItem(i, 3, time_item)
        
        self._update_template_count(len(templates))
    
    def _update_template_count(self, count: int):
        """更新模板数量显示"""
        self.template_count_label.setText(f"({count} 个模板)")
    
    def _get_selected_template_id(self) -> str | None:
        """获取选中模板的ID"""
        row = self.template_table.currentRow()
        if row >= 0:
            item = self.template_table.item(row, 0)
            if item:
                return item.data(Qt.UserRole)
        return None
    
    def _on_template_selected(self):
        """模板选择变化"""
        template_id = self._get_selected_template_id()
        has_selection = template_id is not None
        self.btn_edit.setEnabled(has_selection)
        self.btn_delete.setEnabled(has_selection)
        self.btn_export.setEnabled(has_selection)
        self.btn_duplicate.setEnabled(has_selection)
        
        # 更新当前选中模板显示
        if template_id:
            template = self.template_manager.get_template(template_id)
            if template:
                self.current_template_label.setText(f"（当前模板：{template.name}）")
                self.current_template_label.setStyleSheet("color: #666;")
        else:
            self.current_template_label.setText("（未选择模板）")
            self.current_template_label.setStyleSheet("color: gray; font-style: italic;")
    
    def _on_search_changed(self, text: str):
        """搜索文本变化"""
        if not text.strip():
            self._load_templates()
            return
        
        templates = self.template_manager.search_templates(text.strip())
        self._load_templates(templates)
    
    def _on_add_template(self):
        """新建模板"""
        dialog = TemplateEditDialog(parent=self)
        if dialog.exec():
            template = dialog.get_template()
            if self.template_manager.save_template(template):
                self._load_templates()
                InfoBar.success(
                    title="成功", 
                    content=f"模板 '{template.name}' 已保存",
                    position=InfoBarPosition.TOP, 
                    parent=self
                )
            else:
                InfoBar.error(
                    title="错误", 
                    content="保存模板失败",
                    position=InfoBarPosition.TOP, 
                    parent=self
                )

    def _on_edit_template(self):
        """编辑模板"""
        template_id = self._get_selected_template_id()
        if not template_id:
            return
        
        template = self.template_manager.get_template(template_id)
        if not template:
            InfoBar.warning(title="错误", content="模板不存在", parent=self)
            return
        
        dialog = TemplateEditDialog(template=template, parent=self)
        if dialog.exec():
            updated = dialog.get_template()
            if self.template_manager.save_template(updated):
                self._load_templates()
                InfoBar.success(
                    title="成功", 
                    content=f"模板 '{updated.name}' 已更新",
                    position=InfoBarPosition.TOP, 
                    parent=self
                )

    def _on_delete_template(self):
        """删除模板"""
        template_id = self._get_selected_template_id()
        if not template_id:
            return
        
        template = self.template_manager.get_template(template_id)
        if not template:
            return

        msg = create_message_box("确认删除", f"确定要删除模板「{template.name}」吗？\n\n此操作不可恢复！", self.window())
        if msg.exec() == MessageBox.Yes:
            if self.template_manager.delete_template(template_id):
                self._load_templates()
                InfoBar.success(
                    title="已删除", 
                    content="模板已删除",
                    position=InfoBarPosition.TOP, 
                    parent=self
                )
            else:
                InfoBar.error(
                    title="错误", 
                    content="删除模板失败",
                    position=InfoBarPosition.TOP, 
                    parent=self
                )

    def _on_refresh_templates(self):
        """刷新模板列表"""
        self.template_manager.reload_templates()
        self._load_templates()
        InfoBar.success(
            title="已刷新", 
            content="模板列表已更新",
            position=InfoBarPosition.TOP, 
            parent=self,
            duration=1500
        )
    
    def _on_import_template(self):
        """导入模板"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "导入模板",
            "",
            "JSON 文件 (*.json);;所有文件 (*)"
        )

        if not file_path:
            return

        try:
            import json
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 判断是单个模板还是多个模板
            if isinstance(data, dict):
                templates_to_import = [data]
            elif isinstance(data, list):
                templates_to_import = data
            else:
                raise ValueError("不支持的文件格式")

            imported_count = 0
            skipped_count = 0

            for tpl_data in templates_to_import:
                # 检查是否已存在同名模板
                existing = self.template_manager.search_templates(tpl_data.get('name', ''))
                if existing:
                    dialog = ImportOptionsDialog(tpl_data.get('name', ''), self)
                    if dialog.exec():
                        option = dialog.get_option()
                        if option == "cancel":
                            skipped_count += 1
                            continue
                        elif option == "overwrite":
                            # 找到同名模板并更新
                            for ex in existing:
                                if ex.name == tpl_data.get('name'):
                                    ex.description = tpl_data.get('description', '')
                                    ex.rules = [ParseRule(**r) for r in tpl_data.get('rules', [])]
                                    self.template_manager.save_template(ex)
                                    imported_count += 1
                                    break
                        elif option == "rename":
                            tpl_data['name'] = f"{tpl_data.get('name', '模板')} (导入)"
                            new_tpl = ParseTemplate(**tpl_data)
                            if self.template_manager.save_template(new_tpl):
                                imported_count += 1
                else:
                    new_tpl = ParseTemplate(**tpl_data)
                    if self.template_manager.save_template(new_tpl):
                        imported_count += 1

            self._load_templates()

            if imported_count > 0:
                InfoBar.success(
                    title="导入完成",
                    content=f"成功导入 {imported_count} 个模板" + (f"，跳过 {skipped_count} 个" if skipped_count > 0 else ""),
                    position=InfoBarPosition.TOP,
                    parent=self
                )
            elif skipped_count > 0:
                InfoBar.warning(
                    title="导入取消",
                    content=f"跳过了 {skipped_count} 个已存在的模板",
                    position=InfoBarPosition.TOP,
                    parent=self
                )
            else:
                InfoBar.warning(
                    title="导入结果",
                    content="没有导入任何模板",
                    position=InfoBarPosition.TOP,
                    parent=self
                )

        except Exception as e:
            InfoBar.error(
                title="导入失败",
                content=f"导入失败: {str(e)}",
                position=InfoBarPosition.TOP,
                parent=self
            )
    
    def _on_export_template(self):
        """导出模板"""
        template_id = self._get_selected_template_id()
        if not template_id:
            return
        
        template = self.template_manager.get_template(template_id)
        if not template:
            return
        
        default_name = f"{template.name}.json"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出模板",
            default_name,
            "JSON 文件 (*.json);;所有文件 (*)"
        )
        
        if not file_path:
            return
        
        if self.template_manager.export_template(template_id, file_path):
            InfoBar.success(
                title="导出成功",
                content=f"模板已导出到: {file_path}",
                position=InfoBarPosition.TOP,
                parent=self
            )
        else:
            InfoBar.error(
                title="导出失败",
                content="导出模板失败",
                position=InfoBarPosition.TOP,
                parent=self
            )

    def _on_export_all_templates(self):
        """批量导出所有模板"""
        templates = self.template_manager.get_all_templates()
        if not templates:
            InfoBar.warning(
                title="提示",
                content="没有模板可导出",
                position=InfoBarPosition.TOP,
                parent=self
            )
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "批量导出模板",
            "templates_backup.json",
            "JSON 文件 (*.json);;所有文件 (*)"
        )

        if not file_path:
            return

        try:
            import json
            templates_data = [tpl.to_dict() for tpl in templates]
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(templates_data, f, ensure_ascii=False, indent=2)

            InfoBar.success(
                title="导出成功",
                content=f"已导出 {len(templates)} 个模板到: {file_path}",
                position=InfoBarPosition.TOP,
                parent=self
            )
        except Exception as e:
            InfoBar.error(
                title="导出失败",
                content=f"导出失败: {str(e)}",
                position=InfoBarPosition.TOP,
                parent=self
            )

    def _on_duplicate_template(self):
        """复制模板"""
        template_id = self._get_selected_template_id()
        if not template_id:
            return

        template = self.template_manager.get_template(template_id)
        if not template:
            InfoBar.error(title="错误", content="模板不存在", parent=self)
            return

        # 创建副本
        new_template = ParseTemplate(
            name=f"{template.name} (副本)",
            description=template.description
        )
        new_template.rules = [ParseRule(**rule.to_dict()) for rule in template.rules]

        # 保存
        if self.template_manager.save_template(new_template):
            self._load_templates()
            InfoBar.success(
                title="复制成功",
                content=f"模板「{new_template.name}」已创建",
                position=InfoBarPosition.TOP,
                parent=self
            )
        else:
            InfoBar.error(
                title="复制失败",
                content="保存模板失败",
                position=InfoBarPosition.TOP,
                parent=self
            )

    # ── 正则表达式实时验证 ────────────────────────────────────

    def _on_regex_changed(self, text: str):
        """正则表达式输入变化时实时验证"""
        import re

        if not text.strip():
            self.regex_status_label.setText("")
            self.regex_result.setPlainText("")
            return

        # 验证正则语法
        try:
            pattern = re.compile(text)
            self.regex_status_label.setText("✅ 正则语法正确")
            self.regex_status_label.setStyleSheet("color: green;")
        except re.error as e:
            self.regex_status_label.setText(f"❌ 语法错误: {str(e)}")
            self.regex_status_label.setStyleSheet("color: red;")
            return

        # 如果有测试文本，实时显示匹配结果
        test_text = self.test_text.toPlainText().strip()
        if test_text:
            try:
                matches = pattern.findall(test_text)
                if matches:
                    result_lines = [f"匹配结果 ({len(matches)} 个)："]
                    for i, match in enumerate(matches[:10], 1):
                        match_str = str(match) if isinstance(match, str) else ', '.join(match) if isinstance(match, tuple) else str(match)
                        result_lines.append(f"  {i}. {match_str}")
                    if len(matches) > 10:
                        result_lines.append(f"  ... 还有 {len(matches) - 10} 个匹配")
                    self.regex_result.setPlainText('\n'.join(result_lines))
                    self.add_to_template_button.setEnabled(True)
                else:
                    self.regex_result.setPlainText("无匹配结果")
                    self.add_to_template_button.setEnabled(False)
            except Exception as e:
                self.regex_result.setPlainText(f"匹配失败: {str(e)}")

    def _on_regex_test(self):
        """手动测试正则表达式"""
        text = self.test_text.toPlainText().strip()
        regex_pattern = self.regex_input.text().strip()

        if not text:
            InfoBar.warning(title="提示", content="请先输入测试文本", parent=self)
            return

        if not regex_pattern:
            InfoBar.warning(title="提示", content="请输入正则表达式", parent=self)
            return

        import re
        try:
            pattern = re.compile(regex_pattern)
            matches = pattern.findall(text)

            if matches:
                result_text = f"匹配结果 ({len(matches)} 个)：\n"
                for i, match in enumerate(matches, 1):
                    match_str = str(match) if isinstance(match, str) else ', '.join(match) if isinstance(match, tuple) else str(match)
                    result_text += f"  {i}. {match_str}\n"
                self.regex_result.setPlainText(result_text)
                self.add_to_template_button.setEnabled(True)
            else:
                self.regex_result.setPlainText("无匹配结果")
                self.add_to_template_button.setEnabled(False)

        except re.error as e:
            InfoBar.error(title="正则错误", content=f"正则表达式语法错误: {str(e)}", parent=self)

    # ── 关键词智能生成 ─────────────────────────────────────────

    def _on_suggest_keywords(self):
        """分析测试文本生成关键词建议"""
        text = self.test_text.toPlainText().strip()
        if not text:
            InfoBar.warning(title="提示", content="请先输入测试文本", parent=self)
            return

        suggestions = self._extract_keywords(text)
        if suggestions:
            # 显示建议列表
            suggestion_text = "💡 建议关键词：" + " | ".join([f"「{kw}」" for kw in suggestions])
            self.keyword_suggestions.setText(suggestion_text)

            # 询问是否自动填入第一个建议
            dialog = MessageBox("关键词建议", f"发现以下可能的关键词：\n\n" + "\n".join([f"  • {kw}" for kw in suggestions]) + "\n\n是否使用第一个关键词？", self)
            setup_chinese_buttons(dialog)
            if dialog.exec():
                self.keyword_input.setText(suggestions[0])
                self._on_keyword_changed(suggestions[0])
        else:
            self.keyword_suggestions.setText("")
            InfoBar.warning(title="提示", content="未发现明显的关键词模式", parent=self)

    def _extract_keywords(self, text: str) -> list:
        """从文本中提取可能的关键词

        分析模式：
        1. 冒号/等号前的标签（如 "姓名："）
        2. 常见字段名（电话、地址、账号等）
        3. 数字/特殊格式前的前缀
        """
        import re
        suggestions = []
        seen = set()

        # 常见字段名模式
        common_fields = [
            '姓名', '名字', '名称', '货主', '发货人', '收货人', '客户',
            '电话', '手机', '联系电话', '号码', 'TEL', 'Phone',
            '地址', '收货地址', '发货地址', '地址：', 'Addr',
            '账号', '卡号', '账户', 'Account',
            '单号', '订单号', '运单号', '快递单号', '单号：',
            '金额', '价格', '总计', '运费', '付款',
            '日期', '时间', '下单时间', '发货时间',
            '备注', '备注：', '说明',
            '重量', '件数', '数量', '规格',
            '公司', '单位', '部门',
            '省份', '城市', '区域', '邮编',
        ]

        for field in common_fields:
            if field.lower() in text.lower():
                if field not in seen:
                    suggestions.append(field)
                    seen.add(field.lower())

        # 提取 "标签：" 或 "标签：" 模式
        label_pattern = re.compile(r'^([\u4e00-\u9fa5a-zA-Z]{1,10})[：:]\s*', re.MULTILINE)
        for match in label_pattern.finditer(text):
            label = match.group(1).strip()
            if len(label) >= 2 and label not in seen and label.lower() not in [s.lower() for s in suggestions]:
                suggestions.append(label)
                seen.add(label.lower())

        # 提取 "标签 值" 模式（如 "联系人 李四"）
        contact_pattern = re.compile(r'^([\u4e00-\u9fa5]{2,4})\s+([\u4e00-\u9fa5a-zA-Z0-9]{2,15})$', re.MULTILINE)
        for match in contact_pattern.finditer(text):
            label = match.group(1)
            if label not in seen and len(label) >= 2:
                suggestions.append(label)
                seen.add(label.lower())

        return suggestions[:10]  # 最多返回10个

    def _on_keyword_changed(self, text: str):
        """关键词输入变化时实时匹配"""
        test_text = self.test_text.toPlainText().strip()
        if not text.strip() or not test_text:
            self.keyword_result.setPlainText("")
            self.add_to_template_button.setEnabled(
                bool(self.regex_input.text().strip()) or bool(self.keyword_input.text().strip())
            )
            return

        lines = test_text.split('\n')
        matches = []

        for i, line in enumerate(lines, 1):
            if text in line:
                matches.append((i, line.strip()))

        if matches:
            result_text = f"匹配结果 ({len(matches)} 个)：\n"
            for line_num, line_content in matches[:20]:
                result_text += f"  行{line_num}: {line_content}\n"
            if len(matches) > 20:
                result_text += f"  ... 还有 {len(matches) - 20} 个匹配"
            self.keyword_result.setPlainText(result_text)
            self.add_to_template_button.setEnabled(True)
        else:
            self.keyword_result.setPlainText("无匹配结果")

    def _on_keyword_test(self):
        """手动测试关键词搜索"""
        text = self.test_text.toPlainText().strip()
        keyword = self.keyword_input.text().strip()

        if not text:
            InfoBar.warning(title="提示", content="请先输入测试文本", parent=self)
            return

        if not keyword:
            InfoBar.warning(title="提示", content="请输入关键词", parent=self)
            return

        lines = text.split('\n')
        matches = []

        for i, line in enumerate(lines, 1):
            if keyword in line:
                matches.append((i, line.strip()))

        if matches:
            result_text = f"匹配结果 ({len(matches)} 个)：\n"
            for line_num, line_content in matches:
                result_text += f"  行{line_num}: {line_content}\n"
            self.keyword_result.setPlainText(result_text)
            self.add_to_template_button.setEnabled(True)
        else:
            self.keyword_result.setPlainText("无匹配结果")
            self.add_to_template_button.setEnabled(False)

    # ── 测试解析 ──────────────────────────────────────────────

    def _on_test_parse(self):
        """测试解析"""
        template_id = self._get_selected_template_id()
        if not template_id:
            InfoBar.warning(
                title="提示", 
                content="请先选择一个模板",
                position=InfoBarPosition.TOP, 
                parent=self
            )
            return
        
        text = self.test_text.toPlainText().strip()
        if not text:
            InfoBar.warning(
                title="提示", 
                content="请输入测试文本",
                position=InfoBarPosition.TOP, 
                parent=self
            )
            return
        
        template = self.template_manager.get_template(template_id)
        if not template:
            InfoBar.error(
                title="错误", 
                content="模板不存在",
                position=InfoBarPosition.TOP, 
                parent=self
            )
            return

        try:
            parser = TextParser(template)
            result = parser.parse(text)

            self.test_result.setRowCount(len(result))
            success_count = 0
            
            for i, (field, value) in enumerate(result.items()):
                field_item = QTableWidgetItem(field)

                if value:
                    value_item = QTableWidgetItem(value)
                    success_count += 1
                else:
                    value_item = QTableWidgetItem("(未提取到)")
                    # 设置灰色斜体样式
                    value_item.setForeground(Qt.gray)
                    font = value_item.font()
                    font.setItalic(True)
                    value_item.setFont(font)

                self.test_result.setItem(i, 0, field_item)
                self.test_result.setItem(i, 1, value_item)
            
            # 更新结果统计
            total = len(result)
            self.result_count_label.setText(f"(成功: {success_count}/{total})")
            
            if success_count == total:
                InfoBar.success(
                    title="解析完成",
                    content=f"✅ 成功提取 {success_count}/{total} 个字段",
                    position=InfoBarPosition.TOP,
                    parent=self
                )
            elif success_count > 0:
                InfoBar.warning(
                    title="部分成功",
                    content=f"⚠️ 成功提取 {success_count}/{total} 个字段",
                    position=InfoBarPosition.TOP,
                    parent=self
                )
            else:
                InfoBar.error(
                    title="解析失败",
                    content=f"❌ 未能提取任何字段，请检查模板规则",
                    position=InfoBarPosition.TOP,
                    parent=self
                )
        
        except Exception as e:
            InfoBar.error(
                title="解析错误",
                content=f"解析过程中出错: {str(e)}",
                position=InfoBarPosition.TOP,
                parent=self
            )

    def _on_add_to_template(self):
        """添加测试规则到模板"""
        template_id = self._get_selected_template_id()
        if not template_id:
            InfoBar.warning(
                title="提示", 
                content="请先选择一个模板",
                position=InfoBarPosition.TOP, 
                parent=self
            )
            return
        
        template = self.template_manager.get_template(template_id)
        if not template:
            InfoBar.error(
                title="错误", 
                content="模板不存在",
                position=InfoBarPosition.TOP, 
                parent=self
            )
            return
        
        # 检查是否有测试结果
        regex_pattern = self.regex_input.text().strip()
        keyword = self.keyword_input.text().strip()
        
        if not regex_pattern and not keyword:
            InfoBar.warning(
                title="提示", 
                content="请先进行正则或关键词测试",
                position=InfoBarPosition.TOP, 
                parent=self
            )
            return
        
        # 创建规则
        if regex_pattern:
            rule = ParseRule(name="正则规则", type="regex", pattern=regex_pattern)
        else:
            rule = ParseRule(name="关键词规则", type="keyword", keyword=keyword)
        
        # 打开规则编辑对话框，让用户完善规则
        dialog = RuleEditDialog(rule=rule, parent=self)
        if dialog.exec():
            edited_rule = dialog.get_rule()
            if not edited_rule.name:
                InfoBar.warning(title="提示", content="字段名称不能为空", parent=self)
                return
            
            template.rules.append(edited_rule)
            if self.template_manager.save_template(template):
                InfoBar.success(
                    title="成功",
                    content=f"规则 '{edited_rule.name}' 已添加到模板",
                    position=InfoBarPosition.TOP,
                    parent=self
                )
            else:
                InfoBar.error(
                    title="错误",
                    content="保存模板失败",
                    position=InfoBarPosition.TOP,
                    parent=self
                )