"""
设置页面
使用 qfluentwidgets 的 SettingCard 组件
"""

from PySide6.QtCore import Qt, QAbstractAnimation, QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFileDialog
from qfluentwidgets import (
    SubtitleLabel, BodyLabel,
    InfoBar, InfoBarPosition,
    FluentIcon, setTheme, Theme,
    SettingCardGroup, SettingCard,
    ExpandGroupSettingCard, ExpandLayout,
    OptionsSettingCard, SwitchSettingCard,
    ComboBox, SpinBox, CardWidget, ScrollArea, PushButton
)
from qfluentwidgets.common.config import OptionsConfigItem, OptionsValidator
import os
import logging
from core.config import DEFAULT_OCR_EXE, DEFAULT_MODELS_PATH
from core.error_handler import ConfigError, handle_error, error_handling, ErrorType
from interfaces.fluent.ui_config import UIConfigManager


logger = logging.getLogger(__name__)


class SpinBoxSettingCard(SettingCard):
    """带 SpinBox 的设置卡片（官方样式）"""

    def __init__(self, icon, title, content, min_val, max_val, default_val, suffix="", parent=None):
        """
        Args:
            icon: 图标
            title: 标题
            content: 内容描述
            min_val: 最小值
            max_val: 最大值
            default_val: 默认值
            suffix: 后缀文字（如"条"）
            parent: 父控件
        """
        super().__init__(icon, title, content, parent)

        self.suffix = suffix
        self.spin_box = SpinBox(self)
        self.spin_box.setRange(min_val, max_val)
        self.spin_box.setValue(default_val)
        self.spin_box.setMinimumWidth(70)

        self.hBoxLayout.addStretch(1)
        self.hBoxLayout.addWidget(self.spin_box, 0, Qt.AlignRight)
        if suffix:
            self.hBoxLayout.addWidget(BodyLabel(suffix, self), 0, Qt.AlignRight)
        self.hBoxLayout.addSpacing(16)


# 主题选项列表
THEME_OPTIONS = ["浅色", "深色", "跟随系统"]

# 语言选项列表
from core.config import LANGUAGES
LANGUAGE_OPTIONS = list(LANGUAGES.keys())

# 创建主题配置项
cfg_theme = OptionsConfigItem(
    group="Interface",
    name="theme",
    default="跟随系统",
    validator=OptionsValidator(THEME_OPTIONS)
)





