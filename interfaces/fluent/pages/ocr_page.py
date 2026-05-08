"""
OCR 识别页面
支持拖拽/选择图片、OCR识别、结果显示、复制和导出
"""

import os
import tempfile
import logging
import traceback
import warnings
from datetime import datetime

logger = logging.getLogger(__name__)

# 安装自定义 Qt 消息处理器来捕获 setParent 警告
from PySide6.QtCore import qInstallMessageHandler

def _qt_message_handler(msg_type, context, message):
    msg_str = str(message)
    if 'setParent' in msg_str or 'different thread' in msg_str:
        logger.error(f"[Qt Warning] {msg_str}")
        logger.error(f"  File: {context.file}, Line: {context.line}")
        logger.error(f"  Stack: {traceback.format_stack()}")
    # 抑制 Qt 警告输出到控制台，避免刷屏
    # 原始处理会被跳过，因为我们安装了自定义处理器

_qt_message_handler_installed = False

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFileDialog, QMessageBox,
    QMenu, QFrame, QListWidget, QListWidgetItem,
    QAbstractItemView, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractScrollArea, QApplication
)
from qfluentwidgets import TextBrowser, IndeterminateProgressBar, TableWidget, ListWidget
from PySide6.QtCore import Qt, Signal, QThread, QSize, QTimer, QMetaObject
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QPixmap
from qfluentwidgets import (
    CardWidget, PrimaryPushButton, PushButton,
    ComboBox, MessageDialog, InfoBar, InfoBarPosition,
    SubtitleLabel, BodyLabel, StateToolTip,
    setTheme, Theme, RoundMenu, Action, DropDownPushButton
)
from qfluentwidgets.common.icon import FluentIcon
from PySide6.QtGui import QPainter, QColor, QPen

# 延迟导入核心错误处理模块，避免循环导入



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
            if hasattr(parent, 'api'):
                scan_subdirs = parent.api.get_config("scan_subdirs", True)
                break
            elif hasattr(parent, 'config'):  # 兼容旧代码
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
                self._info_bar_warning("未找到图片", "拖入的文件中没有找到图片文件")
                return
            
            # 只有一个图片文件 → 预览模式
            if len(all_images) == 1 and not has_folder:
                self.file_dropped.emit(all_images[0])
            else:
                # 多个文件或包含文件夹 → 列表模式
                self.folder_dropped.emit(all_images)
            
            event.acceptProposedAction()


class OCRWorker(QThread):
    """OCR 识别工作线程 - 已废弃，使用 core.async_worker.OcrRecognizeWorker 替代"""
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


from PySide6.QtCore import Signal, Slot

