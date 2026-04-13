# -*- coding: utf-8 -*-
"""截图窗口组件 - 交互式框选截图（界面层）"""

from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt, Signal, QRect, QPoint
from PySide6.QtGui import QPainter, QPen, QPixmap, QColor, QFont


class ScreenShotWindow(QWidget):
    """
    全屏截图窗口（界面层）
    负责交互式框选，将选区坐标传递给核心层处理
    """

    # 信号：截图完成时发出，携带选区坐标
    screenshot_finished = Signal(int, int, int, int)
    # 信号：取消截图时发出
    screenshot_cancelled = Signal()

    def __init__(self, bg_path=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("截图")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )

        # 全屏显示
        self.setGeometry(QApplication.primaryScreen().geometry())

        # 选区坐标
        self.start_point = QPoint()
        self.end_point = QPoint()
        self.is_selecting = False

        # 直接加载传入的背景截图
        self.background_pixmap = None
        if bg_path:
            self.background_pixmap = QPixmap(bg_path)
        
        # 立即显示窗口
        self.show()

    def paintEvent(self, event):
        """绘制截图界面 - 纯虚线框样式"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        try:
            # 如果有背景图，先绘制背景（不做任何遮罩）
            if self.background_pixmap and not self.background_pixmap.isNull():
                painter.drawPixmap(self.rect(), self.background_pixmap)
            else:
                painter.fillRect(self.rect(), QColor(0, 0, 0, 200))
                painter.setPen(QColor(255, 255, 255))
                painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "加载中...")

            # 如果正在选择或已有选区，绘制虚线框
            if self.is_selecting or (self.start_point != self.end_point):
                rect = self._get_selection_rect()
                if rect.isValid() and rect.width() > 0 and rect.height() > 0:
                    # 绘制虚线边框
                    pen = QPen(QColor(0, 120, 215), 2)
                    pen.setDashPattern([5, 5])
                    painter.setPen(pen)
                    painter.drawRect(rect)

                    # 绘制四角标记（加粗线条）
                    corner_size = 12
                    p1 = QPen(QColor(0, 120, 215), 3)
                    painter.setPen(p1)
                    # 左上角
                    painter.drawLine(rect.left(), rect.top(), rect.left() + corner_size, rect.top())
                    painter.drawLine(rect.left(), rect.top(), rect.left(), rect.top() + corner_size)
                    # 右上角
                    painter.drawLine(rect.right(), rect.top(), rect.right() - corner_size, rect.top())
                    painter.drawLine(rect.right(), rect.top(), rect.right(), rect.top() + corner_size)
                    # 左下角
                    painter.drawLine(rect.left(), rect.bottom(), rect.left() + corner_size, rect.bottom())
                    painter.drawLine(rect.left(), rect.bottom(), rect.left(), rect.bottom() - corner_size)
                    # 右下角
                    painter.drawLine(rect.right(), rect.bottom(), rect.right() - corner_size, rect.bottom())
                    painter.drawLine(rect.right(), rect.bottom(), rect.right(), rect.bottom() - corner_size)

                    # 绘制尺寸提示
                    width = rect.width()
                    height = rect.height()
                    text = f"{width} x {height}"
                    font = QFont("微软雅黑", 12)
                    painter.setFont(font)

                    text_width = painter.fontMetrics().horizontalAdvance(text) + 20
                    text_height = painter.fontMetrics().height() + 8
                    text_x = rect.center().x() - text_width // 2
                    text_y = rect.bottom() + 15

                    text_rect_x = max(5, min(text_x, self.width() - text_width - 5))
                    text_rect_y = min(text_y, self.height() - text_height - 5)

                    text_rect = QRect(text_rect_x, text_rect_y, text_width, text_height)
                    painter.fillRect(text_rect, QColor(0, 0, 0, 180))
                    painter.setPen(QColor(255, 255, 255))
                    painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, text)

                    # 绘制操作提示
                    hint_text = "拖动选择区域 | ESC 取消"
                    hint_font = QFont("微软雅黑", 10)
                    painter.setFont(hint_font)
                    hint_width = painter.fontMetrics().horizontalAdvance(hint_text) + 20
                    hint_height = painter.fontMetrics().height() + 6
                    hint_rect = QRect(
                        (self.width() - hint_width) // 2,
                        self.height() - hint_height - 10,
                        hint_width,
                        hint_height
                    )
                    painter.fillRect(hint_rect, QColor(0, 0, 0, 160))
                    painter.setPen(QColor(255, 255, 255))
                    painter.drawText(hint_rect, Qt.AlignmentFlag.AlignCenter, hint_text)
        finally:
            painter.end()

    def mousePressEvent(self, event):
        """鼠标按下"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_point = event.position().toPoint()
            self.end_point = self.start_point
            self.is_selecting = True
            self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            self.screenshot_cancelled.emit()
            self.close()

    def mouseMoveEvent(self, event):
        """鼠标移动"""
        if self.is_selecting:
            self.end_point = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        """鼠标释放"""
        if event.button() == Qt.MouseButton.LeftButton and self.is_selecting:
            self.end_point = event.position().toPoint()
            self.is_selecting = False
            self.update()

            rect = self._get_selection_rect()
            if rect.width() > 5 and rect.height() > 5:
                # 发送截图完成信号，携带选区坐标
                self.screenshot_finished.emit(
                    rect.x(), rect.y(), rect.width(), rect.height()
                )
            else:
                self.screenshot_cancelled.emit()

            self.close()

    def keyPressEvent(self, event):
        """按键事件"""
        if event.key() == Qt.Key.Key_Escape:
            self.screenshot_cancelled.emit()
            self.close()

    def _get_selection_rect(self) -> QRect:
        """获取选区矩形"""
        return QRect(
            min(self.start_point.x(), self.end_point.x()),
            min(self.start_point.y(), self.end_point.y()),
            abs(self.end_point.x() - self.start_point.x()),
            abs(self.end_point.y() - self.start_point.y())
        )
