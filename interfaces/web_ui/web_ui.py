# web_ui 主程序 - pywebview Web 界面入口
# 调用 core 模块实现功能

import os
import sys

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)
os.chdir(project_root)

import webview

from .api import WebApi, WindowControlApi


class CombinedApi(WebApi, WindowControlApi):
    """组合 API：同时包含业务 API 和窗口控制"""
    pass


def main():
    """启动 Web UI"""
    # 创建组合 API 实例
    api = CombinedApi()
    
    # 设置状态回调（通过 evaluate_js 推送状态到前端）
    window_ref = [None]

    def status_callback(status, is_error=False):
        if window_ref[0]:
            js = f'updateEngineStatus({repr(status)}, {str(is_error).lower()})'
            try:
                window_ref[0].evaluate_js(js)
            except Exception:
                pass

    api.set_status_callback(status_callback)
    
    # 创建窗口
    html_path = os.path.join(os.path.dirname(__file__), 'web', 'index.html')
    window = webview.create_window(
        title='PaddleOCR 识别工具 v2.0',
        url=html_path,
        width=1100,
        height=750,
        min_size=(800, 600),
        frameless=True,
        resizable=True,
        js_api=api
    )
    window_ref[0] = window
    
    # 尝试设置窗口图标
    icon_path = os.path.join(project_root, 'icon.ico')
    if os.path.exists(icon_path):
        try:
            webview.set_icon(icon_path)
        except Exception:
            pass
    
    # 启动应用
    webview.start(debug=False)


if __name__ == '__main__':
    main()

