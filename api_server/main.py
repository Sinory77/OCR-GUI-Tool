"""
FastAPI主应用
"""
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes.task_routes import router as task_router
from .routes.ocr_routes import router as ocr_router
from .utils.response import APIResponse
from .utils.exceptions import global_exception_handler
from .tasks.task_manager import task_manager


def create_app() -> FastAPI:
    """创建FastAPI应用实例"""
    app = FastAPI(
        title="OCR-GUI API Server",
        description="轻量级OCR API服务，基于FastAPI构建",
        version="1.0.0"
    )

    # 添加CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境中应限制为特定域名
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    app.include_router(task_router)
    app.include_router(ocr_router)

    # 注册全局异常处理器
    app.add_exception_handler(Exception, global_exception_handler)

    @app.get("/")
    async def root():
        """根路径"""
        return APIResponse.success(
            data={"message": "OCR-GUI API Server is running", "version": "1.0.0"},
            message="Server is running"
        )

    @app.get("/health")
    async def health_check():
        """健康检查"""
        return APIResponse.success(
            data={"status": "healthy", "task_manager": "active"},
            message="Health check passed"
        )

    @app.on_event("shutdown")
    async def shutdown_event():
        """应用关闭事件"""
        task_manager.shutdown()
        print("OCR-GUI API Server shutting down...")

    return app


# 创建应用实例
app = create_app()


def run_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """运行服务器"""
    uvicorn.run(
        "api_server.main:app",
        host=host,
        port=port,
        reload=reload,
        workers=1  # 在开发模式下使用单个工作进程
    )


if __name__ == "__main__":
    run_server(host="127.0.0.1", port=8000, reload=True)