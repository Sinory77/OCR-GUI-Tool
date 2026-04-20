"""
模板管理器 - 管理 OCR 结果解析模板

功能：
- 模板 CRUD（创建、读取、更新、删除）
- 模板文件持久化（JSON 格式）
- 模板缓存（内存加速访问）
- 模板导入/导出（备份和分享）
"""
import json
import os
import uuid
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict, field

logger = logging.getLogger(__name__)


@dataclass
class ParseRule:
    """解析规则
    
    支持三种规则类型：
    - keyword: 关键词匹配，查找关键词后提取值
    - regex: 正则表达式匹配
    - position: 固定位置提取（行号+起始/结束位置）
    """
    name: str = ""                    # 字段名称（如：货主、联系电话）
    type: str = "keyword"             # 规则类型: keyword/regex/position
    
    # keyword 类型参数
    keyword: str = ""                 # 关键词
    ignore_spaces: bool = False       # 是否忽略空格匹配（处理"货 主"分行）
    use_next_line: bool = True        # 当前行无值时是否尝试下一行
    
    # regex 类型参数
    pattern: str = ""                 # 正则表达式
    
    # position 类型参数
    line: int = 0                     # 行号（从0开始）
    start: int = 0                    # 起始字符位置
    end: int = 0                      # 结束字符位置
    
    def __post_init__(self):
        """数据验证"""
        if self.type not in ("keyword", "regex", "position"):
            raise ValueError(f"无效的规则类型: {self.type}，必须是 keyword/regex/position")
        
        if not self.name or not self.name.strip():
            raise ValueError("字段名称不能为空")


@dataclass
class ParseTemplate:
    """解析模板
    
    用于定义如何从 OCR 识别结果中提取结构化字段。
    每个模板包含多个解析规则，按顺序执行。
    """
    id: str = ""                      # 模板唯一ID（UUID短格式）
    name: str = ""                    # 模板名称
    description: str = ""             # 模板描述
    rules: List[ParseRule] = field(default_factory=list)  # 解析规则列表
    created_at: str = ""              # 创建时间（ISO格式）
    updated_at: str = ""              # 更新时间（ISO格式）
    
    def __post_init__(self):
        """初始化默认值"""
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at
        if self.rules is None:
            self.rules = []
    
    @property
    def rule_count(self) -> int:
        """获取规则数量"""
        return len(self.rules)
    
    def validate(self) -> Tuple[bool, str]:
        """
        验证模板有效性
        
        Returns:
            (is_valid, error_message)
        """
        if not self.id or not self.id.strip():
            return False, "模板ID不能为空"
        
        if not self.name or not self.name.strip():
            return False, "模板名称不能为空"
        
        if not self.rules:
            return False, "模板至少需要包含一个解析规则"
        
        # 验证每个规则
        for i, rule in enumerate(self.rules):
            try:
                # 触发 ParseRule 的 __post_init__ 验证
                ParseRule(**asdict(rule))
            except ValueError as e:
                return False, f"规则 #{i+1} ({rule.name}): {str(e)}"
        
        return True, ""


class TemplateManagerError(Exception):
    """模板管理器异常基类"""
    pass


class TemplateNotFoundError(TemplateManagerError):
    """模板未找到"""
    pass


class TemplateValidationError(TemplateManagerError):
    """模板验证失败"""
    pass


