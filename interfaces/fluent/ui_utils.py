# -*- coding: utf-8 -*-
"""界面工具类 - 提供界面相关的工具函数

此文件包含界面层专用的工具函数，确保核心功能与界面显示完全分离。
"""

from qfluentwidgets import MessageBox, MessageBoxBase, MessageDialog
from PySide6.QtGui import QGuiApplication


def create_message_box(title: str, content: str, parent=None) -> MessageBox:
    """创建带有中文按钮的消息框
    
    Args:
        title: 对话框标题
        content: 对话框内容
        parent: 父窗口
    
    Returns:
        带有中文按钮的 MessageBox 实例
    """
    msg = MessageBox(title, content, parent)
    msg.yesButton.setText("确定")
    msg.cancelButton.setText("取消")
    return msg


def setup_chinese_buttons(dialog: MessageBoxBase) -> None:
    """为 MessageBoxBase 子类设置中文按钮
    
    Args:
        dialog: MessageBoxBase 的子类实例
    """
    if hasattr(dialog, 'yesButton'):
        dialog.yesButton.setText("确定")
    if hasattr(dialog, 'cancelButton'):
        dialog.cancelButton.setText("取消")


def create_engine_config_dialog(parent=None) -> MessageDialog:
    """创建 OCR 引擎配置提示对话框
    
    Args:
        parent: 父窗口
    
    Returns:
        配置提示对话框实例
    """
    dialog = MessageDialog(
        title="OCR 引擎未配置",
        content="请先配置 OCR 引擎和模型目录路径，才能进行文字识别。\n您希望自动搜索还是手动指定？",
        parent=parent
    )
    dialog.yesButton.setText("自动搜索")
    dialog.cancelButton.setText("取消")
    return dialog


def copy_to_clipboard(text: str) -> bool:
    """
    复制文本到剪贴板（界面层功能）
    
    Args:
        text: 要复制的文本
        
    Returns:
        bool: 是否成功
    """
    try:
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(text)
        return True
    except Exception as e:
        print(f"复制到剪贴板失败: {e}")
        return False