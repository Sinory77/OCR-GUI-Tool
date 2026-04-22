# OcrApi - 提供给前端的 API
import os
import sys
import json
import threading
import tempfile

from datetime import datetime

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from core import OCREngine, get_ocr_engine, reset_ocr_engine
from core import ResultExporter as Exporter
from core.config import DEFAULT_OCR_EXE, DEFAULT_MODELS_PATH, LANGUAGES


class OcrApi:
    """提供给前端的 API"""
    
    def __init__(self):
        self.ocr_engine = None
        self.exporter = Exporter()
        self.history = []
        self.settings = {
            'exe_path': '',
            'det_threshold': 0.3
        }
        self.current_result = None
        
        # 加载历史
        self.load_history()
    
    def load_history(self):
        """加载历史记录"""
        history_file = os.path.join(project_root, 'history.json')
        if os.path.exists(history_file):
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    self.history = json.load(f)
            except:
                self.history = []
    
    def save_history(self):
        """保存历史记录"""
        history_file = os.path.join(project_root, 'history.json')
        try:
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False)
        except:
            pass
    
    def init_engine(self):
        """初始化 OCR 引擎"""
        def init():
            try:
                # 确定引擎路径
                exe_path = self.settings.get('exe_path', '') or DEFAULT_OCR_EXE
                models_path = DEFAULT_MODELS_PATH
                
                # 直接创建 OCREngine 实例（get_ocr_engine 无参数版本）
                from core.ocr_engine import OCREngine
                self.ocr_engine = OCREngine(exe_path=exe_path, models_path=models_path)
                ok = self.ocr_engine.initialize()
                if ok:
                    return {'status': '引擎就绪', 'success': True}
                else:
                    return {'status': '引擎初始化失败，请检查路径', 'success': False, 'error': True}
            except Exception as e:
                return {'status': f'初始化失败: {str(e)}', 'success': False, 'error': str(e)}
        
        result = {'success': True, 'status': '初始化中...'}
        threading.Thread(target=lambda: self._init_async(init), daemon=True).start()
        return result
    
    def _init_async(self, init_fn):
        """异步初始化"""
        import time
        time.sleep(0.5)  # 等待初始化完成
        result = init_fn()
        # 直接返回结果，不再通过JS回调更新状态
        return result
    
    def get_settings(self):
        """获取设置"""
        return self.settings
    
    def save_settings(self, settings):
        """保存设置"""
        self.settings.update(settings)
        # 可以保存到配置文件
        return {'success': True}
    
    def get_history(self):
        """获取历史记录"""
        return self.history[-50:]  # 返回最近50条
    
    def add_history(self, path, text):
        """添加历史记录"""
        self.history.append({
            'path': path,
            'filename': os.path.basename(path),
            'text': text,
            'time': self._get_time()
        })
        self.save_history()
        return {'success': True}
    
    def delete_history(self, index):
        """删除历史记录"""
        # 反转索引，因为前端是从新到旧显示
        actual_index = len(self.history) - 1 - index
        if 0 <= actual_index < len(self.history):
            self.history.pop(actual_index)
            self.save_history()
        return {'success': True}
    
    def clear_history(self):
        """清空历史"""
        self.history = []
        self.save_history()
        return {'success': True}
    
    def get_image_base64(self, image_path):
        """读取图片并返回 base64 编码（解决 file:// 路径被拦截的问题）"""
        try:
            import base64
            import mimetypes
            # 统一转换为绝对路径
            abs_path = self._resolve_path(image_path)
            if not abs_path or not os.path.exists(abs_path):
                return {'success': False, 'error': f'图片不存在: {image_path}'}
            with open(abs_path, 'rb') as f:
                data = f.read()
            mime = mimetypes.guess_type(abs_path)[0] or 'image/jpeg'
            b64 = base64.b64encode(data).decode('utf-8')
            return {'success': True, 'data': f'data:{mime};base64,{b64}'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def open_image(self):
        """打开图片文件（旧方法名保留）"""
        return self.open_file_dialog()
    
    def open_file_dialog(self):
        """打开图片文件（JS 调用的方法名）"""
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
    
    def save_temp_image(self, data_url):
        """将 JS 传来的 data URL（base64）保存为临时文件，返回路径供 OCR 使用"""
        try:
            import base64, re, uuid
            # data_url 格式: data:image/png;base64,xxxxx
            match = re.match(r'data:([^;]+);base64,(.+)', data_url)
            if not match:
                return {'success': False, 'error': '无效的 data URL 格式'}
            ext = match.group(1).split('/')[-1].replace('jpeg', 'jpg')
            filename = f'ocr_temp_{uuid.uuid4().hex[:8]}.{ext}'
            temp_path = os.path.join(tempfile.gettempdir(), filename)
            with open(temp_path, 'wb') as f:
                f.write(base64.b64decode(match.group(2)))
            return {'success': True, 'path': temp_path}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def screenshot(self):
        """截图"""
        try:
            from PIL import ImageGrab
            
            import time
            time.sleep(0.5)
            
            # 截图
            img = ImageGrab.grab()
            
            # 保存到临时文件
            temp_file = os.path.join(tempfile.gettempdir(), 'ocr_screenshot.png')
            img.save(temp_file)
            
            return {'path': temp_file}
        except Exception as e:
            return {'error': str(e)}
    
    def batch_select(self):
        """批量选择图片（旧方法名保留）"""
        return self.open_files_dialog()
    
    def open_files_dialog(self):
        """批量选择图片（JS 调用的方法名）"""
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
    
    def recognize(self, image_path):
        """识别图片"""
        if not self.ocr_engine:
            return {'success': False, 'error': '引擎未初始化'}
        
        # 统一转换为绝对路径
        abs_path = self._resolve_path(image_path)
        if not abs_path or not os.path.exists(abs_path):
            return {'success': False, 'error': f'图片路径无效: {image_path}'}
        
        try:
            result = self.ocr_engine.recognize(abs_path)
            self.current_result = result
            
            if not result.get('success', False):
                return {'success': False, 'error': result.get('data', '识别失败')}
            
            # texts 是列表，合并成字符串
            texts = result.get('texts', [])
            text = '\n'.join(texts)
            
            # 添加到历史
            self.add_history(abs_path, text)
            
            return {
                'success': True,
                'text': text,
                'texts': texts,
                'data': result
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _resolve_path(self, path):
        """将相对路径或带 ~ 的路径转换为绝对路径"""
        if not path:
            return None
        # 转为绝对路径（处理相对路径和 ~）
        abs_path = os.path.abspath(os.path.expanduser(path))
        return abs_path if os.path.exists(abs_path) else (path if os.path.isabs(path) else None)
    
    def copy_to_clipboard(self, text):
        """复制到剪贴板"""
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        root.destroy()
        return {'success': True}
    
    def export_result(self, result, format_type, image_path):
        """导出结果"""
        try:
            filename = os.path.splitext(os.path.basename(image_path))[0]
            file_path = self.exporter.export(result, format_type, filename)
            return {'success': True, 'path': file_path}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def change_language(self, language):
        """切换语言"""
        try:
            reset_ocr_engine(language=language)
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _get_time(self):
        """获取当前时间"""
        return datetime.now().strftime('%Y-%m-%d %H:%M')