# 截图功能模块
# 核心层截图功能，不依赖任何界面

import os
import sys
import tempfile
import ctypes
import time
import threading
import logging
from ctypes import wintypes
from typing import Optional, Tuple
from pathlib import Path

# 配置日志
logger = logging.getLogger(__name__)

# 仅在 Windows 平台导入 Windows API
if sys.platform == 'win32':
    # Windows API
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
else:
    user32 = None
    kernel32 = None
    logger.warning(f"截图功能仅支持 Windows 平台，当前平台: {sys.platform}")


def capture_screen_to_temp() -> Optional[str]:
    """
    截取全屏并保存到临时文件
    
    Returns:
        临时文件路径，失败返回 None
    """
    if sys.platform != 'win32':
        logger.error("截图功能仅支持 Windows 平台")
        return None
    
    try:
        # 优先使用 mss 库（最可靠）
        import mss
        import mss.windows
        
        with mss.mss() as sct:
            temp_path = os.path.join(tempfile.gettempdir(), 'ocr_screenshot.png')
            sct.shot(mon=-1, output=temp_path)
            logger.debug(f"截图成功 (mss): {temp_path}")
            return temp_path
            
    except ImportError:
        logger.debug("mss 库未安装，尝试备用方案")
    except Exception as e:
        logger.warning(f"mss 截图失败: {e}，尝试备用方案")
    
    # 备用方案：使用 PIL ImageGrab
    try:
        from PIL import ImageGrab
        
        img = ImageGrab.grab()
        temp_path = os.path.join(tempfile.gettempdir(), 'ocr_screenshot.png')
        img.save(temp_path, 'PNG')
        logger.debug(f"截图成功 (PIL): {temp_path}")
        return temp_path
        
    except ImportError:
        logger.debug("PIL 库未安装")
    except Exception as e:
        logger.warning(f"PIL 截图失败: {e}")
    
    logger.error("所有截图方案均失败")
    return None


def capture_screen_to_pixmap():
    """
    截取全屏并返回 QPixmap（供界面层使用）
    
    Returns:
        QPixmap: 屏幕截图，失败返回 None
    """
    if sys.platform != 'win32':
        logger.error("截图功能仅支持 Windows 平台")
        return None
    
    try:
        from PySide6.QtGui import QPixmap, QImage
        import io
        
        # 优先使用 mss 库
        try:
            import mss
            import mss.windows
            
            with mss.mss() as sct:
                temp_path = os.path.join(tempfile.gettempdir(), 'ocr_bg_temp.png')
                sct.shot(mon=-1, output=temp_path)
                pixmap = QPixmap(temp_path)
                logger.debug(f"截图成功 (mss -> QPixmap)")
                return pixmap
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"mss 截图失败: {e}")
        
        # 备用：使用 PIL ImageGrab
        try:
            from PIL import ImageGrab
            
            img = ImageGrab.grab()
            # 转换为 RGB（去掉 alpha 通道）
            if img.mode == 'RGBA':
                img = img.convert('RGB')
            # 转换为 QImage
            img_bytes = img.tobytes('raw', 'RGB')
            width, height = img.size
            qimage = QImage(img_bytes, width, height, width * 3, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qimage)
            logger.debug(f"截图成功 (PIL -> QPixmap)")
            return pixmap
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"PIL 截图失败: {e}")
        
        # 最后备用：保存到临时文件再加载
        temp_path = capture_screen_to_temp()
        if temp_path:
            return QPixmap(temp_path)
        
        return None
        
    except Exception as e:
        logger.error(f"截图失败: {e}", exc_info=True)
        return None


def capture_screen_as_bytes() -> Tuple[Optional[bytes], int, int]:
    """
    截取全屏并返回字节数据
    
    Returns:
        (bytes_data, width, height)，失败返回 (None, 0, 0)
    """
    if sys.platform != 'win32':
        logger.error("截图功能仅支持 Windows 平台")
        return None, 0, 0
    
    try:
        import win32gui
        import win32ui
        import win32con
        import win32api
        
        # 获取屏幕DC
        screen_dc = win32gui.GetDC(0)
        mem_dc = win32gui.CreateCompatibleDC(screen_dc)
        
        # 获取屏幕分辨率
        width = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
        height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
        
        # 创建位图
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(screen_dc, width, height)
        mem_dc.SelectObject(bitmap)
        
        # 截图
        mem_dc.BitBlt((0, 0), (width, height), screen_dc, (0, 0), win32con.SRCCOPY)
        
        # 转换为字节
        bmpstr = bitmap.GetBitmapBits(True)
        
        # 释放资源
        win32gui.DeleteObject(bitmap.GetHandle())
        win32gui.DeleteDC(mem_dc)
        win32gui.ReleaseDC(0, screen_dc)
        
        logger.debug(f"截图成功 (Win32 API): {width}x{height}")
        return bmpstr, width, height
        
    except ImportError:
        logger.error("需要安装 pywin32 库")
        return None, 0, 0
    except Exception as e:
        logger.error(f"截图失败: {e}", exc_info=True)
        return None, 0, 0


