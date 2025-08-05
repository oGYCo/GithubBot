"""
API v1 路由聚合
聚合所有 v1 版本的 API 路由器
"""

from fastapi import APIRouter
from .endpoints.repositories import router as repos_router
from .endpoints.settings import router as settings_router

# 创建 v1 API 路由器
api_router = APIRouter()

# 包含各个端点路由器
api_router.include_router(repos_router)
api_router.include_router(settings_router)
