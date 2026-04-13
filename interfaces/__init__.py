# Interfaces 模块 - 界面层
# 只负责 UI 交互，调用 core 模块实现功能

from .tkinter_ui import main as run_tkinter_ui
from .web_ui import main as run_web_ui

__all__ = ['run_tkinter_ui', 'run_web_ui']
