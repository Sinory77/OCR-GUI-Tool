# OCR 引擎封装模块
# 封装 PaddleOCR-json 的调用
# 文档: https://github.com/hiroi-sora/PaddleOCR-json

import sys
import os
import subprocess
import tempfile

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
        self.args = {}
        
        # 添加语言配置
        if language in LANGUAGES:
            self.args["config_path"] = os.path.join(self.models_path, LANGUAGES[language])
        
        # 合并自定义参数（如果传入了的话）
        if custom_args:
            self.args.update(custom_args)
        
        # 注意：不传递 limit_side_len，让 PaddleOCR-json 使用默认值（960）
        
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

    def should_use_slice(self, image_path: str, slice_height: int = 2000) -> bool:
        """判断图片是否需要切片识别
        
        Args:
            image_path: 图片路径
            slice_height: 切片高度阈值
            
        Returns:
            是否需要切片识别
        """
        try:
            from PIL import Image
            with Image.open(image_path) as img:
                return img.height > slice_height
        except Exception:
            return False
    
    def recognize_auto(self, image_path: str, config=None, progress_callback=None) -> dict:
        """自动判断并执行识别（普通图或超长图切片）
        
        Args:
            image_path: 图片路径
            config: 配置对象（可选）
            progress_callback: 切片进度回调函数 (current, total)
            
        Returns:
            识别结果字典
        """
        if config:
            slice_height = config.get_slice_height()
            overlap = config.get_slice_overlap()
        else:
            slice_height = 2000
            overlap = 100
        
        # 自动判断是否需要切片
        if self.should_use_slice(image_path, slice_height):
            return self.recognize_long_image(
                image_path,
                slice_height=slice_height,
                overlap=overlap,
                progress_callback=progress_callback
            )
        else:
            return self.recognize(image_path)

    def recognize_long_image(self, image_path, slice_height=2000, overlap=100, progress_callback=None):
        """
        超长图切片识别：将超高图片切成若干块分别识别，再合并结果。

        Args:
            image_path  : 图片路径
            slice_height: 每块的高度（像素），默认 2000
            overlap     : 相邻切片的重叠像素，防止文字被切断，默认 100
            progress_callback: 进度回调函数，接收 (current, total) 参数

        Returns:
            dict: 与 recognize() 格式相同的识别结果
                  {"code": 100, "data": [...], "texts": [...], "success": True}
        """
        try:
            from PIL import Image
        except ImportError:
            # 没有 Pillow，直接回退到普通识别
            print("[OCR] Pillow 未安装，切片识别不可用，回退到普通识别")
            return self.recognize(image_path)

        # ── 读取图片 ────────────────────────────────────────────────
        try:
            img = Image.open(image_path)
        except Exception as e:
            return {"code": -1, "data": f"图片打开失败: {e}", "texts": [], "success": False}

        img_w, img_h = img.size

        # 高度不超过阈值时直接识别，无需切片
        if img_h <= slice_height:
            return self.recognize(image_path)

        print(f"[OCR] 超长图切片识别: {img_w}×{img_h}, 切片高度={slice_height}, 重叠={overlap}")

        if not self._initialized:
            if not self.initialize():
                return {"code": -1, "data": "引擎初始化失败", "texts": [], "success": False}

        # 预估总切片数（用于进度报告）
        total_slices = 0
        temp_y = 0
        while temp_y < img_h:
            total_slices += 1
            y_end = min(temp_y + slice_height, img_h)
            if y_end >= img_h:
                break
            temp_y = y_end - overlap

        all_data = []   # 合并后的 data 列表（含坐标）
        all_texts = []  # 合并后的纯文本
        y_start = 0
        slice_index = 0

        tmp_files = []  # 记录临时文件，最后统一删除

        try:
            while y_start < img_h:
                y_end = min(y_start + slice_height, img_h)
                slice_index += 1

                # 报告进度
                if progress_callback:
                    progress_callback(slice_index, total_slices)

                # 裁剪当前切片
                slice_img = img.crop((0, y_start, img_w, y_end))

                # 写入临时文件（PaddleOCR-json 需要文件路径）
                # 统一用 .png 后缀，与保存格式保持一致
                tmp_fd, tmp_path = tempfile.mkstemp(suffix=".png", prefix="ocr_slice_")
                os.close(tmp_fd)
                tmp_files.append(tmp_path)

                # 统一保存为 PNG，避免 RGBA/调色板模式无法写入 JPEG 的问题
                # 同时把临时文件后缀也改成 .png，防止扩展名与格式不匹配
                save_img = slice_img
                if save_img.mode not in ("RGB", "L"):
                    # RGBA / P(调色板) 等模式先转 RGB
                    save_img = save_img.convert("RGB")
                save_img.save(tmp_path, format="PNG")

                # 识别切片
                result = self.ocr.run(tmp_path)

                if result["code"] == 100:
                    for item in result["data"]:
                        # 坐标修正：将切片内的 y 坐标加回原图偏移
                        adjusted = dict(item)
                        if "box" in adjusted and adjusted["box"]:
                            adjusted["box"] = [
                                [pt[0], pt[1] + y_start]
                                for pt in adjusted["box"]
                            ]
                        all_data.append(adjusted)
                        all_texts.append(item["text"])
                elif result["code"] == 101:
                    # 当前切片无文字，正常跳过
                    pass
                else:
                    print(f"[OCR] 切片 {slice_index} 识别异常: code={result['code']}")

                # 下一切片起始位置（减去重叠区域）
                if y_end >= img_h:
                    break
                y_start = y_end - overlap

        finally:
            # 删除临时文件
            for f in tmp_files:
                try:
                    os.remove(f)
                except Exception:
                    pass

        if all_data:
            return {"code": 100, "data": all_data, "texts": all_texts, "success": True}
        else:
            return {"code": 101, "data": "未识别到文字", "texts": [], "success": False}
    
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
