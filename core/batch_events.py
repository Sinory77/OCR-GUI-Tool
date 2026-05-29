# -*- coding: utf-8 -*-
"""
批量识别事件 - 核心层推送的标准化事件定义

核心层负责所有逻辑（扫描、排重、识别），界面层只做展示
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class EventType(Enum):
    """事件类型枚举"""
    SCAN_RESULT = "scan_result"           # 扫描结果
    DEDUP_RESULT = "dedup_result"         # 排重结果
    RECOGNIZE_START = "recognize_start"   # 开始识别
    RECOGNIZE_PROGRESS = "recognize_progress"  # 识别进度
    RECOGNIZE_COMPLETE = "recognize_complete"    # 识别完成
    RECOGNIZE_ERROR = "recognize_error"          # 识别错误
    CANCELLED = "cancelled"                     # 任务取消


@dataclass
class DuplicateFile:
    """重复文件信息"""
    file_path: str           # 文件路径
    file_name: str          # 文件名
    reason: str              # 重复原因


@dataclass
class BatchOCREvent:
    """
    批量识别事件 - 统一的事件数据结构

    所有事件都通过这个类推送给界面层，界面层只需根据 type 显示即可
    """
    type: EventType
    data: Dict[str, Any] = field(default_factory=dict)

    # 便捷属性
    @property
    def total(self) -> int:
        """获取总数"""
        return self.data.get('total', 0)

    @property
    def current(self) -> int:
        """获取当前索引"""
        return self.data.get('current', 0)

    @property
    def filename(self) -> str:
        """获取文件名"""
        return self.data.get('filename', '')

    @property
    def file_path(self) -> str:
        """获取文件路径"""
        return self.data.get('file_path', '')

    @property
    def is_duplicate(self) -> bool:
        """是否重复"""
        return self.data.get('is_duplicate', False)

    @property
    def completed(self) -> bool:
        """是否完成"""
        return self.data.get('completed', False)

    @property
    def result(self) -> Optional[Dict]:
        """获取识别结果"""
        return self.data.get('result')

    @property
    def files(self) -> List[str]:
        """获取文件列表"""
        return self.data.get('files', [])

    @property
    def duplicates(self) -> List[DuplicateFile]:
        """获取重复文件列表"""
        dup_list = self.data.get('duplicates', [])
        if not dup_list:
            return []
        if isinstance(dup_list[0], DuplicateFile):
            return dup_list
        # 从字典转换
        return [DuplicateFile(**d) for d in dup_list]

    # 工厂方法
    @classmethod
    def scan_result(cls, folder_path: str, files: List[str]) -> 'BatchOCREvent':
        """扫描结果事件"""
        return cls(
            type=EventType.SCAN_RESULT,
            data={
                'folder_path': folder_path,
                'files': files,
                'count': len(files)
            }
        )

    @classmethod
    def dedup_result(cls, original_count: int, final_count: int,
                     duplicates: List[Dict]) -> 'BatchOCREvent':
        """排重结果事件"""
        dup_files = [
            DuplicateFile(
                file_path=d.get('file_path', ''),
                file_name=d.get('file_name', ''),
                reason=d.get('reason', '内容重复')
            ) for d in duplicates
        ]
        return cls(
            type=EventType.DEDUP_RESULT,
            data={
                'original_count': original_count,
                'final_count': final_count,
                'duplicates': dup_files,
                'dedup_count': original_count - final_count
            }
        )

    @classmethod
    def recognize_start(cls, total: int) -> 'BatchOCREvent':
        """开始识别事件"""
        return cls(
            type=EventType.RECOGNIZE_START,
            data={'total': total}
        )

    @classmethod
    def recognize_progress(cls, current: int, total: int,
                          filename: str, file_path: str,
                          is_duplicate: bool = False,
                          completed: bool = False,
                          result: Optional[Dict] = None) -> 'BatchOCREvent':
        """识别进度事件"""
        return cls(
            type=EventType.RECOGNIZE_PROGRESS,
            data={
                'current': current,
                'total': total,
                'filename': filename,
                'file_path': file_path,
                'is_duplicate': is_duplicate,
                'completed': completed,
                'result': result
            }
        )

    @classmethod
    def recognize_complete(cls, success_count: int, fail_count: int,
                          skip_count: int, results: List[Dict]) -> 'BatchOCREvent':
        """识别完成事件"""
        return cls(
            type=EventType.RECOGNIZE_COMPLETE,
            data={
                'success_count': success_count,
                'fail_count': fail_count,
                'skip_count': skip_count,
                'total': success_count + fail_count + skip_count,
                'results': results
            }
        )

    @classmethod
    def recognize_error(cls, message: str) -> 'BatchOCREvent':
        """识别错误事件"""
        return cls(
            type=EventType.RECOGNIZE_ERROR,
            data={'message': message}
        )

    @classmethod
    def cancelled(cls) -> 'BatchOCREvent':
        """取消事件"""
        return cls(type=EventType.CANCELLED, data={})
