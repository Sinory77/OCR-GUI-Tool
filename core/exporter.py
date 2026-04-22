# 导出模块
# 支持导出为 TXT、JSON、Excel 格式

import json
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

# 配置日志
logger = logging.getLogger(__name__)


class ResultExporter:
    """识别结果导出器
    
    该类负责：
    1. 管理待导出的 OCR 识别结果
    2. 支持导出为 TXT、JSON、Excel 格式
    3. 提供单个结果和批量结果的导出功能
    4. 处理导出过程中的异常
    5. 提供结果的合并和格式化
    """
    
    def __init__(self):
        """初始化导出器"""
        self.results: List[Dict[str, Any]] = []
        self.image_paths: List[str] = []
    
    def add_result(self, image_path: str, ocr_result: Dict[str, Any]) -> None:
        """添加识别结果
        
        Args:
            image_path: 图片路径
            ocr_result: OCR 识别结果
        """
        self.results.append({
            "image_path": image_path,
            "result": ocr_result,
            "timestamp": datetime.now().isoformat()
        })
        if image_path and image_path not in self.image_paths:
            self.image_paths.append(image_path)
    
    def clear(self) -> None:
        """清空所有结果"""
        self.results.clear()
        self.image_paths.clear()
        logger.debug("导出器已清空")
    
    def export_txt(self, file_path: Optional[str] = None) -> str:
        """
        导出为 TXT 格式
        
        Args:
            file_path: 输出文件路径
            
        Returns:
            导出文件路径
        """
        if file_path is None:
            file_path = f"ocr_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("=" * 60 + "\n")
                f.write("OCR 识别结果\n")
                f.write(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"识别图片数: {len(self.results)}\n")
                f.write("=" * 60 + "\n\n")
                
                for i, item in enumerate(self.results, 1):
                    f.write(f"\n--- 图片 {i} ---\n")
                    f.write(f"路径: {item['image_path']}\n")
                    
                    result = item['result']
                    if result.get('code') == 100 and result.get('data'):
                        for j, line in enumerate(result['data'], 1):
                            text = line.get('text', '') if isinstance(line, dict) else str(line)
                            f.write(f"{j}. {text}\n")
                    else:
                        error_code = result.get('code', -1)
                        error_msg = result.get('data', '未知错误')
                        f.write(f"[{error_code}] {error_msg}\n")
                    f.write("\n")
            
            logger.info(f"TXT 导出成功: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"TXT 导出失败: {e}", exc_info=True)
            raise
    
    def export_json(self, file_path: Optional[str] = None, include_details: bool = True) -> str:
        """
        导出为 JSON 格式
        
        Args:
            file_path: 输出文件路径
            include_details: 是否包含详细信息（位置、置信度等）
            
        Returns:
            导出文件路径
        """
        if file_path is None:
            file_path = f"ocr_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            export_data = {
                "export_time": datetime.now().isoformat(),
                "total_images": len(self.results),
                "results": []
            }
            
            for item in self.results:
                result_entry = {
                    "image_path": item['image_path'],
                    "timestamp": item['timestamp'],
                    "code": item['result'].get('code', -1),
                    "success": item['result'].get('code') == 100
                }
                
                if include_details and item['result'].get('code') == 100 and item['result'].get('data'):
                    result_entry["texts"] = []
                    for line in item['result']['data']:
                        if isinstance(line, dict):
                            if include_details:
                                result_entry["texts"].append({
                                    "text": line.get('text', ''),
                                    "confidence": line.get('score', 0),
                                    "box": line.get('box', [])
                                })
                            else:
                                result_entry["texts"].append(line.get('text', ''))
                
                export_data["results"].append(result_entry)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"JSON 导出成功: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"JSON 导出失败: {e}", exc_info=True)
            raise
    
    def export_excel(self, file_path: Optional[str] = None) -> Optional[str]:
        """
        导出为 Excel 格式
        
        Args:
            file_path: 输出文件路径
            
        Returns:
            导出文件路径，失败返回 None
        """
        try:
            import openpyxl
            from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        except ImportError:
            logger.error("需要安装 openpyxl 库来导出 Excel 文件")
            logger.info("请运行: pip install openpyxl")
            return None
        
        if file_path is None:
            file_path = f"ocr_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "OCR识别结果"
            
            # 设置表头样式
            header_font = Font(bold=True, size=12)
            header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
            header_alignment = Alignment(horizontal="center", vertical="center")
            thin_border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )
            
            # 写入表头
            headers = ["序号", "图片路径", "识别状态", "识别文本", "置信度"]
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_alignment
                cell.border = thin_border
            
            # 写入数据
            row = 2
            for i, item in enumerate(self.results, 1):
                result = item['result']
                
                # 序号
                ws.cell(row=row, column=1, value=i).border = thin_border
                
                # 图片路径
                ws.cell(row=row, column=2, value=item['image_path']).border = thin_border
                
                # 识别状态
                status_code = result.get('code', -1)
                status = "成功" if status_code == 100 else f"失败({status_code})"
                ws.cell(row=row, column=3, value=status).border = thin_border
                
                # 识别文本和置信度
                if status_code == 100 and result.get('data'):
                    texts = []
                    confidences = []
                    for line in result['data']:
                        if isinstance(line, dict):
                            texts.append(line.get('text', ''))
                            score = line.get('score', 0)
                            confidences.append(f"{score:.2%}")
                    
                    ws.cell(row=row, column=4, value='\n'.join(texts)).border = thin_border
                    ws.cell(row=row, column=4).alignment = Alignment(wrap_text=True, vertical="top")
                    
                    ws.cell(row=row, column=5, value='\n'.join(confidences)).border = thin_border
                    ws.cell(row=row, column=5).alignment = Alignment(wrap_text=True, vertical="top")
                else:
                    error_msg = result.get('data', '未知错误')
                    ws.cell(row=row, column=4, value=str(error_msg)).border = thin_border
                    ws.cell(row=row, column=5, value="-").border = thin_border
                
                row += 1
            
            # 调整列宽
            ws.column_dimensions['A'].width = 8
            ws.column_dimensions['B'].width = 40
            ws.column_dimensions['C'].width = 12
            ws.column_dimensions['D'].width = 50
            ws.column_dimensions['E'].width = 15
            
            # 添加统计信息
            row += 2
            ws.cell(row=row, column=1, value=f"统计信息").font = Font(bold=True)
            ws.cell(row=row + 1, column=1, value=f"总图片数: {len(self.results)}")
            
            success_count = sum(1 for r in self.results if r['result'].get('code') == 100)
            ws.cell(row=row + 2, column=1, value=f"成功识别: {success_count}")
            ws.cell(row=row + 3, column=1, value=f"失败: {len(self.results) - success_count}")
            ws.cell(row=row + 4, column=1, value=f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            wb.save(file_path)
            logger.info(f"Excel 导出成功: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Excel 导出失败: {e}", exc_info=True)
            return None
    
    def export(self, result: Dict[str, Any], format_type: str, 
              filename: Optional[str] = None, output_dir: Optional[str] = None) -> Optional[str]:
        """
        导出单个结果
        
        Args:
            result: 识别结果（支持两种格式）：
                    - 新格式（JS传来）: {success: true, texts: [...], data: [...]}
                    - 旧格式（原始OCR）: {code: 100, data: [{text: '...', score: ...}, ...]}
            format_type: 导出格式 ("TXT", "JSON", "Excel")
            filename: 文件名（不含扩展名）
            output_dir: 输出目录，默认使用 TEMP 目录
            
        Returns:
            导出文件路径，失败返回 None
        """
        if not result:
            logger.warning("尝试导出空结果")
            return None
        
        if filename is None:
            filename = f"ocr_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 使用指定目录或 TEMP
        if output_dir is None:
            output_dir = os.environ.get('TEMP', '.')
        
        # 确保输出目录存在
        try:
            Path(output_dir).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"创建输出目录失败: {e}")
            return None
        
        # 统一提取文本内容：兼容新旧两种格式
        texts = []
        
        # 新格式（JS传来）
        if 'texts' in result and result['texts']:
            texts = [t for t in result['texts'] if isinstance(t, str)]
        # 旧格式（原始OCR）
        elif result.get('code') == 100 and result.get('data'):
            for item in result['data']:
                if isinstance(item, dict) and 'text' in item:
                    texts.append(item['text'])
        
        if not texts:
            logger.warning("没有可导出的文本内容")
        
        try:
            if format_type.upper() == "TXT":
                # 如果 filename 已包含扩展名，直接使用
                if filename.endswith('.txt'):
                    file_path = os.path.join(output_dir, filename)
                else:
                    file_path = os.path.join(output_dir, f"{filename}.txt")
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(texts))
                
                logger.info(f"TXT 导出成功: {file_path}")
                return file_path
            
            elif format_type.upper() == "JSON":
                if filename.endswith('.json'):
                    file_path = os.path.join(output_dir, filename)
                else:
                    file_path = os.path.join(output_dir, f"{filename}.json")
                
                export_data = {
                    "export_time": datetime.now().isoformat(),
                    "filename": filename,
                    "texts": texts,
                    "count": len(texts),
                    "raw_result": result
                }
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=2)
                
                logger.info(f"JSON 导出成功: {file_path}")
                return file_path
            
            elif format_type.upper() == "EXCEL":
                try:
                    import openpyxl
                    from openpyxl.styles import Font, Alignment
                except ImportError:
                    logger.error("需要安装 openpyxl 库来导出 Excel 文件")
                    return None
                
                if filename.endswith('.xlsx'):
                    file_path = os.path.join(output_dir, filename)
                else:
                    file_path = os.path.join(output_dir, f"{filename}.xlsx")
                
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "OCR识别结果"
                
                # 写入表头
                ws.cell(row=1, column=1, value="序号").font = Font(bold=True)
                ws.cell(row=1, column=2, value="识别文本").font = Font(bold=True)
                
                # 写入数据
                for i, text in enumerate(texts, 1):
                    ws.cell(row=i+1, column=1, value=i)
                    ws.cell(row=i+1, column=2, value=text)
                
                # 调整列宽
                ws.column_dimensions['A'].width = 8
                ws.column_dimensions['B'].width = 60
                
                wb.save(file_path)
                logger.info(f"Excel 导出成功: {file_path}")
                return file_path
            else:
                logger.error(f"不支持的导出格式: {format_type}")
                return None
        except Exception as e:
            logger.error(f"导出失败: {e}", exc_info=True)
            return None
    
    def get_combined_text(self, separator: str = '\n') -> str:
        """获取合并后的文本
        
        Args:
            separator: 分隔符
            
        Returns:
            合并后的文本
        """
        texts = []
        for item in self.results:
            result = item['result']
            if result.get('code') == 100 and result.get('data'):
                for line in result['data']:
                    if isinstance(line, dict) and 'text' in line:
                        texts.append(line['text'])
        return separator.join(texts)


# 全局导出器实例
_exporter: Optional[ResultExporter] = None


def get_exporter() -> ResultExporter:
    """获取全局导出器实例
    
    Returns:
        导出器实例
    """
    global _exporter
    if _exporter is None:
        logger.info("创建全局导出器实例")
        _exporter = ResultExporter()
    return _exporter


def reset_exporter() -> ResultExporter:
    """重置导出器
    
    Returns:
        新的导出器实例
    """
    global _exporter
    logger.info("重置导出器")
    _exporter = ResultExporter()
    return _exporter