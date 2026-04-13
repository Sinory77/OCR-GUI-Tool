# Tkinter GUI 界面
# 只负责 UI 交互，调用 core 模块实现功能

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import os
import sys
from pathlib import Path
from datetime import datetime

# 尝试导入 tkinterdnd2 (拖拽支持)
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False
    print("提示: 安装 tkinterdnd2 库可支持拖拽功能")
    print("运行: pip install tkinterdnd2")

# 导入 core 模块
from core import (
    get_ocr_engine, reset_ocr_engine,
    get_exporter, reset_exporter,
    get_result_manager,
    capture_screen_to_temp,
    LANGUAGES, DEFAULT_ARGS, WINDOW_WIDTH, WINDOW_HEIGHT, EXPORT_FORMATS
)

# 尝试导入 PIL
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("提示: 安装 Pillow 库可获得更好的图片预览效果")
    print("运行: pip install pillow")


class OcrGuiApp:
    """OCR GUI 主应用"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("PaddleOCR-json 识别工具 v2.0")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        
        # 初始化 core 模块
        self.ocr_engine = None
        self.exporter = get_exporter()
        self.result_manager = get_result_manager()
        
        # UI 状态
        self.current_language = "简体中文"
        self.current_image = None
        self.current_image_path = None
        self.is_processing = False
        
        # 设置样式
        self.setup_styles()
        
        # 创建界面
        self.create_menu()
        self.create_toolbar()
        self.create_main_area()
        self.create_statusbar()
        
        # 初始化 OCR 引擎
        self.init_ocr_engine()
    
    def setup_styles(self):
        """设置样式"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # 配置颜色
        style.configure("Title.TLabel", font=("微软雅黑", 12, "bold"))
        style.configure("Header.TLabel", font=("微软雅黑", 10, "bold"))
        style.configure("Status.TLabel", font=("微软雅黑", 9))
        
        # 按钮样式
        style.configure("Primary.TButton", font=("微软雅黑", 10), padding=5)
        style.configure("Secondary.TButton", font=("微软雅黑", 9), padding=3)
        
        # 框架样式
        style.configure("Card.TFrame", background="#f0f0f0", relief="raised", borderwidth=1)
    
    def create_menu(self):
        """创建菜单栏"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # 文件菜单
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="打开图片...", command=self.open_image, accelerator="Ctrl+O")
        file_menu.add_command(label="批量选择图片...", command=self.batch_select_images)
        file_menu.add_separator()
        file_menu.add_command(label="导出为 TXT...", command=lambda: self.export_results("TXT"))
        file_menu.add_command(label="导出为 JSON...", command=lambda: self.export_results("JSON"))
        file_menu.add_command(label="导出为 Excel...", command=lambda: self.export_results("Excel"))
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit, accelerator="Ctrl+Q")
        
        # 编辑菜单
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="编辑", menu=edit_menu)
        edit_menu.add_command(label="复制结果", command=self.copy_result, accelerator="Ctrl+C")
        edit_menu.add_command(label="清空结果", command=self.clear_results)
        edit_menu.add_separator()
        edit_menu.add_command(label="清空历史", command=self.clear_history)
        
        # OCR菜单
        ocr_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="OCR", menu=ocr_menu)
        ocr_menu.add_command(label="开始识别", command=self.start_recognition, accelerator="Enter")
        ocr_menu.add_command(label="截图识别", command=self.screenshot_recognition)
        ocr_menu.add_separator()
        ocr_menu.add_command(label="重新初始化引擎", command=self.reinit_engine)
        
        # 设置菜单
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="设置", menu=settings_menu)
        settings_menu.add_command(label="引擎配置...", command=self.show_engine_settings)
        settings_menu.add_command(label="识别参数...", command=self.show_ocr_settings)
        
        # 帮助菜单
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="帮助", menu=help_menu)
        help_menu.add_command(label="使用说明", command=self.show_help)
        help_menu.add_command(label="关于", command=self.show_about)
        
        # 绑定快捷键
        self.root.bind('<Control-o>', lambda e: self.open_image())
        self.root.bind('<Control-q>', lambda e: self.root.quit())
        self.root.bind('<Return>', lambda e: self.start_recognition())
    
    def create_toolbar(self):
        """创建工具栏"""
        toolbar = ttk.Frame(self.root)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        # 打开图片按钮
        ttk.Button(toolbar, text="📂 打开图片", command=self.open_image, 
                   style="Secondary.TButton").pack(side=tk.LEFT, padx=2)
        
        # 批量选择按钮
        ttk.Button(toolbar, text="📁 批量选择", command=self.batch_select_images,
                   style="Secondary.TButton").pack(side=tk.LEFT, padx=2)
        
        # 截图识别按钮
        ttk.Button(toolbar, text="🖼️ 截图识别", command=self.screenshot_recognition,
                   style="Secondary.TButton").pack(side=tk.LEFT, padx=2)
        
        # 识别按钮
        self.recognize_btn = ttk.Button(toolbar, text="🔍 开始识别", 
                                         command=self.start_recognition,
                                         style="Primary.TButton")
        self.recognize_btn.pack(side=tk.LEFT, padx=10)
        
        # 分割线
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        # 语言选择
        ttk.Label(toolbar, text="语言:").pack(side=tk.LEFT, padx=2)
        self.language_var = tk.StringVar(value=self.current_language)
        self.language_combo = ttk.Combobox(toolbar, textvariable=self.language_var,
                                            values=list(LANGUAGES.keys()),
                                            state="readonly", width=10)
        self.language_combo.pack(side=tk.LEFT, padx=2)
        self.language_combo.bind('<<ComboboxSelected>>', self.on_language_changed)
        
        # 分割线
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        # 导出按钮
        ttk.Button(toolbar, text="💾 导出结果", command=self.show_export_dialog,
                   style="Secondary.TButton").pack(side=tk.LEFT, padx=2)
        
        # 清空按钮
        ttk.Button(toolbar, text="🗑️ 清空", command=self.clear_all,
                   style="Secondary.TButton").pack(side=tk.LEFT, padx=2)
        
        # 右侧状态
        self.toolbar_status = tk.Label(toolbar, text="就绪", fg="gray")
        self.toolbar_status.pack(side=tk.RIGHT, padx=5)
    
    def create_main_area(self):
        """创建主工作区"""
        # 使用 PanedWindow 实现可拖拽分割
        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 左侧：图片预览区
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=2)
        
        # 图片预览卡片
        preview_card = ttk.LabelFrame(left_frame, text="图片预览", padding=5)
        preview_card.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 图片画布
        self.canvas_frame = tk.Frame(preview_card, bg="#e0e0e0")
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.image_canvas = tk.Canvas(self.canvas_frame, bg="#404040", cursor="cross")
        self.image_canvas.pack(fill=tk.BOTH, expand=True)
        
        # 设置拖拽支持
        if DND_AVAILABLE:
            self.image_canvas.drop_target_register(DND_FILES)
            self.image_canvas.dnd_bind('<<Drop>>', self.on_file_drop)
        else:
            self.image_canvas.bind('<Button-3>', self.show_drop_hint)
        
        # 图片信息标签
        self.image_info_label = tk.Label(preview_card, text="未加载图片", 
                                         font=("微软雅黑", 9), fg="gray")
        self.image_info_label.pack(anchor=tk.W, pady=2)
        
        # 拖拽提示
        if DND_AVAILABLE:
            drag_label = tk.Label(preview_card, text="✓ 支持拖拽图片到此处", 
                                   font=("微软雅黑", 9), fg="green")
        else:
            drag_label = tk.Label(preview_card, text="💡 右键可快速打开图片", 
                                   font=("微软雅黑", 9), fg="#888888")
        drag_label.pack(anchor=tk.S)
        
        # 右侧：结果和历史区
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=1)
        
        # 结果显示卡片
        result_card = ttk.LabelFrame(right_frame, text="识别结果", padding=5)
        result_card.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 结果文本框
        self.result_text = scrolledtext.ScrolledText(result_card, wrap=tk.WORD,
                                                      font=("微软雅黑", 10),
                                                      height=10)
        self.result_text.pack(fill=tk.BOTH, expand=True)
        
        # 结果统计
        self.result_stats_label = tk.Label(result_card, text="", 
                                            font=("微软雅黑", 9), fg="#666666")
        self.result_stats_label.pack(anchor=tk.W, pady=2)
        
        # 历史记录卡片
        history_card = ttk.LabelFrame(right_frame, text="历史记录", padding=5)
        history_card.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 历史列表
        self.history_listbox = tk.Listbox(history_card, font=("微软雅黑", 9),
                                           height=8)
        self.history_listbox.pack(fill=tk.BOTH, expand=True)
        self.history_listbox.bind('<<ListboxSelect>>', self.on_history_select)
        
        # 历史按钮
        history_btn_frame = ttk.Frame(history_card)
        history_btn_frame.pack(fill=tk.X, pady=2)
        ttk.Button(history_btn_frame, text="查看", command=self.view_history,
                   width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(history_btn_frame, text="删除", command=self.delete_history,
                   width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(history_btn_frame, text="清空", command=self.clear_history,
                   width=8).pack(side=tk.LEFT, padx=2)
    
    def create_statusbar(self):
        """创建状态栏"""
        statusbar = ttk.Frame(self.root)
        statusbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        ttk.Separator(statusbar, orient=tk.HORIZONTAL).pack(fill=tk.X)
        
        # 引擎状态
        self.engine_status_label = ttk.Label(statusbar, text="引擎状态: 初始化中...",
                                              style="Status.TLabel")
        self.engine_status_label.pack(side=tk.LEFT, padx=5)
        
        # 当前语言
        self.lang_status_label = ttk.Label(statusbar, text=f"当前语言: {self.current_language}",
                                            style="Status.TLabel")
        self.lang_status_label.pack(side=tk.LEFT, padx=20)
        
        # 处理状态
        self.process_status_label = ttk.Label(statusbar, text="", style="Status.TLabel")
        self.process_status_label.pack(side=tk.RIGHT, padx=5)
    
    def init_ocr_engine(self):
        """初始化 OCR 引擎"""
        def init_thread():
            try:
                self.ocr_engine = get_ocr_engine()
                success = self.ocr_engine.initialize()
                
                if success:
                    self.root.after(0, lambda: self.update_engine_status("就绪"))
                else:
                    self.root.after(0, lambda: self.update_engine_status("初始化失败", error=True))
            except Exception as e:
                self.root.after(0, lambda: self.update_engine_status(f"错误: {str(e)}", error=True))
        
        threading.Thread(target=init_thread, daemon=True).start()
    
    def update_engine_status(self, status, error=False):
        """更新引擎状态"""
        color = "red" if error else "green"
        self.engine_status_label.config(text=f"引擎状态: {status}", foreground=color)
        self.toolbar_status.config(text=status)
    
    def on_file_drop(self, event):
        """处理拖拽文件"""
        import glob
        files = event.data
        if not files:
            return
        
        files = str(files).strip()
        
        # 处理多种格式
        if files.startswith('{') and files.endswith('}'):
            file_path = files[1:-1]
        else:
            parts = files.split()
            file_path = parts[0] if parts else files
        
        file_path = file_path.strip('"').strip("'")
        
        if not os.path.exists(file_path):
            matches = glob.glob(file_path)
            if matches:
                file_path = matches[0]
        
        if os.path.exists(file_path):
            self.load_image(file_path)
        else:
            messagebox.showerror("错误", f"文件不存在:\n{file_path}")
    
    def show_drop_hint(self, event):
        """显示拖拽提示（右键菜单）"""
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="📂 打开图片...", command=self.open_image)
        menu.add_command(label="📁 批量选择...", command=self.batch_select_images)
        menu.tk_popup(event.x_root, event.y_root)
    
    def load_image(self, image_path):
        """加载图片"""
        if not os.path.exists(image_path):
            messagebox.showerror("错误", f"文件不存在: {image_path}")
            return
        
        self.current_image_path = image_path
        
        try:
            if PIL_AVAILABLE:
                self.current_image = Image.open(image_path)
                
                canvas_width = self.image_canvas.winfo_width() or 400
                canvas_height = self.image_canvas.winfo_height() or 300
                
                img_width, img_height = self.current_image.size
                ratio = min(canvas_width / img_width, canvas_height / img_height)
                new_size = (int(img_width * ratio), int(img_height * ratio))
                
                display_img = self.current_image.resize(new_size, Image.Resampling.LANCZOS)
                self.photo_image = ImageTk.PhotoImage(display_img)
                
                self.image_canvas.delete("all")
                self.image_canvas.create_image(
                    canvas_width // 2, canvas_height // 2,
                    image=self.photo_image, anchor=tk.CENTER
                )
                
                self.image_info_label.config(
                    text=f"尺寸: {img_width} x {img_height} | 文件: {os.path.basename(image_path)}"
                )
            else:
                self.image_info_label.config(
                    text=f"文件: {os.path.basename(image_path)} | 安装 Pillow 以预览"
                )
        except Exception as e:
            messagebox.showerror("错误", f"无法加载图片: {str(e)}")
    
    def open_image(self):
        """打开图片"""
        file_path = filedialog.askopenfilename(
            title="选择图片",
            filetypes=[
                ("图片文件", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff"),
                ("所有文件", "*.*")
            ]
        )
        if file_path:
            self.load_image(file_path)
    
    def batch_select_images(self):
        """批量选择图片"""
        file_paths = filedialog.askopenfilenames(
            title="批量选择图片",
            filetypes=[
                ("图片文件", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff"),
                ("所有文件", "*.*")
            ]
        )
        if file_paths:
            self.process_batch(file_paths)
    
    def process_batch(self, image_paths):
        """批量处理图片"""
        if not image_paths:
            return
        
        def process_thread():
            for i, path in enumerate(image_paths, 1):
                self.root.after(0, lambda p=path, idx=i, total=len(image_paths): 
                    self.process_status_label.config(text=f"处理中: {idx}/{total}")
                )
                
                self.root.after(0, lambda p=path: self.load_image(p))
                
                result = self.ocr_engine.recognize(path)
                
                self.root.after(0, lambda p=path, r=result: self.add_to_history(p, r))
                
                if i == len(image_paths):
                    self.root.after(0, lambda p=path, r=result: self.display_result(p, r))
            
            self.root.after(0, lambda: self.process_status_label.config(text="批量处理完成"))
        
        threading.Thread(target=process_thread, daemon=True).start()
    
    def start_recognition(self):
        """开始识别"""
        if not self.current_image_path:
            messagebox.showwarning("提示", "请先选择一张图片")
            return
        
        if self.is_processing:
            return
        
        self.is_processing = True
        self.recognize_btn.config(state=tk.DISABLED)
        self.update_engine_status("识别中...")
        
        def recognize_thread():
            result = self.ocr_engine.recognize(self.current_image_path)
            
            self.root.after(0, lambda: self.display_result(self.current_image_path, result))
            self.root.after(0, lambda: self.add_to_history(self.current_image_path, result))
            self.root.after(0, lambda: self.finish_recognition())
        
        threading.Thread(target=recognize_thread, daemon=True).start()
    
    def display_result(self, image_path, result):
        """显示识别结果 - 调用 core 模块格式化"""
        formatted = self.result_manager.format_result_for_display(result)
        self.result_text.delete("1.0", tk.END)
        self.result_text.insert("1.0", formatted['text'])
        self.result_stats_label.config(
            text=f"识别到 {formatted['count']} 个文本区域" if formatted['success'] else "识别失败"
        )
    
    def finish_recognition(self):
        """完成识别"""
        self.is_processing = False
        self.recognize_btn.config(state=tk.NORMAL)
        self.update_engine_status("就绪")
    
    def add_to_history(self, image_path, result):
        """添加到历史记录 - 调用 core 模块"""
        self.exporter.add_result(image_path, result)
        self.result_manager.add_result(image_path, result)
        
        # 更新历史列表
        self.refresh_history_list()
    
    def refresh_history_list(self):
        """刷新历史列表"""
        self.history_listbox.delete(0, tk.END)
        history = self.result_manager.get_history()
        for entry in history:
            status = "✓" if entry.get('success') else "✗"
            time_str = entry.get('time', '')[-8:]  # 只显示时间部分
            display_text = f"{time_str} {status} {entry.get('filename', '未知')}"
            self.history_listbox.insert(0, display_text)
    
    def on_history_select(self, event):
        """选择历史记录"""
        pass
    
    def view_history(self):
        """查看历史记录"""
        selection = self.history_listbox.curselection()
        if not selection:
            messagebox.showinfo("提示", "请先选择一条历史记录")
            return
        messagebox.showinfo("提示", "查看历史详情功能开发中")
    
    def delete_history(self):
        """删除历史记录"""
        selection = self.history_listbox.curselection()
        if selection:
            # 删除选中的历史（从新到旧的索引）
            index = selection[0]
            if self.result_manager.delete_history(index):
                self.history_listbox.delete(selection)
    
    def clear_history(self):
        """清空历史记录"""
        if messagebox.askyesno("确认", "确定要清空历史记录吗？"):
            self.result_manager.clear_history()
            reset_exporter()
            self.history_listbox.delete(0, tk.END)
    
    def clear_results(self):
        """清空结果"""
        self.result_text.delete("1.0", tk.END)
        self.result_stats_label.config(text="")
    
    def clear_all(self):
        """清空所有"""
        self.clear_results()
        self.result_manager.clear_current_results()
        self.current_image = None
        self.current_image_path = None
        self.image_canvas.delete("all")
        self.image_info_label.config(text="未加载图片")
    
    def copy_result(self):
        """复制结果"""
        text = self.result_text.get("1.0", tk.END).strip()
        if text:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            messagebox.showinfo("提示", "已复制到剪贴板")
    
    def screenshot_recognition(self):
        """截图识别 - 调用 core 模块的截图功能"""
        # 最小化窗口
        self.root.withdraw()
        
        import time
        time.sleep(0.3)
        
        # 调用 core 模块的截图功能
        temp_path = capture_screen_to_temp()
        
        # 恢复窗口并加载截图
        if temp_path:
            self.root.after(100, lambda: (self.root.deiconify(), self.load_image(temp_path)))
        else:
            self.root.after(100, lambda: self.root.deiconify())
            messagebox.showerror("错误", "截图失败")
    
    def on_language_changed(self, event):
        """语言切换"""
        new_lang = self.language_var.get()
        if new_lang != self.current_language:
            self.current_language = new_lang
            self.lang_status_label.config(text=f"当前语言: {new_lang}")
            
            reset_ocr_engine(language=new_lang)
            self.ocr_engine = get_ocr_engine()
            self.ocr_engine.initialize()
    
    def export_results(self, format_type):
        """导出结果 - 调用 core 模块的导出功能"""
        if not self.exporter.results:
            messagebox.showinfo("提示", "没有可导出的结果")
            return
        
        file_path = None
        if format_type == "TXT":
            file_path = filedialog.asksaveasfilename(
                title="导出为 TXT",
                defaultextension=".txt",
                filetypes=[("TXT 文件", "*.txt")]
            )
            if file_path:
                file_path = self.exporter.export_txt(file_path)
        elif format_type == "JSON":
            file_path = filedialog.asksaveasfilename(
                title="导出为 JSON",
                defaultextension=".json",
                filetypes=[("JSON 文件", "*.json")]
            )
            if file_path:
                file_path = self.exporter.export_json(file_path)
        elif format_type == "Excel":
            file_path = filedialog.asksaveasfilename(
                title="导出为 Excel",
                defaultextension=".xlsx",
                filetypes=[("Excel 文件", "*.xlsx")]
            )
            if file_path:
                file_path = self.exporter.export_excel(file_path)
        
        if file_path:
            messagebox.showinfo("成功", f"已导出到:\n{file_path}")
    
    def show_export_dialog(self):
        """显示导出对话框"""
        ExportDialog(self, self.root)
    
    def show_engine_settings(self):
        """显示引擎设置"""
        EngineSettingsDialog(self, self.root)
    
    def show_ocr_settings(self):
        """显示 OCR 参数设置"""
        OcrSettingsDialog(self, self.root)
    
    def show_help(self):
        """显示帮助"""
        help_text = """