def capture_screen_region(x, y, width, height):
    """
    截取屏幕指定区域并保存到临时文件
    
    Args:
        x, y: 起始坐标
        width, height: 区域宽高
    
    Returns:
        str: 临时文件路径，失败返回 None
    """
    try:
        # 优先使用 mss 库
        import mss
        import mss.windows
        
        with mss.mss() as sct:
            temp_path = os.path.join(tempfile.gettempdir(), 'ocr_screenshot.png')
            # mss 使用 (left, top, right, bottom) 格式
            region = {
                'left': x,
                'top': y,
                'width': width,
                'height': height
            }
            # 截取区域并保存
            sct_img = sct.grab(region)
            mss.tools.to_png(sct_img.rgb, sct_img.size, output=temp_path)
            return temp_path
            
    except ImportError:
        pass
    
    # 备用方案：使用 PIL ImageGrab
    try:
        from PIL import ImageGrab
        
        # ImageGrab 使用 (left, top, right, bottom) 格式
        bbox = (x, y, x + width, y + height)
        img = ImageGrab.grab(bbox=bbox)
        temp_path = os.path.join(tempfile.gettempdir(), 'ocr_screenshot.png')
        img.save(temp_path, 'PNG')
        return temp_path
        
    except ImportError:
        pass
    
    try:
        from PIL import Image
        import win32gui
        import win32ui
        import win32con
        import win32api
        
        # 获取屏幕 DC
        screen_dc = win32gui.GetDC(0)
        
        # 创建兼容 DC
        mem_dc = win32gui.CreateCompatibleDC(screen_dc)
        
        # 创建位图
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(screen_dc, width, height)
        
        # 选择位图
        old_bitmap = mem_dc.SelectObject(bitmap)
        
        # 截图指定区域
        mem_dc.BitBlt((0, 0), (width, height), screen_dc, (x, y), win32con.SRCCOPY)
        
        # 获取位图信息
        bmpinfo = bitmap.GetInfo()
        bmpstr = bitmap.GetBitmapBits(True)
        
        # 转换为 PIL Image
        img = Image.frombuffer(
            'RGB', 
            (bmpinfo['bmWidth'], bmpinfo['bmHeight']), 
            bmpstr, 
            'raw', 
            'BGRX', 
            0, 
            1
        )
        
        # 保存
        temp_path = os.path.join(tempfile.gettempdir(), 'ocr_screenshot.png')
        img.save(temp_path, 'PNG')
        
        # 释放资源
        mem_dc.SelectObject(old_bitmap)
        win32gui.DeleteObject(bitmap.GetHandle())
        win32gui.DeleteDC(mem_dc)
        win32gui.ReleaseDC(0, screen_dc)
        
        return temp_path
        
    except Exception as e:
        print(f"区域截图失败: {e}")
        return None


class Screenshot:
    """屏幕截图类"""
    
    def __init__(self):
        self.hwnd = None
        self.hdwp = None
    
    def capture_full_screen(self):
        """截取全屏"""
        return capture_screen_to_temp()
    
    def capture_region(self, x, y, width, height):
        """截取指定区域"""
        return capture_screen_region(x, y, width, height)
    
    def save_to_clipboard(self, width, height, bits):
        """将截图保存到剪贴板"""
        try:
            import win32gui
            import win32ui
            import win32con
            import win32clipboard
            
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            
            # 创建位图
            screen_dc = win32gui.GetDC(0)
            mem_dc = win32gui.CreateCompatibleDC(screen_dc)
            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(screen_dc, width, height)
            mem_dc.SelectObject(bitmap)
            
            # 设置位图数据
            bitmap.SetBitmapBits(bits)
            
            # 复制到剪贴板
            win32clipboard.SetClipboardData(win32con.CF_BITMAP, bitmap.GetHandle())
            
            # 释放资源
            win32gui.ReleaseDC(0, screen_dc)
            win32gui.DeleteDC(mem_dc)
            win32clipboard.CloseClipboard()
            win32gui.DeleteObject(bitmap.GetHandle())
            
            return True
        except Exception as e:
            print(f"保存到剪贴板失败: {e}")
            return False