class OCRPage(QWidget):
    """OCR 识别页面"""
    
    ocr_completed = Signal(str)  # 识别完成信号，传递图片路径
    batch_ocr_completed = Signal()  # 批量识别完成信号
    # StateToolTip 更新信号
    update_tooltip_signal = Signal(str, str)  # (title, content)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 安装 Qt 消息处理器来捕获 setParent 警告（仅安装一次）
        global _qt_message_handler_installed
        if not _qt_message_handler_installed:
            qInstallMessageHandler(_qt_message_handler)
            _qt_message_handler_installed = True
            logger.info("[OCRPage] Qt 消息处理器已安装")
        
        self.main_window = parent
        self.current_image_path = None
        self.ocr_result = None
        self.recognize_worker = None
        self.batch_worker = None
        self.scan_worker = None
        self.export_worker = None
        self.init_worker = None
        
        # StateToolTip 实例（用于显示进度提示）
        self._state_tooltip = None
        
        # 批量模式
        self.batch_file_paths = []  # 当前批量文件列表
        self.is_batch_mode = False
        self._last_selected_index = -1  # 记录上次选中的索引

        # 去重器
        self._deduplicator = None  # 延迟初始化

        # 配置管理器
        self._config = None  # 延迟初始化
        
        # 延迟初始化API
        self.api = None
        self.ui_config = None
        
        self.initUI()
    
    def _get_api(self):
        """获取核心API实例，延迟初始化"""
        if self.api is None:
            from api.core_api import get_core_api
            self.api = get_core_api()
        return self.api
    
    def _get_ui_config(self):
        """获取UI配置实例，延迟初始化"""
        if self.ui_config is None:
            from interfaces.fluent.ui_config import UIConfigManager
            self.ui_config = UIConfigManager()
        return self.ui_config

    def _get_deduplicator(self):
        """获取去重器实例，延迟初始化"""
        if self._deduplicator is None:
            from core.deduplication import Deduplicator
            self._deduplicator = Deduplicator()
        return self._deduplicator

    def _get_config(self):
        """获取配置管理器实例，延迟初始化"""
        if self._config is None:
            from core.config import get_config_manager
            self._config = get_config_manager()
        return self._config

    def _reload_template_combo(self):
        """刷新模板下拉列表"""
        if not hasattr(self, 'combo_template'):
            return
        from core.template_manager import get_template_manager
        tm = get_template_manager()
        templates = tm.get_all_templates()
        
        # 保存当前选中
        current_id = self._get_selected_template_id()
        
        self.combo_template.blockSignals(True)
        self.combo_template.clear()
        self.combo_template.addItem("不使用模板", userData=None)
        for tpl in templates:
            self.combo_template.addItem(tpl.name, userData=tpl.id)
        
        # 恢复选中状态
        if current_id:
            idx = self.combo_template.findData(current_id)
            if idx >= 0:
                self.combo_template.setCurrentIndex(idx)
        self.combo_template.blockSignals(False)
    
    def _get_selected_template_id(self):
        """获取当前选中的模板 ID（返回 None 表示不使用模板）"""
        if not hasattr(self, 'combo_template'):
            return None
        return self.combo_template.currentData()
    
    def _on_template_changed(self, index: int):
        """模板选择变更回调"""
        template_id = self._get_selected_template_id()
        if template_id:
            from core.template_manager import get_template_manager
            tm = get_template_manager()
            tpl = tm.get_template(template_id)
            if tpl:
                logger.info(f"[OCRPage] 已选择模板: {tpl.name} ({template_id})")
    
    def _parse_result_by_template(self, result: dict) -> dict:
        """根据当前选中模板解析识别结果
        
        Args:
            result: OCR 识别结果字典
            
        Returns:
            字段名 -> 字段值 的字典，未选择模板或解析失败时返回空字典
        """
        template_id = self._get_selected_template_id()
        if not template_id:
            return {}
        
        from core.template_manager import get_template_manager
        from core.text_parser import TextParser
        
        tm = get_template_manager()
        tpl = tm.get_template(template_id)
        if not tpl:
            return {}
        
        # 提取原始文本
        texts = result.get('texts', [])
        if not texts:
            return {}
        
        full_text = '\n'.join(texts)
        
        # 按模板解析
        try:
            parser = TextParser(tpl)
            return parser.parse(full_text)
        except Exception as e:
            logger.error(f"[OCRPage] 模板解析失败: {e}")
            return {}
    
    def _format_extracted_fields(self, fields: dict) -> str:
        """将提取的字段格式化为可读字符串
        
        Args:
            fields: 字段字典
            
        Returns:
            格式化后的字符串，用于显示
        """
        if not fields:
            return ""
        lines = []
        for key, value in fields.items():
            if value:  # 只显示有值的字段
                lines.append(f"  {key}: {value}")
        return '\n'.join(lines)

    def initUI(self):
        """初始化UI"""
        # 注意：不再在 initUI 中初始化API，而是在需要时通过 _get_api() 方法获取
        
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

    def cleanup_workers(self):
        """清理所有工作线程"""
        # 清理单图识别工作线程
        if hasattr(self, 'recognize_worker') and self.recognize_worker:
            try:
                self.recognize_worker.finished.disconnect()
            except:
                pass
            try:
                self.recognize_worker.error.disconnect()
            except:
                pass
            try:
                self.recognize_worker.cancelled.disconnect()
            except:
                pass
            try:
                self.recognize_worker.progress.disconnect()
            except:
                pass
            if self.recognize_worker.isRunning():
                self.recognize_worker.stop(500)  # 等待最多0.5秒
            self.recognize_worker = None
            
        # 清理批量识别工作线程
        if hasattr(self, 'batch_worker') and self.batch_worker:
            try:
                self.batch_worker.finished.disconnect()
            except:
                pass
            try:
                self.batch_worker.error.disconnect()
            except:
                pass
            try:
                self.batch_worker.cancelled.disconnect()
            except:
                pass
            try:
                self.batch_worker.progress.disconnect()
            except:
                pass
            if self.batch_worker.isRunning():
                self.batch_worker.stop(500)  # 等待最多0.5秒
            self.batch_worker = None
        
        # 清理文件夹扫描工作线程
        if hasattr(self, 'scan_worker') and self.scan_worker:
            try:
                self.scan_worker.finished.disconnect()
            except:
                pass
            try:
                self.scan_worker.error.disconnect()
            except:
                pass
            if self.scan_worker.isRunning():
                self.scan_worker.stop(500)
            self.scan_worker = None
        
        # 清理导出工作线程
        if hasattr(self, 'export_worker') and self.export_worker:
            try:
                self.export_worker.finished.disconnect()
            except:
                pass
            try:
                self.export_worker.error.disconnect()
            except:
                pass
            if self.export_worker.isRunning():
                self.export_worker.stop(500)
            self.export_worker = None
        
        # 清理初始化工作线程
        if hasattr(self, 'init_worker') and self.init_worker:
            try:
                self.init_worker.finished.disconnect()
            except:
                pass
            try:
                self.init_worker.error.disconnect()
            except:
                pass
            if self.init_worker.isRunning():
                self.init_worker.stop(500)
            self.init_worker = None

    def closeEvent(self, event):
        """页面关闭事件"""
        self.cleanup_workers()
        event.accept()

    def createToolbar(self):
        """创建工具栏 - 两行布局：第一行操作按钮，第二行参数选项"""
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
        self.btn_back_to_list.clicked.connect(self._return_to_batch_list)
        self.btn_back_to_list.setVisible(False)
        row1.addWidget(self.btn_back_to_list)

        # 选择图片
        self.btn_select = PrimaryPushButton(FluentIcon.FOLDER, "选择图片", self)
        self.btn_select.clicked.connect(self.selectFile)
        row1.addWidget(self.btn_select)

        # 批量选择（带下拉菜单）
        self.btn_batch = DropDownPushButton(FluentIcon.FOLDER_ADD, "批量选择", self)
        menu = RoundMenu()
        menu.addAction(Action(FluentIcon.FOLDER, "选择文件夹",
                               triggered=self._select_folder))
        menu.addAction(Action(FluentIcon.PHOTO, "选择多个文件",
                               triggered=self._select_multiple_files))
        self.btn_batch.setMenu(menu)
        row1.addWidget(self.btn_batch)

        # 截图识别
        self.btn_screenshot = PushButton(FluentIcon.CAMERA, "截图识别", self)
        self.btn_screenshot.clicked.connect(self.screenshot)
        row1.addWidget(self.btn_screenshot)

        # 开始识别
        self.btn_recognize = PrimaryPushButton(FluentIcon.SEARCH, "开始识别", self)
        self.btn_recognize.clicked.connect(self._on_recognize_clicked)
        self.btn_recognize.setEnabled(False)
        row1.addWidget(self.btn_recognize)

        # 中断
        self.btn_cancel = PushButton(FluentIcon.CLOSE, "中断", self)
        self.btn_cancel.clicked.connect(self._cancel_recognition)
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
        self.combo_lang.currentTextChanged.connect(self.onLanguageChanged)
        row2.addWidget(self.combo_lang)

        row2.addSpacing(24)   # 两个选项组之间留间隔

        # 提取模板
        template_label = BodyLabel("提取模板:", self)
        row2.addWidget(template_label)

        self.combo_template = ComboBox(self)
        self.combo_template.setMinimumWidth(140)
        self.combo_template.currentIndexChanged.connect(self._on_template_changed)
        self._reload_template_combo()
        row2.addWidget(self.combo_template)

        row2.addStretch(1)   # 右侧留白
        outer.addLayout(row2)

        return toolbar_widget
    
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
            self._start_batch_ocr()
        else:
            # 单图模式
            self.startOCR()

    def _update_recognize_button_text(self):
        """根据模式更新识别按钮文字"""
        if self.is_batch_mode and len(self.batch_file_paths) > 1:
            self.btn_recognize.setText(f"批量识别 ({len(self.batch_file_paths)})")
        else:
            self.btn_recognize.setText("开始识别")
    
    @Slot(str, str)
    def update_tooltip_slot(self, title: str, content: str):
        """槽函数：更新 StateToolTip，确保在主线程执行
        
        注意：此方法通过 Qt 信号调用，已在主线程中执行，无需锁保护
        Qt 的信号槽机制本身就是线程安全的
        """
        # 在槽函数中也检查中断状态
        if getattr(self, '_batch_cancel_pending', False):
            return
        
        # 使用辅助方法显示 StateToolTip
        self._show_state_tooltip(title, content)
    
    def _hide_state_tooltip(self):
        """安全隐藏 StateToolTip"""
        def do_hide():
            try:
                if hasattr(self, '_state_tooltip') and self._state_tooltip:
                    self._state_tooltip.hide()
                    self._state_tooltip.deleteLater()
                    self._state_tooltip = None
            except Exception as e:
                logger.warning(f"[OCRPage] 隐藏 StateToolTip 出错: {e}")
        
        QTimer.singleShot(0, do_hide)
    
    def _show_state_tooltip(self, title: str, content: str, is_done: bool = False):
        """显示 StateToolTip 提示框（位于窗口右上角）
        
        Args:
            title: 标题
            content: 内容
            is_done: 是否显示完成状态（会1秒后自动淡出）
        """
        def do_show():
            try:
                # 隐藏旧的提示
                if hasattr(self, '_state_tooltip') and self._state_tooltip:
                    try:
                        self._state_tooltip.hide()
                        self._state_tooltip.deleteLater()
                    except:
                        pass
                    self._state_tooltip = None
                
                # 创建 StateToolTip
                self._state_tooltip = StateToolTip(title, content, self)
                
                # 先显示才能获取正确的尺寸
                self._state_tooltip.show()
                
                # 定位到右上角
                x = self.width() - self._state_tooltip.width() - 10
                y = 30
                self._state_tooltip.move(x, y)
                
                # 如果是完成状态，设置后自动淡出
                if is_done:
                    self._state_tooltip.setState(True)
                    self._state_tooltip = None  # 清除引用，动画完成后会自动销毁
                
            except Exception as e:
                logger.warning(f"[OCRPage] 显示 StateToolTip 出错: {e}")
        
        QTimer.singleShot(0, do_show)
    
    def _update_state_tooltip(self, title: str, content: str):
        """辅助方法：安全更新 StateToolTip
        
        通过 Qt 信号机制确保在主线程执行，无需 Python 锁
        """
        # 在中断过程中不更新 state_tooltip
        if getattr(self, '_batch_cancel_pending', False):
            return
        
        # 使用信号槽机制确保在主线程执行
        self.update_tooltip_signal.emit(title, content)
    
    # ─────────────────────── InfoBar 快捷方法 ─────────────────────── #
    
    def _info_bar_success(self, title: str, content: str, duration: int = 3000,
                          position=InfoBarPosition.TOP_RIGHT):
        InfoBar.success(title=title, content=content, isClosable=True,
                        position=position, duration=duration, parent=self)
    
    def _info_bar_warning(self, title: str, content: str, duration: int = 3000,
                          position=InfoBarPosition.TOP_RIGHT):
        InfoBar.warning(title=title, content=content, isClosable=True,
                        position=position, duration=duration, parent=self)
    
    def _info_bar_error(self, title: str, content: str, duration: int = 5000,
                        position=InfoBarPosition.TOP_RIGHT):
        InfoBar.error(title=title, content=content, isClosable=True,
                      position=position, duration=duration, parent=self)
    
    def _info_bar_info(self, title: str, content: str, duration: int = 3000,
                       position=InfoBarPosition.TOP_RIGHT, isClosable: bool = True):
        InfoBar.info(title=title, content=content, isClosable=isClosable,
                     position=position, duration=duration, parent=self)
    
    def _close_info_bar_by_title(self, title: str):
        """关闭指定标题的 InfoBar"""
        for bar in self.findChildren(InfoBar):
            if getattr(bar, 'title', None) == title:
                bar.close()
    
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
        
        # 批量文件列表模式 - 使用 qfluentwidgets 的 ListWidget（自带 Fluent 风格滚动条）
        self.file_list_widget = ListWidget(self.preview_stack)
        self.file_list_widget.setSpacing(2)
        self.file_list_widget.setIconSize(QSize(64, 64))
        self.file_list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.file_list_widget.itemClicked.connect(self._on_file_list_item_clicked)
        self.file_list_widget.itemDoubleClicked.connect(self._on_file_list_item_double_clicked)
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
        # 切换结果显示控件：单图模式使用文本框
        self.result_table.setVisible(False)
        self.result_text.setVisible(True)
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
        self._update_recognize_button_state()  # 根据引擎状态决定按钮是否可用
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
        # 快速切换到批量模式时显示表格
        self.result_text.setVisible(False)
        self.result_table.setVisible(True)
        
        # 恢复表格数据
        if hasattr(self, 'batch_results') and self.batch_results:
            self.result_table.setRowCount(0)
            for item in self.batch_results:
                self._add_result_to_table(item['file_name'], item['result'])
            # 启用复制和导出
            self.btn_copy.setEnabled(True)
            self.btn_export.setEnabled(True)
        
        # 恢复选择状态
        if self.file_list_widget.count() > 0:
            self.file_list_widget.setCurrentRow(0)
            self.current_image_path = self.batch_file_paths[0]
        
        self._update_recognize_button_state()  # 根据引擎状态决定按钮是否可用
        self.status_label.setText(f"批量模式: {len(self.batch_file_paths)} 个文件")
        
        # 更新按钮文字
        self._update_recognize_button_text()
    
    def _load_list_thumbnail(self, file_path: str, item: QListWidgetItem):
        """异步加载列表缩略图"""
        from core.async_worker import ThumbnailLoadWorker
        
        worker = ThumbnailLoadWorker(
            file_path=file_path,
            size=64,
            parent=self
        )
        
        # 使用 lambda 捕获 file_path 和 item
        def on_finished(result):
            if result.get("success", False):
                thumbnail_data = result.get("thumbnail_data")
                if thumbnail_data:
                    # 在主线程中将base64数据转换为QPixmap
                    try:
                        import base64
                        from PySide6.QtGui import QPixmap, QImage
                        from PySide6.QtCore import Qt
                        
                        # 将base64解码为字节
                        img_bytes = base64.b64decode(thumbnail_data)
                        
                        # 创建QPixmap
                        pixmap = QPixmap()
                        pixmap.loadFromData(img_bytes)
                        
                        # 检查 item 是否还在列表中
                        if item.listWidget() and pixmap:
                            # 使用 QTimer.singleShot 确保在主线程中设置图标
                            def set_icon():
                                try:
                                    item.setIcon(pixmap)
                                except Exception as e:
                                    logger.warning(f"[OCRPage] 设置缩略图图标时出错: {e}")
                            
                            QTimer.singleShot(0, set_icon)
                    except Exception as e:
                        logger.error(f"[OCRPage] 转换缩略图为QPixmap时出错: {e}")
        
        worker.finished.connect(on_finished, Qt.QueuedConnection)
        worker.start()
    
    def _on_file_list_item_clicked(self, item: QListWidgetItem):
        """点击列表项"""
        self.current_image_path = item.data(Qt.UserRole)
        self.result_text.clear()
        self.btn_copy.setEnabled(False)
        self.btn_export.setEnabled(False)
        self._update_recognize_button_state()  # 根据引擎状态决定按钮是否可用
    
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

    def update_engine_status(self, show_notification: bool = False):
        """由 MainWindow 调用，初始化引擎后更新状态栏
        
        Args:
            show_notification: 是否显示通知提示框（默认 False，只在首次初始化时显示）
        """
        # 使用 get_ocr_engine() 方法获取引擎，而不是直接访问属性
        engine = self.main_window.get_ocr_engine()
        
        logger.info(f"[OCRPage] update_engine_status 被调用: engine={engine}, _initialized={engine._initialized if engine else 'N/A'}, show_notification={show_notification}")
        
        if engine and engine._initialized:
            # 绿色 - 已就绪
            self.status_icon.setPixmap(_create_status_dot("#4CAF50"))
            self.status_label.setText("OCR 引擎已就绪")
            logger.info("[OCRPage] 状态栏已更新为: OCR 引擎已就绪")
            
            # 启用识别按钮（如果有图片）
            self._update_recognize_button_state()
            
            # 只在首次初始化时显示通知
            if show_notification:
                self._info_bar_success("引擎就绪", "OCR 引擎初始化完成，可以开始识别")
                logger.info("[OCRPage] 已显示引擎就绪提示框")
        else:
            # 红色 - 未就绪
            self.status_icon.setPixmap(_create_status_dot("#F44336"))
            self.status_label.setText("引擎未就绪")
            # 禁用识别按钮
            self.btn_recognize.setEnabled(False)
            logger.info("[OCRPage] 状态栏已更新为: 引擎未就绪")

    def _update_recognize_button_state(self):
        """根据引擎和图片状态更新识别按钮可用性"""
        engine = self.main_window.get_ocr_engine()
        has_image = self.current_image_path is not None
        has_batch = self.is_batch_mode and len(self.batch_file_paths) > 1
        
        # 引擎就绪且有图片/批量文件时才启用
        if engine and engine._initialized and (has_image or has_batch):
            self.btn_recognize.setEnabled(True)
        else:
            self.btn_recognize.setEnabled(False)

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
        """选择文件夹 - 异步扫描"""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "选择文件夹",
            "",
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )

        if folder_path:
            # 显示加载中提示
            self._info_bar_info("扫描中", f"正在扫描文件夹: {folder_path}", duration=-1, isClosable=False)
            
            # 使用异步工作线程扫描文件夹
            from core.async_worker import FolderScanWorker
            
            self.scan_worker = FolderScanWorker(
                folder_path=folder_path,
                recursive=self._get_api().get_config("scan_subdirs", True),
                parent=self
            )
            
            # 连接信号
            self.scan_worker.finished.connect(self._on_folder_scan_finished, Qt.QueuedConnection)
            self.scan_worker.error.connect(self._on_folder_scan_error, Qt.QueuedConnection)
            
            # 启动线程
            self.scan_worker.start()
    
    def _on_folder_scan_finished(self, result: dict):
        """文件夹扫描完成回调"""
        # 关闭加载提示
        self._close_info_bar_by_title("扫描中")
        
        image_files = result.get("image_files", [])
        count = result.get("count", 0)
        
        if image_files:
            self._switch_to_batch_mode(image_files)
            self._info_bar_success("扫描完成", f"找到 {count} 个图片文件")
        else:
            self._info_bar_warning("文件夹为空", "该文件夹中没有找到图片文件")
    
    def _on_folder_scan_error(self, error_msg: str):
        """文件夹扫描错误回调"""
        # 关闭加载提示
        self._close_info_bar_by_title("扫描中")
        
        self._info_bar_error("扫描失败", error_msg)

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
        # 局部导入错误处理模块
        from core.error_handler import error_handling, ErrorType, FileOperationError
        
        # 应用错误处理装饰器
        @error_handling(ErrorType.FILE_OPERATION, "加载图片失败")
        def decorated_method():
            if not os.path.exists(file_path):
                raise FileOperationError(f"图片文件不存在: {file_path}")
            
            self.current_image_path = file_path
            
            # 如果是批量模式，切换到预览模式
            if self.is_batch_mode:
                self._switch_to_preview_mode()
            
            # 显示图片预览
            pixmap = QPixmap(file_path)
            if pixmap.isNull():
                raise FileOperationError(f"无法加载图片: {file_path}")
            
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
            self._update_recognize_button_state()  # 根据引擎状态决定按钮是否可用
            self.result_text.clear()
            self.result_table.setRowCount(0)  # 清空表格
            self.btn_copy.setEnabled(False)
            self.btn_export.setEnabled(False)
        
        return decorated_method()
    
    def onFileDropped(self, file_path: str):
        """处理拖放的文件（保留兼容）"""
        self.loadImage(file_path)
    
    def onLanguageChanged(self, language):
        """切换语言（运行时动态选择，不保存配置）"""
        # 直接应用到引擎
        if hasattr(self.main_window, 'ocr_engine'):
            success = self.main_window.ocr_engine.set_language(language)
            if success:
                self.status_label.setText(f"已切换语言: {language}")
            else:
                # 如果切换失败，可能是因为引擎未初始化或路径未设置
                self.status_label.setText(f"语言切换失败: 请先配置 OCR 引擎路径")
                # 提示用户配置引擎
                self._info_bar_warning("提示", "请先配置 OCR 引擎路径，才能切换语言")
    
    def startOCR(self):
        """开始OCR识别（自动判断单图/批量）"""
        # 局部导入错误处理模块
        from core.error_handler import error_handling, ErrorType, OCRError
        
        # 应用错误处理装饰器
        @error_handling(ErrorType.OCR_ENGINE, "OCR 识别失败")
        def decorated_method():
            if not self.current_image_path:
                raise OCRError("请先选择或拖入图片")
            
            # 检查 main_window
            if not hasattr(self, 'main_window') or not self.main_window:
                raise OCRError("主窗口未初始化")
            
            # 检查 OCR 引擎状态
            engine = self._get_api().ocr_engine  # 使用 CoreAPI 中的 OCR 引擎
            if not engine._initialized:
                if not engine.initialize():
                    raise OCRError("OCR 引擎无法初始化，请检查配置")
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
        
        return decorated_method()
    
    def _start_single_ocr(self):
        """单图OCR识别 - 异步执行"""
        file_name = os.path.basename(self.current_image_path)[:30]
        
        # 使用信号机制更新 StateToolTip（确保在主线程执行）
        self._update_state_tooltip("正在识别", file_name)
        
        # 保存原始按钮文字
        self._original_button_text = self.btn_recognize.text()
        
        # 禁用按钮并更改文字
        self.btn_recognize.setEnabled(False)
        self.btn_recognize.setText("识别中...")
        self.btn_cancel.setEnabled(True)
        
        self.progress_bar.setVisible(True)
        self.progress_bar.start()
        
        # 使用异步工作线程执行 OCR
        from core.async_worker import OcrRecognizeWorker
        
        # 使用基于 CoreAPI 的工作线程
        from core.async_worker import APIBasedOcrRecognizeWorker
        
        self.recognize_worker = APIBasedOcrRecognizeWorker(
            core_api=self._get_api(),  # 使用 CoreAPI
            image_path=self.current_image_path,
            parent=self
        )
        
        # 连接信号
        self.recognize_worker.finished.connect(self.onOCRFinished, Qt.QueuedConnection)
        self.recognize_worker.error.connect(self.onOCRError, Qt.QueuedConnection)
        
        # 启动线程
        self.recognize_worker.start()
    
    def _start_batch_ocr(self):
        """批量OCR识别 - 异步执行"""
        self.batch_results = []  # 存储所有识别结果
        self.batch_current_index = 0

        # ── 识别前排重 ──
        # 检查开关状态
        if self._get_config().get_file_dedup_enabled():
            dedup = self._get_deduplicator()
            original_count = len(self.batch_file_paths)
            unique_files = []
            duplicate_count = 0

            for file_path in self.batch_file_paths:
                if dedup.check_file_duplicate(file_path):
                    duplicate_count += 1
                    logger.info(f"[OCRPage] 文件重复，已跳过: {file_path}")
                else:
                    unique_files.append(file_path)

            self.batch_file_paths = unique_files
            self.batch_total = len(self.batch_file_paths)

            # 如果全部重复，给出提示
            if self.batch_total == 0:
                InfoBar.warning(
                    title="去重提示",
                    content=f"选中的 {original_count} 个文件全部重复，已无可识别文件",
                    position=InfoBarPosition.TOP,
                    parent=self
                )
                return

            # 提示去重信息
            if duplicate_count > 0:
                logger.info(f"[OCRPage] 识别前排重完成：原始 {original_count} 个文件，去重后 {self.batch_total} 个，跳过 {duplicate_count} 个重复文件")
                # 延迟显示提示，等界面准备好
                QTimer.singleShot(100, lambda: InfoBar.info(
                    title="文件去重",
                    content=f"已自动跳过 {duplicate_count} 个重复文件",
                    position=InfoBarPosition.TOP,
                    parent=self,
                    duration=3000
                ))
        else:
            # 去重功能关闭
            self.batch_total = len(self.batch_file_paths)

        # 切换到表格显示
        self.result_text.setVisible(False)
        self.result_table.setVisible(True)
        self.result_table.setRowCount(0)
        
        # 根据是否选择模板，显示/隐藏提取字段列
        template_id = self._get_selected_template_id()
        if template_id:
            from core.template_manager import get_template_manager
            tm = get_template_manager()
            tpl = tm.get_template(template_id)
            template_name = tpl.name if tpl else "提取字段"
            self.result_table.setHorizontalHeaderLabels(["文件名", "识别内容", template_name])
            self.result_table.setColumnHidden(2, False)
        else:
            self.result_table.setHorizontalHeaderLabels(["文件名", "识别内容", "提取字段"])
            self.result_table.setColumnHidden(2, True)
        
        # 显示进度 - 使用信号机制更新 StateToolTip
        self._update_state_tooltip("正在批量识别", f"已处理 0/{self.batch_total}")
        
        self.btn_recognize.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.btn_select.setEnabled(False)
        self.btn_batch.setEnabled(False)
        self.file_list_widget.setEnabled(False)
        
        # 使用异步工作线程执行批量 OCR
        # 使用基于 CoreAPI 的批量工作线程
        self.batch_worker = self._get_api().create_api_based_batch_worker(
            file_paths=self.batch_file_paths
        )
        
        # 连接信号
        def on_batch_finished(result_data):
            # 注意：由于使用 Qt.QueuedConnection，回调在主线程执行
            # 不需要使用 threading.Lock，直接检查状态即可
            if getattr(self, '_batch_cancel_pending', False):
                # 在中断过程中，忽略 finished 信号以避免UI更新冲突
                logger.info("[OCRPage] 批量识别已中断，忽略 finished 信号")
                return
            # result_data 是批量结果列表，需要逐个处理
            self.onBatchComplete(result_data)
        
        def on_batch_error(error_msg):
            # 注意：由于使用 Qt.QueuedConnection，回调在主线程执行
            # 不需要使用 threading.Lock，直接检查状态即可
            if getattr(self, '_batch_cancel_pending', False):
                # 在中断过程中，忽略错误信号
                logger.info(f"[OCRPage] 批量识别已中断，忽略 error 信号: {error_msg}")
                return
            # 不在中断过程中，正常处理错误
            self._on_batch_error(error_msg)
        
        def on_batch_cancelled():
            logger.info("[OCRPage] BatchWorker cancelled 信号已接收")
            # Umi-OCR风格：执行资源清理和状态恢复
            # 使用 QTimer.singleShot 确保在主线程中执行
            QTimer.singleShot(0, self._do_restore_batch_ui)
        
        self.batch_worker.progress.connect(self.onBatchProgress, Qt.QueuedConnection)
        self.batch_worker.finished.connect(on_batch_finished, Qt.QueuedConnection)
        self.batch_worker.error.connect(on_batch_error, Qt.QueuedConnection)
        self.batch_worker.cancelled.connect(on_batch_cancelled, Qt.QueuedConnection)
        
        # 启动线程
        self.batch_worker.start()
    
    def _on_batch_error(self, error_msg: str):
        """批量识别错误回调"""
        # 使用 QTimer.singleShot 确保所有操作在主线程安全执行
        def update_ui():
            try:
                # 安全隐藏 StateToolTip
                self._hide_state_tooltip()
                
                # 恢复按钮状态
                if hasattr(self, 'btn_recognize'):
                    try:
                        self.btn_recognize.setEnabled(True)
                    except:
                        pass
                if hasattr(self, 'btn_select'):
                    try:
                        self.btn_select.setEnabled(True)
                    except:
                        pass
                if hasattr(self, 'btn_batch'):
                    try:
                        self.btn_batch.setEnabled(True)
                    except:
                        pass
                if hasattr(self, 'file_list_widget'):
                    try:
                        self.file_list_widget.setEnabled(True)
                    except:
                        pass
                
                # 移除 InfoBar 创建，避免跨线程父对象设置
                # InfoBar.error(
                #     title="批量识别错误",
                #     content=error_msg,
                #     orient=Qt.Horizontal,
                #     isClosable=True,
                #     position=InfoBarPosition.TOP,
                #     duration=5000,
                #     parent=self
                # )
                
            except Exception as e:
                logger.error(f"[OCRPage] _on_batch_error 错误: {e}")
        
        QTimer.singleShot(0, update_ui)
    
    def onBatchProgress(self, progress_data: dict):
        """批量识别进度更新"""
        # 在函数最开始就检查中断状态，这是最重要的保护
        if getattr(self, '_batch_cancel_pending', False):
            logger.info("[OCRPage] 中断过程中，忽略进度更新")
            return  # 如果正在取消，则不执行任何UI更新
        
        # 使用 QTimer.singleShot 确保所有操作在主线程安全执行
        def update_ui():
            try:
                # 在函数开始时再次检查状态
                if getattr(self, '_batch_cancel_pending', False):
                    logger.info("[OCRPage] 中断过程中，忽略进度更新（内部检查）")
                    return  # 如果正在取消，则不执行任何UI更新
                
                # 检查工作线程是否仍然存在，如果不存在则不执行UI更新
                if not hasattr(self, 'batch_worker') or self.batch_worker is None:
                    logger.info("[OCRPage] 批量工作线程不存在，忽略进度更新")
                    return  # 如果工作线程已清理，则不执行UI更新
                
                current = progress_data.get("current", 0)
                total = progress_data.get("total", 0)
                filename = progress_data.get("filename", "")
                
                # 更新进度显示 - 通过信号槽机制安全更新 state_tooltip
                # 在每次操作前都检查状态
                if not getattr(self, '_batch_cancel_pending', False):
                    # 使用信号槽机制更新 StateToolTip
                    self._update_state_tooltip("正在批量识别", f"已处理 {current}/{total}")
                
                # 更新状态栏 - 在每次操作前都检查状态
                if not getattr(self, '_batch_cancel_pending', False):
                    status_text = f"正在识别: {filename} ({current}/{total})"
                    if hasattr(self, 'status_label') and self.status_label:
                        try:
                            self.status_label.setText(status_text)
                        except Exception as e:
                            logger.warning(f"[OCRPage] 更新 status_label 时出错: {e}")
                
                # 高亮当前项 - 在每次操作前都检查状态
                if (filename and hasattr(self, 'batch_file_paths') and
                    not getattr(self, '_batch_cancel_pending', False)):
                    for i, file_path in enumerate(self.batch_file_paths):
                        if os.path.basename(file_path) == filename:
                            if (hasattr(self, 'file_list_widget') and 
                                self.file_list_widget and
                                not getattr(self, '_batch_cancel_pending', False)):
                                try:
                                    self.file_list_widget.setCurrentRow(i)
                                except Exception as e:
                                    logger.warning(f"[OCRPage] 更新 file_list_widget 时出错: {e}")
                            break
                
                # 检查是否单个文件已完成识别，如果是则实时更新表格
                # 但在中断过程中不执行任何更新
                if (progress_data.get("completed", False) and 
                    "result" in progress_data and
                    not getattr(self, '_batch_cancel_pending', False)):
                    
                    file_path = progress_data.get("file_path", "")
                    result = progress_data.get("result", {})
                    file_name = progress_data.get("filename", os.path.basename(file_path))

                    # 再次检查中断状态，确保在更新前状态未改变
                    if getattr(self, '_batch_cancel_pending', False):
                        logger.info(f"[OCRPage] 在更新表格前检测到中断状态，跳过更新: {file_name}")
                        return  # 如果在中断过程中，则不执行任何更新

                    # ── 识别后排重 ──
                    dedup = self._get_deduplicator()
                    is_duplicate = False

                    # 检查开关状态
                    if self._get_config().get_text_dedup_enabled():
                        # 提取识别文本
                        if result and isinstance(result, dict):
                            texts = result.get('texts', [])
                            if texts:
                                full_text = '\n'.join([t.get('text', '') for t in texts if isinstance(t, dict)])

                                # 检查文本是否重复
                                if dedup.check_text_duplicate(full_text):
                                    is_duplicate = True
                                    logger.info(f"[OCRPage] 识别内容重复，已跳过: {file_name}")
                                    # 仍然添加到结果表格，但标记为重复
                                    self._add_result_to_table(file_name, result, is_duplicate=True)
                                    # 显示去重提示（限流）
                                    if not getattr(self, '_last_dedup_info_time', None) or \
                                       (datetime.now() - self._last_dedup_info_time).total_seconds() > 2:
                                        self._last_dedup_info_time = datetime.now()
                                        InfoBar.info(
                                            title="内容去重",
                                            content="发现重复内容，已自动跳过",
                                            position=InfoBarPosition.TOP,
                                            parent=self,
                                            duration=2000
                                        )
                                else:
                                    # 文本不重复，检查表格内容
                                    table_result = dedup.check_table_from_text(full_text)
                                    if table_result[0]:  # 表格重复
                                        is_duplicate = True
                                        logger.info(f"[OCRPage] 表格内容重复，已跳过: {file_name}")

                    # 初始化批量结果存储（如果尚未初始化）
                    if not hasattr(self, 'batch_results'):
                        self.batch_results = []

                    # 添加到批量结果列表（无论是否重复）
                    result_item = {
                        'file_path': file_path,
                        'file_name': file_name,
                        'result': result,
                        'is_duplicate': is_duplicate  # 标记是否重复
                    }
                    self.batch_results.append(result_item)

                    # 只有非重复结果才添加到历史记录
                    if not is_duplicate:
                        # 添加到历史记录 - 使用 _get_api() 获取 result_manager
                        self._get_api().result_manager.add_result(file_path, result)

                    # 添加到结果表格
                    self._add_result_to_table(file_name, result, is_duplicate=is_duplicate)
                    
            except Exception as e:
                logger.error(f"[OCRPage] onBatchProgress 错误: {e}")
        
        QTimer.singleShot(0, update_ui)
    
    def onBatchItemFinished(self, result_data: dict):
        """批量中单个图片识别完成"""
        # 使用 QTimer.singleShot 确保所有操作在主线程安全执行
        def update_ui():
            # 检查是否正在取消批量识别，如果是则不再处理完成事件
            if getattr(self, '_batch_cancel_pending', False):
                return  # 如果正在取消，则不执行任何处理
            
            # 检查工作线程是否仍然存在，如果不存在则不执行处理
            if not hasattr(self, 'batch_worker') or self.batch_worker is None:
                return  # 如果工作线程已清理，则不执行处理
            
            try:
                # 单个文件完成
                file_path = result_data.get("file_path", "")
                result = result_data.get("result", {})
                file_name = os.path.basename(file_path)
                
                result_item = {
                    'file_path': file_path,
                    'file_name': file_name,
                    'result': result
                }
                if not hasattr(self, 'batch_results'):
                    self.batch_results = []
                self.batch_results.append(result_item)
                
                # 添加到历史记录 - 使用 _get_api() 获取 result_manager
                self._get_api().result_manager.add_result(file_path, result)
                
                # 添加到结果表格
                self._add_result_to_table(file_name, result)
            except Exception as e:
                logger.error(f"[OCRPage] onBatchItemFinished 错误: {e}")
        
    
    def _batch_process_next(self):
        """已废弃 - 使用 BatchOcrWorker 替代"""
        pass
    
    def _do_batch_process(self):
        """已废弃 - 使用 BatchOcrWorker 替代"""
        pass
    
    def _on_batch_item_finished(self, result):
        """已废弃 - 使用 onBatchItemFinished 替代"""
        pass
    
    def _on_batch_item_error(self, error_msg):
        """已废弃 - 使用 onBatchError 替代"""
        pass
    
    def onBatchComplete(self, batch_results: list):
        """批量识别完成 - 处理最终状态"""
        # 使用 QTimer.singleShot 确保所有操作在主线程安全执行
        def update_ui():
            logger.info(f"[OCRPage] onBatchComplete 被调用，结果数量: {len(batch_results) if isinstance(batch_results, list) else 'Unknown'}")
            
            # 检查是否正在取消批量识别，如果是则不再处理完成事件
            if getattr(self, '_batch_cancel_pending', False):
                logger.info("[OCRPage] 批量识别正在取消，跳过 onBatchComplete")
                return  # 如果正在取消，则不执行任何处理
            
            # 检查工作线程是否仍然存在，如果不存在则不执行处理
            if not hasattr(self, 'batch_worker') or self.batch_worker is None:
                logger.info("[OCRPage] 批量工作线程不存在，跳过 onBatchComplete")
                return  # 如果工作线程已清理，则不执行处理
            
            # 确保结果表格存在
            if not hasattr(self, 'result_table') or self.result_table is None:
                logger.error("[OCRPage] result_table 不存在")
                return
            
            try:
                # 确保 batch_results 是列表
                if not isinstance(batch_results, list):
                    logger.warning(f"[OCRPage] 批量结果不是列表格式: {type(batch_results)}")
                    return
                
                # 初始化批量结果存储
                if not hasattr(self, 'batch_results'):
                    self.batch_results = []
                    logger.info("[OCRPage] 初始化 batch_results 列表")
                
                logger.info(f"[OCRPage] 批量识别完成，总共 {len(batch_results)} 个文件，结果已实时添加到表格")
                
                # 检查表格行数
                table_row_count = self.result_table.rowCount()
                logger.info(f"[OCRPage] 结果表格当前行数: {table_row_count}")
                
                # 更新批量总数（用于统计）
                self.batch_total = len(batch_results)
                
                # 调用批量完成的UI恢复逻辑
                self._on_batch_ocr_finished()
                
            except Exception as e:
                logger.error(f"[OCRPage] onBatchComplete 错误: {e}", exc_info=True)
        
        # 在主线程中执行UI更新
        QTimer.singleShot(0, update_ui)
    
    def _add_result_to_table(self, file_name: str, result: dict, is_duplicate: bool = False):
        """添加结果到表格

        Args:
            file_name: 文件名
            result: 识别结果
            is_duplicate: 是否为重复内容
        """
        logger.info(f"[OCRPage] _add_result_to_table 被调用，文件名: {file_name}, 重复: {is_duplicate}")

        # 确保表格存在
        if not hasattr(self, 'result_table') or self.result_table is None:
            logger.error("[OCRPage] _add_result_to_table: result_table 不存在")
            return

        row = self.result_table.rowCount()
        logger.info(f"[OCRPage] 准备插入表格行 {row}，文件名: {file_name}")

        self.result_table.insertRow(row)

        # 文件名列（重复时添加标记）
        display_name = f"{file_name} 🔄" if is_duplicate else file_name
        file_item = QTableWidgetItem(display_name)
        file_item.setToolTip(file_name + (" (重复内容)" if is_duplicate else ""))
        # 重复项使用灰色显示
        if is_duplicate:
            from PySide6.QtGui import QColor
            file_item.setForeground(QColor(128, 128, 128))
        self.result_table.setItem(row, 0, file_item)

        # ★★★ 识别内容列 - 优先检查 cancelled ★★★
        # PaddleOCR-json 管道模式：取消后仍会等待任务完成返回结果
        # 即使 code=100，被取消的任务也不应显示内容
        if result.get('cancelled'):
            # 任务被取消，不显示内容
            content = "识别已取消"
        elif is_duplicate:
            content = "(重复内容，已跳过)"
        elif result.get('code') == 100:
            texts = result.get('texts', [])
            content = '\n'.join(texts) if texts else "(未识别到文字)"
        else:
            content = f"识别失败: {result.get('data', '未知错误')}"

        content_item = QTableWidgetItem(content)
        content_item.setToolTip(content)
        if is_duplicate:
            from PySide6.QtGui import QColor
            content_item.setForeground(QColor(128, 128, 128))
        self.result_table.setItem(row, 1, content_item)

        # ── 提取字段列 ──
        if not self.result_table.isColumnHidden(2):
            extracted_text = ""
            if result.get('code') == 100 and not is_duplicate:
                extracted_fields = self._parse_result_by_template(result)
                if extracted_fields:
                    extracted_text = self._format_extracted_fields(extracted_fields)
                    # 将提取字段附加到 result（供复制/导出使用）
                    result['_extracted_fields'] = extracted_fields
            
            field_item = QTableWidgetItem(extracted_text)
            field_item.setToolTip(extracted_text)
            self.result_table.setItem(row, 2, field_item)

        # 行高自适应内容（支持多行文本换行显示）
        self.result_table.resizeRowToContents(row)

        logger.info(f"[OCRPage] 已添加到表格行 {row}，当前总行数: {self.result_table.rowCount()}")
    
    def _append_batch_result_text(self, result_data):
        """追加批量识别结果到文本框"""
        file_name = result_data['file_name']
        result = result_data['result']
        
        # 添加分隔符和文件名
        separator = "=" * 50
        self.result_text.append(f"\n{separator}")
        self.result_text.append(f"📄 {file_name}")
        self.result_text.append(separator)

        # ★★★ 优先检查 cancelled ★★★
        if result.get('cancelled'):
            # 任务被取消，不显示内容
            self.result_text.append("识别已取消")
        elif result.get('code') == 100:
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
    
    def _cancel_recognition(self):
        """中断识别任务（异步等待线程退出，不阻塞 UI）"""
        logger.info("[OCRPage] _cancel_recognition 被调用")
        
        # 检查是否已经有中断正在进行
        if getattr(self, '_batch_cancel_pending', False):
            logger.info("[OCRPage] 批量识别已在中断过程中")
            # 确保按钮状态正确
            self.btn_cancel.setEnabled(False)
            return
        elif getattr(self, '_cancel_pending', False):
            logger.info("[OCRPage] 单图识别已在中断过程中")
            # 确保按钮状态正确
            self.btn_cancel.setEnabled(False)
            return

        # 防止重复点击
        self.btn_cancel.setEnabled(False)

        # 直接检查 worker 是否存在，避免调用可能阻塞的 isRunning() 方法
        if self.recognize_worker:
            self._do_cancel_single_worker()
        elif self.batch_worker:
            self._do_cancel_batch_worker()
        else:
            logger.info("[OCRPage] 无活跃的识别任务，调用UI状态恢复")
            # 如果没有活跃的任务，也要确保UI状态正确恢复
            QTimer.singleShot(0, self._do_restore_batch_ui)

    def _do_cancel_single_worker(self):
        """取消单图识别，依赖 Qt 的信号异步处理"""
        worker = self.recognize_worker
        if not worker:
            logger.warning("[OCRPage] _do_cancel_single_worker: worker is None")
            return

        logger.info(f"[OCRPage] 开始取消单图识别, worker={id(worker)}")
        # 标记为取消状态
        self._cancel_pending = True

        # 监听 cancelled 信号（取消时由 worker 发送）
        def on_worker_cancelled():
            logger.info("[OCRPage] Worker cancelled 信号已接收")
            # 使用 QTimer.singleShot 确保在主线程中执行
            QTimer.singleShot(0, self._do_restore_single_ui)

        # 监听 finished 信号（正常完成时）
        def on_worker_finished(result_data=None):
            logger.info("[OCRPage] Worker finished 信号已接收")
            # 如果有取消待处理，说明是取消后的完成
            if getattr(self, '_cancel_pending', False):
                # 使用 QTimer.singleShot 确保在主线程中执行
                QTimer.singleShot(0, self._do_restore_single_ui)

        # 先连接信号，再请求中断
        try:
            worker.cancelled.disconnect()
        except RuntimeError:
            pass
        worker.cancelled.connect(on_worker_cancelled, Qt.QueuedConnection)

        try:
            worker.finished.disconnect()
        except RuntimeError:
            pass
        worker.finished.connect(on_worker_finished, Qt.QueuedConnection)

        # 请求工作线程停止（使用wait_ms=0确保非阻塞）
        worker.stop(0)

        # 立即更新 UI 状态 - 安全处理 state_tooltip 以避免 setParent 问题
        # 不在中断过程中直接操作 state_tooltip
        QTimer.singleShot(0, lambda: self.progress_bar.stop() if hasattr(self, 'progress_bar') and self.progress_bar else None)
        QTimer.singleShot(0, lambda: self.progress_bar.setVisible(False) if hasattr(self, 'progress_bar') and self.progress_bar else None)
        # 使用更安全的文本状态提示，避免使用可能引起 setParent 问题的组件
        QTimer.singleShot(0, lambda: self.status_label.setText("正在取消识别...") if hasattr(self, 'status_label') and self.status_label else None)

    def _do_cancel_batch_worker(self):
        """取消批量识别 - Umi-OCR风格的中断实现"""
        worker = self.batch_worker
        if not worker:
            # 如果没有活跃的工作线程，可能已经完成或被中断
            logger.info("[OCRPage] 无活跃的批量识别工作线程，跳过中断请求")
            # 确保UI状态正确恢复
            QTimer.singleShot(0, self._do_restore_batch_ui)
            return

        logger.info(f"[OCRPage] 开始中断批量识别, worker={id(worker)}")

        # 防止重复中断请求 - 简单的布尔赋值是原子的
        if getattr(self, '_batch_cancel_pending', False):
            logger.info("[OCRPage] 批量识别已在中断过程中，跳过重复请求")
            return
        
        # 设置中断状态标记
        self._batch_cancel_pending = True

        # 请求工作线程中断 - 让工作线程通过状态检查主动停止
        if worker:
            worker.requestInterruption()
        
        logger.info("[OCRPage] 已请求中断，工作线程将主动停止")
        
        # 使用 QTimer.singleShot 确保 UI 更新在主线程中安全执行
        def update_ui_safely():
            if hasattr(self, 'btn_cancel') and self.btn_cancel:
                try:
                    self.btn_cancel.setEnabled(False)
                except:
                    pass
            
            if hasattr(self, 'status_label') and self.status_label:
                try:
                    self.status_label.setText("正在中断批量识别...")
                except:
                    pass
        
        QTimer.singleShot(0, update_ui_safely)

        # 断开 progress, finished, error 信号连接以防止中断后仍处理信号
        # 注意：保留 cancelled 信号连接，让它能正常触发 UI 恢复
        try:
            if hasattr(self, 'batch_worker') and self.batch_worker:
                try:
                    self.batch_worker.progress.disconnect()
                except TypeError:
                    pass
                try:
                    self.batch_worker.finished.disconnect()
                except TypeError:
                    pass
                try:
                    self.batch_worker.error.disconnect()
                except TypeError:
                    pass
                # 不再断开 cancelled 信号，允许它正常触发 UI 恢复
        except Exception as e:
            logger.warning(f"[OCRPage] 断开信号连接时出错: {e}")

        # 断开 update_tooltip_signal 连接，防止积压的更新信号被处理
        # 注意：cancelled 信号会重新连接它
        signal = getattr(self, 'update_tooltip_signal', None)
        if signal is not None:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message=".*disconnect.*", category=RuntimeWarning)
                try:
                    signal.disconnect()
                except (TypeError, RuntimeError, AttributeError):
                    pass
        
        # 注意：不要在主线程中等待工作线程结束（worker.stop(0) 不等待）
        # 工作线程会在检查 isInterruptionRequested() 后自行退出
        # cancelled 信号会触发 UI 恢复，避免阻塞主线程导致界面卡死
        
        # 在中断后，确保不再处理任何积压的信号
        # 设置一个标志，让 onBatchProgress 等方法知道中断已经开始
        # 重要：即使中断请求已发送，也要确保工作线程正确完成清理
        # 避免因缓存快速返回导致的信号竞争问题

    def _do_restore_single_ui(self):
        """恢复单图识别 UI 状态（在主线程安全执行）"""
        # 检查对象是否已经被销毁
        try:
            if self.isDestroyed():
                logger.warning("[OCRPage] _do_restore_single_ui: 页面对象已被销毁，跳过UI更新")
                return
        except RuntimeError:
            logger.warning("[OCRPage] _do_restore_single_ui: 页面对象已被销毁，跳过UI更新")
            return
        except Exception:
            pass
            
        if getattr(self, '_cancel_pending', False):
            self._cancel_pending = False
            # 直接在主线程中执行，因为此方法通过 QTimer.singleShot 调用
            try:
                if hasattr(self, 'btn_recognize'):
                    try:
                        self.btn_recognize.setEnabled(True)
                    except:
                        pass  # 如果更新失败，忽略错误
                if hasattr(self, 'btn_cancel'):
                    try:
                        self.btn_cancel.setEnabled(False)
                    except:
                        pass  # 如果更新失败，忽略错误
                if hasattr(self, '_original_button_text') and hasattr(self, 'btn_recognize'):
                    try:
                        self.btn_recognize.setText(self._original_button_text)
                    except:
                        pass  # 如果更新失败，忽略错误
                if hasattr(self, 'status_label'):
                    try:
                        self.status_label.setText("Recognition cancelled")
                    except:
                        pass  # 如果更新失败，忽略错误
            except Exception as e:
                logger.error(f"[OCRPage] _do_restore_single_ui 错误: {e}")
            # 移除 InfoBar 创建，避免跨线程父对象设置
            # 避免在此处断开信号连接以防止并发问题，只需清理引用
            if hasattr(self, 'recognize_worker'):
                self.recognize_worker = None
            # 安全隐藏 state_tooltip
            self._hide_state_tooltip()

    def _do_restore_batch_ui(self):
        """恢复批量识别 UI 状态（Umi-OCR风格的资源清理）"""
        try:
            # 检查对象是否已经被销毁
            try:
                if self.isDestroyed():
                    logger.warning("[OCRPage] _do_restore_batch_ui: 页面对象已被销毁，跳过UI更新")
                    return
            except RuntimeError:
                logger.warning("[OCRPage] _do_restore_batch_ui: 页面对象已被销毁，跳过UI更新")
                return
            except Exception:
                pass
            
            # 使用原子操作检查并重置中断状态
            was_pending = getattr(self, '_batch_cancel_pending', False)
            self._batch_cancel_pending = False
            
            # 清理工作线程引用
            if hasattr(self, 'batch_worker'):
                self.batch_worker = None
            
            # 延迟到下一个事件循环执行 UI 操作，避免在当前锁外调用
            def do_ui_restore():
                # 检查状态
                if getattr(self, '_batch_cancel_pending', False):
                    return

                try:
                    # 恢复按钮状态
                    self._restore_batch_ui_after_cancel()
                except:
                    pass

                # 安全清理进度 InfoBar
                self._hide_state_tooltip()

                # 更新状态栏
                if hasattr(self, 'status_label') and self.status_label:
                    try:
                        self.status_label.setText("批量识别已中断")
                    except:
                        pass

                # 重新连接 update_tooltip_signal（中断后必须重新连接）
                # 使用 getattr 安全地获取信号，避免对象状态异常
                signal = getattr(self, 'update_tooltip_signal', None)
                if signal is not None:
                    with warnings.catch_warnings():
                        warnings.filterwarnings("ignore", message=".*disconnect.*", category=RuntimeWarning)
                        try:
                            signal.disconnect()
                        except (TypeError, RuntimeError, AttributeError):
                            pass  # 已断开或无法断开
                    try:
                        signal.connect(self.update_tooltip_slot)
                    except (TypeError, RuntimeError, AttributeError):
                        logger.warning("[OCRPage] 无法重新连接 update_tooltip_signal")

                # 显示中断通知 - 使用 StateToolTip（is_done=True 会自动1秒后淡出）
                if was_pending:
                    self._show_state_tooltip("识别中断", "批量识别已被用户中断", is_done=True)

            QTimer.singleShot(0, do_ui_restore)
                    
        except Exception as e:
            logger.error(f"[OCRPage] _do_restore_batch_ui 错误: {e}")
            # 即使出现异常，也要确保基本UI状态恢复
            QTimer.singleShot(0, self._ensure_ui_state_restored)
    
    def _ensure_ui_state_restored(self):
        """确保UI状态被恢复的后备方法"""
        try:
            # 确保按钮状态正确恢复
            if hasattr(self, 'btn_recognize') and self.btn_recognize:
                try:
                    self.btn_recognize.setEnabled(True)
                except:
                    pass
            if hasattr(self, 'btn_cancel') and self.btn_cancel:
                try:
                    self.btn_cancel.setEnabled(False)
                except:
                    pass
            if hasattr(self, 'btn_select') and self.btn_select:
                try:
                    self.btn_select.setEnabled(True)
                except:
                    pass
            if hasattr(self, 'btn_batch') and self.btn_batch:
                try:
                    self.btn_batch.setEnabled(True)
                except:
                    pass
            if hasattr(self, 'file_list_widget') and self.file_list_widget:
                try:
                    self.file_list_widget.setEnabled(True)
                except:
                    pass
            
            # 更新状态栏
            if hasattr(self, 'status_label') and self.status_label:
                try:
                    self.status_label.setText("批量识别已中断或完成")
                except:
                    pass
        except Exception as e:
            logger.error(f"[OCRPage] _ensure_ui_state_restored 错误: {e}")

    def _on_batch_cancelled(self):
        """BatchOcrWorker 发出 cancelled 信号时的回调（已废弃，由 _do_cancel_batch_worker 中的 on_cancelled 处理）"""
        logger.info("[OCRPage] _on_batch_cancelled 被调用（废弃函数）")
        pass

    def _restore_batch_ui_after_cancel(self):
        """恢复批量识别被取消后的 UI 按钮状态"""
        # 直接在主线程中执行，因为此方法只在 _do_restore_batch_ui 中被调用，而 _do_restore_batch_ui 已经在主线程中执行
        self.btn_recognize.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.btn_select.setEnabled(True)
        self.btn_batch.setEnabled(True)
        self.file_list_widget.setEnabled(True)
    
    def _on_batch_ocr_finished(self):
        """批量识别全部完成"""
        # 使用 QTimer.singleShot 确保所有操作在主线程安全执行
        def update_ui():
            # 检查是否正在取消批量识别，如果是则不再执行完成处理
            if getattr(self, '_batch_cancel_pending', False):
                return  # 如果正在取消，则不执行完成处理
            
            try:
                # 恢复按钮状态
                if hasattr(self, 'btn_recognize'):
                    try:
                        self.btn_recognize.setEnabled(True)
                    except:
                        pass
                if hasattr(self, 'btn_cancel'):
                    try:
                        self.btn_cancel.setEnabled(False)
                    except:
                        pass
                if hasattr(self, 'btn_select'):
                    try:
                        self.btn_select.setEnabled(True)
                    except:
                        pass
                if hasattr(self, 'btn_batch'):
                    try:
                        self.btn_batch.setEnabled(True)
                    except:
                        pass
                if hasattr(self, 'file_list_widget'):
                    try:
                        self.file_list_widget.setEnabled(True)
                    except:
                        pass
                
                # 统计成功/失败/跳过数量
                if hasattr(self, 'batch_results') and hasattr(self, 'batch_total'):
                    success_count = sum(1 for r in self.batch_results if r.get('result', {}).get('code') == 100)
                    fail_count = sum(1 for r in self.batch_results if r.get('result', {}).get('code') != 100 and r.get('result', {}).get('code') is not None)
                    skip_count = self.batch_total - success_count - fail_count
                    
                    # 更新右下角状态栏 - 显示最终结果
                    if skip_count > 0:
                        status_text = f"批量识别完成: {success_count} 成功, {fail_count} 失败, {skip_count} 跳过 (共 {self.batch_total} 个)"
                    else:
                        status_text = f"批量识别完成: {success_count} 成功, {fail_count} 失败 (共 {self.batch_total} 个)"
                    
                    # 安全更新状态标签
                    if hasattr(self, 'status_label') and self.status_label:
                        try:
                            self.status_label.setText(status_text)
                        except:
                            pass
                
                # 启用复制和导出
                if hasattr(self, 'btn_copy'):
                    try:
                        self.btn_copy.setEnabled(True)
                    except:
                        pass
                if hasattr(self, 'btn_export'):
                    try:
                        self.btn_export.setEnabled(True)
                    except:
                        pass
                
                # 检查是否启用自动复制
                if self._get_ui_config().get_auto_copy() and hasattr(self, 'batch_results') and self.batch_results:
                    # 将所有成功识别的结果合并并复制到剪贴板
                    all_texts = []
                    for item in self.batch_results:
                        result = item.get('result', {})
                        if result.get('code') == 100:
                            texts = result.get('texts', [])
                            if texts:
                                all_texts.extend(texts)
                    
                    if all_texts:
                        combined_text = '\n'.join(all_texts)
                        # 调用界面层复制到剪贴板
                        from interfaces.fluent.ui_utils import copy_to_clipboard
                        if copy_to_clipboard(combined_text):
                            # 可选：显示复制成功的提示
                            pass  # 自动复制成功，无需额外提示
                
                # 清理工作线程对象
                # 避免在此处断开信号连接以防止并发问题，只需清理引用
                if hasattr(self, 'batch_worker'):
                    self.batch_worker = None

                # 隐藏进度 InfoBar
                self._hide_state_tooltip()

                # 使用定时器延时显示 StateToolTip，确保旧的提示完全消失
                def show_completion_info():
                    # 再次检查中断状态，确保在显示 StateToolTip 前没有中断
                    if getattr(self, '_batch_cancel_pending', False):
                        logger.info("[OCRPage] 中断过程中，跳过 StateToolTip 显示")
                        return
                    
                    if hasattr(self, 'batch_total') and hasattr(self, 'batch_results'):
                        success_count = sum(1 for r in self.batch_results if r.get('result', {}).get('code') == 100)
                        fail_count = sum(1 for r in self.batch_results if r.get('result', {}).get('code') != 100 and r.get('result', {}).get('code') is not None)
                        
                        if self.batch_total > 0:
                            if success_count == self.batch_total:
                                # 全部成功
                                success_msg = f"批量识别完成！全部 {success_count} 个文件识别成功"
                            elif fail_count == 0:
                                # 没有失败，可能有跳过的
                                skip_count = self.batch_total - success_count
                                success_msg = f"批量识别完成！{success_count} 个成功，{skip_count} 个跳过"
                            else:
                                # 有成功有失败
                                success_msg = f"批量识别完成！{success_count} 个成功，{fail_count} 个失败"
                            
                            # 使用 _show_state_tooltip 显示完成提示（is_done=True 会自动1秒后淡出）
                            self._show_state_tooltip("批量识别完成", success_msg, is_done=True)
                
                # 再次确认在显示 StateToolTip 前没有中断
                if not getattr(self, '_batch_cancel_pending', False):
                    # 延时500毫秒显示 StateToolTip，确保旧的提示完全消失
                    QTimer.singleShot(500, show_completion_info)
                
                # 发送批量识别完成信号，刷新历史记录
                self.batch_ocr_completed.emit()
            except Exception as e:
                logger.error(f"[OCRPage] _on_batch_ocr_finished 错误: {e}")
        
        QTimer.singleShot(0, update_ui)
    
    def onOCRFinished(self, result):
        """OCR识别完成（单图模式）"""
        # 使用 QTimer.singleShot 确保所有操作在主线程安全执行
        def update_ui():
            try:
                # 安全地隐藏 state_tooltip
                self._hide_state_tooltip()
                
                self.progress_bar.stop()
                self.progress_bar.setVisible(False)
                
                # 恢复按钮状态和文字
                self.btn_recognize.setEnabled(True)
                self.btn_cancel.setEnabled(False)
                if hasattr(self, '_original_button_text'):
                    self.btn_recognize.setText(self._original_button_text)
                
                # 单图模式切换到文本框显示
                self.result_table.setVisible(False)
                self.result_text.setVisible(True)
                
                self.ocr_result = result
                
                if result.get('code') == 100:
                    # 成功
                    texts = result.get('texts', [])
                    raw_text = '\n'.join(texts)
                    self.result_text.setPlainText(raw_text)
                    
                    # ── 模板解析：按选中的模板提取结构化字段 ──
                    extracted_fields = self._parse_result_by_template(result)
                    if extracted_fields:
                        formatted = self._format_extracted_fields(extracted_fields)
                        if formatted:
                            # 在原始文本下方追加结构化字段区域
                            self.result_text.append(
                                '\n\n<span style="color:#0078d4; font-weight:bold;">'
                                '─ ─ ─ 模板提取结果 ─ ─ ─'
                                '</span>'
                            )
                            self.result_text.append(
                                '<span style="color:#555;">' + formatted.replace('\n', '<br>') + '</span>'
                            )
                            self.status_label.setText(
                                f"识别成功，共 {len(texts)} 行文字，提取 {sum(1 for v in extracted_fields.values() if v)} 个字段"
                            )
                        # 将解析结果附加到 ocr_result，供复制/导出使用
                        result['_extracted_fields'] = extracted_fields
                    else:
                        self.status_label.setText(f"识别成功，共 {len(texts)} 行文字")
                    
                    # 添加到历史记录 - 使用 _get_api() 获取 result_manager
                    self._get_api().result_manager.add_result(
                        self.current_image_path, 
                        result
                    )
                    
                    self.status_label.setText(f"识别成功，共 {len(texts)} 行文字")
                    self.btn_copy.setEnabled(True)
                    self.btn_export.setEnabled(True)
                    
                    # 检查是否启用自动复制
                    if self._get_ui_config().get_auto_copy():
                        text = '\n'.join(texts)
                        if text:
                            # 调用界面层复制到剪贴板
                            from interfaces.fluent.ui_utils import copy_to_clipboard
                            if copy_to_clipboard(text):
                                # 可选：显示复制成功的提示
                                # InfoBar.success(
                                #     title="已自动复制",
                                #     content="识别结果已自动复制到剪贴板",
                                #     orient=Qt.Horizontal,
                                #     isClosable=True,
                                #     position=InfoBarPosition.TOP,
                                #     duration=2000,
                                #     parent=self
                                # )
                                pass  # 自动复制成功，无需额外提示
                    
                    # 发送完成信号
                    self.ocr_completed.emit(self.current_image_path)
                else:
                    # 失败
                    error_msg = result.get('data', '未知错误')
                    self.result_text.setPlainText(f"识别失败: {error_msg}")
                    self.status_label.setText(f"识别失败: {error_msg}")
            except Exception as e:
                logger.error(f"[OCRPage] onOCRFinished 错误: {e}")
        
        QTimer.singleShot(0, update_ui)
        
        # 清理工作线程对象
        self.recognize_worker = None
    
    def onOCRError(self, error_msg):
        """OCR识别错误"""
        # 使用 QTimer.singleShot 确保所有操作在主线程安全执行
        def update_ui():
            try:
                # 安全地隐藏 state_tooltip
                self._hide_state_tooltip()
                
                self.progress_bar.stop()
                self.progress_bar.setVisible(False)
                
                # 恢复按钮状态和文字
                self.btn_recognize.setEnabled(True)
                self.btn_cancel.setEnabled(False)
                if hasattr(self, '_original_button_text'):
                    self.btn_recognize.setText(self._original_button_text)
                
                self.result_text.setPlainText(f"识别出错: {error_msg}")
                self.status_label.setText(f"识别出错: {error_msg}")
                
                # 移除 InfoBar 创建，避免跨线程父对象设置
                # InfoBar.error(
                #     title="识别出错",
                #     content=error_msg,
                #     orient=Qt.Horizontal,
                #     isClosable=True,
                #     position=InfoBarPosition.TOP,
                #     duration=3000,
                #     parent=self
                # )
                
                self.recognize_worker = None
            except Exception as e:
                logger.error(f"[OCRPage] onOCRError 错误: {e}")
        
        QTimer.singleShot(0, update_ui)
    
    def copyResult(self):
        """复制结果"""
        from interfaces.fluent.ui_utils import copy_to_clipboard

        if self.is_batch_mode and hasattr(self, 'batch_results') and self.batch_results:
            # 批量模式：拼接所有成功识别的文本
            all_texts = []
            for item in self.batch_results:
                result = item.get('result', {})
                if result.get('code') == 100:
                    texts = result.get('texts', [])
                    if texts:
                        # 每个文件的识别内容用空行分隔，前置文件名注释
                        file_name = item.get('file_name', '')
                        if file_name:
                            all_texts.append(f"[{file_name}]")
                        all_texts.extend(texts)
                        # 附加提取字段
                        extracted_fields = result.get('_extracted_fields', {})
                        if extracted_fields:
                            formatted = self._format_extracted_fields(extracted_fields)
                            if formatted:
                                all_texts.append('  [模板提取]')
                                for line in formatted.split('\n'):
                                    all_texts.append(f'  {line}')
                        all_texts.append('')  # 文件间空行

            # 去掉末尾多余的空行
            while all_texts and all_texts[-1] == '':
                all_texts.pop()

            text = '\n'.join(all_texts)
            if text:
                if copy_to_clipboard(text):
                    success_count = sum(
                        1 for item in self.batch_results
                        if item.get('result', {}).get('code') == 100
                    )
                    self._info_bar_success(
                        "已复制",
                        f"已将 {success_count} 个文件的识别结果复制到剪贴板",
                        duration=2000
                    )
            else:
                self._info_bar_warning("无内容", "没有可复制的识别结果", duration=2000)
        else:
            # 单图模式：优先使用原始 OCR 结果（含提取字段）
            if self.ocr_result and self.ocr_result.get('code') == 100:
                texts = self.ocr_result.get('texts', [])
                raw_text = '\n'.join(texts)
                extracted_fields = self.ocr_result.get('_extracted_fields', {})
                
                if extracted_fields:
                    formatted = self._format_extracted_fields(extracted_fields)
                    if formatted:
                        full_text = f"{raw_text}\n\n── 模板提取结果 ──\n{formatted}"
                    else:
                        full_text = raw_text
                else:
                    full_text = raw_text
                
                if full_text and copy_to_clipboard(full_text):
                    self._info_bar_success("已复制", "识别结果已复制到剪贴板", duration=2000)
                elif raw_text and copy_to_clipboard(raw_text):
                    self._info_bar_success("已复制", "识别结果已复制到剪贴板", duration=2000)
            else:
                text = self.result_text.toPlainText()
                if text and copy_to_clipboard(text):
                    self._info_bar_success("已复制", "识别结果已复制到剪贴板", duration=2000)
    
    def exportResult(self, format_type):
        """导出结果 - 异步执行"""
        # 局部导入错误处理模块
        from core.error_handler import error_handling, ErrorType, ExportError
        
        # 应用错误处理装饰器
        @error_handling(ErrorType.EXPORT, "导出结果失败")
        def decorated_method():
            # 检查是否有识别结果
            if self.is_batch_mode and hasattr(self, 'batch_results') and self.batch_results:
                # 批量模式导出
                self._export_batch_results(format_type)
            elif self.ocr_result:
                # 单图模式导出
                self._export_single_result(format_type)
            else:
                # 无结果可导出
                raise ExportError("没有识别结果可导出")
        
        return decorated_method()
    
    def _export_single_result(self, format_type):
        """导出单个识别结果"""
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
            # 显示导出中提示
            self._info_bar_info("导出中", f"正在导出为 {format_type} 格式...", duration=-1, isClosable=False)
            
            # 使用异步工作线程执行导出
            from core.async_worker import ExportWorker
            
            self.export_worker = ExportWorker(
                # 使用CoreAPI进行导出，不再直接使用exporter
                results=self.ocr_result,
                format_type=format_type,
                output_path=file_path,
                parent=self
            )
            
            # 连接信号
            self.export_worker.finished.connect(lambda r: self._on_export_finished(r), Qt.QueuedConnection)
            self.export_worker.error.connect(self._on_export_error, Qt.QueuedConnection)
            
            # 启动线程
            self.export_worker.start()
    
    def _export_batch_results(self, format_type):
        """导出批量识别结果"""
        # 获取文件夹名作为基础名称
        if self.batch_file_paths:
            folder = os.path.dirname(self.batch_file_paths[0])
            base_name = os.path.basename(folder) or "批量识别"
        else:
            base_name = "批量识别"
        
        # 打开保存对话框
        filters = {
            "TXT": "文本文件 (*.txt)",
            "JSON": "JSON文件 (*.json)",
            "Excel": "Excel文件 (*.xlsx)"
        }
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"导出批量结果为 {format_type}",
            f"{base_name}_批量识别结果.{format_type.lower()}",
            filters.get(format_type, "")
        )
        
        if file_path:
            # 显示导出中提示
            self._info_bar_info("导出中", f"正在导出批量结果为 {format_type} 格式...", duration=-1, isClosable=False)
            
            # 使用CoreAPI进行批量导出
            result = self._get_api().export_batch_results(self.batch_results, format_type, file_path)
            if result.success:
                # 导出成功
                self._info_bar_success("导出成功", f"已导出到: {os.path.basename(file_path)}")
            else:
                # 导出失败
                error_msg = result.error.message if result.error else "导出过程中发生未知错误"
                self._info_bar_error("导出失败", error_msg)
            
            # 关闭导出中提示
            self._close_info_bar_by_title("导出中")
    
    def _on_export_finished(self, result: dict):
        """导出完成回调"""
        # 关闭导出中提示
        self._close_info_bar_by_title("导出中")
        
        success = result.get("success", False)
        output_path = result.get("output_path", "")
        
        if success:
            self._info_bar_success("导出成功", f"已保存到: {output_path}", duration=5000)
        else:
            self._info_bar_error("导出失败", "无法导出文件")
    
    def _on_export_error(self, error_msg: str):
        """导出错误回调"""
        # 关闭导出中提示
        self._close_info_bar_by_title("导出中")
        
        self._info_bar_error("导出错误", error_msg)
    
    def screenshot(self):
        """截图识别"""
        # 局部导入错误处理模块
        from core.error_handler import error_handling, ErrorType
        
        # 应用错误处理装饰器
        @error_handling(ErrorType.SCREENSHOT, "截图失败")
        def decorated_method():
            # 先截取当前屏幕（主窗口还在，所以会包含主窗口内容）
            from core.screenshot import get_screenshot_manager
            bg_path = get_screenshot_manager().capture_full_screen(save_to_history=False)
            
            # 隐藏主窗口
            self.main_window.hide()
            
            # 延迟启动截图窗口，传入背景截图路径
            QTimer.singleShot(100, lambda: self._show_screenshot_window(bg_path))
        
        return decorated_method()

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
            from core.screenshot import get_screenshot_manager
            temp_path = get_screenshot_manager().capture_screen_region(x, y, width, height, save_to_history=False)

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