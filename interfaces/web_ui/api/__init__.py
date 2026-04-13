# web_ui/api 模块 - 提供给前端 Web 界面的 API
# 简化版：只负责桥接 core 模块和前端

import os
import sys
import threading

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# 导入 core 模块
from core import (
    get_ocr_engine, reset_ocr_engine,
    get_result_manager,
    get_exporter,
    capture_screen_to_temp,
    LANGUAGES, DEFAULT_OCR_EXE, DEFAULT_MODELS_PATH
)


class WebApi:
    """提供给前端的简化 API - 调用 core 模块"""

    def __init__(self):
        # 不存储 result_manager/exporter 避免 pywebview 序列化 pathlib.Path 报错
        self._ocr_engine = None
        self._current_result = None
        self._status_callback = None
    
    def set_status_callback(self, callback):
        """设置状态回调函数（由 web_ui.py 调用）"""
        self._status_callback = callback
    
    def _update_status(self, status, is_error=False):
        """更新状态"""
        if self._status_callback:
            self._status_callback(status, is_error)
    
    def init_engine(self):
        """初始化 OCR 引擎"""
        def init():
            try:
                self._ocr_engine = get_ocr_engine()
                success = self._ocr_engine.initialize()
                if success:
                    self._update_status("引擎就绪", False)
                    return True
                else:
                    self._update_status("初始化失败", True)
                    return False
            except Exception as e:
                self._update_status(f"错误: {str(e)}", True)
                return False

        threading.Thread(target=init, daemon=True).start()
        return True
    
    def get_languages(self):
        """获取支持的语言列表"""
        return list(LANGUAGES.keys())
    
    def recognize(self, image_path):
        """识别图片"""
        if not self._ocr_engine:
            return {'success': False, 'error': '引擎未初始化'}

        try:
            result = self._ocr_engine.recognize(image_path)
            self._current_result = result

            # 添加到结果管理器
            get_result_manager().add_result(image_path, result)
            get_exporter().add_result(image_path, result)
            
            # 格式化结果
            if result.get('code') == 100:
                texts = []
                for item in result.get('data', []):
                    texts.append(item.get('text', ''))
                return {
                    'success': True,
                    'texts': texts,
                    'count': len(texts),
                    'data': result.get('data', [])
                }
            else:
                return {
                    'success': False,
                    'error': f"识别失败: {result.get('data', '未知错误')}",
                    'code': result.get('code')
                }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def screenshot(self):
        """截图"""
        temp_path = capture_screen_to_temp()
        if temp_path:
            return {'path': temp_path}
        return {'error': '截图失败'}

    def get_image_base64(self, image_path):
        """获取图片的 base64 编码（用于预览）"""
        import base64
        try:
            abs_path = os.path.abspath(os.path.expanduser(image_path))
            if not os.path.exists(abs_path):
                return {'success': False, 'error': f'文件不存在: {abs_path}'}
            ext = os.path.splitext(abs_path)[1].lower()
            mime_map = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
                         '.bmp': 'image/bmp', '.gif': 'image/gif', '.webp': 'image/webp'}
            mime = mime_map.get(ext, 'image/jpeg')
            with open(abs_path, 'rb') as f:
                data = base64.b64encode(f.read()).decode('utf-8')
            return {'success': True, 'data': f'data:{mime};base64,{data}'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def save_temp_image(self, data_url):
        """保存 base64 图片为临时文件，返回路径"""
        import tempfile
        import base64
        try:
            # 解析 data URL
            if ',' not in data_url:
                return {'success': False, 'error': '无效的 data URL'}
            header, data = data_url.split(',', 1)
            # 提取 mime 类型
            if 'image/png' in header:
                ext = '.png'
            elif 'image/gif' in header:
                ext = '.gif'
            elif 'image/webp' in header:
                ext = '.webp'
            else:
                ext = '.jpg'
            # 解码并写入临时文件
            img_data = base64.b64decode(data)
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(img_data)
                tmp_path = tmp.name
            return {'success': True, 'path': tmp_path}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def open_file_dialog(self):
        """打开文件对话框"""
        import tkinter as tk
        from tkinter import filedialog
        
        root = tk.Tk()
        root.withdraw()
        
        file_path = filedialog.askopenfilename(
            title='选择图片',
            filetypes=[
                ('图片文件', '*.jpg *.jpeg *.png *.bmp *.gif *.webp'),
                ('所有文件', '*.*')
            ]
        )
        root.destroy()
        
        if file_path:
            return {'path': file_path}
        return None
    
    def open_files_dialog(self):
        """打开多文件对话框"""
        import tkinter as tk
        from tkinter import filedialog
        
        root = tk.Tk()
        root.withdraw()
        
        file_paths = filedialog.askopenfilenames(
            title='批量选择图片',
            filetypes=[
                ('图片文件', '*.jpg *.jpeg *.png *.bmp *.gif *.webp'),
                ('所有文件', '*.*')
            ]
        )
        root.destroy()
        
        if file_paths:
            return {'paths': list(file_paths)}
        return None
    
    def get_settings(self):
        """获取当前设置"""
        try:
            from core.config import DEFAULT_OCR_EXE, DEFAULT_ARGS
            return {
                'exe_path': DEFAULT_OCR_EXE,
                'det_threshold': DEFAULT_ARGS.get('det_db_thresh', 0.3)
            }
        except Exception:
            return {'exe_path': '', 'det_threshold': 0.3}
    
    def save_settings(self, settings):
        """保存设置"""
        try:
            # 暂存到实例变量，供后续引擎初始化使用
            self._settings = settings
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def add_history(self, path, text):
        """添加历史记录（兼容 JS 直接调用）"""
        # recognize() 已通过 result_manager.add_result() 添加，此方法为兼容保留
        return {'success': True}
    
    def get_history(self):
        """获取历史记录"""
        return get_result_manager().get_history()

    def clear_history(self):
        """清空历史"""
        get_result_manager().clear_history()
        return {'success': True}

    def delete_history(self, index):
        """删除历史记录"""
        success = get_result_manager().delete_history(index)
        return {'success': success}

    def export_result(self, result, format_type, filename=None):
        """导出结果 - 支持新旧两种格式"""
        try:
            if filename is None:
                filename = "ocr_result"
            file_path = get_exporter().export(result, format_type, filename)
            return {'success': True, 'path': file_path}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def change_language(self, language):
        """切换语言"""
        if language in LANGUAGES:
            reset_ocr_engine(language=language)
            self._ocr_engine = get_ocr_engine()
            threading.Thread(target=lambda: self._ocr_engine.initialize(), daemon=True).start()
            return {'success': True}
        return {'success': False, 'error': '不支持的语言'}
    
    def copy_to_clipboard(self, text):
        """
        复制到剪贴板 - 使用 pyperclip 库（最可靠的方式）
        
        Args:
            text: 要复制的文本，可以是字符串或包含 texts 字段的对象
            
        Returns:
            dict: {'success': bool, 'text': str, 'error'?: str}
        """
        import logging
        
        logger = logging.getLogger(__name__)
        
        try:
            # 兼容处理：如果是字典，提取其中的文本
            if isinstance(text, dict):
                if 'text' in text and text['text']:
                    text_content = text['text']
                elif 'texts' in text and text['texts']:
                    text_content = '\n'.join(text['texts'])
                else:
                    text_content = ''
            else:
                text_content = str(text) if text else ''
            
            if not text_content:
                return {'success': False, 'error': '没有可复制的内容'}
            
            logger.info(f"复制到剪贴板，内容长度: {len(text_content)} 字符")
            
            # 尝试使用 pyperclip
            try:
                import pyperclip
                pyperclip.copy(text_content)
                return {'success': True, 'text': text_content}
            except ImportError:
                pass
            
            # 备用方案：使用 Windows API (CF_TEXT ANSI 格式)
            import ctypes
            CF_TEXT = 1
            GMEM_MOVEABLE = 0x0002
            
            # 转换为 ANSI 编码（Windows 默认）
            data = text_content.encode('mbcs') + b'\x00'
            size = len(data)
            
            if not ctypes.windll.user32.OpenClipboard(0):
                return {'success': False, 'error': '无法打开剪贴板'}
            
            try:
                ctypes.windll.user32.EmptyClipboard()
                h_global = ctypes.windll.kernel32.GlobalAlloc(GMEM_MOVEABLE, size)
                if h_global:
                    p_global = ctypes.windll.kernel32.GlobalLock(h_global)
                    if p_global:
                        ctypes.memmove(p_global, data, size)
                        ctypes.windll.kernel32.GlobalUnlock(h_global)
                    ctypes.windll.user32.SetClipboardData(CF_TEXT, h_global)
                return {'success': True, 'text': text_content}
            finally:
                ctypes.windll.user32.CloseClipboard()
                
        except Exception as e:
            logger.error(f"复制到剪贴板失败: {e}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"复制到剪贴板失败: {e}")
            return {'success': False, 'error': str(e)}


class WindowControlApi:
    """窗口控制 API"""
    
    def minimize(self):
        """最小化窗口"""
        import webview
        try:
            if webview.windows:
                webview.windows[0].minimize()
                return True
        except Exception:
            pass
        return False
    
    def maximize(self):
        """最大化窗口"""
        import webview
        try:
            if webview.windows:
                webview.windows[0].maximize()
                return True
        except Exception:
            pass
        return False
    
    def restore(self):
        """还原窗口"""
        import webview
        try:
            if webview.windows:
                webview.windows[0].restore()
                return True
        except Exception:
            pass
        return False
    
    def close(self):
        """关闭窗口"""
        import webview
        try:
            if webview.windows:
                webview.windows[0].destroy()
                return True
        except Exception:
            pass
        return False
    
    def start_drag(self):
        """开始窗口拖动（供 JS 调用）"""
        import webview
        try:
            if webview.windows:
                webview.windows[0].start_dragging()
                return True
        except Exception:
            pass
        return False
    
    def prevent_drag(self):
        """阻止窗口拖动（供 JS 调用，Python 端无需处理）"""
        return True


# 创建全局 API 实例
_web_api = None


def get_web_api():
    """获取 Web API 实例"""
    global _web_api
    if _web_api is None:
        _web_api = WebApi()
    return _web_api
