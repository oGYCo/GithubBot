from celery import Celery
import os
from ..core.config import settings

def make_celery_config() -> dict:
    """生成 Celery 配置"""
    return {
        "broker_url": settings.REDIS_URL,
        "result_backend": settings.REDIS_URL,
        "task_serializer": "json",
        "accept_content": ["json"],
        "result_serializer": "json",
        "timezone": "UTC",
        "enable_utc": True,
        "task_track_started": True,
        "worker_prefetch_multiplier": 1,  # 防止任务积压
        "task_acks_late": True,  # 任务完成后才确认
        "worker_disable_rate_limits": False,
        "task_compression": 'gzip',  # 压缩大任务
        "result_expires": 3600,  # 结果过期时间（1小时）
        "task_routes": {
            "src.worker.tasks.process_query": {"queue": "query_queue"},
        },
        "task_annotations": {
            "*": {"rate_limit": "10/s"}  # 全局限流
        }
    }

# 创建Celery实例，使用配置文件中的Redis URL
celery_app = Celery(
    settings.APP_NAME.lower().replace(" ", "_"),  # 使用配置中的应用名称
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["src.worker.tasks"]  # 修正导入路径
)

# 应用配置
celery_app.conf.update(make_celery_config())

# 如果在调试模式下，启用更详细的日志
if settings.DEBUG:
    celery_app.conf.update(
        worker_log_level="DEBUG",
        task_eager_propagates_exceptions=True,
    )