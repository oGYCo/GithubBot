from .celery_app import celery_app
from ..schemas.repository import QueryRequest
from ..services.query_service import query_service
from ..services.ingestion_service import ingestion_service
from ..services.embedding_manager import EmbeddingConfig
import logging

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, name="process_repository")
def process_repository_task(self, repo_url: str, session_id: str, embedding_config: dict):
    """
    Celery 任务：处理仓库分析
    
    Args:
        repo_url: 仓库URL
        session_id: 会话ID
        embedding_config: Embedding配置字典
    """
    try:
        logger.info(f"🚀 [任务开始] 会话ID: {session_id}")
        logger.info(f"📂 [仓库信息] URL: {repo_url}")
        logger.info(f"🤖 [模型配置] Provider: {embedding_config.get('provider')}, Model: {embedding_config.get('model_name')}")
        
        # 更新任务进度
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 100, 'status': '初始化任务...', 'session_id': session_id}
        )
        
        # 调用 ingestion_service 处理仓库
        success = ingestion_service.process_repository(
            repo_url=repo_url,
            session_id=session_id,
            embedding_config=embedding_config,
            task_instance=self  # 传递任务实例用于进度更新
        )
        
        if success:
            logger.info(f"✅ [任务完成] 会话ID: {session_id} - 仓库分析成功完成")
            return {
                "success": True,
                "session_id": session_id,
                "message": "Repository analysis completed successfully"
            }
        else:
            logger.error(f"❌ [任务失败] 会话ID: {session_id} - 仓库分析处理失败")
            return {
                "success": False,
                "session_id": session_id,
                "error": "Repository analysis failed"
            }
            
    except Exception as e:
        logger.error(f"💥 [任务异常] 会话ID: {session_id}, 错误详情: {str(e)}")
        return {
            "success": False,
            "session_id": session_id,
            "error": str(e)
        }


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
            "data": query_response.model_dump() if hasattr(query_response, 'model_dump') else query_response,
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