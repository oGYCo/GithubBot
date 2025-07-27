"""
GitHub Bot 主应用入口
FastAPI 应用实例，聚合所有 API 路由
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from datetime import datetime

from .core.config import settings, setup_logging, validate_config
from .api.v1.api import api_router
from .db.session import create_tables

# 配置日志
setup_logging()
logger = logging.getLogger(__name__)

# 创建 FastAPI 应用实例
app = FastAPI(
    title="GitHub Repository Analysis Bot",
    description="智能分析 GitHub 仓库并提供问答服务",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该设置具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    logger.info("正在启动 GitHub Bot API 服务...")
    
    # 验证配置
    validate_config()
    
    # 创建数据库表
    try:
        create_tables()
        logger.info("数据库表创建完成")
    except Exception as e:
        logger.error(f"数据库表创建失败: {str(e)}")
        raise
    
    logger.info("GitHub Bot API 服务启动完成")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    logger.info("GitHub Bot API 服务正在关闭...")


# 注册路由
app.include_router(api_router, prefix="/api/v1")

@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "GitHub Repository Analysis Bot API",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    """健康检查"""
    from .db.session import get_db_session
    from .services.vector_store import vector_store
    
    health_status = {
        "status": "healthy",
        "service": "github-bot",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "checks": {}
    }
    
    # 数据库连接检查
    try:
        db = get_db_session()
        db.execute("SELECT 1")
        db.close()
        health_status["checks"]["database"] = "healthy"
    except Exception as e:
        health_status["checks"]["database"] = f"unhealthy: {str(e)}"
        health_status["status"] = "unhealthy"
    
    # Redis 连接检查（间接通过 Celery）
    try:
        from .worker.celery_app import celery_app
        inspect = celery_app.control.inspect()
        inspect.stats()
        health_status["checks"]["redis"] = "healthy"
    except Exception as e:
        health_status["checks"]["redis"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    # ChromaDB 连接检查
    try:
        vector_store._connect()
        health_status["checks"]["chromadb"] = "healthy"
    except Exception as e:
        health_status["checks"]["chromadb"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    return health_status

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
