from .celery_app import celery_app
from ..schemas.repository import QueryRequest
from ..services.query_service import query_service
import logging

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, name="process_query")
def process_query(self, session_id: str, request_data: dict):
    """
    Celery task to process query requests
    """
    try:
        # 重构QueryRequest对象
        query_request = QueryRequest(**request_data)
        
        # 执行实际的query操作 - 注意这里不能用async/await
        # 如果query_service.query是异步的，需要用同步包装器
        query_response = query_service.query(query_request)
        
        # 返回结果
        result = {
            "success": True,
            "data": query_response.dict() if hasattr(query_response, 'dict') else query_response,
            "session_id": session_id
        }
        
        logger.info(f"Query task {session_id} completed successfully")
        return result
        
    except Exception as e:
        logger.error(f"Query task {session_id} failed: {e}")
        # 返回错误结果
        return {
            "success": False,
            "error": str(e),
            "session_id": session_id
        }