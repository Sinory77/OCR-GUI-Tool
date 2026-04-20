# 结果和历史记录管理器
# 核心层业务逻辑，不依赖任何界面

import json
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from .config import HISTORY_FILE

# 配置日志
logger = logging.getLogger(__name__)


class ResultManager:
    """识别结果和历史记录管理器"""
    
    def __init__(self, history_file=None):
        """
        初始化结果管理器
        
        Args:
            history_file: 历史记录文件路径
        """
        self.history_file = Path(history_file) if history_file else HISTORY_FILE
        self.history = []
        self.current_results = {}  # image_path -> result
        
        # 加载配置
        from .config import get_config_manager
        self.config = get_config_manager()
        
        # 加载历史记录
        self.load_history()
    
    def load_history(self) -> bool:
        """加载历史记录
        
        Returns:
            是否加载成功
        """
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self.history = json.load(f)
                logger.info(f"已加载 {len(self.history)} 条历史记录")
                return True
            except json.JSONDecodeError as e:
                logger.error(f"历史记录文件格式错误: {e}")
                self.history = []
            except Exception as e:
                logger.error(f"加载历史记录失败: {e}", exc_info=True)
                self.history = []
        else:
            logger.debug("历史记录文件不存在，创建新记录")
            self.history = []
        
        return False
    
    def save_history(self) -> bool:
        """保存历史记录到文件
        
        Returns:
            是否保存成功
        """
        try:
            # 确保目录存在
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
            logger.debug(f"已保存 {len(self.history)} 条历史记录")
            return True
        except Exception as e:
            logger.error(f"保存历史记录失败: {e}", exc_info=True)
            return False
    
    def add_result(self, image_path: str, ocr_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        添加识别结果
        
        Args:
            image_path: 图片路径
            ocr_result: OCR 识别结果
            
        Returns:
            历史记录条目
        """
        if not image_path:
            logger.warning("尝试添加空图片路径的识别结果")
        
        # 保存到当前结果
        self.current_results[image_path] = ocr_result
        
        # 提取纯文本
        texts = []
        if ocr_result.get('code') == 100 and ocr_result.get('data'):
            for item in ocr_result['data']:
                if isinstance(item, dict) and 'text' in item:
                    texts.append(item['text'])
        
        # 添加到历史记录
        entry = {
            'path': image_path,
            'filename': os.path.basename(image_path) if image_path else '未知',
            'text': '\n'.join(texts),
            'full_texts': texts,
            'time': self._get_timestamp(),
            'success': ocr_result.get('code') == 100
        }
        
        self.history.append(entry)
        
        # 只保留最近配置上限条
        storage_limit = self.config.get_history_storage_limit()
        if len(self.history) > storage_limit:
            removed_count = len(self.history) - storage_limit
            self.history = self.history[-storage_limit:]
            logger.debug(f"历史记录超出限制，已删除 {removed_count} 条旧记录")
        
        # 保存到文件
        self.save_history()
        
        logger.info(f"已添加识别结果到历史记录: {entry['filename']}")
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
            self.save_history()
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
        self.save_history()
        logger.info(f"已清空 {count} 条历史记录")
        return True
        return True
    
    def get_result(self, image_path):
        """
        获取指定图片的识别结果
        
        Args:
            image_path: 图片路径
            
        Returns:
            dict: 识别结果
        """
        return self.current_results.get(image_path)
    
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
            if result.get('code') == 100 and result.get('data'):
                for item in result['data']:
                    if isinstance(item, dict) and 'text' in item:
                        texts.append(item['text'])
        return separator.join(texts)
    
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
