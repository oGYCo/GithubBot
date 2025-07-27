import json
import logging
from typing import Optional, Dict, Any
from ..schemas.repository import QueryRequest
from ..worker.tasks import process_query
from celery.result import AsyncResult
from celery.exceptions import Retry, WorkerLostError

logger = logging.getLogger(__name__)

class TaskQueue:
    def __init__(self):
        self.result_prefix = "celery-task-meta-"
        
    async def push_query_task(self, session_id: str, request: QueryRequest) -> str:
        """Push query task to Celery"""
        try:
            # 使用Celery任务，task_id就是session_id
            task = process_query.apply_async(
                args=[session_id, request.model_dump()],  # 使用 model_dump() 替代 dict()
                task_id=session_id,
                retry=True,
                retry_policy={
                    'max_retries': 3,
                    'interval_start': 0,
                    'interval_step': 0.2,
                    'interval_max': 0.2,
                }
            )
            logger.info(f"Task {session_id} submitted successfully")
            return task.id
        except Exception as e:
            logger.error(f"Failed to submit task {session_id}: {str(e)}")
            raise
        
    async def get_query_result(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get query result from Celery"""
        try:
            result = AsyncResult(session_id)
            
            if result.ready():
                if result.successful():
                    logger.info(f"Task {session_id} completed successfully")
                    return result.result
                else:
                    error_info = result.info
                    logger.error(f"Task {session_id} failed: {error_info}")
                    return {
                        "success": False,
                        "error": str(error_info) if error_info else "Unknown error",
                        "session_id": session_id,
                        "status": result.status
                    }
            else:
                # 任务还在处理中
                logger.debug(f"Task {session_id} is still processing")
                return None
                
        except (WorkerLostError, ConnectionError) as e:
            logger.error(f"Worker connection error for task {session_id}: {str(e)}")
            return {
                "success": False,
                "error": "Worker connection lost",
                "session_id": session_id,
                "status": "FAILURE"
            }
        except Exception as e:
            logger.error(f"Error retrieving result for task {session_id}: {str(e)}")
            return {
                "success": False,
                "error": f"Error retrieving result: {str(e)}",
                "session_id": session_id,
                "status": "UNKNOWN"
            }
        
    async def get_task_status(self, session_id: str) -> str:
        """Get task status"""
        try:
            result = AsyncResult(session_id)
            status = result.status
            logger.debug(f"Task {session_id} status: {status}")
            return status
        except Exception as e:
            logger.error(f"Error getting status for task {session_id}: {str(e)}")
            return "UNKNOWN"
            
    async def cancel_task(self, session_id: str) -> bool:
        """Cancel a task"""
        try:
            result = AsyncResult(session_id)
            result.revoke(terminate=True)
            logger.info(f"Task {session_id} cancelled successfully")
            return True
        except Exception as e:
            logger.error(f"Error cancelling task {session_id}: {str(e)}")
            return False
    
    async def cancel_repository_task(self, task_id: str) -> bool:
        """Cancel a repository analysis task"""
        try:
            result = AsyncResult(task_id)
            result.revoke(terminate=True)
            logger.info(f"🛑 [任务取消] 仓库分析任务已取消 - 任务ID: {task_id}")
            return True
        except Exception as e:
            logger.error(f"❌ [取消失败] 取消仓库分析任务失败 - 任务ID: {task_id}, 错误: {str(e)}")
            return False
    
    async def get_repository_task_status(self, task_id: str) -> str:
        """Get repository analysis task status"""
        try:
            result = AsyncResult(task_id)
            status = result.status
            logger.debug(f"📊 [任务状态] 仓库分析任务状态 - 任务ID: {task_id}, 状态: {status}")
            return status
        except Exception as e:
            logger.error(f"❌ [状态查询失败] 获取仓库分析任务状态失败 - 任务ID: {task_id}, 错误: {str(e)}")
            return "UNKNOWN"
    
    async def get_task_info(self, session_id: str) -> Dict[str, Any]:
        """Get comprehensive task information"""
        try:
            result = AsyncResult(session_id)
            return {
                "task_id": session_id,
                "status": result.status,
                "ready": result.ready(),
                "successful": result.successful() if result.ready() else None,
                "result": result.result if result.ready() and result.successful() else None,
                "error": str(result.info) if result.ready() and not result.successful() else None,
                "traceback": result.traceback if result.ready() and not result.successful() else None
            }
        except Exception as e:
            logger.error(f"Error getting task info for {session_id}: {str(e)}")
            return {
                "task_id": session_id,
                "status": "UNKNOWN",
                "error": str(e)
            }

task_queue = TaskQueue()