class OcrEngineSettingCard(ExpandGroupSettingCard):
    """OCR 引擎设置 - 手风琴展开式"""

    def __init__(self, parent=None):
        super().__init__(
            FluentIcon.SETTING,
            "OCR 引擎设置",
            "配置 OCR 识别引擎的相关参数",
            parent
        )

        # 调整内部布局
        self.viewLayout.setContentsMargins(0, 0, 0, 0)
        self.viewLayout.setSpacing(0)

        # 防止展开动画连点竞态：动画运行中时忽略新触发
        original_set_expand = self.setExpand

        def _safe_set_expand(isExpand: bool):
            if self.expandAni.state() == QAbstractAnimation.State.Running:
                return  # 动画正在跑，忽略本次触发
            original_set_expand(isExpand)

        self.setExpand = _safe_set_expand

        # 覆写 _adjustViewSize，跳过隐藏的子项（库默认方法不处理可见性）
        def _adjusted_adjust_view_size():
            h = sum(w.sizeHint().height() + 3 for w in self.widgets if w.isVisible())
            self.spaceWidget.setFixedHeight(h)
            if self.isExpand:
                self.setFixedHeight(self.card.height() + h)

        self._adjustViewSize = _adjusted_adjust_view_size

        # 初始化控件
        self._init_controls()

        # 添加各组设置项
        self._add_groups()

        # 如果配置中自动检测为开启，隐藏手动指定的子项
        if getattr(self, '_auto_detect_enabled', False):
            self._set_group_visible(self.exePathGroup, False)
            self._set_group_visible(self.modelsPathGroup, False)



    def _init_controls(self):
        """初始化控件"""
        from qfluentwidgets import PushButton, SwitchButton
        from api.core_api import get_core_api

        # 获取核心API
        self.api = get_core_api()

        # 自动搜索开关 - 从配置读取初始状态
        # 如果 OCR 引擎或模型目录未配置，强制为 False
        exe_path = self.api.get_config("ocr_exe_path")
        models_path = self.api.get_config("models_path")
        auto_detect = self.api.get_config("auto_detect", False)

        if not exe_path or not models_path:
            auto_detect = False

        self.autoDetectSwitch = SwitchButton()
        self.autoDetectSwitch.setChecked(auto_detect)
        self.autoDetectSwitch.checkedChanged.connect(self._on_auto_detect_toggled)

        # 如果自动检测开启，隐藏手动指定的子项（需要在 _add_groups 后调用）
        self._auto_detect_enabled = auto_detect

        # OCR 程序路径按钮
        self.exePathButton = PushButton("浏览")
        self.exePathButton.setFixedWidth(135)
        self.exePathButton.clicked.connect(self._browse_exe)

        # 模型文件夹按钮
        self.modelsPathButton = PushButton("浏览")
        self.modelsPathButton.setFixedWidth(135)
        self.modelsPathButton.clicked.connect(self._browse_models)

        # 置信度阈值 - Slider + Label
        self.confidenceWidget = QWidget()
        confidenceLayout = QHBoxLayout(self.confidenceWidget)
        confidenceLayout.setContentsMargins(0, 0, 0, 0)
        confidenceLayout.setSpacing(8)

        from qfluentwidgets import Slider
        self.slider = Slider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(self.api.get_config("confidence_threshold", 50))
        self.slider.setFixedWidth(150)

        self.confidenceLabel = BodyLabel(str(self.slider.value()))
        self.confidenceLabel.setFixedWidth(30)

        self.slider.valueChanged.connect(
            lambda v: self.confidenceLabel.setText(str(v))
        )
        self.slider.sliderReleased.connect(self._on_confidence_changed)

        confidenceLayout.addWidget(self.confidenceLabel)
        confidenceLayout.addWidget(self.slider)
        
        # 语言选择已移至识别页面，此处不再需要
        # self.languageComboBox = ComboBox()
        # self.languageComboBox.addItems(LANGUAGE_OPTIONS)
        # current_language = self.config.get_language()
        # if current_language in LANGUAGE_OPTIONS:
        #     self.languageComboBox.setCurrentText(current_language)
        # self.languageComboBox.currentTextChanged.connect(self._on_language_changed)

    def _add_groups(self):
        """添加各组设置项"""
        # 自动搜索开关 — 顶部，开启后搜索并隐藏手动子项
        self.autoDetectGroup = self.addGroup(
            FluentIcon.SEARCH,
            "自动搜索路径",
            "开启后在程序目录中自动搜索 PaddleOCR-json.exe 和 models",
            self.autoDetectSwitch
        )
        # 手动指定子项 - 自动搜索成功后隐藏
        self.exePathGroup = self.addGroup(
            FluentIcon.FOLDER,
            "OCR 引擎路径",
            self.api.get_config("ocr_exe_path") or "未配置",
            self.exePathButton
        )
        self.modelsPathGroup =         self.addGroup(
            FluentIcon.FOLDER,
            "OCR 模型路径",
            self.api.get_config("models_path") or "未配置",
            self.modelsPathButton
        )
        self.addGroup(
            FluentIcon.RINGER,
            "置信度阈值",
            "设置识别结果的置信度过滤",
            self.confidenceWidget
        )
        
        # 语言选择组已移至识别页面
        # self.addGroup(
        #     FluentIcon.LANGUAGE,
        #     "识别语言",
        #     "选择 OCR 识别的语言",
        #     self.languageComboBox
        # )
        
        # 重置配置按钮
        self.resetButton = PushButton("重置所有配置")
        self.resetButton.setFixedWidth(135)
        self.resetButton.clicked.connect(self._on_reset_config)
        
        self.addGroup(
            FluentIcon.DELETE,
            "重置配置",
            "将所有配置恢复到默认值",
            self.resetButton
        )

    # ──────────────────────────────────────────────────────────────
    # 工具：显示/隐藏某个 GroupWidget 及其分隔线
    # ──────────────────────────────────────────────────────────────
    def _set_group_visible(self, group_widget, visible: bool):
        """显示或隐藏某个子项（同时处理紧邻分隔线）"""
        idx = self.viewLayout.indexOf(group_widget)
        group_widget.setVisible(visible)
        # 每个 group 前面有一条 GroupSeparator（index > 0 时存在）
        if idx > 0:
            sep = self.viewLayout.itemAt(idx - 1).widget()
            if sep is not None:
                sep.setVisible(visible)
        # 覆写后的 _adjustViewSize 会自动跳过隐藏 widget
        self._adjustViewSize()

    # ──────────────────────────────────────────────────────────────
    # 自动搜索开关
    # ──────────────────────────────────────────────────────────────
    # 搜索成功后对外广播（供 MainWindow 监听以更新 OCR 引擎）
    engine_auto_detect_success = None  # callable, 由外部注入

    def trigger_auto_detect(self):
        """公开方法：触发自动搜索（供 MainWindow 调用）"""
        self._on_auto_detect_toggled(True)

    def _on_auto_detect_toggled(self, checked: bool):
        """开关状态变化"""
        if checked:
            # 禁用开关防止重复触发，启动异步搜索
            self.autoDetectSwitch.setEnabled(False)
            self.autoDetectGroup.contentLabel.setText("搜索中…")
            self._start_detect_thread()
        else:
            # 关闭开关 → 恢复手动子项
            self.api.set_config("auto_detect", False)  # 保存开关状态
            self.autoDetectGroup.contentLabel.setText(
                "开启后在程序目录中自动搜索 PaddleOCR-json.exe 和 models"
            )
            self._set_group_visible(self.exePathGroup, True)
            self._set_group_visible(self.modelsPathGroup, True)

    def _start_detect_thread(self):
        """异步执行搜索，使用 QTimer.singleShot 避免线程生命周期问题"""
        # 标记当前搜索任务，防止旧任务结果覆盖新任务
        self._detect_counter = getattr(self, '_detect_counter', 0) + 1
        current_id = self._detect_counter

        def _do_search():
            # 显示搜索进度
            self.autoDetectGroup.contentLabel.setText("正在搜索 PaddleOCR-json.exe...")
            QTimer.singleShot(500, lambda: self.autoDetectGroup.contentLabel.setText("正在搜索 models 目录..."))
            
            result = self.config.auto_detect_paths()
            # 仅处理最新一次搜索的结果，忽略旧任务
            if current_id == getattr(self, '_detect_counter', 0):
                self._on_detect_finished(result)

        # 下一帧执行，不阻塞 UI
        QTimer.singleShot(0, _do_search)

    def _on_detect_finished(self, result: dict):
        """搜索完成回调"""
        self.autoDetectSwitch.setEnabled(True)

        exe = result.get("exe")
        models = result.get("models")

        if exe and models:
            # 两个都找到：更新路径显示、隐藏手动子项、更新开关描述
            self.exePathGroup.contentLabel.setText(exe)
            self.modelsPathGroup.contentLabel.setText(models)
            self._set_group_visible(self.exePathGroup, False)
            self._set_group_visible(self.modelsPathGroup, False)
            self.autoDetectGroup.contentLabel.setText("已自动配置 OCR 引擎和模型目录")
            self.config.set_auto_detect(True)  # 保存开关状态
            InfoBar.success(
                title="搜索完成",
                content="已自动配置 OCR 引擎和模型目录，手动指定已隐藏",
                position=InfoBarPosition.TOP,
                parent=self.window()
            )
            # 对外通知：MainWindow 收到后更新 OCR 引擎
            if self.engine_auto_detect_success:
                self.engine_auto_detect_success(exe, models)
        else:
            # 未同时找到 exe 和 models → 回拨开关，保持手动子项可见
            self.autoDetectSwitch.blockSignals(True)
            self.autoDetectSwitch.setChecked(False)
            self.autoDetectSwitch.blockSignals(False)
            self.config.set_auto_detect(False)  # 保存开关状态
            self.autoDetectGroup.contentLabel.setText(
                "开启后在程序目录中自动搜索 PaddleOCR-json.exe 和 models"
            )
            InfoBar.error(
                title="未找到",
                content="在程序目录中未同时搜索到 PaddleOCR-json.exe 和 models 目录，请手动浏览设置",
                position=InfoBarPosition.TOP,
                parent=self.window()
            )

    # ──────────────────────────────────────────────────────────────
    # 手动浏览
    # ──────────────────────────────────────────────────────────────
    @error_handling(ErrorType.CONFIG, "设置 OCR 引擎路径失败")
    def _browse_exe(self):
        """浏览选择 exe 文件 - 核心层处理"""
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(
            self, "选择 OCR 程序", "", "可执行文件 (*.exe)"
        )
        if path:
            success = self.config.set_ocr_exe_path(path)
            if not success:
                raise ConfigError("无法保存配置")
            self.exePathGroup.contentLabel.setText(path)
            InfoBar.success(
                title="设置成功",
                content=f"已设置: {path}",
                position=InfoBarPosition.TOP,
                parent=self.window()
            )

    @error_handling(ErrorType.CONFIG, "设置 OCR 模型路径失败")
    def _browse_models(self):
        """浏览选择模型文件夹 - 核心层处理"""
        from PySide6.QtWidgets import QFileDialog

        path = QFileDialog.getExistingDirectory(self, "选择模型文件夹")
        if path:
            success = self.config.set_models_path(path)
            if not success:
                raise ConfigError("无法保存配置")
            self.modelsPathGroup.contentLabel.setText(path)
            InfoBar.success(
                title="设置成功",
                content=f"已设置: {path}",
                position=InfoBarPosition.TOP,
                parent=self.window()
            )

    @error_handling(ErrorType.CONFIG, "设置置信度阈值失败")
    def _on_confidence_changed(self):
        """置信度变化 - 核心层处理"""
        threshold = self.slider.value()
        self.config.set_confidence_threshold(threshold)
        InfoBar.success(
            title="设置已保存",
            content=f"置信度阈值: {threshold}%",
            position=InfoBarPosition.TOP,
            parent=self.window()
        )
    
    # 语言变化处理已移至识别页面
    # def _on_language_changed(self, language):
    #     """语言变化 - 核心层处理"""
    #     self.config.set_language(language)
    #     InfoBar.success(
    #         title="设置已保存",
    #         content=f"识别语言: {language}",
    #         position=InfoBarPosition.TOP,
    #         parent=self.window()
    #     )
    #     # 通知主窗口重新初始化 OCR 引擎
    #     if hasattr(self, 'engine_auto_detect_success') and self.engine_auto_detect_success:
    #         exe_path = self.config.get_ocr_exe_path()
    #         models_path = self.config.get_models_path()
    #         if exe_path and models_path:
    #             self.engine_auto_detect_success(exe_path, models_path)
    
    @error_handling(ErrorType.CONFIG, "重置配置失败")
    def _on_reset_config(self):
        """重置所有配置"""
        from qfluentwidgets import MessageBox
        from ..ui_utils import create_message_box
        msg_box = create_message_box(
            "重置配置",
            "确定要将所有配置恢复到默认值吗？",
            self.window()
        )
        
        if msg_box.exec() == MessageBox.Yes:
            # 重置配置
            # 由于ConfigManager没有reset_config方法，我们手动重置每个配置项
            self.config.set_ocr_exe_path(DEFAULT_OCR_EXE)
            self.config.set_models_path(DEFAULT_MODELS_PATH)
            self.api.set_config("language", "简体中文")
            self.ui_config.set_ui_language("中文")
            self.ui_config.set_auto_copy(False)
            self.ui_config.set_theme("跟随系统")
            self.config.set_confidence_threshold(50)
            self.config.set_auto_detect(False)
            self.config.set_long_image_mode(True)
            self.config.set_slice_height(2000)
            self.config.set_slice_overlap(100)
            self.config.set_scan_subdirs(False)  # 默认不扫描子目录
            self.config.set_history_storage_limit(100)
            self.config.set_history_display_limit(50)
            
            # 更新界面
            self.autoDetectSwitch.setChecked(False)
            self.exePathGroup.contentLabel.setText(DEFAULT_OCR_EXE)
            self.modelsPathGroup.contentLabel.setText(DEFAULT_MODELS_PATH)
            self.slider.setValue(50)  # 默认置信度
            # 语言选择已移至识别页面，此处不再需要
            # self.languageComboBox.setCurrentText("简体中文")  # 默认语言
            
            # 显示成功信息
            InfoBar.success(
                title="重置成功",
                content="所有配置已恢复到默认值",
                position=InfoBarPosition.TOP,
                parent=self.window()
            )