class TemplateManager:
    """模板管理器
    
    负责模板的 CRUD 操作、文件持久化、缓存管理。
    使用单例模式，通过 get_template_manager() 获取全局实例。
    
    Attributes:
        templates_dir: 模板文件存储目录
        _templates: 内存中的模板缓存 {template_id: ParseTemplate}
    """
    
    def __init__(self, templates_dir: str = None):
        """
        初始化模板管理器
        
        Args:
            templates_dir: 模板文件存放目录，默认为项目根目录下的 templates/
        
        Raises:
            OSError: 无法创建模板目录
        """
        if templates_dir is None:
            # 默认路径：项目根目录/templates
            base_dir = Path(__file__).resolve().parent.parent
            self.templates_dir = str(base_dir / "templates")
        else:
            self.templates_dir = templates_dir
        
        # 确保目录存在
        try:
            os.makedirs(self.templates_dir, exist_ok=True)
            logger.info(f"模板目录: {self.templates_dir}")
        except OSError as e:
            logger.error(f"无法创建模板目录: {e}")
            raise
        
        # 内存缓存
        self._templates: Dict[str, ParseTemplate] = {}
        
        # 加载所有模板
        self._load_all_templates()
        logger.info(f"已加载 {len(self._templates)} 个模板")
    
    # ──────────────────────────────────────────────────────
    # 内部方法 - 文件操作
    # ──────────────────────────────────────────────────────
    
    def _load_all_templates(self):
        """从文件系统加载所有模板到内存缓存
        
        会清空现有缓存并重新加载所有 .json 文件。
        加载失败的模板会被跳过并记录日志。
        """
        self._templates.clear()
        
        if not os.path.exists(self.templates_dir):
            logger.warning(f"模板目录不存在: {self.templates_dir}")
            return
        
        loaded_count = 0
        failed_count = 0
        
        for filename in sorted(os.listdir(self.templates_dir)):
            if not filename.endswith('.json'):
                continue
            
            filepath = os.path.join(self.templates_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                template = self._dict_to_template(data)
                
                # 验证模板
                is_valid, error_msg = template.validate()
                if not is_valid:
                    logger.warning(f"模板验证失败 {filename}: {error_msg}")
                    failed_count += 1
                    continue
                
                self._templates[template.id] = template
                loaded_count += 1
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON 解析失败 {filename}: {e}")
                failed_count += 1
            except Exception as e:
                logger.error(f"加载模板失败 {filename}: {e}", exc_info=True)
                failed_count += 1
        
        if failed_count > 0:
            logger.warning(f"模板加载完成: {loaded_count} 成功, {failed_count} 失败")
        else:
            logger.info(f"模板加载完成: {loaded_count} 个模板")
    
    def _save_template_to_file(self, template: ParseTemplate) -> str:
        """
        原子性地保存模板到文件
        
        使用临时文件 + 重命名的方式，防止写入过程中断导致文件损坏。
        
        Args:
            template: 要保存的模板对象
        
        Returns:
            保存的文件路径
        
        Raises:
            TemplateManagerError: 保存失败
        """
        filename = f"{template.id}.json"
        filepath = os.path.join(self.templates_dir, filename)
        temp_filepath = filepath + ".tmp"
        
        try:
            # 序列化模板
            data = self._template_to_dict(template)
            
            # 写入临时文件
            with open(temp_filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())  # 确保数据写入磁盘
            
            # 原子性重命名
            if os.path.exists(filepath):
                os.replace(temp_filepath, filepath)
            else:
                os.rename(temp_filepath, filepath)
            
            logger.debug(f"模板已保存: {filepath}")
            return filepath
            
        except Exception as e:
            # 清理临时文件
            if os.path.exists(temp_filepath):
                try:
                    os.remove(temp_filepath)
                except:
                    pass
            raise TemplateManagerError(f"保存模板失败: {e}")
    
    def _delete_template_file(self, template_id: str) -> bool:
        """
        删除模板文件
        
        Args:
            template_id: 模板ID
        
        Returns:
            是否成功删除
        """
        filepath = os.path.join(self.templates_dir, f"{template_id}.json")
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                logger.debug(f"模板文件已删除: {filepath}")
                return True
            except OSError as e:
                logger.error(f"删除模板文件失败: {e}")
                return False
        return False
    
    # ──────────────────────────────────────────────────────
    # 内部方法 - 数据转换
    # ──────────────────────────────────────────────────────
    
    def _dict_to_template(self, data: dict) -> ParseTemplate:
        """将字典转换为模板对象
        
        Args:
            data: JSON 解析后的字典
        
        Returns:
            ParseTemplate 对象
        """
        rules = []
        for rule_data in data.get('rules', []):
            try:
                rules.append(ParseRule(
                    name=rule_data.get('name', ''),
                    type=rule_data.get('type', 'keyword'),
                    keyword=rule_data.get('keyword', ''),
                    pattern=rule_data.get('pattern', ''),
                    line=int(rule_data.get('line', 0)),
                    start=int(rule_data.get('start', 0)),
                    end=int(rule_data.get('end', 0)),
                    ignore_spaces=bool(rule_data.get('ignore_spaces', False)),
                    use_next_line=bool(rule_data.get('use_next_line', True))
                ))
            except (ValueError, TypeError) as e:
                logger.warning(f"跳过无效规则: {rule_data.get('name', '?')} - {e}")
        
        return ParseTemplate(
            id=data.get('id', ''),
            name=data.get('name', ''),
            description=data.get('description', ''),
            rules=rules,
            created_at=data.get('created_at', ''),
            updated_at=data.get('updated_at', '')
        )
    
    def _template_to_dict(self, template: ParseTemplate) -> dict:
        """将模板对象转换为可序列化的字典
        
        Args:
            template: 模板对象
        
        Returns:
            可 JSON 序列化的字典
        """
        return {
            'id': template.id,
            'name': template.name,
            'description': template.description,
            'rules': [
                {
                    'name': rule.name,
                    'type': rule.type,
                    'keyword': rule.keyword,
                    'pattern': rule.pattern,
                    'line': rule.line,
                    'start': rule.start,
                    'end': rule.end,
                    'ignore_spaces': rule.ignore_spaces,
                    'use_next_line': rule.use_next_line
                }
                for rule in template.rules
            ],
            'created_at': template.created_at,
            'updated_at': template.updated_at
        }
    
    # ──────────────────────────────────────────────────────
    # 公共方法 - CRUD 操作
    # ──────────────────────────────────────────────────────
    
    def get_all_templates(self) -> List[ParseTemplate]:
        """获取所有模板（按名称排序）
        
        Returns:
            模板列表，按名称字母顺序排序
        """
        templates = list(self._templates.values())
        templates.sort(key=lambda t: t.name)
        return templates
    
    def get_template(self, template_id: str) -> Optional[ParseTemplate]:
        """根据 ID 获取模板
        
        Args:
            template_id: 模板唯一ID
        
        Returns:
            模板对象，未找到返回 None
        """
        return self._templates.get(template_id)
    
    def save_template(self, template: ParseTemplate) -> bool:
        """
        保存模板（创建或更新）
        
        如果模板ID已存在则更新，否则创建新模板。
        同时更新内存缓存和文件系统。
        
        Args:
            template: 模板对象
        
        Returns:
            是否保存成功
        """
        try:
            # 验证模板
            is_valid, error_msg = template.validate()
            if not is_valid:
                logger.error(f"模板验证失败: {error_msg}")
                return False
            
            # 生成ID（如果是新模板）
            if not template.id:
                template.id = self._generate_id()
            
            # 更新时间戳
            template.updated_at = datetime.now().isoformat()
            
            # 保存到文件
            self._save_template_to_file(template)
            
            # 更新内存缓存
            self._templates[template.id] = template
            
            logger.info(f"模板已保存: {template.name} ({template.id})")
            return True
            
        except Exception as e:
            logger.error(f"保存模板失败: {e}", exc_info=True)
            return False
    
    def delete_template(self, template_id: str) -> bool:
        """
        删除模板
        
        同时从内存缓存和文件系统中删除。
        
        Args:
            template_id: 模板ID
        
        Returns:
            是否删除成功
        """
        try:
            # 检查模板是否存在
            if template_id not in self._templates:
                logger.warning(f"模板不存在: {template_id}")
                return False
            
            template = self._templates[template_id]
            
            # 从内存删除
            del self._templates[template_id]
            
            # 删除文件
            self._delete_template_file(template_id)
            
            logger.info(f"模板已删除: {template.name} ({template_id})")
            return True
            
        except Exception as e:
            logger.error(f"删除模板失败: {e}", exc_info=True)
            return False
    
    def create_template(self, name: str, description: str = "") -> ParseTemplate:
        """
        创建新模板（仅创建对象，不保存）
        
        Args:
            name: 模板名称
            description: 模板描述
        
        Returns:
            新创建的模板对象
        
        Raises:
            ValueError: 名称为空
        """
        if not name or not name.strip():
            raise ValueError("模板名称不能为空")
        
        return ParseTemplate(
            id=self._generate_id(),
            name=name.strip(),
            description=description.strip() if description else "",
            rules=[]
        )
    
    # ──────────────────────────────────────────────────────
    # 公共方法 - 批量操作
    # ──────────────────────────────────────────────────────
    
    def reload_templates(self):
        """重新加载所有模板（从文件系统刷新缓存）"""
        self._load_all_templates()
        logger.info("模板已重新加载")
    
    def export_template(self, template_id: str, output_path: str) -> bool:
        """
        导出单个模板到指定路径
        
        Args:
            template_id: 模板ID
            output_path: 输出文件路径（.json）
        
        Returns:
            是否导出成功
        """
        try:
            template = self.get_template(template_id)
            if not template:
                raise TemplateNotFoundError(f"模板不存在: {template_id}")
            
            # 确保输出目录存在
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            
            # 复制模板文件
            src_path = os.path.join(self.templates_dir, f"{template_id}.json")
            if os.path.exists(src_path):
                shutil.copy2(src_path, output_path)
            else:
                # 如果文件不存在，从内存序列化
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(self._template_to_dict(template), f, ensure_ascii=False, indent=2)
            
            logger.info(f"模板已导出: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"导出模板失败: {e}", exc_info=True)
            return False
    
    def import_template(self, source_path: str) -> Tuple[bool, str]:
        """
        从文件导入模板
        
        Args:
            source_path: 源文件路径（.json）
        
        Returns:
            (success, message)
        """
        try:
            if not os.path.exists(source_path):
                return False, f"文件不存在: {source_path}"
            
            # 读取并解析
            with open(source_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            template = self._dict_to_template(data)
            
            # 验证
            is_valid, error_msg = template.validate()
            if not is_valid:
                return False, f"模板验证失败: {error_msg}"
            
            # 检查ID冲突，如果存在则生成新ID
            if template.id in self._templates:
                old_id = template.id
                template.id = self._generate_id()
                logger.info(f"模板ID冲突，{old_id} -> {template.id}")
            
            # 保存
            if self.save_template(template):
                return True, f"模板已导入: {template.name}"
            else:
                return False, "保存模板失败"
                
        except json.JSONDecodeError as e:
            return False, f"JSON 解析失败: {e}"
        except Exception as e:
            logger.error(f"导入模板失败: {e}", exc_info=True)
            return False, f"导入失败: {e}"
    
    def export_all_templates(self, output_dir: str) -> Tuple[bool, str]:
        """
        导出所有模板到指定目录
        
        Args:
            output_dir: 输出目录路径
        
        Returns:
            (success, message)
        """
        try:
            os.makedirs(output_dir, exist_ok=True)
            
            count = 0
            for template in self._templates.values():
                output_path = os.path.join(output_dir, f"{template.id}.json")
                if self.export_template(template.id, output_path):
                    count += 1
            
            return True, f"已导出 {count} 个模板到: {output_dir}"
            
        except Exception as e:
            logger.error(f"批量导出失败: {e}", exc_info=True)
            return False, f"导出失败: {e}"
    
    def import_from_directory(self, source_dir: str) -> Tuple[int, int, str]:
        """
        从目录批量导入模板
        
        Args:
            source_dir: 源目录路径
        
        Returns:
            (success_count, failed_count, message)
        """
        if not os.path.isdir(source_dir):
            return 0, 0, f"目录不存在: {source_dir}"
        
        success_count = 0
        failed_count = 0
        
        for filename in os.listdir(source_dir):
            if not filename.endswith('.json'):
                continue
            
            source_path = os.path.join(source_dir, filename)
            success, msg = self.import_template(source_path)
            if success:
                success_count += 1
            else:
                failed_count += 1
                logger.warning(f"导入失败 {filename}: {msg}")
        
        message = f"导入完成: {success_count} 成功, {failed_count} 失败"
        return success_count, failed_count, message
    
    # ──────────────────────────────────────────────────────
    # 工具方法
    # ──────────────────────────────────────────────────────
    
    @staticmethod
    def _generate_id() -> str:
        """生成唯一的模板ID（8位短UUID）"""
        return uuid.uuid4().hex[:8]
    
    def get_template_names(self) -> Dict[str, str]:
        """获取所有模板的 ID->名称 映射
        
        Returns:
            {template_id: template_name}
        """
        return {tid: tpl.name for tid, tpl in self._templates.items()}
    
    def search_templates(self, keyword: str) -> List[ParseTemplate]:
        """搜索模板（按名称或描述）
        
        Args:
            keyword: 搜索关键词
        
        Returns:
            匹配的模板列表
        """
        keyword_lower = keyword.lower()
        results = []
        
        for template in self._templates.values():
            if (keyword_lower in template.name.lower() or 
                keyword_lower in template.description.lower()):
                results.append(template)
        
        results.sort(key=lambda t: t.name)
        return results


# ──────────────────────────────────────────────────────────────
# 全局单例
# ──────────────────────────────────────────────────────────────

_template_manager: Optional[TemplateManager] = None


def get_template_manager() -> TemplateManager:
    """获取全局模板管理器实例（单例）
    
    Returns:
        TemplateManager 全局实例
    """
    global _template_manager
    if _template_manager is None:
        _template_manager = TemplateManager()
    return _template_manager


def reset_template_manager():
    """重置全局模板管理器（主要用于测试）"""
    global _template_manager
    _template_manager = None
