"""生成 icon_restore.png（还原按钮图标）"""
from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor
from PySide6.QtCore import QSize
import os

# 创建 20x20 的透明图片
pixmap = QPixmap(20, 20)
pixmap.fill(QColor(0, 0, 0, 0))  # 透明背景

painter = QPainter(pixmap)
painter.setRenderHint(QPainter.RenderHint.Antialiasing)

# 外框（大方框）
painter.setPen(QPen(QColor(248, 248, 242), 1.5))  # Dracula TEXT_PRIMARY
painter.drawRect(2, 4, 14, 12)  # 外框稍微小一点，底部留空

# 内框/填充（小方块，表示已还原状态）
painter.setPen(QPen(QColor(248, 248, 242), 1.5))
painter.drawRect(5, 1, 10, 8)  # 上方的"小窗口"表示已还原到小窗口状态

painter.end()

# 保存
output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           'images', 'icons', 'icon_restore.png')
pixmap.save(output_path)
print(f"已生成: {output_path}")
