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
from typing import Optional, Tuple, Dict, Any
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


class ScreenshotManager:
    """截图管理器
    
    该类负责：
    1. 提供全屏截图功能
    2. 支持指定区域截图
    3. 支持窗口截图
    4. 提供延迟截图功能
    5. 管理截图历史记录
    6. 支持将截图保存到剪贴板
    
    支持多种截图方式：
    - mss 库（优先）
    - PIL ImageGrab（备用）
    - Win32 API（备用）
    """
    
    def __init__(self):
        """初始化截图管理器"""
        self.screenshot_history = []  # 截图历史记录
        self.max_history = 10  # 最大历史记录数
    
    def capture_full_screen(self, save_to_history: bool = True) -> Optional[str]:
        """
        截取全屏并保存到临时文件
        
        Args:
            save_to_history: 是否保存到历史记录
        
        Returns:
            临时文件路径，失败返回 None
        """
        if sys.platform != 'win32':
            logger.error("截图功能仅支持 Windows 平台")
            return None
        
        try:
            # 优先使用 mss 库（最可靠、最快）
            import mss
            
            with mss.mss() as sct:
                # 生成唯一的临时文件路径
                temp_path = os.path.join(tempfile.gettempdir(), f'ocr_screenshot_{int(time.time())}.png')
                sct.shot(mon=-1, output=temp_path)
                logger.debug(f"全屏截图成功 (mss): {temp_path}")
                
                if save_to_history:
                    self._add_to_history(temp_path)
                
                return temp_path
                
        except ImportError:
            logger.debug("mss 库未安装，尝试备用方案")
        except Exception as e:
            logger.warning(f"mss 截图失败: {e}，尝试备用方案")
        
        # 备用方案：使用 PIL ImageGrab
        try:
            from PIL import ImageGrab
            
            img = ImageGrab.grab()
            temp_path = os.path.join(tempfile.gettempdir(), f'ocr_screenshot_{int(time.time())}.png')
            img.save(temp_path, 'PNG')
            logger.debug(f"全屏截图成功 (PIL): {temp_path}")
            
            if save_to_history:
                self._add_to_history(temp_path)
            
            return temp_path
            
        except ImportError:
            logger.debug("PIL 库未安装")
        except Exception as e:
            logger.warning(f"PIL 截图失败: {e}")
        
        logger.error("所有截图方案均失败")
        return None
    
    def capture_screen_region(self, x: int, y: int, width: int, height: int, 
                            save_to_history: bool = True) -> Optional[str]:
        """
        截取屏幕指定区域并保存到临时文件
        
        Args:
            x, y: 起始坐标
            width, height: 区域宽高
            save_to_history: 是否保存到历史记录
        
        Returns:
            临时文件路径，失败返回 None
        """
        if sys.platform != 'win32':
            logger.error("截图功能仅支持 Windows 平台")
            return None
        
        try:
            # 优先使用 mss 库
            import mss
            
            with mss.mss() as sct:
                temp_path = os.path.join(tempfile.gettempdir(), f'ocr_screenshot_{int(time.time())}.png')
                # mss 使用 (left, top, width, height) 格式
                region = {
                    'left': x,
                    'top': y,
                    'width': width,
                    'height': height
                }
                # 截取区域并保存
                sct_img = sct.grab(region)
                mss.tools.to_png(sct_img.rgb, sct_img.size, output=temp_path)
                logger.debug(f"区域截图成功 (mss): {temp_path}")
                
                if save_to_history:
                    self._add_to_history(temp_path)
                
                return temp_path
                
        except ImportError:
            logger.debug("mss 库未安装，尝试备用方案")
        except Exception as e:
            logger.warning(f"mss 区域截图失败: {e}，尝试备用方案")
        
        # 备用方案：使用 PIL ImageGrab
        try:
            from PIL import ImageGrab
            
            # ImageGrab 使用 (left, top, right, bottom) 格式
            bbox = (x, y, x + width, y + height)
            img = ImageGrab.grab(bbox=bbox)
            temp_path = os.path.join(tempfile.gettempdir(), f'ocr_screenshot_{int(time.time())}.png')
            img.save(temp_path, 'PNG')
            logger.debug(f"区域截图成功 (PIL): {temp_path}")
            
            if save_to_history:
                self._add_to_history(temp_path)
            
            return temp_path
            
        except ImportError:
            logger.debug("PIL 库未安装")
        except Exception as e:
            logger.warning(f"PIL 区域截图失败: {e}")
        
        # 最后备用：使用 Win32 API
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
            temp_path = os.path.join(tempfile.gettempdir(), f'ocr_screenshot_{int(time.time())}.png')
            img.save(temp_path, 'PNG')
            logger.debug(f"区域截图成功 (Win32 API): {temp_path}")
            
            # 释放资源
            mem_dc.SelectObject(old_bitmap)
            win32gui.DeleteObject(bitmap.GetHandle())
            win32gui.DeleteDC(mem_dc)
            win32gui.ReleaseDC(0, screen_dc)
            
            if save_to_history:
                self._add_to_history(temp_path)
            
            return temp_path
            
        except Exception as e:
            logger.error(f"区域截图失败: {e}", exc_info=True)
            return None
    
    def capture_window(self, hwnd: int) -> Optional[str]:
        """
        截取指定窗口
        
        Args:
            hwnd: 窗口句柄
        
        Returns:
            临时文件路径，失败返回 None
        """
        if sys.platform != 'win32':
            logger.error("截图功能仅支持 Windows 平台")
            return None
        
        try:
            import win32gui
            import win32ui
            import win32con
            from PIL import Image
            
            # 获取窗口矩形
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            width = right - left
            height = bottom - top
            
            # 获取窗口 DC
            hwindc = win32gui.GetWindowDC(hwnd)
            srcdc = win32ui.CreateDCFromHandle(hwindc)
            memdc = srcdc.CreateCompatibleDC()
            bmp = win32ui.CreateBitmap()
            bmp.CreateCompatibleBitmap(srcdc, width, height)
            memdc.SelectObject(bmp)
            
            # 截图
            memdc.BitBlt((0, 0), (width, height), srcdc, (0, 0), win32con.SRCCOPY)
            
            # 转换为 PIL Image
            bmpinfo = bmp.GetInfo()
            bmpstr = bmp.GetBitmapBits(True)
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
            temp_path = os.path.join(tempfile.gettempdir(), f'ocr_window_{int(time.time())}.png')
            img.save(temp_path, 'PNG')
            logger.debug(f"窗口截图成功: {temp_path}")
            
            # 释放资源
            win32gui.DeleteObject(bmp.GetHandle())
            memdc.DeleteDC()
            srcdc.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwindc)
            
            self._add_to_history(temp_path)
            return temp_path
            
        except Exception as e:
            logger.error(f"窗口截图失败: {e}", exc_info=True)
            return None
    
    def capture_with_delay(self, delay: int = 3) -> Optional[str]:
        """
        延迟截图
        
        Args:
            delay: 延迟时间（秒）
        
        Returns:
            临时文件路径，失败返回 None
        """
        logger.info(f"延迟 {delay} 秒后截图")
        time.sleep(delay)
        return self.capture_full_screen()
    
    def capture_screen_to_pixmap(self):
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
                
                with mss.mss() as sct:
                    # 直接获取屏幕数据，避免临时文件
                    monitor = sct.monitors[0]
                    sct_img = sct.grab(monitor)
                    # 转换为 QImage
                    width, height = sct_img.size
                    qimage = QImage(sct_img.rgb, width, height, width * 3, QImage.Format.Format_RGB888)
                    pixmap = QPixmap.fromImage(qimage)
                    logger.debug("截图成功 (mss -> QPixmap)")
                    return pixmap
            except ImportError:
                logger.debug("mss 库未安装，尝试备用方案")
            except Exception as e:
                logger.warning(f"mss 截图失败: {e}，尝试备用方案")
            
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
                logger.debug("截图成功 (PIL -> QPixmap)")
                return pixmap
            except ImportError:
                logger.debug("PIL 库未安装")
            except Exception as e:
                logger.warning(f"PIL 截图失败: {e}")
            
            # 最后备用：保存到临时文件再加载
            temp_path = self.capture_full_screen(save_to_history=False)
            if temp_path:
                pixmap = QPixmap(temp_path)
                # 清理临时文件
                try:
                    os.unlink(temp_path)
                except:
                    pass
                return pixmap
            
            return None
            
        except Exception as e:
            logger.error(f"截图失败: {e}", exc_info=True)
            return None
    
    def capture_screen_as_bytes(self) -> Tuple[Optional[bytes], int, int]:
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
    
    def save_to_clipboard(self, image_path: str) -> bool:
        """
        将图片保存到剪贴板
        
        Args:
            image_path: 图片文件路径
        
        Returns:
            bool: 是否成功
        """
        if sys.platform != 'win32':
            logger.error("保存到剪贴板功能仅支持 Windows 平台")
            return False
        
        try:
            from PIL import Image
            import win32clipboard
            import io
            
            # 打开图片
            img = Image.open(image_path)
            
            # 转换为 BMP 格式
            output = io.BytesIO()
            img.convert('RGB').save(output, format='BMP')
            data = output.getvalue()[14:]  # 去掉 BMP 头
            output.close()
            
            # 保存到剪贴板
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
            win32clipboard.CloseClipboard()
            
            logger.debug(f"图片已保存到剪贴板: {image_path}")
            return True
            
        except Exception as e:
            logger.error(f"保存到剪贴板失败: {e}", exc_info=True)
            return False
    
    def _add_to_history(self, image_path: str):
        """
        添加截图到历史记录
        
        Args:
            image_path: 图片文件路径
        """
        # 添加到历史记录
        self.screenshot_history.insert(0, {
            'path': image_path,
            'timestamp': time.time()
        })
        
        # 限制历史记录数量
        if len(self.screenshot_history) > self.max_history:
            # 删除最旧的记录
            old_record = self.screenshot_history.pop()
            # 尝试删除文件
            try:
                if os.path.exists(old_record['path']):
                    os.unlink(old_record['path'])
            except Exception as e:
                logger.warning(f"删除旧截图文件失败: {e}")
    
    def get_history(self) -> list:
        """
        获取截图历史记录
        
        Returns:
            list: 历史记录列表
        """
        return self.screenshot_history
    
    def clear_history(self):
        """
        清空截图历史记录
        """
        # 删除所有历史文件
        for record in self.screenshot_history:
            try:
                if os.path.exists(record['path']):
                    os.unlink(record['path'])
            except Exception as e:
                logger.warning(f"删除历史截图文件失败: {e}")
        
        # 清空历史记录
        self.screenshot_history = []
        logger.debug("截图历史已清空")