class HotkeyManager:
    """全局快捷键管理器"""
    
    def __init__(self):
        self.hotkeys = {}
        self.running = False
        self.thread = None
        self.callback = None
    
    def register(self, hotkey_id, modifiers, key, callback):
        """
        注册快捷键
        
        Args:
            hotkey_id: 快捷键ID
            modifiers: 修饰键 (0=无, 1=Alt, 2=Ctrl, 4=Shift, 8=Win)
            key: 虚拟键码
            callback: 回调函数
        """
        self.hotkeys[hotkey_id] = callback
        
        # 注册系统级热键
        if not user32.RegisterHotKey(None, hotkey_id, modifiers, key):
            print(f"注册热键失败: ID={hotkey_id}")
            return False
        
        return True
    
    def unregister(self, hotkey_id):
        """注销快捷键"""
        if hotkey_id in self.hotkeys:
            del self.hotkeys[hotkey_id]
            user32.UnregisterHotKey(None, hotkey_id)
    
    def unregister_all(self):
        """注销所有快捷键"""
        for hotkey_id in list(self.hotkeys.keys()):
            self.unregister(hotkey_id)
    
    def start_listening(self):
        """开始监听快捷键"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.thread.start()
    
    def stop_listening(self):
        """停止监听"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
    
    def _listen_loop(self):
        """监听循环"""
        msg = wintypes.MSG()
        
        while self.running:
            # 使用 PeekMessage 实现非阻塞检测
            if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                if msg.message == 0x0312:  # WM_HOTKEY
                    hotkey_id = msg.wParam
                    if hotkey_id in self.hotkeys:
                        try:
                            self.hotkeys[hotkey_id]()
                        except Exception as e:
                            print(f"快捷键回调执行失败: {e}")
                
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            else:
                time.sleep(0.01)


# 虚拟键码映射
VK_CODE = {
    'F1': 0x70, 'F2': 0x71, 'F3': 0x72, 'F4': 0x73, 'F5': 0x74, 'F6': 0x75,
    'F7': 0x76, 'F8': 0x77, 'F9': 0x78, 'F10': 0x79, 'F11': 0x7A, 'F12': 0x7B,
    'A': 0x41, 'B': 0x42, 'C': 0x43, 'D': 0x44, 'E': 0x45, 'F': 0x46,
    'G': 0x47, 'H': 0x48, 'I': 0x49, 'J': 0x4A, 'K': 0x4B, 'L': 0x4C,
    'M': 0x4D, 'N': 0x4E, 'O': 0x4F, 'P': 0x50, 'Q': 0x51, 'R': 0x52,
    'S': 0x53, 'T': 0x54, 'U': 0x55, 'V': 0x56, 'W': 0x57, 'X': 0x58,
    'Y': 0x59, 'Z': 0x5A,
    '0': 0x30, '1': 0x31, '2': 0x32, '3': 0x33, '4': 0x34,
    '5': 0x35, '6': 0x36, '7': 0x37, '8': 0x38, '9': 0x39,
}

# 修饰键
MOD_ALT = 1
MOD_CTRL = 2
MOD_SHIFT = 4
MOD_WIN = 8


def parse_hotkey(hotkey_str):
    """
    解析快捷键字符串
    
    Args:
        hotkey_str: 快捷键字符串，如 "Ctrl+Shift+F1"
    
    Returns:
        tuple: (modifiers, key_code)
    """
    modifiers = 0
    key = 0
    
    parts = hotkey_str.upper().split('+')
    
    for part in parts:
        part = part.strip()
        if part == 'CTRL' or part == 'CONTROL':
            modifiers |= MOD_CTRL
        elif part == 'ALT':
            modifiers |= MOD_ALT
        elif part == 'SHIFT':
            modifiers |= MOD_SHIFT
        elif part == 'WIN' or part == 'WINDOWS':
            modifiers |= MOD_WIN
        elif part in VK_CODE:
            key = VK_CODE[part]
    
    return modifiers, key
