// PaddleOCR WebUI - 前端逻辑
// 与 Python 后端通过 pywebview API 通信

class OcrApp {
    constructor() {
        this.currentImagePath = null;
        this.currentResult = null;
        this.history = [];
        this.isProcessing = false;

        this.initElements();
        this.bindEvents();
        this.initBackend();
    }

    initElements() {
        this.languageSelect = document.getElementById('languageSelect');
        this.settingsBtn = document.getElementById('settingsBtn');
        this.openImageBtn = document.getElementById('openImageBtn');
        this.screenshotBtn = document.getElementById('screenshotBtn');
        this.batchBtn = document.getElementById('batchBtn');
        this.dropZone = document.getElementById('dropZone');
        this.imagePreview = document.getElementById('imagePreview');
        this.imageInfo = document.getElementById('imageInfo');
        this.recognizeBtn = document.getElementById('recognizeBtn');
        this.copyBtn = document.getElementById('copyBtn');
        this.exportBtn = document.getElementById('exportBtn');
        this.resultArea = document.getElementById('resultArea');
        this.resultStats = document.getElementById('resultStats');
        this.charCount = document.getElementById('charCount');
        this.lineCount = document.getElementById('lineCount');
        this.historyList = document.getElementById('historyList');
        this.clearHistoryBtn = document.getElementById('clearHistoryBtn');
        this.engineStatus = document.getElementById('engineStatus');
        this.progressText = document.getElementById('progressText');
        this.exportMenu = document.getElementById('exportMenu');
        this.settingsPanel = document.getElementById('settingsPanel');
        this.exePath = document.getElementById('exePath');
        this.detThreshold = document.getElementById('detThreshold');
        this.detThresholdValue = document.getElementById('detThresholdValue');
        this.saveSettingsBtn = document.getElementById('saveSettingsBtn');
        this.cancelSettingsBtn = document.getElementById('cancelSettingsBtn');
        this.closeSettingsBtn = document.getElementById('closeSettingsBtn');
        this.toast = document.getElementById('toast');
        this.toastMessage = document.getElementById('toastMessage');
    }

    bindEvents() {
        if (this.languageSelect) this.languageSelect.addEventListener('change', () => this.onLanguageChange());
        if (this.openImageBtn) this.openImageBtn.addEventListener('click', () => this.openImage());
        if (this.screenshotBtn) this.screenshotBtn.addEventListener('click', () => this.screenshot());
        if (this.batchBtn) this.batchBtn.addEventListener('click', () => this.batchSelect());
        if (this.recognizeBtn) this.recognizeBtn.addEventListener('click', () => this.recognize());
        if (this.dropZone) {
            this.dropZone.addEventListener('dragover', (e) => this.onDragOver(e));
            this.dropZone.addEventListener('dragleave', (e) => this.onDragLeave(e));
            this.dropZone.addEventListener('drop', (e) => this.onDrop(e));
        }
        if (this.copyBtn) this.copyBtn.addEventListener('click', () => this.copyResult());
        if (this.exportBtn) this.exportBtn.addEventListener('click', (e) => this.toggleExportMenu(e));
        document.querySelectorAll('.menu-item').forEach(item => {
            item.addEventListener('click', () => this.exportResult(item.dataset.format));
        });
        document.addEventListener('click', (e) => {
            if (!e.target.closest('#exportBtn') && !e.target.closest('#exportMenu')) {
                this.exportMenu.classList.add('hidden');
            }
        });
        this.clearHistoryBtn.addEventListener('click', () => this.clearHistory());
        this.settingsBtn.addEventListener('click', () => this.showSettings());
        this.closeSettingsBtn.addEventListener('click', () => this.hideSettings());
        this.cancelSettingsBtn.addEventListener('click', () => this.hideSettings());
        this.saveSettingsBtn.addEventListener('click', () => this.saveSettings());
        this.detThreshold.addEventListener('input', () => {
            this.detThresholdValue.textContent = this.detThreshold.value;
        });
        
        // 阻止非标题栏区域的窗口拖动
        this.preventDragOnInteractiveElements();
    }
    
    preventDragOnInteractiveElements() {
        // 非标题栏元素：阻止默认拖动行为
        document.querySelectorAll('.app-container').forEach(el => {
            el.addEventListener('mousedown', (e) => {
                // 阻止拖动
                if (window.pywebview && window.pywebview.api) {
                    window.pywebview.api.prevent_drag();
                }
            });
        });
    }
    