class SettingsPage(ScrollArea):
    """设置页面（继承自 ScrollArea，按官方示例实现）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent

        # 创建滚动内容部件
        self.scrollWidget = QWidget()
        self.expandLayout = ExpandLayout(self.scrollWidget)

        # 初始化所有设置组
        self._initSettings()

        self._initWidget()

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

    def _initSettings(self):
        """初始化所有设置"""
        from core.config import get_config_manager
        self.config = get_config_manager()
        self.ui_config = UIConfigManager()

        # 设置标题（放在 scrollWidget 内部）
        self.settingLabel = SubtitleLabel("设置", self.scrollWidget)
        self.settingLabel.move(36, 28)

        # OCR 设置组
        self.ocr_group = SettingCardGroup("OCR设置", self.scrollWidget)
        self.add_ocr_cards()

        # 个性化组
        self.ui_group = SettingCardGroup("个性化", self.scrollWidget)
        self.add_ui_cards()

        # 关于组
        self.about_group = SettingCardGroup("关于", self.scrollWidget)
        self.add_about_card()

        # 添加到布局（官方样式）
        self.expandLayout.setSpacing(16)
        self.expandLayout.setContentsMargins(36, 56, 36, 0)  # 顶部留出标题空间
        self.expandLayout.addWidget(self.ocr_group)
        self.expandLayout.addWidget(self.ui_group)
        self.expandLayout.addWidget(self.about_group)


    def add_ocr_cards(self):
        """添加 OCR 设置卡片"""
        # OCR 引擎设置 - ExpandGroupSettingCard
        self.engine_card = OcrEngineSettingCard(self.scrollWidget)
        self.ocr_group.addSettingCard(self.engine_card)

        # 扫描子目录 - SwitchSettingCard
        self.scan_subdirs_card = SwitchSettingCard(
            icon=FluentIcon.FOLDER,
            title="扫描子目录",
            content="拖入文件夹时递归搜索子目录中的图片",
            parent=self.ocr_group
        )
        self.scan_subdirs_card.switchButton.setChecked(self.config.get_scan_subdirs())
        self.scan_subdirs_card.switchButton.checkedChanged.connect(self._on_scan_subdirs_changed)
        self.ocr_group.addSettingCard(self.scan_subdirs_card)

        # 自动复制结果 - SwitchSettingCard
        self.auto_copy_card = SwitchSettingCard(
            icon=FluentIcon.COPY,
            title="自动复制结果",
            content="识别成功后自动复制到剪贴板",
            parent=self.ocr_group
        )
        self.auto_copy_card.switchButton.setChecked(self.ui_config.get_auto_copy())
        self.auto_copy_card.switchButton.checkedChanged.connect(self._on_auto_copy_changed)
        self.ocr_group.addSettingCard(self.auto_copy_card)

        # 超长图切片高度 - SpinBoxSettingCard
        self.slice_height_card = SpinBoxSettingCard(
            icon=FluentIcon.ZOOM,
            title="切片高度",
            content="超长图识别时的切片高度阈值（像素）",
            min_val=500,
            max_val=5000,
            default_val=self.config.get_slice_height(),
            suffix="px",
            parent=self.ocr_group
        )
        self.slice_height_card.spin_box.valueChanged.connect(self._on_slice_height_changed)
        self.ocr_group.addSettingCard(self.slice_height_card)

        # 超长图切片重叠 - SpinBoxSettingCard
        self.slice_overlap_card = SpinBoxSettingCard(
            icon=FluentIcon.ZOOM_IN,
            title="切片重叠",
            content="相邻切片的重叠区域，防止文字被切断",
            min_val=0,
            max_val=500,
            default_val=self.config.get_slice_overlap(),
            suffix="px",
            parent=self.ocr_group
        )
        self.slice_overlap_card.spin_box.valueChanged.connect(self._on_slice_overlap_changed)
        self.ocr_group.addSettingCard(self.slice_overlap_card)

        # 历史记录存储上限 - SpinBoxSettingCard（官方样式）
        self.storage_limit_card = SpinBoxSettingCard(
            icon=FluentIcon.HISTORY,
            title="历史记录存储上限",
            content="最多保存的历史记录条数",
            min_val=10,
            max_val=500,
            default_val=self.config.get_history_storage_limit(),
            suffix="条",
            parent=self.ocr_group
        )
        self.storage_limit_card.spin_box.valueChanged.connect(self._on_storage_limit_changed)
        self.ocr_group.addSettingCard(self.storage_limit_card)

        # 历史记录显示上限 - SpinBoxSettingCard（官方样式）
        self.display_limit_card = SpinBoxSettingCard(
            icon=FluentIcon.VIEW,
            title="历史记录显示上限",
            content="历史页面默认显示的条数",
            min_val=10,
            max_val=500,
            default_val=self.config.get_history_display_limit(),
            suffix="条",
            parent=self.ocr_group
        )
        self.display_limit_card.spin_box.valueChanged.connect(self._on_display_limit_changed)
        self.ocr_group.addSettingCard(self.display_limit_card)

        # ── 去重设置 ──
        # 文件去重开关
        self.file_dedup_card = SwitchSettingCard(
            icon=FluentIcon.FILTER,
            title="识别前文件去重",
            content="自动跳过相同内容的图片文件（基于 MD5 哈希）",
            parent=self.ocr_group
        )
        self.file_dedup_card.switchButton.setChecked(self.config.get_file_dedup_enabled())
        self.file_dedup_card.switchButton.checkedChanged.connect(self._on_file_dedup_changed)
        self.ocr_group.addSettingCard(self.file_dedup_card)

        # 内容去重开关
        self.text_dedup_card = SwitchSettingCard(
            icon=FluentIcon.DICTIONARY,
            title="识别后内容去重",
            content="自动跳过相同识别结果的图片（基于 SimHash 精确匹配）",
            parent=self.ocr_group
        )
        self.text_dedup_card.switchButton.setChecked(self.config.get_text_dedup_enabled())
        self.text_dedup_card.switchButton.checkedChanged.connect(self._on_text_dedup_changed)
        self.ocr_group.addSettingCard(self.text_dedup_card)

    def add_ui_cards(self):
        """添加个性化设置卡片"""
        # 主题设置 - OptionsSettingCard
        self.theme_card = OptionsSettingCard(
            icon=FluentIcon.BRUSH,
            title="界面主题",
            texts=THEME_OPTIONS,
            configItem=cfg_theme,
            parent=self.ui_group
        )
        self.theme_card.optionChanged.connect(self.onThemeChanged)
        self.ui_group.addSettingCard(self.theme_card)
        
        # 界面语言设置 - OptionsSettingCard
        # 从配置中获取当前界面语言
        current_ui_language = self.ui_config.get_ui_language()
        # 创建一个临时的OptionsConfigItem用于OptionsSettingCard
        ui_language_config = OptionsConfigItem(
            group="Interface",
            name="ui_language",
            default="中文",
            validator=OptionsValidator(["中文", "English"])
        )
        # 设置当前值
        ui_language_config.value = current_ui_language
        # 创建OptionsSettingCard
        self.ui_language_card = OptionsSettingCard(
            icon=FluentIcon.LANGUAGE,
            title="界面语言",
            texts=["中文", "English"],
            configItem=ui_language_config,
            parent=self.ui_group
        )
        self.ui_language_card.optionChanged.connect(self._on_ui_language_changed)
        self.ui_group.addSettingCard(self.ui_language_card)
        
        # 导出时包含原始文本 - SwitchSettingCard
        self.export_include_original_text_card = SwitchSettingCard(
            icon=FluentIcon.SAVE,
            title="导出时包含原始文本",
            content="Excel 导出时，在最后一列添加原始的 OCR 识别文本",
            parent=self.ui_group
        )
        self.export_include_original_text_card.switchButton.setChecked(
            self.ui_config.get_export_include_original_text()
        )
        self.export_include_original_text_card.switchButton.checkedChanged.connect(
            self._on_export_include_original_text_changed
        )
        self.ui_group.addSettingCard(self.export_include_original_text_card)

    def add_about_card(self):
        """添加关于信息"""
        self.about_card = SettingCard(
            icon=FluentIcon.INFO,
            title="关于",
            content="OCR GUI Tool v2.0 - 基于 PaddleOCR-json",
            parent=self.about_group
        )
        
        # 添加版本信息和链接
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        
        self.versionLabel = BodyLabel("版本: 2.0.0", self.about_card)
        self.versionLabel.move(20, 80)
        
        self.githubButton = PushButton("GitHub", self.about_card)
        self.githubButton.setFixedWidth(100)
        self.githubButton.move(20, 110)
        self.githubButton.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com")))
        
        self.about_group.addSettingCard(self.about_card)
    
    def add_performance_card(self):
        """添加性能监控卡片（手风琴样式）"""
        from qfluentwidgets import TextBrowser, PushButton
        
        # 创建手风琴卡片
        self.performance_card = ExpandGroupSettingCard(
            FluentIcon.INFO,
            "性能监控",
            "查看 OCR 识别的性能统计信息",
            parent=self.about_group
        )
        
        # 调整内部布局
        self.performance_card.viewLayout.setContentsMargins(0, 0, 0, 0)
        self.performance_card.viewLayout.setSpacing(0)
        
        # 防止展开动画连点竞态：动画运行中时忽略新触发
        original_set_expand = self.performance_card.setExpand

        def _safe_set_expand(isExpand: bool):
            if self.performance_card.expandAni.state() == QAbstractAnimation.State.Running:
                return  # 动画正在跑，忽略本次触发
            original_set_expand(isExpand)

        self.performance_card.setExpand = _safe_set_expand

        # 覆写 _adjustViewSize，跳过隐藏的子项（库默认方法不处理可见性）
        def _adjusted_adjust_view_size():
            h = sum(w.sizeHint().height() + 3 for w in self.performance_card.widgets if w.isVisible())
            self.performance_card.spaceWidget.setFixedHeight(h)
            if self.performance_card.isExpand:
                self.performance_card.setFixedHeight(self.performance_card.card.height() + h)

        self.performance_card._adjustViewSize = _adjusted_adjust_view_size
        
        # 创建内容区域
        self.content_widget = QWidget()
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setSpacing(12)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建文本浏览器显示性能统计
        self.performance_browser = TextBrowser()
        self.performance_browser.setStyleSheet("""
            TextBrowser {
                background-color: transparent;
                border: 1px solid rgba(0, 0, 0, 0.1);
                border-radius: 4px;
                padding: 12px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 12px;
                min-height: 300px;
                height: 300px;
            }
        """)
        self.performance_browser.setFixedHeight(300)
        content_layout.addWidget(self.performance_browser)
        
        # 添加刷新按钮（右对齐）
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.refresh_performance_btn = PushButton("刷新")
        self.refresh_performance_btn.setFixedWidth(80)
        self.refresh_performance_btn.clicked.connect(self._refresh_performance_stats)
        button_layout.addWidget(self.refresh_performance_btn)
        
        content_layout.addLayout(button_layout)
        
        # 添加到手风琴卡片
        self.performance_card.addGroup(
            FluentIcon.CHAT,
            "性能统计",
            "OCR 识别的详细性能数据",
            self.content_widget
        )
        
        # 添加到组
        self.about_group.addSettingCard(self.performance_card)
        
        # 调整视图大小
        self.performance_card._adjustViewSize()
        
        # 初始刷新
        self._refresh_performance_stats()
    
    

    def onThemeChanged(self, theme):
        """切换主题 - 核心层处理"""
        # 确保theme是字符串
        if hasattr(theme, 'value'):
            theme = theme.value
        theme_map = {
            "浅色": Theme.LIGHT,
            "深色": Theme.DARK,
            "跟随系统": Theme.AUTO
        }
        if theme in theme_map:
            setTheme(theme_map[theme])
            # 保存到界面配置层
            self.ui_config.set_theme(theme)
            InfoBar.success(
                title="设置已保存",
                content=f"界面主题: {theme}",
                position=InfoBarPosition.TOP,
                parent=self
            )
    
    def _on_ui_language_changed(self, language):
        """切换界面语言"""
        # 确保language是字符串
        if hasattr(language, 'value'):
            language = language.value
        # 保存到界面配置层
        self.ui_config.set_ui_language(language)
        InfoBar.success(
            title="设置已保存",
            content=f"界面语言: {language}",
            position=InfoBarPosition.TOP,
            parent=self
        )
        # 提示需要重启应用
        InfoBar.warning(
            title="提示",
            content="界面语言变更需要重启应用才能生效",
            position=InfoBarPosition.TOP,
            parent=self
        )

    def _on_auto_copy_changed(self, checked):
        """自动复制设置变化 - 界面层处理"""
        self.ui_config.set_auto_copy(checked)

    def _on_scan_subdirs_changed(self, checked: bool):
        """扫描子目录开关变化 - 核心层处理"""
        self.config.set_scan_subdirs(checked)
        status = "递归扫描子目录" if checked else "仅扫描当前目录"
        InfoBar.success(
            title="设置已保存",
            content=status,
            position=InfoBarPosition.TOP,
            parent=self
        )

    def _on_storage_limit_changed(self, value: int):
        """历史记录存储上限变化 - 核心层处理"""
        self.config.set_history_storage_limit(value)
        InfoBar.success(
            title="设置已保存",
            content=f"历史记录存储上限: {value} 条",
            position=InfoBarPosition.TOP,
            parent=self
        )

    def _on_display_limit_changed(self, value: int):
        """历史记录显示上限变化 - 核心层处理"""
        self.config.set_history_display_limit(value)
        InfoBar.success(
            title="设置已保存",
            content=f"历史记录显示上限: {value} 条",
            position=InfoBarPosition.TOP,
            parent=self
        )

    def _on_file_dedup_changed(self, enabled: bool):
        """文件去重开关变化"""
        self.config.set_file_dedup_enabled(enabled)
        status = "已开启" if enabled else "已关闭"
        InfoBar.success(
            title="设置已保存",
            content=f"识别前文件去重：{status}",
            position=InfoBarPosition.TOP,
            parent=self
        )

    def _on_text_dedup_changed(self, enabled: bool):
        """内容去重开关变化"""
        self.config.set_text_dedup_enabled(enabled)
        status = "已开启" if enabled else "已关闭"
        InfoBar.success(
            title="设置已保存",
            content=f"识别后内容去重：{status}",
            position=InfoBarPosition.TOP,
            parent=self
        )

    def _on_slice_height_changed(self, value: int):
        """切片高度变化 - 核心层处理"""
        self.config.set_slice_height(value)
        InfoBar.success(
            title="设置已保存",
            content=f"切片高度: {value}px，超过此高度的图片将自动切片识别",
            position=InfoBarPosition.TOP,
            parent=self
        )

    def _on_slice_overlap_changed(self, value: int):
        """切片重叠变化 - 核心层处理"""
        self.config.set_slice_overlap(value)
        InfoBar.success(
            title="设置已保存",
            content=f"切片重叠: {value}px，相邻切片将重叠 {value} 像素",
            position=InfoBarPosition.TOP,
            parent=self
        )
    def _on_export_include_original_text_changed(self, checked: bool):
        """导出时包含原始文本 - 开关状态变化"""
        self.ui_config.set_export_include_original_text(checked)
        
        if checked:
            InfoBar.success(
                title="设置已保存",
                content="Excel 导出时将包含原始 OCR 文本",
                position=InfoBarPosition.TOP,
                parent=self.window()
            )
        else:
            InfoBar.success(
                title="设置已保存",
                content="Excel 导出时将不包含原始 OCR 文本",
                position=InfoBarPosition.TOP,
                parent=self.window()
            )
