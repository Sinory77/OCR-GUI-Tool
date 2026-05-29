# 结果和历史记录管理器
# 核心层业务逻辑，不依赖任何界面

import hashlib
import json
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from .config import HISTORY_FILE

# 配置日志
logger = logging.getLogger(__name__)

# 导入错误处理模块
from .error_handler import FileOperationError, handle_error, error_handling, ErrorType


class ResultManager:
    """
    识别结果和历史记录管理器
    
    该类负责：
    1. 管理 OCR 识别结果
    2. 维护识别历史记录
    3. 提供结果的格式化和查询
    4. 支持历史记录的增删改查
    5. 管理历史记录的存储和加载
    6. 历史记录 JSON 内嵌 __hash__ 校验头，防止手动篡改
    7. 延迟写入：批量识别时合并写磁盘
    8. 图片哈希缓存：避免图片内容变化但路径不变导致的缓存误命中
    
    使用线程安全的方式确保全局只有一个结果管理器实例
    """
    
    def __init__(self, history_file=None):
        """
        初始化结果管理器
        
        Args:
            history_file: 历史记录文件路径
        """
        self.history_file = Path(history_file) if history_file else HISTORY_FILE
        # current_results: image_path -> {'result': ocr_result, 'image_hash': str}
        self.current_results = {}
        self._emit = None  # EventBus 事件推送器（由 CoreAPI 注入）
        
        # 延迟写入相关
        self._pending_save = False
        self._save_timer = None
        
        # 加载配置
        from .config import get_config_manager
        self.config = get_config_manager()
        
        # 加载历史记录（含哈希校验）
        self.load_history()
        
        # 缓存预热：把历史记录中图片仍存在的条目加载到 current_results
        self._warmup_cache()
    
    def set_event_emitter(self, emitter) -> None:
        """设置事件推送器（由 CoreAPI 注入）
        
        核心模块通过此方法获得向 EventBus 推送事件的能力。
        只在 _emit 不为 None 时推送，兼容没有 CoreAPI 的场景。
        
        Args:
            emitter: 事件推送函数，签名为 emitter(channel: str, **data)
        """
        self._emit = emitter
    
    # ------------------------------------------------------------------ #
    #  哈希相关方法
    # ------------------------------------------------------------------ #
    
    def _calc_data_hash(self, data: list) -> str:
        """计算历史记录数据的 MD5 哈希（用于完整性校验）
        
        Args:
            data: 历史记录列表
            
        Returns:
            MD5 哈希字符串（32位十六进制）
        """
        data_json = json.dumps(data, ensure_ascii=False, sort_keys=True)
        return hashlib.md5(data_json.encode('utf-8')).hexdigest()
    
    def _calc_image_hash(self, image_path: str) -> str:
        """计算图片文件的 MD5 哈希（用于缓存 Key）
        
        Args:
            image_path: 图片文件路径
            
        Returns:
            MD5 哈希字符串（32位十六进制），失败返回空字符串
        """
        try:
            if not os.path.exists(image_path):
                return ''
            h = hashlib.md5()
            with open(image_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    h.update(chunk)
            return h.hexdigest()
        except Exception as e:
            logger.warning(f"计算图片哈希失败 [{image_path}]: {e}")
            return ''
    
    # ------------------------------------------------------------------ #
    #  缓存核心方法
    # ------------------------------------------------------------------ #

    def _set_cache(self, path: str, ocr_result: Dict):
        """统一的缓存写入入口（保证唯一性、路径标准化）

        Args:
            path: 图片路径
            ocr_result: OCR 识别结果（可以是简化版或完整版）
        """
        path = os.path.normpath(path)
        image_hash = self._calc_image_hash(path)
        
        # ★ 规范化：确保有 success 字段（下游 core_api 用 success 判断状态）
        if 'success' not in ocr_result and 'code' in ocr_result:
            ocr_result['success'] = (ocr_result['code'] == 100)
        
        # ★ 规范化：确保有 texts 字段（下游 core_api 读取 texts 展示识别内容）
        if 'texts' not in ocr_result and 'data' in ocr_result:
            data = ocr_result['data']
            if isinstance(data, list):
                texts = []
                for item in data:
                    if isinstance(item, dict) and 'text' in item:
                        texts.append(item['text'])
                    elif isinstance(item, str):
                        texts.append(item)
                ocr_result['texts'] = texts
        
        self.current_results[path] = {
            'result': ocr_result,
            'image_hash': image_hash
        }
        logger.debug(f"[Cache] 已写入缓存: {path.split('/')[-1].split('\\\\')[-1]}")

    # ------------------------------------------------------------------ #
    #  缓存预热
    # ------------------------------------------------------------------ #

    def _warmup_cache(self):
        """缓存预热：把历史记录中图片仍存在的条目加载到 current_results
        
        注意：history 里只存了 full_texts（文本列表），
        没有存 OCR 引擎返回的坐标等完整信息，
        因此这里构造的是简化版 ocr_result（只含文本，不含坐标）。
        命中缓存时，若只需要文本内容，可以直接使用；
        若需要坐标等完整信息，仍需重新识别。
        """
        count = 0
        for entry in self.history:
            path = entry.get('path', '')
            if not path or not os.path.exists(path):
                continue  # 图片文件已不存在，跳过
            
            # 构造简化版 OCR 结果（只含文本，不含坐标）
            full_texts = entry.get('full_texts', [])
            ocr_result = {
                'code': 100 if entry.get('success') else -1,
                'data': [{'text': t} for t in full_texts]
            }
            
            # ★ 统一调用 _set_cache()，确保路径标准化和哈希计算一致
            self._set_cache(path, ocr_result)
            count += 1
        
        logger.info(f"[Cache] 预热完成：加载 {count} 条历史记录到内存缓存")
    
    # ------------------------------------------------------------------ #
    #  历史记录加载 / 保存（含哈希校验）
    # ------------------------------------------------------------------ #
    
    @error_handling(ErrorType.FILE_OPERATION, "加载历史记录失败")
    def load_history(self) -> bool:
        """加载历史记录（带哈希校验）
        
        Returns:
            是否加载成功
        """
        if not self.history_file.exists():
            logger.debug("历史记录文件不存在，创建新记录")
            self.history = []
            return False
        
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            if not content:
                self.history = []
                return False
            
            # 解析 JSON
            wrapped = json.loads(content)
            
            # 检查是否是新版格式（带哈希）
            if isinstance(wrapped, dict) and '__hash__' in wrapped:
                stored_hash = wrapped['__hash__']
                data = wrapped['data']
                
                # 验证哈希
                actual_hash = self._calc_data_hash(data)
                
                if stored_hash != actual_hash:
                    logger.warning("历史记录文件哈希校验失败（可能被手动编辑），丢弃并重建")
                    self.history = []
                    self.save_history()  # 重建空文件
                    return False
                
                self.history = data
                logger.info(f"已加载 {len(self.history)} 条历史记录（哈希校验通过）")
            else:
                # 旧版格式（直接是数组），信任并升级
                logger.info("检测到旧版历史记录格式，自动升级并添加哈希...")
                self.history = wrapped
                self.save_history()  # 保存为新格式
            
            return True
        except json.JSONDecodeError as e:
            logger.warning(f"历史记录文件格式错误，重置为空: {e}")
            self.history = []
            return True  # 不再抛出异常，允许程序启动
        except Exception as e:
            logger.warning(f"加载历史记录失败，重置为空: {e}")
            self.history = []
            return True  # 不再抛出异常，允许程序启动
    
    @error_handling(ErrorType.FILE_OPERATION, "保存历史记录失败")
    def save_history(self) -> bool:
        """保存历史记录到文件（带哈希校验头）
        
        Returns:
            是否保存成功
        """
        try:
            # 确保目录存在
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 计算哈希
            md5_hash = self._calc_data_hash(self.history)
            
            # 构造带哈希的包装结构
            wrapped = {
                '__hash__': md5_hash,
                'data': self.history
            }
            
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(wrapped, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"已保存 {len(self.history)} 条历史记录（哈希：{md5_hash[:8]}...）")
            return True
        except Exception as e:
            raise FileOperationError(f"保存历史记录失败: {str(e)}", e)
    
    # ------------------------------------------------------------------ #
    #  延迟写入
    # ------------------------------------------------------------------ #
    
    def flush_cache(self) -> bool:
        """强制立即保存缓存（程序关闭时调用）
        
        Returns:
            是否保存成功
        """
        # 取消定时器
        if self._save_timer:
            self._save_timer.cancel()
            self._save_timer = None
        
        if not self._pending_save:
            return True  # 没有待保存的数据
        
        # 执行保存
        self._pending_save = False
        return self.save_history()
    
    def _schedule_save(self):
        """调度延迟保存（5秒后执行）"""
        # 如果已经有定时器在跑，先取消
        if self._save_timer:
            self._save_timer.cancel()
        
        # 创建新定时器（5秒后执行）
        import threading
        self._save_timer = threading.Timer(5.0, self._on_save_timer_timeout)
        self._save_timer.daemon = True  # 守护线程，主线程退出时自动结束
        self._save_timer.start()
        logger.debug("已调度延迟保存（5秒后执行）")
    
    def _on_save_timer_timeout(self):
        """定时器超时回调：执行延迟保存"""
        logger.debug("延迟保存定时器触发")
        self.flush_cache()
    
    # ------------------------------------------------------------------ #
    #  历史记录增删改查
    # ------------------------------------------------------------------ #
    
    def add_result(self, image_path: str, ocr_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        添加识别结果（按路径排重：已存在则更新，不存在则新增）
        同时使用图片哈希做缓存 Key，避免图片内容变化但路径不变导致的缓存误命中。

        Args:
            image_path: 图片路径
            ocr_result: OCR 识别结果

        Returns:
            历史记录条目
        """
        if not image_path:
            logger.warning("尝试添加空图片路径的识别结果")

        # ★ 统一调用 _set_cache()，确保路径标准化和哈希计算一致
        self._set_cache(image_path, ocr_result)

        # 提取纯文本（直接从 ocr_result 提取，不绕弯）
        texts = []
        if ocr_result.get('code') == 100 and ocr_result.get('data'):
            for item in ocr_result['data']:
                if isinstance(item, dict) and 'text' in item:
                    texts.append(item['text'])

        # 检查是否已存在相同路径的记录（按路径排重）
        # ★ 查找时用标准化后的路径，与 _set_cache 保持一致
        norm_path = os.path.normpath(image_path)
        timestamp = self._get_timestamp()
        for entry in self.history:
            if os.path.normpath(entry.get('path', '')) == norm_path:
                # 已存在，更新时间和结果
                entry['time'] = timestamp
                entry['text'] = '\n'.join(texts)
                entry['full_texts'] = texts
                entry['success'] = ocr_result.get('code') == 100

                # 延迟写入
                self._pending_save = True
                self._schedule_save()

                logger.info(f"已更新历史记录: {entry['filename']}")
                return entry

        # 不存在，新增记录
        entry = {
            'path': image_path,
            'filename': os.path.basename(image_path) if image_path else '未知',
            'text': '\n'.join(texts),
            'full_texts': texts,
            'time': timestamp,
            'success': ocr_result.get('code') == 100
        }

        self.history.append(entry)

        # 只保留最近配置上限条
        storage_limit = self.config.get_history_storage_limit()
        if len(self.history) > storage_limit:
            removed_count = len(self.history) - storage_limit
            self.history = self.history[-storage_limit:]
            logger.debug(f"历史记录超出限制，已删除 {removed_count} 条旧记录")

        # 延迟写入
        self._pending_save = True
        self._schedule_save()

        logger.info(f"已添加识别结果到历史记录: {entry['filename']}")
        # ★ 推送缓存更新事件
        if self._emit:
            self._emit("result:event", type="cache_updated", count=len(self.history))
        return entry
    
    def get_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取历史记录
        
        Args:
            limit: 返回条数限制（None 表示从配置读取）
            
        Returns:
            历史记录列表（从新到旧）
        """
        if limit is None:
            limit = self.config.get_history_display_limit()
        
        # 确保 limit 有效
        limit = max(1, min(limit, len(self.history)))
        return self.history[-limit:][::-1]  # 反转，从新到旧
    
    def get_history_count(self) -> int:
        """获取历史记录总数
        
        Returns:
            历史记录数量
        """
        return len(self.history)
    
    def delete_history(self, index: int) -> bool:
        """
        删除历史记录
        
        Args:
            index: 索引（从 0 开始，对应显示顺序，即从新到旧）
            
        Returns:
            是否删除成功
        """
        # 前端传入的是从新到旧的索引，需要转换为实际索引
        actual_index = len(self.history) - 1 - index
        if 0 <= actual_index < len(self.history):
            deleted_entry = self.history.pop(actual_index)
            # ★ 同步清理缓存（路径标准化，和 _set_cache/get_result 保持一致）
            path = os.path.normpath(deleted_entry.get('path', ''))
            if path and path in self.current_results:
                del self.current_results[path]
            self.save_history()  # 删除操作立即保存（用户主动操作，不能延迟）
            logger.info(f"已删除历史记录: {deleted_entry.get('filename', '未知')}")
            return True
        
        logger.warning(f"删除历史记录失败：索引 {index} 超出范围")
        return False
    
    def clear_history(self) -> bool:
        """清空所有历史记录
        
        Returns:
            是否清空成功
        """
        count = len(self.history)
        self.history = []
        self.current_results = {}  # ★ 同步清理缓存
        self.save_history()  # 清空操作立即保存
        logger.info(f"已清空 {count} 条历史记录和当前缓存")
        return True
    
    def clear_all(self) -> bool:
        """清空所有历史记录和当前结果
        
        Returns:
            是否清空成功
        """
        # 清空历史记录
        history_count = len(self.history)
        self.history = []
        
        # 清空当前结果
        current_count = len(self.current_results)
        self.current_results = {}
        
        # 保存历史记录（此时为空）
        self.save_history()
        
        logger.info(f"已清空所有数据：{history_count} 条历史记录，{current_count} 条当前结果")
        # ★ 推送缓存清空事件
        if self._emit:
            self._emit("result:event", type="cache_cleared")
        return True
    
    # ------------------------------------------------------------------ #
    #  当前结果查询
    # ------------------------------------------------------------------ #
    
    def get_result(self, image_path):
        """
        获取指定图片的识别结果（含图片哈希校验）
        
        如果图片哈希发生变化（图片内容被修改），则返回 None，
        强制重新识别。
        
        Args:
            image_path: 图片路径
            
        Returns:
            dict: 识别结果，若缓存未命中或哈希变化则返回 None
        """
        # ★ 路径标准化，确保和 _warmup_cache() 存入的 key 一致
        image_path = os.path.normpath(image_path)
        
        logger.debug(f"[Cache] get_result() 查找: {image_path}")
        logger.debug(f"[Cache] 当前缓存 key 数量: {len(self.current_results)}")
        if len(self.current_results) <= 20:
            for k in self.current_results.keys():
                logger.debug(f"[Cache]   缓存 key: {k}")

        cached = self.current_results.get(image_path)
        if cached is None:
            logger.info(f"[Cache] 未命中: {image_path.split('/')[-1].split('\\')[-1]}")
            return None
        
        # 校验图片哈希（若之前计算过）
        cached_hash = cached.get('image_hash', '')
        if cached_hash:
            current_hash = self._calc_image_hash(image_path)
            if current_hash and cached_hash != current_hash:
                logger.info(f"[Cache] 图片内容已变化，缓存失效: {image_path.split('/')[-1].split('\\')[-1]}")
                del self.current_results[image_path]
                return None
        
        logger.info(f"[Cache] 命中: {image_path.split('/')[-1].split('\\')[-1]}")
        return cached['result']
    
    def get_current_results(self):
        """
        获取所有当前识别结果
        
        Returns:
            dict: image_path -> result
        """
        return self.current_results.copy()
    
    def clear_current_results(self):
        """清空当前识别结果"""
        self.current_results = {}
    
    def invalidate_cache(self, image_path: str):
        """清除单张图片的缓存（用于重新识别等场景）
        
        Args:
            image_path: 图片路径
        """
        path = os.path.normpath(image_path)
        if path in self.current_results:
            del self.current_results[path]
            logger.debug(f"已清除缓存: {path.split('/')[-1].split('\\')[-1]}")
    
    def get_combined_text(self, separator: str = '\n') -> str:
        """
        获取合并后的文本
        
        Args:
            separator: 分隔符
            
        Returns:
            合并后的文本
        """
        texts = []
        for result in self.current_results.values():
            ocr_result = result['result']
            if ocr_result.get('code') == 100 and ocr_result.get('data'):
                for item in ocr_result['data']:
                    if isinstance(item, dict) and 'text' in item:
                        texts.append(item['text'])
        return separator.join(texts)
    
    # ------------------------------------------------------------------ #
    #  工具方法
    # ------------------------------------------------------------------ #
    
    def _get_timestamp(self) -> str:
        """获取当前时间戳
        
        Returns:
            格式化的时间字符串
        """
        return datetime.now().strftime('%Y-%m-%d %H:%M')
    
    def format_result_for_display(self, ocr_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        格式化结果用于显示
        
        Args:
            ocr_result: OCR 识别结果
            
        Returns:
            格式化后的结果字典
        """
        if ocr_result.get('code') == 100 and ocr_result.get('data'):
            lines = []
            for i, item in enumerate(ocr_result['data'], 1):
                text = item.get('text', '')
                score = item.get('score', 0)
                line = f"{i}. {text}"
                if score:
                    line += f"  (置信度: {score:.2%})"
                lines.append(line)
            
            return {
                'success': True,
                'text': '\n'.join(lines),
                'count': len(ocr_result['data']),
                'raw_data': ocr_result['data']
            }
        else:
            error_code = ocr_result.get('code', -1)
            error_msg = ocr_result.get('data', '未知错误')
            logger.warning(f"OCR 识别失败 - 错误码: {error_code}, 消息: {error_msg}")
            
            return {
                'success': False,
                'text': f"识别失败\n\n错误码: {error_code}\n{error_msg}",
                'count': 0,
                'error_code': error_code,
                'error_message': error_msg
            }


# 全局结果管理器实例（线程安全）
_result_manager: Optional[ResultManager] = None
_manager_lock = None


def _get_manager_lock():
    """获取管理器锁（延迟初始化）"""
    global _manager_lock
    if _manager_lock is None:
        import threading
        _manager_lock = threading.Lock()
    return _manager_lock


def get_result_manager() -> ResultManager:
    """获取全局结果管理器实例（线程安全）
    
    Returns:
        结果管理器实例
    """
    global _result_manager
    
    if _result_manager is None:
        with _get_manager_lock():
            # 双重检查锁定
            if _result_manager is None:
                logger.info("创建全局结果管理器实例")
                _result_manager = ResultManager()
    
    return _result_manager
