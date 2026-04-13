# OCR 引擎封装模块
# 封装 PaddleOCR-json 的调用
# 文档: https://github.com/hiroi-sora/PaddleOCR-json

import sys
import os
import subprocess

# 添加父目录到路径以便导入 PPOCR_api
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from api.PPOCR_api import GetOcrApi
from .config import DEFAULT_OCR_EXE, DEFAULT_MODELS_PATH, DEFAULT_ARGS, LANGUAGES

# 状态码说明（官方文档）
OCR_CODES = {
    100: "识别成功",
    101: "未识别到文字",
    200: "图片路径不存在",
    202: "文件无法打开",
    203: "图片解码失败",
    901: "引擎实例不存在",
    902: "子进程崩溃或连接失败",
    903: "读取输出失败",
    904: "JSON反序列化失败",
}


class OCREngine:
    """OCR 引擎封装类"""
    
    def __init__(self, exe_path=None, models_path=None, language="简体中文", custom_args=None):
        """
        初始化 OCR 引擎
        
        Args:
            exe_path: PaddleOCR-json.exe 路径
            models_path: models 文件夹路径
            language: 识别语言
            custom_args: 自定义 OCR 参数
        """
        self.exe_path = exe_path or DEFAULT_OCR_EXE
        self.models_path = models_path or DEFAULT_MODELS_PATH
        self.language = language
        self.args = DEFAULT_ARGS.copy()
        
        # 添加语言配置
        if language in LANGUAGES:
            self.args["config_path"] = os.path.join(self.models_path, LANGUAGES[language])
        
        # 合并自定义参数
        if custom_args:
            self.args.update(custom_args)
        
        self.ocr = None
        self._initialized = False
    
    def _cleanup_residual_processes(self):
        """清理残留的 PaddleOCR 进程"""
        try:
            # 获取 exe 文件名（不带路径）
            exe_name = os.path.basename(self.exe_path)
            
            # 查找所有同名进程
            result = subprocess.run(
                ['tasklist', '/FI', f'IMAGENAME eq {exe_name}', '/FO', 'CSV', '/NH'],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            
            # 解析进程列表并清理
            for line in result.stdout.strip().split('\n'):
                if exe_name.lower() in line.lower():
                    parts = line.split(',')
                    if len(parts) >= 2:
                        pid = parts[1].strip('"')
                        try:
                            subprocess.run(['taskkill', '/F', '/PID', pid],
                                        capture_output=True,
                                        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
                            print(f"[OCR] 已清理残留进程 PID={pid}")
                        except:
                            pass
        except Exception as e:
            print(f"[OCR] 清理残留进程失败: {e}")
    
    def _is_process_alive(self):
        """检查子进程是否存活"""
        if not self.ocr or not hasattr(self.ocr, 'ret') or not self.ocr.ret:
            return False
        return self.ocr.ret.poll() is None  # None = 进程仍在运行
    
    @staticmethod
    def get_code_message(code: int) -> str:
        """获取状态码说明"""
        return OCR_CODES.get(code, f"未知状态码: {code}")
    
    def initialize(self):
        """初始化 OCR 引擎"""
        if self._initialized and self._is_process_alive():
            return True
        
        # 进程已不存在，需要重新初始化
        if self._initialized and not self._is_process_alive():
            print("[OCR] 子进程已终止，准备重新初始化...")
            self._initialized = False
            self.ocr = None
        
        try:
            # 清理残留进程
            self._cleanup_residual_processes()
            
            self.ocr = GetOcrApi(
                self.exe_path,
                self.models_path,
                self.args,
                ipcMode="pipe"
            )
            self._initialized = True
            return True
        except Exception as e:
            print(f"OCR 引擎初始化失败: {e}")
            return False
    
    def recognize(self, image_path):
        """
        识别图片中的文字
        
        Args:
            image_path: 图片路径
            
        Returns:
            dict: 识别结果 {"code": int, "data": list/str, "texts": list, "success": bool}
        """
        if not self._initialized:
            if not self.initialize():
                return {"code": -1, "data": "引擎初始化失败", "texts": [], "success": False}
        
        try:
            result = self.ocr.run(image_path)
            
            # 提取纯文本
            texts = []
            if result["code"] == 100:
                for item in result["data"]:
                    texts.append(item["text"])
            
            result["texts"] = texts
            result["success"] = result["code"] == 100
            
            return result
            
        except Exception as e:
            return {"code": -1, "data": str(e), "texts": [], "success": False}
    
    def recognize_bytes(self, image_bytes):
        """
        识别图片字节流
        
        Args:
            image_bytes: 图片字节数据
            
        Returns:
            dict: 识别结果
        """
        if not self._initialized:
            if not self.initialize():
                return {"code": -1, "data": "引擎初始化失败", "texts": [], "success": False}
        
        try:
            result = self.ocr.runBytes(image_bytes)
            
            # 提取纯文本
            texts = []
            if result["code"] == 100:
                for item in result["data"]:
                    texts.append(item["text"])
            
            result["texts"] = texts
            result["success"] = result["code"] == 100
            
            return result
            
        except Exception as e:
            return {"code": -1, "data": str(e), "texts": [], "success": False}
    
    def set_language(self, language):
        """
        切换识别语言（按官方文档，完全重建 OCR 引擎）
        
        Args:
            language: 语言名称，对应 LANGUAGES 中的键
            
        Returns:
            bool: 是否成功
        """
        if language not in LANGUAGES:
            print(f"[OCR] 不支持的语言: {language}")
            return False
        
        if self.language == language:
            return True
        
        print(f"[OCR] 切换语言: {self.language} -> {language}")
        self.language = language
        # 更新 config_path
        self.args["config_path"] = os.path.join(self.models_path, LANGUAGES[language])
        
        # 完全重建 OCR 引擎（官方推荐方式）
        self._reinit_engine()
        return True
    
    def _reinit_engine(self):
        """重建 OCR 引擎"""
        # 关闭旧引擎
        if self.ocr:
            try:
                self.ocr.exit()
            except:
                pass
        self.ocr = None
        self._initialized = False
        
        # 清理残留进程
        self._cleanup_residual_processes()
        
        # 重新初始化
        try:
            self.ocr = GetOcrApi(
                self.exe_path,
                self.models_path,
                self.args,
                ipcMode="pipe"
            )
            self._initialized = True
            print(f"[OCR] 引擎已重建，语言: {self.language}")
        except Exception as e:
            print(f"[OCR] 引擎重建失败: {e}")
            self._initialized = False
    
    def update_args(self, new_args):
        """更新 OCR 参数"""
        self.args.update(new_args)
        self._initialized = False  # 需要重新初始化
    
    def close(self):
        """关闭 OCR 引擎"""
        if self.ocr:
            try:
                self.ocr.exit()
            except:
                pass
            self.ocr = None
            self._initialized = False
    
    def __del__(self):
        self.close()


# 全局 OCR 引擎实例
_ocr_engine = None


def get_ocr_engine():
    """获取全局 OCR 引擎实例"""
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = OCREngine()
    return _ocr_engine


def reset_ocr_engine(exe_path=None, models_path=None, language=None, custom_args=None):
    """重置并重新初始化 OCR 引擎"""
    global _ocr_engine
    if _ocr_engine:
        _ocr_engine.close()
    _ocr_engine = OCREngine(exe_path, models_path, language, custom_args)
    return _ocr_engine