    startTitlebarDrag(e) {
        // 标题栏开始拖动
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.start_drag();
        }
    }

    async initBackend() {
        try {
            await this._waitForPywebview();
            if (typeof window.pywebview.api.get_settings === 'function') {
                const settings = await window.pywebview.api.get_settings();
                if (settings) {
                    this.exePath.value = settings.exe_path || '';
                    this.detThreshold.value = settings.det_threshold || 0.3;
                    this.detThresholdValue.textContent = this.detThreshold.value;
                }
            }
            this.history = await window.pywebview.api.get_history() || [];
            this.renderHistory();
            await window.pywebview.api.init_engine();
        } catch (e) {
            this.showToast('初始化失败: ' + e.message, 'error');
        }
    }

    _waitForPywebview() {
        return new Promise((resolve) => {
            if (window.pywebview && window.pywebview.api) { resolve(); return; }
            window.addEventListener('pywebviewready', function handler() {
                window.removeEventListener('pywebviewready', handler);
                resolve();
            });
            let attempts = 0;
            const poll = setInterval(() => {
                attempts++;
                if (window.pywebview && window.pywebview.api) {
                    clearInterval(poll); resolve();
                } else if (attempts >= 100) {
                    clearInterval(poll); resolve();
                }
            }, 100);
        });
    }

    async openImage() {
        try {
            const result = await window.pywebview.api.open_file_dialog();
            if (result) this.loadImage(result.path);
        } catch (e) {
            this.showToast('打开图片失败: ' + e.message, 'error');
        }
    }

    async screenshot() {
        try {
            const result = await window.pywebview.api.screenshot();
            if (result && result.path) this.loadImage(result.path);
        } catch (e) {
            this.showToast('截图失败: ' + e.message, 'error');
        }
    }

    async batchSelect() {
        try {
            const result = await window.pywebview.api.open_files_dialog();
            if (result && result.paths && result.paths.length > 0) {
                this.loadImage(result.paths[0]);
                this.showToast(`已选择 ${result.paths.length} 张图片`, 'success');
            }
        } catch (e) {
            this.showToast('批量选择失败: ' + e.message, 'error');
        }
    }

    // 加载图片：path=文件路径，dataUrl=可选的 base64（拖拽/截图来源直接预览）
    async loadImage(path, dataUrl) {
        this.currentImagePath = path;
        this.imageInfo.innerHTML = `<span>📄 ${path.split(/[/\\]/).pop()}</span>`;
        this.recognizeBtn.disabled = false;
        this.resultArea.innerHTML = '<p class="placeholder-text">点击"开始识别"提取文字...</p>';
        this.resultStats.classList.add('hidden');

        const imgEl = document.createElement('img');
        imgEl.alt = '预览';

        if (dataUrl) {
            // 有 base64（拖拽/截图）：直接用 dataUrl 预览，无需跨域
            imgEl.src = dataUrl;
            imgEl.onload = () => { this.imagePreview.innerHTML = ''; this.imagePreview.appendChild(imgEl); };
            imgEl.onerror = () => { this.imagePreview.innerHTML = `<p style="color:#e74c3c;font-size:13px">预览失败</p>`; };
        } else {
            // 文件对话框：尝试 file://，失败则用 Python base64 fallback
            imgEl.onload = () => { this.imagePreview.innerHTML = ''; this.imagePreview.appendChild(imgEl); };
            imgEl.onerror = async () => {
                try {
                    const res = await window.pywebview.api.get_image_base64(path);
                    if (res && res.success) {
                        imgEl.src = res.data;
                        this.imagePreview.innerHTML = '';
                        this.imagePreview.appendChild(imgEl);
                    } else {
                        this.imagePreview.innerHTML = `<p style="color:#e74c3c;font-size:13px">预览失败: ${(res && res.error) || '未知错误'}</p>`;
                    }
                } catch (e) {
                    this.imagePreview.innerHTML = `<p style="color:#e74c3c;font-size:13px">预览失败: ${e.message}</p>`;
                }
            };
            imgEl.src = `file:///${path.replace(/\\/g, '/')}`;
        }
        this.imagePreview.innerHTML = '<p style="color:#999;font-size:13px">加载中...</p>';
    }

    onDragOver(e) { e.preventDefault(); e.stopPropagation(); this.dropZone.classList.add('drag-over'); }
    onDragLeave(e) { e.preventDefault(); e.stopPropagation(); this.dropZone.classList.remove('drag-over'); }

    async onDrop(e) {
        e.preventDefault();
        e.stopPropagation();
        this.dropZone.classList.remove('drag-over');
        const files = e.dataTransfer.files;
        if (files.length > 0 && files[0].type.startsWith('image/')) {
            // WebView2 下 file.path 不可靠，用 FileReader 读为 base64 后传给 Python 保存
            const base64 = await this._readFileAsBase64(files[0]);
            this.loadImageFromDataURL(base64, files[0].name);
        }
    }

    _readFileAsBase64(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = () => reject(new Error('读取文件失败'));
            reader.readAsDataURL(file);
        });
    }

    async loadImageFromDataURL(dataUrl, filename) {
        try {
            const result = await window.pywebview.api.save_temp_image(dataUrl);
            if (result && result.success) {
                this.loadImage(result.path, dataUrl);
            } else {
                this.showToast('保存图片失败: ' + (result && result.error), 'error');
            }
        } catch (e) {
            this.showToast('加载图片失败: ' + e.message, 'error');
        }
    }

    async recognize() {
        if (!this.currentImagePath || this.isProcessing) return;
        this.isProcessing = true;
        this.recognizeBtn.disabled = true;
        this.recognizeBtn.innerHTML = '<span class="loading">🔄</span> 识别中...';
        this.progressText.classList.remove('hidden');
        this.progressText.textContent = '正在识别...';

        try {
            const result = await window.pywebview.api.recognize(this.currentImagePath);
            if (result.success) {
                if (!result.text && result.texts) result.text = result.texts.join('\n');
                this.currentResult = result;
                this.displayResult(result.text);
                await this.addToHistory(this.currentImagePath, result);
                this.showToast('识别完成！', 'success');
            } else {
                this.showToast('识别失败: ' + (result.error || '未知错误'), 'error');
            }
        } catch (e) {
            this.showToast('识别失败: ' + e.message, 'error');
        } finally {
            this.isProcessing = false;
            this.recognizeBtn.disabled = false;
            this.recognizeBtn.innerHTML = '🔍 开始识别';
            this.progressText.classList.add('hidden');
        }
    }

    displayResult(text) {
        this.resultArea.textContent = text || '(未识别到文字)';
        this.copyBtn.disabled = !text;
        this.exportBtn.disabled = !text;
        const chars = text ? text.length : 0;
        const lines = text ? text.split('\n').length : 0;
        this.charCount.textContent = `${chars} 字符`;
        this.lineCount.textContent = `${lines} 行`;
        this.resultStats.classList.remove('hidden');
    }

    async copyResult() {
        if (!this.currentResult) {
            this.showToast('没有可复制的内容', 'error');
            return;
        }
        try {
            // 确保传递的是文本字符串，而非整个对象
            const textToCopy = this.currentResult.text || 
                               (this.currentResult.texts ? this.currentResult.texts.join('\n') : '');
            
            if (!textToCopy) {
                this.showToast('没有可复制的内容', 'error');
                return;
            }
            
            const result = await window.pywebview.api.copy_to_clipboard(textToCopy);
            if (result && result.success) {
                this.showToast(`已复制 ${result.text?.length || 0} 字符到剪贴板`, 'success');
            } else {
                this.showToast('复制失败: ' + (result?.error || '未知错误'), 'error');
            }
        } catch (e) {
            this.showToast('复制失败: ' + e.message, 'error');
        }
    }

    toggleExportMenu(e) {
        e.stopPropagation();
        const rect = this.exportBtn.getBoundingClientRect();
        const menuWidth = 180; // 下拉菜单宽度
        const menuHeight = 120; // 估算菜单高度
        const vw = window.innerWidth;
        const vh = window.innerHeight;

        // 检测右边缘：菜单贴右侧还是左侧
        if (rect.right + menuWidth > vw - 10) {
            // 右侧空间不够，菜单向左展开
            this.exportMenu.style.left = (rect.right - menuWidth) + 'px';
        } else {
            this.exportMenu.style.left = rect.left + 'px';
        }

        // 检测下边缘：菜单贴底部还是顶部
        if (rect.bottom + menuHeight + 10 > vh) {
            // 下方空间不够，菜单向上展开
            this.exportMenu.style.top = (rect.top - menuHeight - 5) + 'px';
        } else {
            this.exportMenu.style.top = (rect.bottom + 5) + 'px';
        }

        this.exportMenu.classList.toggle('hidden');
    }

    async exportResult(format) {
        if (!this.currentResult) return;
        this.exportMenu.classList.add('hidden');
        try {
            const result = await window.pywebview.api.export_result(this.currentResult, format, this.currentImagePath);
            if (result.success) {
                this.showToast(`已导出到: ${result.path}`, 'success');
            } else {
                this.showToast('导出失败: ' + (result.error || '未知错误'), 'error');
            }
        } catch (e) {
            this.showToast('导出失败: ' + e.message, 'error');
        }
    }

    async onLanguageChange() {
        const lang = this.languageSelect.value;
        try {
            await window.pywebview.api.change_language(lang);
            this.showToast(`已切换到 ${lang}`, 'success');
        } catch (e) {
            this.showToast('切换语言失败', 'error');
        }
    }

    async addToHistory(path, result) {
        try {
            await window.pywebview.api.add_history(path, result.text);
            this.history = await window.pywebview.api.get_history();
            this.renderHistory();
        } catch (e) {
            console.error('添加历史失败:', e);
        }
    }

    renderHistory() {
        if (this.history.length === 0) {
            this.historyList.innerHTML = '<p class="placeholder-text">暂无历史记录</p>';
            return;
        }
        this.historyList.innerHTML = this.history.map((item, index) => `
            <div class="history-item" data-index="${index}">
                <span class="filename" title="${item.path}">📄 ${item.filename}</span>
                <button class="delete-btn" data-index="${index}">×</button>
            </div>
        `).join('');
        this.historyList.querySelectorAll('.history-item').forEach(item => {
            item.addEventListener('click', (e) => {
                if (!e.target.classList.contains('delete-btn')) {
                    this.loadHistoryItem(parseInt(item.dataset.index));
                }
            });
        });
        this.historyList.querySelectorAll('.delete-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.deleteHistoryItem(parseInt(btn.dataset.index));
            });
        });
    }

    async loadHistoryItem(index) {
        const item = this.history[index];
        if (item) {
            this.currentImagePath = item.path;
            this.loadImage(item.path);
            this.displayResult(item.text);
        }
    }

    async deleteHistoryItem(index) {
        try {
            await window.pywebview.api.delete_history(index);
            this.history = await window.pywebview.api.get_history();
            this.renderHistory();
        } catch (e) {
            console.error('删除历史失败:', e);
        }
    }

    async clearHistory() {
        try {
            await window.pywebview.api.clear_history();
            this.history = [];
            this.renderHistory();
            this.showToast('历史已清空', 'success');
        } catch (e) {
            this.showToast('清空失败', 'error');
        }
    }

    showSettings() { this.settingsPanel.classList.remove('hidden'); }
    hideSettings() { this.settingsPanel.classList.add('hidden'); }

    async saveSettings() {
        try {
            await window.pywebview.api.save_settings({
                exe_path: this.exePath.value,
                det_threshold: parseFloat(this.detThreshold.value)
            });
            this.hideSettings();
            this.showToast('设置已保存', 'success');
        } catch (e) {
            this.showToast('保存失败: ' + e.message, 'error');
        }
    }

    showToast(message, type = 'info') {
        this.toastMessage.textContent = message;
        this.toast.classList.remove('hidden', 'success', 'error', 'info');
        this.toast.classList.add(type);
        setTimeout(() => { this.toast.classList.add('hidden'); }, 3000);
    }
}

function updateEngineStatus(status, error = false) {
    const el = document.getElementById('engineStatus');
    if (el) {
        el.textContent = (error ? '❌ ' : '✅ ') + status;
        el.className = 'status-item ' + (error ? 'error' : 'success');
    }
}

document.addEventListener('DOMContentLoaded', () => { window.app = new OcrApp(); });

function minimizeWindow() { window.pywebview?.api?.minimize?.(); }
function toggleMaximize() {
    const btn = document.getElementById('maximizeBtn');
    const isMax = btn && btn.dataset.maximized === 'true';
    if (isMax) {
        window.pywebview?.api?.restore?.();
        if (btn) { btn.textContent = '☐'; btn.dataset.maximized = 'false'; }
    } else {
        window.pywebview?.api?.maximize?.();
        if (btn) { btn.textContent = '❐'; btn.dataset.maximized = 'true'; }
    }
}
function closeWindow() { window.pywebview?.api?.close?.(); }
