# OCR 引擎封装模块
# 封装 PaddleOCR-json 的调用
# 文档: https://github.com/hiroi-sora/PaddleOCR-json

import sys
import os
import atexit
import signal
import time
import subprocess
import tempfile
import logging
import hashlib
import threading
import queue
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Callable, Any, Set

# 配置日志
logger = logging.getLogger(__name__)

# 识别结果缓存
_ocr_cache: Dict[str, Dict[str, Any]] = {}
# 缓存大小限制
MAX_CACHE_SIZE = 100

# 全局关闭标志（用于 emergency_cleanup 通知所有实例）
_global_shutting_down = False

# 添加父目录到路径以便导入 PPOCR_api
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from api.PPOCR_api import GetOcrApi
from .config import DEFAULT_OCR_EXE, DEFAULT_MODELS_PATH, DEFAULT_ARGS, LANGUAGES

from .error_handler import OCREngineError, handle_error, error_handling, ErrorType
from .log_context import LogContext

# 状态码说明（官方文档 + 自定义）
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
    998: "引擎内部错误或子进程异常",
    999: "未知错误",
}


class OCREngine:
    """OCR 引擎封装类 - 管理 PaddleOCR-json 进程和识别任务
    
    该类负责：
    1. 初始化和管理 PaddleOCR-json 进程
    2. 处理 OCR 识别请求
    3. 支持普通图片和超长图片的识别
    4. 维护识别结果缓存
    5. 提供语言切换功能
    """
    
    def __init__(self, exe_path: Optional[str] = None, models_path: Optional[str] = None, 
                 language: str = "简体中文", custom_args: Optional[Dict[str, Any]] = None):
        """
        初始化 OCR 引擎
        
        Args:
            exe_path: PaddleOCR-json.exe 路径
            models_path: models 文件夹路径
            language: 识别语言
            custom_args: 自定义 OCR 参数
            
        Raises:
            FileNotFoundError: OCR 可执行文件不存在
        """
        self.exe_path = exe_path or DEFAULT_OCR_EXE
        self.models_path = models_path or DEFAULT_MODELS_PATH
        self.language = language
        self.args: Dict[str, Any] = {}
        self.retry_count = 3  # 默认重试次数

        # 验证路径
        self._validate_paths()

        # 添加语言配置
        if language in LANGUAGES:
            self.args["config_path"] = os.path.join(self.models_path, LANGUAGES[language])

        # 合并自定义参数（如果传入了的话）
        if custom_args:
            self.args.update(custom_args)

        # 注意：不传递 limit_side_len，让 PaddleOCR-json 使用默认值（960）

        self.ocr = None
        self._initialized = False
        self._shutting_down = False  # 关闭标志
        self._engine_lock = threading.RLock()  # 管道引擎不支持并发，必须串行化访问（使用 RLock 允许重入）
        self._emit = None  # EventBus 事件推送器（由 CoreAPI 注入）
    
    def _validate_paths(self) -> None:
        """验证 OCR 引擎和模型路径的有效性"""
        if not Path(self.exe_path).exists():
            logger.warning(f"OCR 引擎路径不存在: {self.exe_path}")
        
        if not Path(self.models_path).exists():
            logger.warning(f"模型路径不存在: {self.models_path}")
    
    def set_event_emitter(self, emitter) -> None:
        """设置事件推送器（由 CoreAPI 注入）

        核心模块通过此方法获得向 EventBus 推送事件的能力。
        只在 _emit 不为 None 时推送，兼容没有 CoreAPI 的场景。

        Args:
            emitter: 事件推送函数，签名为 emitter(channel: str, **data)
        """
        self._emit = emitter
    
    def check_config(self) -> bool:
        """检查 OCR 引擎配置是否完整有效"""
        try:
            # 检查必需的路径是否存在
            exe_exists = Path(self.exe_path).exists() if self.exe_path else False
            models_exist = Path(self.models_path).exists() if self.models_path else False
            
            return exe_exists and models_exist
        except Exception:
            return False
    
    def _cleanup_residual_processes(self) -> None:
        """清理残留的 PaddleOCR 进程
        
        防止多次启动导致资源浪费。
        使用 taskkill /F /T 终止进程树（包括子进程）。
        """
        try:
            # 仅在 Windows 平台执行
            if sys.platform != 'win32':
                return
            
            # 获取 exe 文件名（不带路径）
            exe_name = os.path.basename(self.exe_path)
            
            # 查找所有同名进程
            result = subprocess.run(
                ['tasklist', '/FI', f'IMAGENAME eq {exe_name}', '/FO', 'CSV', '/NH'],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
                timeout=5  # 添加超时
            )
            
            # 解析进程列表并清理
            cleaned_count = 0
            for line in result.stdout.strip().split('\n'):
                if exe_name.lower() in line.lower():
                    parts = line.split(',')
                    if len(parts) >= 2:
                        pid = parts[1].strip('"')
                        try:
                            # 使用 /F (强制) + /T (终止进程树) 参数
                            kill_result = subprocess.run(
                                ['taskkill', '/F', '/T', '/PID', pid],
                                capture_output=True,
                                timeout=5,
                                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
                            )
                            
                            if kill_result.returncode == 0:
                                cleaned_count += 1
                                logger.info(f"[OCR] 已终止进程树 (PID={pid})")
                            else:
                                # 可能进程已经退出
                                logger.debug(f"[OCR] taskkill 返回码 {kill_result.returncode} for PID={pid}")
                        except subprocess.TimeoutExpired:
                            logger.warning(f"[OCR] 终止进程超时 (PID={pid})")
                        except Exception as e:
                            logger.warning(f"[OCR] 终止进程失败 (PID={pid}): {e}")
            
            if cleaned_count > 0:
                logger.info(f"[OCR] 已清理 {cleaned_count} 个残留进程")
            
            # 额外：使用 taskkill /F /IM 作为二次清理（防止遗漏）
            try:
                subprocess.run(
                    ['taskkill', '/F', '/T', '/IM', exe_name],
                    capture_output=True,
                    timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
                )
            except Exception:
                pass  # 忽略二次清理的错误
                
        except subprocess.TimeoutExpired:
            logger.warning("[OCR] 清理进程超时")
        except Exception as e:
            logger.error(f"[OCR] 清理残留进程失败: {e}", exc_info=True)
    
    def _is_process_alive(self) -> bool:
        """检查子进程是否存活
        
        Returns:
            进程是否仍在运行
        """
        if not self.ocr or not hasattr(self.ocr, 'ret') or not self.ocr.ret:
            return False
        return self.ocr.ret.poll() is None  # None = 进程仍在运行
    
    def _ensure_engine_ready(self) -> bool:
        """确保引擎处于可用状态
        
        检查引擎状态，如果子进程已损坏则重新初始化。
        这对于快速中断-重新识别场景很重要。
        
        Returns:
            引擎是否可用
        """
        # ★★★ 关键：如果正在关闭，不初始化引擎 ★★★
        if self._shutting_down or _global_shutting_down:
            logger.warning("[OCR] 程序正在关闭，不初始化引擎")
            return False
        
        if not self._initialized:
            return self.initialize()
        
        # 检查子进程是否还活着
        if not self._is_process_alive():
            logger.info("[OCR] 检测到子进程已损坏，准备重新初始化...")
            self._initialized = False
            self.ocr = None
            return self.initialize()
        
        return True
    
    def _terminate_ocr_process(self):
        """处理 OCR 子进程异常（超时或崩溃）

        注意：本方法不会强制杀死进程！
        - 超时：只标记引擎需要重新初始化，不杀死子进程
        - 进程崩溃：子进程已退出，无需处理

        为什么不杀死进程？
        - PaddleOCR-json 管道模式是顺序处理的，杀进程可能影响其他任务
        - 下次识别时会检查子进程状态，如果崩溃会自动重新初始化
        """
        logger.warning("[OCR] OCR 子进程异常，标记引擎需要重新初始化")
        if self.ocr and hasattr(self.ocr, 'ret') and self.ocr.ret:
            try:
                proc = self.ocr.ret
                if proc.poll() is None:  # 进程还在运行
                    # 进程还在运行，不杀死它
                    # 只断开引用，让下次识别时重新初始化
                    logger.info("[OCR] 子进程仍在运行，不强制终止，将在下次识别时重新初始化")
            except Exception as e:
                logger.warning(f"[OCR] 检查子进程状态时出错: {e}")

        # 标记引擎需要重新初始化
        self._initialized = False
        self.ocr = None
    
    def _request_cancel(self):
        """请求取消识别（优雅取消）
        
        设置取消标志，让当前任务完成后自动停止后续任务。
        不会终止子进程，引擎可以继续使用。
        """
        logger.info("[OCR] 请求优雅取消识别")
        self._force_cancel = True
    
    def _check_cancel(self) -> bool:
        """检查是否请求了取消
        
        Returns:
            True 表示需要取消，False 表示继续
        """
        return getattr(self, '_force_cancel', False)
    
    def _run_with_interrupt_check(
        self,
        image_path: str,
        is_interrupted: Optional[Callable[[], bool]] = None,
        poll_interval: float = 0.1,
        timeout: float = 120.0,
    ) -> Dict[str, Any]:
        """在守护子线程里执行 ocr.run()，主线程通过 queue.get(timeout) 等待结果。

        优雅中断机制（PaddleOCR-json 管道模式专用）：
        - PaddleOCR-json 管道模式是同步阻塞的，子进程顺序处理任务
        - 没有官方的优雅中断接口，只能等待子进程完成当前任务
        - 检测到中断后，等待当前任务完成，然后返回取消结果
        - 不杀死子进程，引擎可以继续使用

        Args:
            image_path:     要识别的图片路径
            is_interrupted: 中断检查回调，返回 True 表示需要中断
            poll_interval:  阻塞等待的超时时间（秒），每次超时即检查 is_interrupted
            timeout:        单张图片最长等待秒数，超时视为引擎故障

        Returns:
            正常时返回 OCR 识别结果字典
            取消时返回 {"code": 100, "data": [...], "texts": [...], "success": True, "cancelled": True}
            超时时返回 {"code": 999, "data": "...", "success": False}
            异常时抛出 OCREngineError

        Raises:
            OCREngineError: 引擎超时或进程异常
        """
        result_queue: queue.Queue = queue.Queue()

        def _worker():
            try:
                logger.debug(f"[OCR] 守护线程开始执行 ocr.run({os.path.basename(image_path)})")
                # 管道引擎不支持并发，必须串行化访问
                # 同时在此处原子地检查引擎是否就绪，避免 TOCTOU 竞态
                with self._engine_lock:
                    if not self._ensure_engine_ready():
                        logger.error("[OCR] 守护线程：引擎初始化失败")
                        result_queue.put(("err", OCREngineError("OCR 引擎初始化失败，请检查引擎状态")))
                        return
                    res = self.ocr.run(image_path)
                logger.debug(f"[OCR] 守护线程 ocr.run() 返回，code={res.get('code')}")
                result_queue.put(("ok", res))
            except Exception as exc:
                logger.debug(f"[OCR] 守护线程异常: {exc}")
                result_queue.put(("err", exc))

        t = threading.Thread(target=_worker, daemon=True, name=f"OCR-daemon-{os.path.basename(image_path)}")
        t.start()
        logger.debug(f"[OCR] 守护线程已启动，线程ID={t.ident}")

        start_time = time.time()
        was_interrupted = False  # 记录是否曾经被中断

        while True:
            # 注意：不在这里检查中断！
            # PaddleOCR-json 管道模式不支持真正的优雅中断
            # 如果在这里检查并立即返回，子进程仍在处理，导致：
            # 1. 子进程被占用，无法处理新任务
            # 2. 用户快速启动新识别时会失败
            # 所以必须等待当前任务完成

            # 阻塞等待结果，最长等待 poll_interval 秒
            try:
                status, payload = result_queue.get(timeout=poll_interval)
                if status == "ok":
                    logger.debug("[OCR] 收到识别结果")

                    # ★★★ 关键：任务完成后才检查中断标志 ★★★
                    # 这样子进程已经完成当前任务，可以继续处理新任务
                    try:
                        if is_interrupted and is_interrupted():
                            was_interrupted = True
                            logger.info("[OCR] 任务完成后检测到中断请求，标记为取消")
                    except Exception as e:
                        logger.warning(f"[OCR] 中断检查异常: {e}")

                    if was_interrupted:
                        # 任务被取消，但仍然返回结果（子进程已完成）
                        # 标记为 cancelled，让调用方决定如何处理
                        payload["cancelled"] = True
                        return payload
                    else:
                        return payload
                else:
                    logger.debug("[OCR] 收到守护线程异常，重新抛出")
                    raise payload
            except queue.Empty:
                # 超时，检查总超时
                elapsed = time.time() - start_time

                # 检查中断标志（只在超时时检查，不主动中断）
                try:
                    if is_interrupted and is_interrupted():
                        was_interrupted = True
                        logger.info("[OCR] 超时检测到中断请求，继续等待任务完成")
                        # 不立即返回，继续等待子进程完成
                except Exception as e:
                    logger.warning(f"[OCR] 中断检查异常: {e}")

                if elapsed >= timeout:
                    logger.error(f"[OCR] 超时 {timeout}s")
                    # 超时不算子进程崩溃，只是任务太慢
                    # 不杀死子进程，只返回超时错误
                    raise OCREngineError(f"OCR 引擎处理超时（>{timeout}s）")

    @staticmethod
    def get_code_message(code: int) -> str:
        """获取状态码说明
        
        Args:
            code: OCR 返回的状态码
            
        Returns:
            状态码对应的文字说明
        """
        return OCR_CODES.get(code, f"未知状态码: {code}")
    
    @error_handling(ErrorType.OCR_ENGINE, "OCR 引擎初始化失败")
    def initialize(self) -> bool:
        """初始化 OCR 引擎
        
        Returns:
            是否初始化成功
        """
        # ★★★ 关键：如果正在关闭，不初始化引擎 ★★★
        if self._shutting_down or _global_shutting_down:
            logger.warning("[OCR] 程序正在关闭，不初始化引擎")
            return False
        
        # 加锁防止多线程同时创建多个子进程，并避免 TOCTOU 竞态条件
        with self._engine_lock:
            # 双重检查：其他线程可能已初始化完成
            if self._initialized and self._is_process_alive():
                return True

            # 进程已不存在，需要重新初始化
            if self._initialized and not self._is_process_alive():
                logger.info("[OCR] 子进程已终止，准备重新初始化...")
                self._initialized = False
                self.ocr = None

            # 验证路径存在性
            if not Path(self.exe_path).exists():
                raise OCREngineError(f"OCR 引擎文件不存在: {self.exe_path}")

            if not Path(self.models_path).exists():
                raise OCREngineError(f"模型文件夹不存在: {self.models_path}")

            # 清理残留进程
            self._cleanup_residual_processes()

            _t0 = time.time()
            logger.info(f"[OCR] 正在初始化引擎: {self.exe_path}")
            self.ocr = GetOcrApi(
                self.exe_path,
                self.models_path,
                self.args,
                ipcMode="pipe"
            )
            self._initialized = True
            _elapsed = time.time() - _t0
            logger.info(f"[OCR] 引擎初始化成功，耗时 {_elapsed:.1f}s")
            return True
    
    def is_ready(self) -> bool:
        """
        检查 OCR 引擎是否已就绪
        
        Returns:
            bool: 引擎已初始化返回 True，否则返回 False
        """
        return self._initialized and self.ocr is not None
    
    def get_status(self) -> str:
        """
        获取 OCR 引擎详细状态
        
        Returns:
            str: 'ready' | 'not_initialized' | 'error'
        """
        if self._initialized and self.ocr is not None:
            # 检查进程是否还活着
            if self._is_process_alive():
                return 'ready'
            else:
                self._initialized = False
                return 'error'
        else:
            return 'not_initialized'
    
    def _get_image_hash(self, image_path: str) -> str:
        """
        计算图片的哈希值，用于缓存
        
        Args:
            image_path: 图片路径
            
        Returns:
            图片的哈希值
        """
        try:
            with open(image_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            logger.error(f"[OCR] 计算图片哈希值失败: {e}")
            return str(os.path.getmtime(image_path))
    
    def _get_cache_key(self, image_path: str) -> str:
        """
        获取缓存键
        
        Args:
            image_path: 图片路径
            
        Returns:
            缓存键
        """
        image_hash = self._get_image_hash(image_path)
        return f"{image_hash}_{self.language}"
    
    def _check_cache(self, image_path: str) -> Optional[Dict[str, Any]]:
        """
        检查缓存
        
        Args:
            image_path: 图片路径
            
        Returns:
            缓存的识别结果，如果没有缓存则返回 None
        """
        cache_key = self._get_cache_key(image_path)
        if cache_key in _ocr_cache:
            logger.debug(f"[OCR] 命中缓存")
            return _ocr_cache[cache_key]
        return None
    
    def _update_cache(self, image_path: str, result: Dict[str, Any]) -> None:
        """
        更新缓存
        
        Args:
            image_path: 图片路径
            result: 识别结果
        """
        if not result.get("success"):
            return
        
        cache_key = self._get_cache_key(image_path)
        
        # 检查缓存大小
        if len(_ocr_cache) >= MAX_CACHE_SIZE:
            # 删除最旧的缓存
            oldest_key = next(iter(_ocr_cache))
            del _ocr_cache[oldest_key]
        
        _ocr_cache[cache_key] = result
        logger.debug(f"[OCR] 更新缓存，当前缓存大小: {len(_ocr_cache)}")
    
    @error_handling(ErrorType.OCR_ENGINE, "OCR 识别失败")
    def recognize(self, image_path: str, is_interrupted: Optional[Callable[[], bool]] = None) -> Dict[str, Any]:
        """
        识别图片中的文字
        
        Args:
            image_path: 图片路径
            is_interrupted: 中断检查函数，返回 True 表示需要中断
            
        Returns:
            识别结果 {"code": int, "data": list/str, "texts": list, "success": bool}
        """
        # 验证输入
        if not image_path or not Path(image_path).exists():
            raise OCREngineError(f"图片路径不存在: {image_path}")
        
        logger.debug(f"[OCR] 开始识别: {image_path}")
        
        # 检查缓存
        cached_result = self._check_cache(image_path)
        if cached_result:
            # 即使从缓存返回，也要检查中断状态
            if is_interrupted and is_interrupted():
                raise OCREngineError("识别任务已被中断")
            logger.debug(f"[OCR] 命中缓存，跳过引擎调用: {image_path}")
            return cached_result
        
        # 引擎就绪检查已移至 _run_with_interrupt_check._worker 内部（加锁原子操作）
        # 此处不再需要显式检查，避免 TOCTOU 竞态条件
        logger.debug(f"[OCR] 开始识别，引擎状态: initialized={self._initialized}")
        
        # 定义可重试的错误码（引擎相关错误，重新初始化后可能恢复）
        RETRYABLE_CODES = {901, 902, 903, 904, 998, 999}
        
        _recog_start = time.time()
        
        retry = 0
        while retry < self.retry_count:
            try:
                result = self._run_with_interrupt_check(
                    image_path, is_interrupted=is_interrupted
                )
                
                # 打印原始返回数据（用于调试）
                logger.debug(f"[OCR] 原始返回: code={result.get('code')}, data={result.get('data')}")
                
                code = result.get("code", -1)
                
                # 检查是否是可重试的错误码
                if code in RETRYABLE_CODES:
                    retry += 1
                    logger.warning(f"[OCR] 可重试错误: code={code}, {self.get_code_message(code)}, 重试 {retry}/{self.retry_count}")
                    
                    # ★★★ 关键：如果正在关闭，不重试，直接返回错误 ★★★
                    if self._shutting_down or _global_shutting_down:
                        logger.warning(f"[OCR] 程序正在关闭，不再重试，直接返回错误")
                        result["texts"] = []
                        result["success"] = False
                        return result
                    
                    if retry >= self.retry_count:
                        # 已用完重试次数，返回错误结果
                        result["texts"] = []
                        result["success"] = False
                        # ★ 推送重试失败事件
                        if self._emit:
                            self._emit("engine:event", type="retry_failed", retry=retry,
                                      reason=self.get_code_message(code))
                        return result
                    
                    # ★ 推送崩溃恢复事件（即将重试）
                    if self._emit:
                        self._emit("engine:event", type="crash_recovered", retry=retry)
                    
                    # 标记引擎需要重新初始化
                    logger.info(f"[OCR] 标记引擎需要重新初始化（错误码 {code}）")
                    self._initialized = False
                    self.ocr = None
                    
                    # 等待一段时间后重试（指数退避）
                    time.sleep(0.5 * retry)
                    continue
                
                # ★★★ 重要：只有 code=100 才提取文本和标记成功 ★★★
                # 这是引擎的强制要求
                # code=101: 未识别到文字（成功但无文本）
                # 其他 code: 识别失败
                
                texts = []
                
                if code == 100:
                    # 只有 code=100 时才提取文本
                    if result.get("data"):
                        data = result["data"]
                        if isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict) and "text" in item:
                                    texts.append(item["text"])
                    
                    result["texts"] = texts
                    result["success"] = True
                    _recog_elapsed = time.time() - _recog_start
                    logger.info(f"[OCR] 识别成功，code={code}，共 {len(texts)} 行文本，耗时 {_recog_elapsed:.1f}s")
                    # 更新缓存
                    self._update_cache(image_path, result)
                else:
                    # code≠100，不提取文本，标记为失败
                    result["texts"] = []
                    result["success"] = False
                    
                    # 只有在非取消时才记录警告
                    if not result.get('cancelled'):
                        logger.warning(f"[OCR] 识别失败: code={code}, {self.get_code_message(code)}")
                        logger.debug(f"[OCR] 识别失败详情: data={result.get('data')}")
                
                return result
                
            except Exception as e:
                # 检查中断
                if is_interrupted and is_interrupted():
                    raise OCREngineError("识别任务已被中断")
                
                # ★★★ 关键：如果正在关闭，不重试，直接抛出异常 ★★★
                if self._shutting_down or _global_shutting_down:
                    logger.warning(f"[OCR] 程序正在关闭，不再重试，直接抛出异常")
                    raise OCREngineError(f"识别过程出错（程序正在关闭）: {str(e)}", e)
                    
                retry += 1
                logger.debug(f"[OCR] 重试 {retry}/{self.retry_count}: {e}")
                if retry >= self.retry_count:
                    # ★ 推送重试失败事件
                    if self._emit:
                        self._emit("engine:event", type="retry_failed", retry=retry, reason=str(e))
                    raise OCREngineError(f"识别过程出错: {str(e)}", e)
                # ★ 推送崩溃恢复事件（即将重试）
                if self._emit:
                    self._emit("engine:event", type="crash_recovered", retry=retry)
                # 等待一段时间后重试
                time.sleep(0.5)
    
    @error_handling(ErrorType.OCR_ENGINE, "OCR 字节流识别失败")
    def recognize_bytes(self, image_bytes: bytes) -> Dict[str, Any]:
        """
        识别图片字节流
        
        Args:
            image_bytes: 图片字节数据
            
        Returns:
            识别结果
        """
        if not image_bytes:
            raise OCREngineError("图片字节数据为空")
        
        retry = 0
        while retry < self.retry_count:
            try:
                # 管道引擎不支持并发，必须串行化访问
                # 同时在此处原子地检查引擎是否就绪，避免 TOCTOU 竞态
                with self._engine_lock:
                    if not self._ensure_engine_ready():
                        raise OCREngineError("OCR 引擎初始化失败，请检查引擎状态")
                    result = self.ocr.runBytes(image_bytes)
                
                # 提取纯文本
                texts = []
                if result.get("code") == 100 and result.get("data"):
                    for item in result["data"]:
                        if isinstance(item, dict) and "text" in item:
                            texts.append(item["text"])
                
                result["texts"] = texts
                result["success"] = result.get("code") == 100
                
                if result["success"]:
                    logger.debug(f"[OCR] 字节流识别成功，共 {len(texts)} 行文本")
                
                return result
                
            except Exception as e:
                # ★★★ 关键：如果正在关闭，不重试，直接抛出异常 ★★★
                if self._shutting_down or _global_shutting_down:
                    logger.warning(f"[OCR] 程序正在关闭，不再重试，直接抛出异常")
                    raise OCREngineError(f"字节流识别出错（程序正在关闭）: {str(e)}", e)
                    
                retry += 1
                if retry >= self.retry_count:
                    # ★ 推送重试失败事件
                    if self._emit:
                        self._emit("engine:event", type="retry_failed", retry=retry, reason=str(e))
                    raise OCREngineError(f"字节流识别出错: {str(e)}", e)
                # ★ 推送崩溃恢复事件（即将重试）
                if self._emit:
                    self._emit("engine:event", type="crash_recovered", retry=retry)
                # 等待一段时间后重试
                time.sleep(0.5)

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
                needs_slice = img.height > slice_height
                if needs_slice:
                    logger.info(f"[OCR] 图片高度 {img.height}px 超过阈值 {slice_height}px，将使用切片识别")
                return needs_slice
        except Exception as e:
            logger.error(f"[OCR] 检查图片尺寸失败: {e}")
            return False
    
    def recognize_auto(self, image_path: str, config=None, 
                      progress_callback: Optional[Callable[[int, int], None]] = None, 
                      is_interrupted: Optional[Callable[[], bool]] = None) -> Dict[str, Any]:
        """自动判断并执行识别（普通图或超长图切片）
        
        Args:
            image_path: 图片路径
            config: 配置对象（可选），需提供 get_slice_height() 和 get_slice_overlap() 方法
            progress_callback: 切片进度回调函数 (current, total)
            is_interrupted: 中断检查函数，返回 True 表示需要中断
            
        Returns:
            识别结果字典
        """
        # 检查中断
        if is_interrupted and is_interrupted():
            raise OCREngineError("识别任务已被中断")
            
        # 获取切片参数及开关
        long_image_mode = True  # 默认开启
        if config:
            try:
                slice_height = config.get_slice_height()
                overlap = config.get_slice_overlap()
                long_image_mode = config.get_long_image_mode()
            except AttributeError:
                logger.warning("配置对象缺少必要方法，使用默认切片参数")
                slice_height = 2000
                overlap = 100
        else:
            slice_height = 2000
            overlap = 100
        
        # 自动判断是否需要切片（须检查 long_image_mode 开关）
        if long_image_mode and self.should_use_slice(image_path, slice_height):
            logger.info("[OCR] 开始超长图切片识别")
            return self.recognize_long_image(
                image_path,
                slice_height=slice_height,
                overlap=overlap,
                progress_callback=progress_callback,
                is_interrupted=is_interrupted
            )
        else:
            return self.recognize(image_path, is_interrupted=is_interrupted)

    @error_handling(ErrorType.OCR_ENGINE, "OCR 超长图识别失败")
    def recognize_long_image(self, image_path: str, slice_height: int = 2000, 
                             overlap: int = 100, progress_callback: Optional[Callable[[int, int], None]] = None, 
                             is_interrupted: Optional[Callable[[], bool]] = None) -> Dict[str, Any]:
        """
        超长图切片识别：将超高图片切成若干块分别识别，再合并结果。

        Args:
            image_path: 图片路径
            slice_height: 每块的高度（像素），默认 2000
            overlap: 相邻切片的重叠像素，防止文字被切断，默认 100
            progress_callback: 进度回调函数，接收 (current, total) 参数
            is_interrupted: 中断检查函数，返回 True 表示需要中断

        Returns:
            与 recognize() 格式相同的识别结果
            {"code": 100, "data": [...], "texts": [...], "success": True}
        """
        # 检查中断
        if is_interrupted and is_interrupted():
            raise OCREngineError("识别任务已被中断")
            
        # 检查缓存
        cached_result = self._check_cache(image_path)
        if cached_result:
            # 即使从缓存返回，也要检查中断状态
            if is_interrupted and is_interrupted():
                raise OCREngineError("识别任务已被中断")
            return cached_result
            
        try:
            from PIL import Image
        except ImportError:
            raise OCREngineError("Pillow 库未安装，无法进行切片识别")

        # ── 读取图片 ────────────────────────────────────────────────
        try:
            img = Image.open(image_path)
        except Exception as e:
            raise OCREngineError(f"图片打开失败: {str(e)}", e)

        img_w, img_h = img.size

        # 高度不超过阈值时直接识别，无需切片
        if img_h <= slice_height:
            logger.info(f"[OCR] 图片高度 {img_h}px 未超过阈值，使用普通识别")
            img.close()
            result = self.recognize(image_path, is_interrupted=is_interrupted)
            # 更新缓存
            self._update_cache(image_path, result)
            return result

        logger.info(f"[OCR] 开始超长图切片识别: {img_w}×{img_h}, 切片高度={slice_height}, 重叠={overlap}")

        # 计算总切片数（用于进度报告）
        total_slices = 0
        temp_y = 0
        _slice_start = time.time()
        while temp_y < img_h:
            # 检查中断
            if is_interrupted and is_interrupted():
                img.close()
                raise OCREngineError("识别任务已被中断")
                
            total_slices += 1
            y_end = min(temp_y + slice_height, img_h)
            if y_end >= img_h:
                break
            temp_y = y_end - overlap

        logger.info(f"[OCR] 预计切片数: {total_slices}")

        all_data = []   # 合并后的 data 列表（含坐标）
        all_texts = []  # 合并后的纯文本
        y_start = 0
        slice_index = 0

        tmp_files = []  # 记录临时文件，最后统一删除

        try:
            while y_start < img_h:
                # 检查中断
                if is_interrupted and is_interrupted():
                    img.close()
                    # 清理临时文件
                    for f in tmp_files:
                        try:
                            os.remove(f)
                        except Exception:
                            pass
                    raise OCREngineError("识别任务已被中断")
                    
                y_end = min(y_start + slice_height, img_h)
                slice_index += 1

                # 报告进度
                if progress_callback:
                    try:
                        progress_callback(slice_index, total_slices)
                    except Exception as e:
                        logger.warning(f"[OCR] 进度回调执行失败: {e}")

                # 裁剪当前切片
                slice_img = img.crop((0, y_start, img_w, y_end))

                # 检查中断
                if is_interrupted and is_interrupted():
                    img.close()
                    slice_img.close()
                    # 清理临时文件
                    for f in tmp_files:
                        try:
                            os.remove(f)
                        except Exception:
                            pass
                    raise OCREngineError("识别任务已被中断")

                # 写入临时文件（PaddleOCR-json 需要文件路径）
                tmp_fd, tmp_path = tempfile.mkstemp(suffix=".png", prefix="ocr_slice_")
                os.close(tmp_fd)
                tmp_files.append(tmp_path)

                # 检查中断
                if is_interrupted and is_interrupted():
                    img.close()
                    slice_img.close()
                    # 清理临时文件
                    for f in tmp_files:
                        try:
                            os.remove(f)
                        except Exception:
                            pass
                    raise OCREngineError("识别任务已被中断")

                try:
                    # 统一保存为 PNG，避免 RGBA/调色板模式无法写入 JPEG 的问题
                    save_img = slice_img
                    if save_img.mode not in ("RGB", "L"):
                        # RGBA / P(调色板) 等模式先转 RGB
                        save_img = save_img.convert("RGB")
                    save_img.save(tmp_path, format="PNG", optimize=True, compress_level=5)
                except Exception as e:
                    img.close()
                    slice_img.close()
                    # 清理临时文件
                    for f in tmp_files:
                        try:
                            os.remove(f)
                        except Exception:
                            pass
                    raise OCREngineError(f"保存切片失败: {str(e)}", e)
                finally:
                    slice_img.close()

                # 检查中断
                if is_interrupted and is_interrupted():
                    img.close()
                    # 清理临时文件
                    for f in tmp_files:
                        try:
                            os.remove(f)
                        except Exception:
                            pass
                    raise OCREngineError("识别任务已被中断")

                # 识别切片（带重试机制，使用可中断调用）
                retry = 0
                slice_result = None
                while retry < self.retry_count:
                    try:
                        # 守护线程 + 轮询：每 100ms 检查一次中断标志，响应快
                        slice_result = self._run_with_interrupt_check(
                            tmp_path, is_interrupted=is_interrupted
                        )
                        break
                    except OCREngineError:
                        # 中断或超时异常直接向上传播
                        raise
                    except Exception as e:
                        retry += 1
                        if retry >= self.retry_count:
                            raise OCREngineError(f"切片 {slice_index} 识别异常: {str(e)}", e)
                        time.sleep(0.3)
                
                if not slice_result:
                    continue

                # 检查是否是取消结果
                if slice_result.get("cancelled") or slice_result.get("code") == 998:
                    logger.info(f"[OCR] 切片 {slice_index} 识别被取消")
                    # 检查是否完全取消（没有收集到任何数据）
                    if not all_data:
                        raise OCREngineError("识别任务已被取消")
                    # 有部分数据，返回已收集的结果
                    result = {
                        "code": 100, 
                        "data": all_data, 
                        "texts": all_texts, 
                        "success": True,
                        "cancelled": True
                    }
                    self._update_cache(image_path, result)
                    return result

                if slice_result.get("code") == 100:
                    for item in slice_result.get("data", []):
                        # 坐标修正：将切片内的 y 坐标加回原图偏移
                        adjusted = dict(item)
                        if "box" in adjusted and adjusted["box"]:
                            adjusted["box"] = [
                                [pt[0], pt[1] + y_start]
                                for pt in adjusted["box"]
                            ]
                        all_data.append(adjusted)
                        all_texts.append(item.get("text", ""))
                elif slice_result.get("code") == 101:
                    # 当前切片无文字，正常跳过
                    logger.debug(f"[OCR] 切片 {slice_index} 未识别到文字")
                else:
                    logger.warning(f"[OCR] 切片 {slice_index} 识别异常: code={slice_result.get('code')}")

                # 检查是否请求了取消
                if slice_result.get("cancelled") or slice_result.get("code") == 998:
                    logger.info("[OCR] 识别已取消，停止后续切片")
                    result = {
                        "code": 100, 
                        "data": all_data, 
                        "texts": all_texts, 
                        "success": True,
                        "cancelled": True
                    }
                    if all_data:
                        self._update_cache(image_path, result)
                    return result

                # 下一切片起始位置（减去重叠区域）
                if y_end >= img_h:
                    break
                y_start = y_end - overlap

        finally:
            # 确保关闭图片
            img.close()
            
            # 删除临时文件
            cleaned = 0
            for f in tmp_files:
                try:
                    os.remove(f)
                    cleaned += 1
                except Exception as e:
                    logger.warning(f"[OCR] 删除临时文件失败 {f}: {e}")
            
            if cleaned > 0:
                logger.debug(f"[OCR] 已清理 {cleaned} 个临时文件")

        result = {}
        if all_data:
            _slice_elapsed = time.time() - _slice_start
            logger.info(f"[OCR] 切片识别完成，共 {total_slices} 片，{len(all_texts)} 行文本，总耗时 {_slice_elapsed:.1f}s")
            result = {"code": 100, "data": all_data, "texts": all_texts, "success": True}
            # 更新缓存
            self._update_cache(image_path, result)
        else:
            result = {"code": 101, "data": "未识别到文字", "texts": [], "success": False}
        
        return result
    
    def set_language(self, language: str) -> bool:
        """
        切换识别语言（按官方文档，完全重建 OCR 引擎）
        
        Args:
            language: 语言名称，对应 LANGUAGES 中的键
            
        Returns:
            是否切换成功
        """
        if language not in LANGUAGES:
            logger.error(f"[OCR] 不支持的语言: {language}")
            return False
        
        if self.language == language:
            logger.debug(f"[OCR] 语言未变化: {language}")
            return True
        
        logger.info(f"[OCR] 切换语言: {self.language} -> {language}")
        self.language = language
        # 更新 config_path
        self.args["config_path"] = os.path.join(self.models_path, LANGUAGES[language])
        
        # 完全重建 OCR 引擎（官方推荐方式）
        return self._reinit_engine()
    
    def _reinit_engine(self) -> bool:
        """重建 OCR 引擎

        Returns:
            是否重建成功
        """
        with self._engine_lock:
            # 关闭旧引擎
            if self.ocr:
                try:
                    self.ocr.exit()
                except Exception as e:
                    logger.warning(f"[OCR] 关闭旧引擎时出错: {e}")
            self.ocr = None
            self._initialized = False

            # 清理残留进程
            self._cleanup_residual_processes()

            # 重新初始化
            try:
                logger.info(f"[OCR] 正在重建引擎，语言: {self.language}")
                self.ocr = GetOcrApi(
                    self.exe_path,
                    self.models_path,
                    self.args,
                    ipcMode="pipe"
                )
                self._initialized = True
                logger.info(f"[OCR] 引擎已重建，语言: {self.language}")
                return True
            except Exception as e:
                logger.error(f"[OCR] 引擎重建失败: {e}", exc_info=True)
                self._initialized = False
                return False
    
    def update_args(self, new_args: Dict[str, Any]) -> None:
        """更新 OCR 参数
        
        Args:
            new_args: 新的参数字典
        """
        self.args.update(new_args)
        self._initialized = False  # 需要重新初始化
        logger.info("[OCR] 参数已更新，将在下次识别时重新初始化")
    
    def begin_shutdown(self) -> None:
        """设置关闭标志（非阻塞）
        
        供 closeEvent() 调用：立即设置标志，不等待锁，不阻塞主线程。
        同时取消 PPOCR_api.exit() 的 atexit 注册，防止它在优雅关闭前强杀进程。
        """
        logger.info("[OCR] begin_shutdown() 被调用，设置关闭标志")
        self._shutting_down = True
        global _global_shutting_down
        _global_shutting_down = True
        
        # ★ 推送引擎关闭事件
        if self._emit:
            self._emit("engine:status", type="shutting_down")
        
        # ★ 关键：取消 PPOCR_api.exit() 的 atexit 注册
        # PPOCR_api.exit() 在 atexit 中后注册先执行（LIFO），会在 _global_emergency_cleanup 之前
        # 强杀进程并把 self.ret 设为 None，导致优雅关闭无法执行
        if self.ocr and hasattr(self.ocr, 'exit'):
            try:
                atexit.unregister(self.ocr.exit)
                logger.debug("[OCR] 已取消 PPOCR_api.exit() 的 atexit 注册")
            except Exception:
                pass
        
        logger.info(f"[OCR] 关闭标志已设置，self.ocr={self.ocr is not None}, _initialized={self._initialized}")
        logger.info("[OCR] begin_shutdown() 完成，等待 atexit 执行优雅关闭")

    def close(self) -> None:
        """关闭 OCR 引擎并释放资源（阻塞版，会等待锁释放）
        
        优先使用优雅关闭（让引擎自行退出），失败后强制终止。
        由 atexit / __del__ 调用，此时识别线程已退出，不存在死锁。
        """
        logger.info("[OCR] close() 方法被调用")
        # 设置关闭标志，防止重试逻辑重新启动引擎
        self._shutting_down = True
        global _global_shutting_down
        _global_shutting_down = True

        # 取消 atexit 注册，防止 _global_emergency_cleanup 再次被触发
        try:
            atexit.unregister(_global_emergency_cleanup)
            logger.debug("[OCR] 已取消 atexit 紧急清理注册")
        except Exception:
            pass

        logger.info("[OCR] 等待引擎锁...")
        with self._engine_lock:
            logger.info("[OCR] 开始关闭引擎...")

            # 1. 尝试通过 self.ocr 优雅关闭
            if self.ocr and hasattr(self.ocr, 'ret') and self.ocr.ret:
                proc = self.ocr.ret
                try:
                    # 取消 atexit 注册，防止 Python 退出时再次调用 exit()
                    atexit.unregister(self.ocr.exit)

                    # 向 stdin 写入 exit 指令（官方优雅关闭方式，stdin 是二进制流）
                    if not proc.stdin.closed:
                        logger.info("[OCR] 发送优雅关闭指令 (exit\\n)...")
                        proc.stdin.write(b"exit\n")
                        proc.stdin.flush()
                        proc.stdin.close()

                    # 等待进程自行退出（最多5秒）
                    logger.info("[OCR] 等待引擎自行退出...")
                    try:
                        proc.wait(timeout=5)
                        logger.info("[OCR] 引擎已自行退出（优雅关闭成功）")
                        self.ocr = None
                        self._initialized = False
                        logger.info("[OCR] 引擎资源已释放")
                        return
                    except subprocess.TimeoutExpired:
                        logger.warning("[OCR] 引擎未能在5秒内退出，转为强制终止...")
                except Exception as e:
                    logger.warning(f"[OCR] 优雅关闭失败: {e}，转为强制终止...")
            else:
                # self.ocr 为 None（可能在重试时被清空），但进程可能还在运行
                logger.info("[OCR] ocr 实例已为 None，检查是否有残留进程...")

            # 2. 强制终止（优雅关闭超时 或 ocr 已为 None 时的兜底）
            if sys.platform == 'win32':
                for proc_name in ['PaddleOCR-json.exe']:
                    try:
                        check = subprocess.run(
                            ['tasklist', '/FI', f'IMAGENAME eq {proc_name}', '/NH', '/FO', 'CSV'],
                            capture_output=True, text=True, timeout=5,
                            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
                        )
                        if proc_name in check.stdout:
                            logger.warning(f"[OCR] 发现残留进程 {proc_name}，强制终止...")
                            kill_result = subprocess.run(
                                ['taskkill', '/F', '/T', '/IM', proc_name],
                                capture_output=True, text=True, timeout=10,
                                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
                            )
                            if kill_result.returncode == 0:
                                logger.info(f"[OCR] 进程 {proc_name} 已强制终止")
                            else:
                                logger.warning(f"[OCR] taskkill 返回码: {kill_result.returncode}")
                        else:
                            logger.info(f"[OCR] 未发现残留进程 {proc_name}，无需强制终止")
                    except Exception as e:
                        logger.warning(f"[OCR] 检查/终止进程时出错: {e}")
            else:
                # Linux/Mac 兜底
                if self.ocr and hasattr(self.ocr, 'ret') and self.ocr.ret:
                    try:
                        self.ocr.ret.kill()
                        self.ocr.ret.wait(timeout=2)
                    except Exception:
                        pass

            # 3. 清理状态
            self.ocr = None
            self._initialized = False
            logger.info("[OCR] 引擎资源已释放")
    
    def shutdown(self) -> None:
        """强制关闭引擎（公开接口，供外部调用）
        
        与 close() 的区别：会额外清理残留进程。
        """
        logger.info("[OCR] 强制关闭引擎...")
        # 设置关闭标志（close() 也会设置，这里双重保险）
        self._shutting_down = True
        global _global_shutting_down
        _global_shutting_down = True
        
        self.close()
        
        # 额外清理：确保没有残留进程
        try:
            self._cleanup_residual_processes()
        except Exception as e:
            logger.warning(f"[OCR] 清理残留进程时出错: {e}")
    
    @staticmethod
    def emergency_cleanup():
        """
        独立资源回收方法（不依赖 TaskManager）
        
        处理以下场景：
        1. 用户强行终止（任务管理器结束进程）
        2. 程序错误意外退出（未捕获的异常）
        3. 用户强行关闭程序（Alt+F4、点击X按钮）
        
        此方法可以直接调用，无需通过 TaskManager 调度。
        """
        # 检查全局关闭标志，如果正在关闭则直接返回（避免重复清理）
        global _global_shutting_down
        if _global_shutting_down:
            logger.debug("[OCR] 程序正在关闭，跳过紧急资源回收")
            return
        
        # 设置全局关闭标志，防止重试逻辑重新启动引擎
        _global_shutting_down = True
        logger.warning("[OCR] 执行紧急资源回收...")
        
        try:
            # 定义要清理的进程名列表
            process_names = ['PaddleOCR-json.exe', 'PaddleOCR-json']
            
            if os.name == 'nt':
                # Windows: 使用 taskkill /F /T 终止进程树
                for proc_name in process_names:
                    try:
                        # 先检查进程是否存在
                        result = subprocess.run(
                            ['tasklist', '/FI', f'IMAGENAME eq {proc_name}', '/NH', '/FO', 'CSV'],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        
                        if proc_name in result.stdout:
                            logger.warning(f"[OCR] 发现残留进程 {proc_name}，正在终止（含子进程）...")
                            
                            # 使用 /F (强制) + /T (终止进程树) 参数
                            kill_result = subprocess.run(
                                ['taskkill', '/F', '/T', '/IM', proc_name],
                                capture_output=True,
                                text=True,
                                timeout=10
                            )
                            
                            if kill_result.returncode == 0:
                                logger.info(f"[OCR] 进程 {proc_name} 及其子进程已终止")
                            else:
                                logger.warning(f"[OCR] taskkill 返回码: {kill_result.returncode}, stderr: {kill_result.stderr}")
                                
                    except subprocess.TimeoutExpired:
                        logger.error(f"[OCR] taskkill 超时: {proc_name}")
                    except Exception as e:
                        logger.error(f"[OCR] 终止进程 {proc_name} 时出错: {e}")
                
                # 额外：使用 wmic 作为备选方案（更彻底）
                try:
                    logger.info("[OCR] 使用 wmic 二次清理...")
                    for proc_name in process_names:
                        subprocess.run(
                            ['wmic', 'process', 'where', f'name="{proc_name}"', 'delete'],
                            capture_output=True,
                            timeout=5
                        )
                except Exception as e:
                    logger.debug(f"[OCR] wmic 清理失败（可忽略）: {e}")
                    
            else:
                # Linux/Mac: 使用 pkill -9
                for proc_name in process_names:
                    try:
                        result = subprocess.run(
                            ['pgrep', '-f', proc_name],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        
                        if result.stdout.strip():
                            pids = result.stdout.strip().split('\n')
                            for pid in pids:
                                try:
                                    pid_int = int(pid)
                                    logger.warning(f"[OCR] 发现残留进程 (pid={pid_int})，正在终止...")
                                    os.kill(pid_int, signal.SIGKILL)
                                except Exception as e:
                                    logger.warning(f"[OCR] 终止进程 {pid_int} 失败: {e}")
                    except Exception as e:
                        logger.error(f"[OCR] 查找/终止进程 {proc_name} 时出错: {e}")
        
        except Exception as e:
            logger.error(f"[OCR] 紧急资源回收失败: {e}", exc_info=True)
        
        logger.info("[OCR] 紧急资源回收完成")

        # ★ 同步状态：进程已被清理，标记引擎为未初始化
        if _ocr_engine is not None:
            _ocr_engine._initialized = False
            _ocr_engine.ocr = None
            logger.info("[OCR] 引擎状态已重置为未初始化")
    
    def __del__(self) -> None:
        """析构函数 - 确保资源被释放"""
        try:
            self.close()
        except Exception:
            pass


# 全局 OCR 引擎实例（使用懒加载和线程安全）
_ocr_engine: Optional[OCREngine] = None
_engine_lock = None


def _get_lock():
    """获取线程锁（延迟初始化）"""
    global _engine_lock
    if _engine_lock is None:
        import threading
        _engine_lock = threading.Lock()
    return _engine_lock


def get_ocr_engine() -> OCREngine:
    """获取全局 OCR 引擎实例（线程安全）
    
    Returns:
        OCR 引擎实例
    """
    global _ocr_engine
    
    if _ocr_engine is None:
        with _get_lock():
            # 双重检查锁定
            if _ocr_engine is None:
                logger.info("[OCR] 创建全局 OCR 引擎实例")
                _ocr_engine = OCREngine()
    
    return _ocr_engine


def reset_ocr_engine(exe_path: Optional[str] = None, models_path: Optional[str] = None, 
                    language: Optional[str] = None, custom_args: Optional[Dict[str, Any]] = None) -> OCREngine:
    """重置并重新初始化 OCR 引擎
    
    Args:
        exe_path: OCR 可执行文件路径
        models_path: 模型文件夹路径
        language: 识别语言
        custom_args: 自定义参数
        
    Returns:
        新的 OCR 引擎实例
    """
    global _ocr_engine
    
    with _get_lock():
        if _ocr_engine:
            logger.info("[OCR] 关闭旧的全局 OCR 引擎实例")
            _ocr_engine.close()
        
        logger.info("[OCR] 创建新的全局 OCR 引擎实例")
        _ocr_engine = OCREngine(exe_path, models_path, language or "简体中文", custom_args)
        return _ocr_engine
# =============================================================================
# 独立资源回收机制（不依赖 TaskManager）
# =============================================================================

def _global_emergency_cleanup():
    """全局清理函数（供 atexit 调用，不依赖 closeEvent）
    
    始终执行：设置关闭标志 → 等待线程释放锁 → 优雅关闭（exit\n） → 兜底强杀
    注意：begin_shutdown() 会提前取消 PPOCR_api.exit() 的 atexit 注册，
          防止它在优雅关闭前强杀进程（atexit LIFO 顺序问题）。
    """
    global _global_shutting_down
    
    # 1. 先设置关闭标志，让识别线程停止重试
    _global_shutting_down = True
    
    # 2. 取消 atexit 注册，防止递归调用
    try:
        atexit.unregister(_global_emergency_cleanup)
    except Exception:
        pass
    
    logger.info("[OCR] atexit: 开始关闭清理...")
    
    # 3. 等待识别线程释放引擎锁（给1秒时间检测到关闭标志）
    time.sleep(1)
    
    # 4. 尝试优雅关闭
    try:
        from api.core_api import _core_api_instance
        engine = _core_api_instance._ocr_engine if _core_api_instance else None
        if engine and engine.ocr and hasattr(engine.ocr, 'ret') and engine.ocr.ret:
            logger.info("[OCR] 等待引擎锁...")
            acquired = engine._engine_lock.acquire(timeout=8)  # 非阻塞，最多等8秒
            try:
                if acquired and engine.ocr.ret:
                    proc = engine.ocr.ret
                    # 取消 PPOCR_api 的 atexit 注册（begin_shutdown 已尝试取消，这里兜底）
                    try:
                        atexit.unregister(engine.ocr.exit)
                    except Exception:
                        pass
                    # 发送优雅关闭指令
                    if not proc.stdin.closed:
                        logger.info("[OCR] 发送优雅关闭指令 (exit\\n)...")
                        proc.stdin.write(b"exit\n")
                        proc.stdin.flush()
                        proc.stdin.close()
                    # 等待退出（5秒）
                    logger.info("[OCR] 等待引擎自行退出...")
                    try:
                        proc.wait(timeout=5)
                        logger.info("[OCR] 引擎已自行退出（优雅关闭成功）")
                        engine.ocr = None
                        engine._initialized = False
                        logging.shutdown()
                        return
                    except subprocess.TimeoutExpired:
                        logger.warning("[OCR] 引擎未能在5秒内退出")
                elif not acquired:
                    logger.warning("[OCR] 无法在8秒内获取引擎锁，跳过优雅关闭")
            finally:
                if acquired:
                    engine._engine_lock.release()
        else:
            logger.info("[OCR] 引擎实例不存在或已关闭")
    except Exception as e:
        logger.warning(f"[OCR] 优雅关闭过程出错: {e}")
    
    # 5. 兜底：强制清理残留进程
    logger.info("[OCR] 执行兜底强制清理...")
    try:
        OCREngine.emergency_cleanup()
    except Exception:
        pass
    
    # 6. 确保所有日志写入文件
    logging.shutdown()

# 1. 注册 atexit 处理程序正常退出
atexit.register(_global_emergency_cleanup)

# 2. 注册 sys.excepthook 处理未捕获异常
_original_excepthook = sys.excepthook

def _ocr_excepthook(exc_type, exc_value, exc_traceback):
    """未捕获异常处理器（仅记录，不触发紧急清理）

    emergency_cleanup 只由 atexit（正常关闭）和 signal（SIGTERM/SIGINT）触发，
    excepthook 不应强制杀进程，因为大多数未捕获异常（如 AttributeError）
    不会导致程序崩溃，Qt 事件循环会继续运行。
    """
    if exc_type and issubclass(exc_type, Exception):
        logger.error("[OCR] 未捕获异常: %s: %s", exc_type.__name__, exc_value, exc_info=(exc_type, exc_value, exc_traceback))

    # 不再调用 emergency_cleanup() —— 非致命异常不应强制杀引擎

    # 调用原始的 excepthook（打印到控制台）
    if _original_excepthook:
        try:
            _original_excepthook(exc_type, exc_value, exc_traceback)
        except Exception:
            pass

sys.excepthook = _ocr_excepthook

# 3. 注册信号处理（Windows: SIGTERM, SIGINT）
def _signal_handler(signum, frame):
    """信号处理器"""
    import signal as sig
    sig_name = {sig.SIGTERM: "SIGTERM", sig.SIGINT: "SIGINT"}.get(signum, f"信号 {signum}")
    
    # 如果程序正在正常关闭，跳过紧急清理（由 atexit 正常路径处理）
    if _global_shutting_down:
        logger.debug(f"[OCR] 收到 {sig_name} 信号，但程序正在关闭，跳过紧急清理")
    else:
        logger.warning(f"[OCR] 收到 {sig_name} 信号，执行紧急清理...")
        OCREngine.emergency_cleanup()
    
    # 重新发送信号给原始处理器
    sig.signal(signum, sig.SIG_DFL)
    if os.name == 'nt':
        import ctypes
        ctypes.windll.kernel32.RaiseException(0xC0000000 | signum, 0, 0, 0)
    else:
        os.kill(os.getpid(), signum)

try:
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)
    logger.info("[OCR] 信号处理已注册（SIGTERM, SIGINT）")
except Exception as e:
    logger.warning(f"[OCR] 注册信号处理失败: {e}")

logger.info("[OCR] 独立资源回收机制已初始化")
