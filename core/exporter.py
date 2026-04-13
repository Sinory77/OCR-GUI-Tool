# 导出模块
# 支持导出为 TXT、JSON、Excel 格式

import json
import os
from datetime import datetime
from pathlib import Path


class ResultExporter:
    """识别结果导出器"""
    
    def __init__(self):
        self.results = []
        self.image_paths = []
    
    def add_result(self, image_path, ocr_result):
        """添加识别结果"""
        self.results.append({
            "image_path": image_path,
            "result": ocr_result,
            "timestamp": datetime.now().isoformat()
        })
        if image_path and image_path not in self.image_paths:
            self.image_paths.append(image_path)
    
    def clear(self):
        """清空所有结果"""
        self.results.clear()
        self.image_paths.clear()
    
    def export_txt(self, file_path=None):
        """
        导出为 TXT 格式
        
        Args:
            file_path: 输出文件路径
            
        Returns:
            str: 导出文件路径
        """
        if file_path is None:
            file_path = f"ocr_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
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
                if result['code'] == 100:
                    for j, line in enumerate(result['data'], 1):
                        f.write(f"{j}. {line['text']}\n")
                else:
                    f.write(f"[{result['code']}] {result['data']}\n")
                f.write("\n")
        
        return file_path
    
    def export_json(self, file_path=None, include_details=True):
        """
        导出为 JSON 格式
        
        Args:
            file_path: 输出文件路径
            include_details: 是否包含详细信息（位置、置信度等）
            
        Returns:
            str: 导出文件路径
        """
        if file_path is None:
            file_path = f"ocr_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        export_data = {
            "export_time": datetime.now().isoformat(),
            "total_images": len(self.results),
            "results": []
        }
        
        for item in self.results:
            result_entry = {
                "image_path": item['image_path'],
                "timestamp": item['timestamp'],
                "code": item['result']['code'],
                "success": item['result']['code'] == 100
            }
            
            if include_details and item['result']['code'] == 100:
                result_entry["texts"] = []
                for line in item['result']['data']:
                    if include_details:
                        result_entry["texts"].append({
                            "text": line['text'],
                            "confidence": line['score'],
                            "box": line['box']
                        })
                    else:
                        result_entry["texts"].append(line['text'])
            
            export_data["results"].append(result_entry)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        return file_path
    
    def export_excel(self, file_path=None):
        """
        导出为 Excel 格式
        
        Args:
            file_path: 输出文件路径
            
        Returns:
            str: 导出文件路径
        """
        try:
            import openpyxl
            from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        except ImportError:
            print("需要安装 openpyxl 库来导出 Excel 文件")
            print("运行: pip install openpyxl")
            return None
        
        if file_path is None:
            file_path = f"ocr_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
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
            status = "成功" if result['code'] == 100 else f"失败({result['code']})"
            ws.cell(row=row, column=3, value=status).border = thin_border
            
            # 识别文本和置信度
            if result['code'] == 100:
                texts = []
                confidences = []
                for line in result['data']:
                    texts.append(line['text'])
                    confidences.append(f"{line['score']:.2%}")
                
                ws.cell(row=row, column=4, value='\n'.join(texts)).border = thin_border
                ws.cell(row=row, column=4).alignment = Alignment(wrap_text=True, vertical="top")
                
                ws.cell(row=row, column=5, value='\n'.join(confidences)).border = thin_border
                ws.cell(row=row, column=5).alignment = Alignment(wrap_text=True, vertical="top")
            else:
                ws.cell(row=row, column=4, value=result['data']).border = thin_border
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
        
        success_count = sum(1 for r in self.results if r['result']['code'] == 100)
        ws.cell(row=row + 2, column=1, value=f"成功识别: {success_count}")
        ws.cell(row=row + 3, column=1, value=f"失败: {len(self.results) - success_count}")
        ws.cell(row=row + 4, column=1, value=f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        wb.save(file_path)
        return file_path
    
    def export(self, result, format_type, filename=None, output_dir=None):
        """
        导出单个结果
        
        Args:
            result: 识别结果（支持两种格式）：
                    - 新格式（JS传来）: {success: true, texts: [...], data: [...]}
                    - 旧格式（原始OCR）: {code: 100, data: [{text: '...', score: ...}, ...]}
            format_type: 导出格式 ("TXT", "JSON", "Excel")
            filename: 文件名（不含扩展名）
            output_dir: 输出目录，默认使用图片所在目录
            
        Returns:
            str: 导出文件路径
        """
        if filename is None:
            filename = "ocr_result"
        
        # 使用指定目录或 TEMP
        if output_dir is None:
            output_dir = os.environ.get('TEMP', '.')
        
        # 统一提取文本内容：兼容新旧两种格式
        texts = []
        
        # 新格式（JS传来）
        if 'texts' in result and result['texts']:
            texts = result['texts']
        # 旧格式（原始OCR）
        elif result.get('code') == 100:
            for item in result.get('data', []):
                texts.append(item.get('text', ''))
        
        if format_type.upper() == "TXT":
            # 如果 filename 已包含扩展名，直接使用
            if filename.endswith('.txt'):
                file_path = os.path.join(output_dir, filename)
            else:
                file_path = os.path.join(output_dir, f"{filename}.txt")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(texts))
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
            return file_path
        
        elif format_type.upper() == "EXCEL":
            try:
                import openpyxl
                from openpyxl.styles import Font, Alignment
            except ImportError:
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
            return file_path
        
        return None
    
    def get_combined_text(self, separator='\n'):
        """获取合并后的文本"""
        texts = []
        for item in self.results:
            result = item['result']
            if result['code'] == 100:
                for line in result['data']:
                    texts.append(line['text'])
        return separator.join(texts)


# 全局导出器实例
_exporter = None


def get_exporter():
    """获取全局导出器实例"""
    global _exporter
    if _exporter is None:
        _exporter = ResultExporter()
    return _exporter


def reset_exporter():
    """重置导出器"""
    global _exporter
    _exporter = ResultExporter()
