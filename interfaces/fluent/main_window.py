"""
OCR GUI - Fluent Design 风格主窗口
基于 PySide6-Fluent-Widgets 构建
"""

import sys
import os
import logging

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
from .pages.excel_page import ExcelPage
from .pages.cert_query_page import CertQueryPage
from .ui_utils import create_engine_config_dialog
from .error_ui import ErrorHandlerUI
from core.error_handler import get_error_handler, ErrorType, OCRError

logger = logging.getLogger(__name__)


class MainWindow(FluentWindow):
    """OCR 工具主窗口 - Fluent Design 风格"""

    # ★ 引擎状态推送信号（核心模块 → 主线程 UI 更新）
    engine_status_pushed = Signal(str)  # status: 'ready' | 'not_initialized' | 'error' | 'initializing'
    engine_event_pushed = Signal(dict)     # 引擎内部事件（crash_recovered, retry_failed）
    result_event_pushed = Signal(dict)     # 结果缓存变更（cache_updated, cache_cleared）
    template_event_pushed = Signal(dict)   # 模板变更（created, updated, deleted）
    
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
        
        logger.info("[App] 主窗口初始化完成 (1200×850, min: 900×850)")
    
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
    
    def _get_api(self):
        """获取核心API实例，延迟初始化"""
        if not hasattr(self, 'api') or self.api is None:
            from api.core_api import get_core_api
            self.api = get_core_api()
        return self.api
    
    def initCore(self):
        """初始化核心模块"""
        # 延迟初始化核心API，直到需要时才创建
        # 注意：不再在 initCore 中初始化API，而是在需要时通过 _get_api() 方法获取
        pass
    
    def initErrorHandling(self):
        """初始化错误处理"""
        # 创建界面错误处理器
        self.error_ui = ErrorHandlerUI(self)
        
        # 连接信号：在主线程显示 InfoBar
        self.error_ui.show_info_bar_signal.connect(self._on_show_info_bar)
        
        # 获取全局错误处理器
        error_handler = get_error_handler()
        
        # 注册错误处理回调
        for error_type in ErrorType:
            error_handler.register_callback(error_type, self._handle_error)
        
        logger.info("[App] 错误处理已注册 (%d 种错误类型)", len(ErrorType))

        # ★ 订阅引擎状态推送：核心模块状态变更 → 界面自动更新
        api = self._get_api()
        api.on_engine_status_changed(self._on_engine_status_pushed)
        self.engine_status_pushed.connect(self._apply_engine_status)
        logger.info("[App] 引擎状态推送已订阅")

        # ★ 订阅 EventBus 事件频道：核心模块主动推送事件 → 界面自动响应
        api.on("engine:event", self._on_engine_event_pushed)
        self.engine_event_pushed.connect(self._apply_engine_event)

        api.on("result:event", self._on_result_event_pushed)
        self.result_event_pushed.connect(self._apply_result_event)

        api.on("template:event", self._on_template_event_pushed)
        self.template_event_pushed.connect(self._apply_template_event)
        logger.info("[App] EventBus 事件频道已订阅 (engine:event, result:event, template:event)")
    
    def loadTranslator(self):
        """加载翻译器"""
        # 使用 FluentTranslator
        translator = FluentTranslator()
        self.setupTranslation(translator)
    
    def setupTranslation(self, translator):
        """设置翻译"""
        self.translator = translator
    
    def _handle_error(self, error: OCRError):
        """处理错误的回调函数（可能在 worker 线程执行）"""
        # handle_ocr_error 会通过信号在主线程显示 UI
        self.error_ui.handle_ocr_error(error)
    
    def _on_show_info_bar(self, data: str):
        """
        在主线程显示 InfoBar（槽函数）
        
        Args:
            data: 格式 "success|消息" 或 "error|标题|内容"
        """
        parts = data.split("|", 2)
        if parts[0] == "success":
            self.error_ui.show_success("恢复成功", parts[1])
        elif parts[0] == "error":
            self.error_ui.show_error(parts[1], parts[2])

    def _on_engine_status_pushed(self, status: str, error: str = None):
        """引擎状态推送回调（可能在其他线程调用，转发到主线程）"""
        self.engine_status_pushed.emit(status)

    def _apply_engine_status(self, status: str):
        """在主线程更新引擎状态 UI"""
        logger.info("[App] 引擎状态推送: %s，更新 UI", status)
        self.ocr_page.update_engine_status()

    # ── EventBus 回调转发（可能在其他线程调用，转发 Qt Signal 到主线程）──

    def _on_engine_event_pushed(self, data: dict):
        """引擎事件回调 → 转发到主线程"""
        self.engine_event_pushed.emit(data)

    def _on_result_event_pushed(self, data: dict):
        """结果缓存事件回调 → 转发到主线程"""
        self.result_event_pushed.emit(data)

    def _on_template_event_pushed(self, data: dict):
        """模板事件回调 → 转发到主线程"""
        self.template_event_pushed.emit(data)

    # ── 主线程处理槽函数 ──

    def _apply_engine_event(self, data: dict):
        """在主线程响应引擎事件"""
        event_type = data.get("type", "")
        if event_type == "crash_recovered":
            retry = data.get("retry", 0)
            if retry >= 3:
                InfoBar.warning(
                    title="引擎异常",
                    content=f"引擎已自动重连{retry}次",
                    position=InfoBarPosition.TOP,
                    parent=self,
                )
        elif event_type == "process_died":
            # 引擎子进程被意外终止
            InfoBar.error(
                title="引擎已停止",
                content="OCR 引擎进程已意外终止，下次操作将自动重新初始化",
                position=InfoBarPosition.TOP,
                parent=self,
                duration=5000,
            )
            # 更新状态栏
            if hasattr(self, 'ocr_page'):
                self.ocr_page.update_engine_status()

    def _apply_result_event(self, data: dict):
        """在主线程响应结果缓存变更"""
        event_type = data.get("type", "")
        # 结果变更 → 通知 OCR 页面刷新按钮状态
        if hasattr(self, 'ocr_page'):
            self.ocr_page.update_engine_status()

    def _apply_template_event(self, data: dict):
        """在主线程响应模板变更"""
        event_type = data.get("type", "")
        name = data.get("name", "")
        if event_type == "created":
            InfoBar.success(
                title="模板已创建",
                content=f"模板 '{name}' 已创建",
                position=InfoBarPosition.TOP,
                parent=self,
            )
        elif event_type == "deleted":
            InfoBar.success(
                title="模板已删除",
                content=f"模板 '{name}' 已删除",
                position=InfoBarPosition.TOP,
                parent=self,
            )
        # 通知 OCR 页面刷新模板下拉框
        if hasattr(self, 'ocr_page'):
            self.ocr_page._load_templates()
    
    def initNavigation(self):
        """初始化导航"""
        # 创建页面
        self.ocr_page = OCRPage(self)
        self.ocr_page.setObjectName("ocr_page")
        
        self.excel_page = ExcelPage(self)
        self.excel_page.setObjectName("excel_page")
        
        self.template_page = TemplatePage(self)
        self.template_page.setObjectName("template_page")
        
        self.history_page = HistoryPage(self)
        self.history_page.setObjectName("history_page")
        # 确保 api 已初始化，然后刷新历史页面
        self._get_api()
        self.history_page.loadHistory()
        
        self.cert_query_page = CertQueryPage(self)
        self.cert_query_page.setObjectName("cert_query_page")
        
        self.settings_page = SettingsPage(self)
        self.settings_page.setObjectName("settings_page")
        
        # 添加导航项
        self.addSubInterface(
            self.ocr_page,
            icon=FIF.VIEW,
            text="文字识别",
            position=NavigationItemPosition.TOP
        )
        
        # Excel 数据透视页面
        self.addSubInterface(
            self.excel_page,
            icon=FIF.DOCUMENT,
            text="数据透视",
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
        
        # ★ 检疫证查询
        self.addSubInterface(
            self.cert_query_page,
            icon=FIF.SEARCH,
            text="检疫证查询",
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
        
        # 批量识别完成时刷新历史记录
        self.ocr_page.batch_ocr_completed.connect(self.onOcrCompleted)
        
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
        
        api = self._get_api()
        config = api.config_manager
        exe_path = config.get_ocr_exe_path()
        models_path = config.get_models_path()
        
        # 检查路径是否存在，不存在则清空配置
        if exe_path and not os.path.exists(exe_path):
            logger.info(f"[警告] OCR 引擎路径不存在: {exe_path}，已清空配置")
            exe_path = None
            config.set_ocr_exe_path(None)
            config.set_auto_detect(False)
        
        if models_path and not os.path.exists(models_path):
            logger.info(f"[警告] OCR 模型目录不存在: {models_path}，已清空配置")
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
            
            # 使用 CoreAPI 初始化引擎
            self._start_async_ocr_init()
    
    def _start_async_ocr_init(self):
        """启动异步 OCR 引擎初始化"""
        api = self._get_api()
        
        # 直接调用 CoreAPI 的异步初始化方法
        def on_complete(result: dict):
            self._on_ocr_init_finished(result)
        
        def on_error(error_msg: str):
            self._on_ocr_init_error(error_msg)
        
        # 调用异步初始化方法
        api.init_ocr_engine(
            on_progress=None,  # 可以在这里添加进度回调
            on_complete=on_complete,
            on_error=on_error
        )
    
    def _on_ocr_init_finished(self, result: dict):
        """OCR 引擎初始化完成回调"""
        import logging
        logger = logging.getLogger(__name__)
        
        success = result.get("success", False)
        message = result.get("message", "")
        
        if success:
            # 初始化成功（绿色），显示通知
            logger.info(f"[MainWindow] 收到初始化成功信号，准备更新状态栏")
            self.ocr_page.update_engine_status(show_notification=True)
            logger.info(f"[OCR] 引擎初始化成功: {message}")
        else:
            # 初始化失败（红色）
            logger.error(f"[MainWindow] 收到初始化失败信号: {message}")
            self.ocr_page.set_engine_error()
            logger.error(f"[OCR] 引擎初始化失败: {message}")
    
    def _on_ocr_init_error(self, error_msg: str):
        """OCR 引擎初始化错误回调"""
        self.ocr_page.set_engine_error()
        logger.info(f"[OCR] 引擎初始化异常: {error_msg}")
    
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
        # 更新配置
        api = self._get_api()
        api.config_manager.set_ocr_exe_path(exe_path)
        api.config_manager.set_models_path(models_path)
        
        # 显示初始化中状态
        self.ocr_page.set_engine_initializing()
        
        # 重新初始化引擎
        self._start_async_ocr_init()
    
    def onOcrCompleted(self, image_path=None):
        """OCR 识别完成（单图/批量均可触发）"""
        # 刷新历史记录
        self.history_page.loadHistory()
        # 注释掉：识别完成后不跳转到历史记录
        # self.stackedWidget.setCurrentWidget(self.history_page)
        # self.navigationInterface.setCurrentItem("history_page")
    
    def closeEvent(self, event):
        """关闭窗口 - 设置关闭标志（非阻塞），由 atexit 完成优雅关闭"""
        logger.info("[App] ── 窗口关闭流程开始 ──")
        try:
            api = self._get_api()
            if api:
                ocr_engine = api.ocr_engine
                if ocr_engine:
                    logger.info("[App] 步骤1: 设置引擎关闭标志...")
                    ocr_engine.begin_shutdown()
                    logger.info("[App] 关闭标志已设置，atexit 将完成优雅关闭")
                else:
                    logger.info("[App] OCR 引擎实例不存在，跳过关闭")
            else:
                logger.info("[App] 核心 API 未初始化，跳过关闭")
        except Exception as e:
            logger.warning("[App] 关闭流程异常: %s", e)
        
        logger.info("[App] ── 窗口关闭流程完成，event.accept() ──")
        super().closeEvent(event)
