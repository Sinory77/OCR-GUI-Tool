"""
OCR GUI - Fluent Design 风格主窗口
基于 PySide6-Fluent-Widgets 构建
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel
from PySide6.QtCore import Qt, Signal, QLocale
from qfluentwidgets import FluentWindow, NavigationItemPosition, FluentIcon as FIF
from qfluentwidgets.common import FluentTranslator
from qfluentwidgets import MessageDialog, InfoBar, InfoBarPosition

from .pages.ocr_page import OCRPage
from .pages.history_page import HistoryPage
from .pages.template_page import TemplatePage
from .pages.settings_page import SettingsPage
from .ui_utils import create_engine_config_dialog
from .error_ui import ErrorHandlerUI
from core.error_handler import get_error_handler, ErrorType, OCRError


class MainWindow(FluentWindow):
    """OCR 工具主窗口 - Fluent Design 风格"""
    
    def __init__(self):
        super().__init__()
        
        # 初始化窗口
        self.initWindow()
        
        # 初始化核心模块（必须在界面之前）
        self.initCore()
        
        # 初始化界面
        self.initNavigation()
        
        # 初始化错误处理
        self.initErrorHandling()
        
        # 加载翻译
        self.loadTranslator()
    
    def initWindow(self):
        """初始化窗口属性"""
        self.resize(1200, 850)
        self.setMinimumWidth(900)
        self.setMinimumHeight(850)
        self.setWindowTitle("OCR 识别工具")
        
        # 设置窗口居中
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QScreen
        screen: QScreen = QApplication.primaryScreen()
        if screen:
            rect = screen.availableGeometry()
            x = (rect.width() - self.width()) // 2 + rect.x()
            y = (rect.height() - self.height()) // 2 + rect.y()
            self.move(x, y)
    
    def initCore(self):
        """初始化核心模块"""
        from core.ocr_engine import get_ocr_engine
        from core.result_manager import get_result_manager
        from core.exporter import get_exporter
        from core.async_worker import get_task_manager
        
        # 获取全局 OCR 引擎实例
        self.ocr_engine = get_ocr_engine()
        self.result_manager = get_result_manager()
        self.exporter = get_exporter()
        
        # 获取全局任务管理器
        self.task_manager = get_task_manager()
    
    def loadTranslator(self):
        """加载翻译器"""
        # 使用 FluentTranslator
        translator = FluentTranslator()
        self.setupTranslation(translator)
    
    def setupTranslation(self, translator):
        """设置翻译"""
        self.translator = translator
    
    def initErrorHandling(self):
        """初始化错误处理"""
        # 创建界面错误处理器
        self.error_ui = ErrorHandlerUI(self)
        
        # 获取全局错误处理器
        error_handler = get_error_handler()
        
        # 注册错误处理回调
        for error_type in ErrorType:
            error_handler.register_callback(error_type, self._handle_error)
    
    def _handle_error(self, error: OCRError):
        """处理错误的回调函数"""
        # 显示错误信息
        self.error_ui.handle_ocr_error(error)
    
    def initNavigation(self):
        """初始化导航"""
        # 创建页面
        self.ocr_page = OCRPage(self)
        self.ocr_page.setObjectName("ocr_page")
        
        self.template_page = TemplatePage(self)
        self.template_page.setObjectName("template_page")
        
        self.history_page = HistoryPage(self)
        self.history_page.setObjectName("history_page")
        
        self.settings_page = SettingsPage(self)
        self.settings_page.setObjectName("settings_page")
        
        # 添加导航项
        self.addSubInterface(
            self.ocr_page,
            icon=FIF.VIEW,
            text="文字识别",
            position=NavigationItemPosition.TOP
        )
        
        self.addSubInterface(
            self.template_page,
            icon=FIF.LABEL,
            text="模板管理",
            position=NavigationItemPosition.TOP
        )
        
        self.addSubInterface(
            self.history_page,
            icon=FIF.HISTORY,
            text="识别历史",
            position=NavigationItemPosition.TOP
        )
        
        self.addSubInterface(
            self.settings_page,
            icon=FIF.SETTING,
            text="设置",
            position=NavigationItemPosition.BOTTOM
        )
        
        # 连接信号（必须在 setCurrentItem 之前）
        self.connectSignals()
        
        # 设置当前页面，触发初始检查
        self.navigationInterface.setCurrentItem("ocr_page")
        
        # 程序启动时检查配置并初始化引擎
        self._init_ocr_engine_on_startup()
    
    def connectSignals(self):
        """连接信号"""
        # 从 OCR 页面跳转到历史记录
        self.ocr_page.ocr_completed.connect(self.onOcrCompleted)

        # 监听页面切换，切换到 OCR 页面时检查引擎就绪状态
        # 使用 stackedWidget.currentChanged 而不是 navigationInterface（后者没有此信号）
        self.stackedWidget.currentChanged.connect(self._on_stacked_widget_changed)

        # 向设置页面的引擎卡片注入成功回调
        self._setup_engine_callback()

    def _setup_engine_callback(self):
        """注入 OCR 引擎自动检测成功后的回调"""
        def on_auto_detect_success(exe_path, models_path):
            # 用新路径重新初始化 OCR 引擎
            self._reinit_ocr_engine(exe_path, models_path)

        engine_card = self.settings_page.engine_card
        engine_card.engine_auto_detect_success = on_auto_detect_success

    def _init_ocr_engine_on_startup(self):
        """程序启动时异步初始化 OCR 引擎"""
        import os
        from core.config import get_config_manager

        config = get_config_manager()
        exe_path = config.get_ocr_exe_path()
        models_path = config.get_models_path()

        # 检查路径是否存在，不存在则清空配置
        if exe_path and not os.path.exists(exe_path):
            print(f"[警告] OCR 引擎路径不存在: {exe_path}，已清空配置")
            exe_path = None
            config.set_ocr_exe_path(None)
            config.set_auto_detect(False)

        if models_path and not os.path.exists(models_path):
            print(f"[警告] OCR 模型目录不存在: {models_path}，已清空配置")
            models_path = None
            config.set_models_path(None)
            config.set_auto_detect(False)

        # 更新设置页面的显示
        settings_card = self.settings_page.engine_card
        if not exe_path:
            settings_card.exePathGroup.contentLabel.setText("未配置")
        if not models_path:
            settings_card.modelsPathGroup.contentLabel.setText("未配置")

        # 强制更新开关状态（防止配置中的 auto_detect 与实际路径不同步）
        auto_detect = config.get_auto_detect()
        if not exe_path or not models_path:
            auto_detect = False
            config.set_auto_detect(False)

        settings_card.autoDetectSwitch.blockSignals(True)
        settings_card.autoDetectSwitch.setChecked(auto_detect)
        settings_card.autoDetectSwitch.blockSignals(False)

        # 如果开关关闭，恢复手动子项显示
        if not auto_detect:
            settings_card._set_group_visible(settings_card.exePathGroup, True)
            settings_card._set_group_visible(settings_card.modelsPathGroup, True)
            settings_card.autoDetectGroup.contentLabel.setText(
                "开启后在程序目录中自动搜索 PaddleOCR-json.exe 和 models"
            )

        # 异步初始化引擎（延迟到后台执行，让窗口先显示）
        if exe_path and models_path:
            # 显示初始化中状态（黄色）
            self.ocr_page.set_engine_initializing()
            
            # 使用异步工作线程初始化引擎
            self._start_async_ocr_init(exe_path, models_path, config.get_language())
    
    def _start_async_ocr_init(self, exe_path: str, models_path: str, language: str):
        """启动异步 OCR 引擎初始化"""
        from core.async_worker import OcrInitWorker
        
        # 创建工作线程
        self.init_worker = OcrInitWorker(
            ocr_engine=self.ocr_engine,
            exe_path=exe_path,
            models_path=models_path,
            language=language,
            parent=self
        )
        
        # 连接信号
        self.init_worker.finished.connect(self._on_ocr_init_finished)
        self.init_worker.error.connect(self._on_ocr_init_error)
        
        # 启动线程
        self.init_worker.start()
    
    def _on_ocr_init_finished(self, result: dict):
        """OCR 引擎初始化完成回调"""
        success = result.get("success", False)
        message = result.get("message", "")
        
        if success:
            # 初始化成功（绿色），显示通知
            self.ocr_page.update_engine_status(show_notification=True)
            print(f"[OCR] 引擎初始化成功: {message}")
        else:
            # 初始化失败（红色）
            self.ocr_page.set_engine_error()
            print(f"[OCR] 引擎初始化失败: {message}")
    
    def _on_ocr_init_error(self, error_msg: str):
        """OCR 引擎初始化错误回调"""
        self.ocr_page.set_engine_error()
        print(f"[OCR] 引擎初始化异常: {error_msg}")

    def _on_stacked_widget_changed(self, index):
        """页面切换时检查 OCR 引擎状态（不重新初始化）"""
        widget = self.stackedWidget.widget(index)
        if widget is None or widget.objectName() != "ocr_page":
            return

        # 只检查引擎是否已就绪，不需要重新初始化
        self.ocr_page.update_engine_status()

    def _prompt_configure_engine(self):
        """提示用户配置 OCR 引擎"""
        dialog = create_engine_config_dialog(parent=self)

        dialog.yesSignal.connect(self._auto_detect_and_init_engine)
        dialog.cancelSignal.connect(self._switch_to_settings)

        dialog.exec()

    def _auto_detect_and_init_engine(self):
        """触发设置页面的自动搜索"""
        self.settings_page.engine_card.trigger_auto_detect()

    def _switch_to_settings(self):
        """切换到设置页面"""
        self.navigationInterface.setCurrentItem("settings_page")

    def _reinit_ocr_engine(self, exe_path, models_path):
        """配置修改后异步重新初始化 OCR 引擎"""
        from core.config import get_config_manager
        from core.async_worker import OcrInitWorker
        
        # 显示初始化中状态
        self.ocr_page.set_engine_initializing()
        
        # 创建工作线程
        self.init_worker = OcrInitWorker(
            ocr_engine=self.ocr_engine,
            exe_path=exe_path,
            models_path=models_path,
            language=get_config_manager().get_language(),
            parent=self
        )
        
        # 连接信号
        self.init_worker.finished.connect(self._on_ocr_init_finished)
        self.init_worker.error.connect(self._on_ocr_init_error)
        
        # 启动线程
        self.init_worker.start()
    
    def onOcrCompleted(self, image_path):
        """OCR 识别完成"""
        # 刷新历史记录
        self.history_page.loadHistory()
        # 注释掉：识别完成后不跳转到历史记录
        # self.stackedWidget.setCurrentWidget(self.history_page)
        # self.navigationInterface.setCurrentItem("history_page")
    
    def closeEvent(self, event):
        """关闭窗口"""
        # 停止所有异步任务
        if hasattr(self, 'task_manager'):
            self.task_manager.cleanup()
        
        # 关闭 OCR 引擎
        if hasattr(self, 'ocr_engine'):
            self.ocr_engine.close()
        
        super().closeEvent(event)