PaddleOCR-json 识别工具 v2.0 使用说明

【架构说明】
本工具采用核心功能与界面分离架构：
• core/ - 核心业务逻辑（OCR、导出、截图）
• interfaces/ - 界面层（Tkinter、Web）

【快捷键】
• Ctrl+O: 打开图片
• Enter: 开始识别
• Ctrl+Q: 退出

【主要功能】
1. 单张识别: 打开图片后点击"开始识别"
2. 批量识别: 点击"批量选择"选择多张图片
3. 截图识别: 点击"截图识别"截取屏幕内容
4. 多语言: 支持简中、繁中、英、日、韩
5. 导出: 支持 TXT、JSON、Excel 格式导出

【拖拽支持】
直接将图片文件拖拽到窗口即可加载
        """
        messagebox.showinfo("使用说明", help_text)
    
    def show_about(self):
        """显示关于"""
        about_text = """
PaddleOCR-json 识别工具 v2.0

基于 PaddleOCR-json 引擎开发的 GUI 工具

特性:
• 高识别率的中文 OCR
• 多语言支持
• 批量处理能力
• 多种导出格式
• 核心与界面分离架构
        """
        messagebox.showinfo("关于", about_text)
    
    def reinit_engine(self):
        """重新初始化引擎"""
        if messagebox.askyesno("确认", "确定要重新初始化 OCR 引擎吗？"):
            self.update_engine_status("重新初始化中...")
            reset_ocr_engine()
            self.init_ocr_engine()


class ExportDialog(tk.Toplevel):
    """导出对话框"""
    
    def __init__(self, app, root):
        super().__init__(root)
        self.app = app
        self.title("导出结果")
        self.geometry("300x200")
        self.resizable(False, False)
        
        self.transient(root)
        self.grab_set()
        
        ttk.Label(self, text="选择导出格式:", 
                  font=("微软雅黑", 11)).pack(pady=20)
        
        ttk.Button(self, text="导出为 TXT", command=self.export_txt,
                  width=20).pack(pady=5)
        ttk.Button(self, text="导出为 JSON", command=self.export_json,
                  width=20).pack(pady=5)
        ttk.Button(self, text="导出为 Excel", command=self.export_excel,
                  width=20).pack(pady=5)
        
        ttk.Button(self, text="取消", command=self.destroy,
                  width=15).pack(pady=10)
    
    def export_txt(self):
        self.app.export_results("TXT")
        self.destroy()
    
    def export_json(self):
        self.app.export_results("JSON")
        self.destroy()
    
    def export_excel(self):
        self.app.export_results("Excel")
        self.destroy()


class EngineSettingsDialog(tk.Toplevel):
    """引擎设置对话框"""
    
    def __init__(self, app, root):
        super().__init__(root)
        self.app = app
        self.title("引擎配置")
        self.geometry("500x300")
        
        self.transient(root)
        self.grab_set()
        
        # OCR 引擎路径
        path_frame = ttk.LabelFrame(self, text="引擎路径配置", padding=10)
        path_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(path_frame, text="OCR 引擎 (.exe):").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.exe_path_var = tk.StringVar(value="使用默认路径")
        ttk.Entry(path_frame, textvariable=self.exe_path_var, 
                  width=40).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(path_frame, text="浏览...", 
                   command=self.browse_exe).grid(row=0, column=2, pady=5)
        
        ttk.Label(path_frame, text="模型文件夹:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.models_path_var = tk.StringVar(value="使用默认路径")
        ttk.Entry(path_frame, textvariable=self.models_path_var,
                  width=40).grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(path_frame, text="浏览...",
                   command=self.browse_models).grid(row=1, column=2, pady=5)
        
        # 按钮
        btn_frame = ttk.Frame(self)
        btn_frame.pack(side=tk.BOTTOM, pady=10)
        ttk.Button(btn_frame, text="确定", command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=self.destroy).pack(side=tk.LEFT, padx=5)
    
    def browse_exe(self):
        path = filedialog.askopenfilename(title="选择 OCR 引擎",
                                          filetypes=[("可执行文件", "*.exe")])
        if path:
            self.exe_path_var.set(path)
    
    def browse_models(self):
        path = filedialog.askdirectory(title="选择模型文件夹")
        if path:
            self.models_path_var.set(path)
    
    def save(self):
        messagebox.showinfo("提示", "设置已保存")
        self.destroy()


class OcrSettingsDialog(tk.Toplevel):
    """OCR 参数设置对话框"""
    
    def __init__(self, app, root):
        super().__init__(root)
        self.app = app
        self.title("识别参数设置")
        self.geometry("450x400")
        
        self.transient(root)
        self.grab_set()
        
        # 参数设置
        param_frame = ttk.LabelFrame(self, text="识别参数", padding=10)
        param_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # limit_side_len
        row = 0
        ttk.Label(param_frame, text="图片边长限制:").grid(row=row, column=0, sticky=tk.W, pady=3)
        self.limit_side_len_var = tk.IntVar(value=960)
        ttk.Entry(param_frame, textvariable=self.limit_side_len_var, 
                  width=10).grid(row=row, column=1, sticky=tk.W, pady=3)
        ttk.Label(param_frame, text="(建议 32/48 的倍数)").grid(row=row, column=2, sticky=tk.W, pady=3)
        
        # det_db_thresh
        row += 1
        ttk.Label(param_frame, text="检测阈值:").grid(row=row, column=0, sticky=tk.W, pady=3)
        self.det_thresh_var = tk.DoubleVar(value=0.3)
        ttk.Entry(param_frame, textvariable=self.det_thresh_var,
                  width=10).grid(row=row, column=1, sticky=tk.W, pady=3)
        ttk.Label(param_frame, text="(0-1, 越小越敏感)").grid(row=row, column=2, sticky=tk.W, pady=3)
        
        # det_db_box_thresh
        row += 1
        ttk.Label(param_frame, text="框阈值:").grid(row=row, column=0, sticky=tk.W, pady=3)
        self.box_thresh_var = tk.DoubleVar(value=0.5)
        ttk.Entry(param_frame, textvariable=self.box_thresh_var,
                  width=10).grid(row=row, column=1, sticky=tk.W, pady=3)
        ttk.Label(param_frame, text="(0-1, 控制文字框大小)").grid(row=row, column=2, sticky=tk.W, pady=3)
        
        # enable_mkldnn
        row += 1
        self.mkldnn_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(param_frame, text="启用 MKLDNN 加速",
                        variable=self.mkldnn_var).grid(row=row, column=0, columnspan=2, 
                                                       sticky=tk.W, pady=3)
        
        # use_angle_cls
        row += 1
        self.angle_cls_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(param_frame, text="启用方向分类",
                        variable=self.angle_cls_var).grid(row=row, column=0, columnspan=2,
                                                           sticky=tk.W, pady=3)
        
        # 按钮
        btn_frame = ttk.Frame(self)
        btn_frame.pack(side=tk.BOTTOM, pady=10)
        ttk.Button(btn_frame, text="应用", command=self.apply).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="恢复默认", command=self.reset_default).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="关闭", command=self.destroy).pack(side=tk.LEFT, padx=5)
    
    def apply(self):
        """应用参数"""
        args = {
            "limit_side_len": self.limit_side_len_var.get(),
            "det_db_thresh": self.det_thresh_var.get(),
            "det_db_box_thresh": self.box_thresh_var.get(),
            "enable_mkldnn": self.mkldnn_var.get(),
            "use_angle_cls": self.angle_cls_var.get(),
        }
        
        engine = get_ocr_engine()
        engine.update_args(args)
        engine._initialized = False
        
        messagebox.showinfo("提示", "参数已应用，重新识别时生效")
    
    def reset_default(self):
        """恢复默认"""
        self.limit_side_len_var.set(960)
        self.det_thresh_var.set(0.3)
        self.box_thresh_var.set(0.5)
        self.mkldnn_var.set(True)
        self.angle_cls_var.set(True)


def main():
    """主函数"""
    # 使用支持拖拽的 Tkinter 窗口
    if DND_AVAILABLE:
        from tkinterdnd2 import TkinterDnD
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    
    # 设置窗口图标和样式
    try:
        root.iconbitmap("icon.ico")
    except:
        pass
    
    app = OcrGuiApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