class HotkeyManager:
    """全局快捷键管理器"""
    
    def __init__(self):
        self.hotkeys = {}
        self.running = False
        self.thread = None
        self.hotkey_counter = 1  # 用于生成唯一的热键ID
    
    def register(self, hotkey_str: str, callback) -> Optional[int]:
        """
        注册快捷键
        
        Args:
            hotkey_str: 快捷键字符串，如 "Ctrl+Shift+F"
            callback: 回调函数
        
        Returns:
            int: 快捷键ID，失败返回 None
        """
        if sys.platform != 'win32':
            logger.error("快捷键功能仅支持 Windows 平台")
            return None
        
        # 解析快捷键
        modifiers, key = parse_hotkey(hotkey_str)
        if key == 0:
            logger.error(f"无效的快捷键: {hotkey_str}")
            return None
        
        # 生成唯一的热键ID
        hotkey_id = self.hotkey_counter
        self.hotkey_counter += 1
        
        # 注册系统级热键
        if not user32.RegisterHotKey(None, hotkey_id, modifiers, key):
            logger.error(f"注册热键失败: {hotkey_str}")
            return None
        
        # 保存回调
        self.hotkeys[hotkey_id] = {
            'callback': callback,
            'hotkey_str': hotkey_str
        }
        
        logger.info(f"快捷键注册成功: {hotkey_str}")
        return hotkey_id
    
    def unregister(self, hotkey_id: int):
        """注销快捷键"""
        if hotkey_id in self.hotkeys:
            del self.hotkeys[hotkey_id]
            user32.UnregisterHotKey(None, hotkey_id)
            logger.info(f"快捷键注销成功: ID={hotkey_id}")
    
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
        logger.info("快捷键监听已启动")
    
    def stop_listening(self):
        """停止监听"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
        logger.info("快捷键监听已停止")
    
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
                            self.hotkeys[hotkey_id]['callback']()
                        except Exception as e:
                            logger.error(f"快捷键回调执行失败: {e}", exc_info=True)
                
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            else:
                time.sleep(0.01)  # 减少CPU占用
    
    def get_registered_hotkeys(self) -> dict:
        """
        获取已注册的快捷键
        
        Returns:
            dict: 已注册的快捷键
        """
        return self.hotkeys


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
    'SPACE': 0x20, 'ENTER': 0x0D, 'ESCAPE': 0x1B, 'TAB': 0x09,
    'BACKSPACE': 0x08, 'DELETE': 0x2E, 'INSERT': 0x2D,
    'HOME': 0x24, 'END': 0x23, 'PAGEUP': 0x21, 'PAGEDOWN': 0x22,
    'UP': 0x26, 'DOWN': 0x28, 'LEFT': 0x25, 'RIGHT': 0x27,
}

# 修饰键
MOD_ALT = 1
MOD_CTRL = 2
MOD_SHIFT = 4
MOD_WIN = 8


def parse_hotkey(hotkey_str: str) -> Tuple[int, int]:
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


# 创建全局截图管理器实例
screenshot_manager = ScreenshotManager()

# 创建全局快捷键管理器实例
hotkey_manager = HotkeyManager()


def get_screenshot_manager() -> ScreenshotManager:
    """
    获取截图管理器实例
    
    Returns:
        ScreenshotManager: 截图管理器实例
    """
    return screenshot_manager


def get_hotkey_manager() -> HotkeyManager:
    """
    获取快捷键管理器实例
    
    Returns:
        HotkeyManager: 快捷键管理器实例
    """
    return hotkey_manager