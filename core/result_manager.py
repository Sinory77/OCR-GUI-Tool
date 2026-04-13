# 结果和历史记录管理器
# 核心层业务逻辑，不依赖任何界面

import json
import os
from datetime import datetime
from pathlib import Path
from .config import HISTORY_FILE


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
    
    def load_history(self):
        """加载历史记录"""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self.history = json.load(f)
            except Exception as e:
                print(f"加载历史记录失败: {e}")
                self.history = []
        else:
            self.history = []
    
    def save_history(self):
        """保存历史记录到文件"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存历史记录失败: {e}")
            return False
    
    def add_result(self, image_path, ocr_result):
        """
        添加识别结果
        
        Args:
            image_path: 图片路径
            ocr_result: OCR 识别结果
        """
        # 保存到当前结果
        self.current_results[image_path] = ocr_result
        
        # 提取纯文本
        texts = []
        if ocr_result.get('code') == 100:
            for item in ocr_result.get('data', []):
                texts.append(item.get('text', ''))
        
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
            self.history = self.history[-storage_limit:]
        
        # 保存到文件
        self.save_history()
        
        return entry
    
    def get_history(self, limit=None):
        """
        获取历史记录
        
        Args:
            limit: 返回条数限制（None 表示从配置读取）
            
        Returns:
            list: 历史记录列表（从新到旧）
        """
        if limit is None:
            limit = self.config.get_history_display_limit()
        return self.history[-limit:][::-1]  # 反转，从新到旧
    
    def get_history_count(self):
        """获取历史记录总数"""
        return len(self.history)
    
    def delete_history(self, index):
        """
        删除历史记录
        
        Args:
            index: 索引（从 0 开始，对应列表顺序）
            
        Returns:
            bool: 是否成功
        """
        # 前端传入的是从新到旧的索引，需要转换
        actual_index = len(self.history) - 1 - index
        if 0 <= actual_index < len(self.history):
            self.history.pop(actual_index)
            self.save_history()
            return True
        return False
    
    def clear_history(self):
        """清空所有历史记录"""
        self.history = []
        self.save_history()
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
    
    def get_combined_text(self, separator='\n'):
        """
        获取合并后的文本
        
        Args:
            separator: 分隔符
            
        Returns:
            str: 合并后的文本
        """
        texts = []
        for result in self.current_results.values():
            if result.get('code') == 100:
                for item in result.get('data', []):
                    texts.append(item.get('text', ''))
        return separator.join(texts)
    
    def _get_timestamp(self):
        """获取当前时间戳"""
        return datetime.now().strftime('%Y-%m-%d %H:%M')
    
    def format_result_for_display(self, ocr_result):
        """
        格式化结果用于显示
        
        Args:
            ocr_result: OCR 识别结果
            
        Returns:
            dict: 格式化后的结果
        """
        if ocr_result.get('code') == 100:
            lines = []
            for i, item in enumerate(ocr_result.get('data', []), 1):
                text = item.get('text', '')
                score = item.get('score', 0)
                line = f"{i}. {text}"
                if score:
                    line += f"  (置信度: {score:.2%})"
                lines.append(line)
            
            return {
                'success': True,
                'text': '\n'.join(lines),
                'count': len(ocr_result.get('data', [])),
                'raw_data': ocr_result.get('data', [])
            }
        else:
            return {
                'success': False,
                'text': f"识别失败\n\n错误码: {ocr_result.get('code')}\n{ocr_result.get('data', '未知错误')}",
                'count': 0,
                'error_code': ocr_result.get('code'),
                'error_message': ocr_result.get('data')
            }


# 全局结果管理器实例
_result_manager = None


def get_result_manager():
    """获取全局结果管理器实例"""
    global _result_manager
    if _result_manager is None:
        _result_manager = ResultManager()
    return _result_manager
