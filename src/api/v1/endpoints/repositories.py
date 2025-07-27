from fastapi import APIRouter, HTTPException, BackgroundTasks
from ....schemas.repository import *
import uuid
from ....services.task_queue import task_queue
from ....worker.tasks import process_repository_task
from ....db.session import get_db_session
from ....db.models import AnalysisSession, TaskStatus
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/repos",
    tags=["repos"],
    responses={404: {"description": "Not found"}},
)


@router.post("/analyze")
async def analyze(req: RepoAnalyzeRequest):
    """
    分析仓库
    接收包含 embedding_config 的请求，并将任务推送到 Celery 队列进行异步处理
    """
    try:
        # 生成唯一的会话ID
        session_id = str(uuid.uuid4())
        
        # 创建数据库会话记录
        db = get_db_session()
        try:
            analysis_session = AnalysisSession(
                session_id=session_id,
                repository_url=req.repo_url,
                status=TaskStatus.PENDING,
                embedding_config=req.embedding_config.model_dump(),
                created_at=datetime.now(timezone.utc)
            )
            db.add(analysis_session)
            db.commit()
            logger.info(f"创建分析会话: {session_id}")
        except Exception as e:
            logger.error(f"创建会话记录失败: {str(e)}")
            db.rollback()
            raise HTTPException(status_code=500, detail="Failed to create session")
        finally:
            if db:
                db.close()
        
        # 将任务推送到 Celery
        task = process_repository_task.delay(
            repo_url=req.repo_url,
            session_id=session_id,
            embedding_config=req.embedding_config.model_dump()
        )
        
        return {
            "session_id": session_id,
            "task_id": task.id,
            "status": "queued",
            "message": "Repository analysis has been queued for processing"
        }
        
    except Exception as e:
        logger.error(f"启动分析任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start analysis: {str(e)}")


@router.get("/status/{session_id}")
async def status(session_id: str):
    """
    获取分析会话状态
    从数据库中获取指定会话的状态信息
    """
    try:
        db = get_db_session()
        try:
            session = db.query(AnalysisSession).filter(
                AnalysisSession.session_id == session_id
            ).first()
            
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
            
            return {
                "session_id": session_id,
                "status": session.status.value if hasattr(session.status, 'value') else session.status,
                "repository_url": session.repository_url,
                "repository_name": session.repository_name,
                "repository_owner": session.repository_owner,
                "total_files": session.total_files,
                "processed_files": session.processed_files,
                "total_chunks": session.total_chunks,
                "indexed_chunks": session.indexed_chunks,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "completed_at": session.completed_at.isoformat() if session.completed_at else None,
                "error_message": session.error_message
            }
        finally:
            if db:
                db.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取会话状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get session status: {str(e)}")

@router.post("/query")
async def query(req: QueryRequest):
    """
    Receive requests containing generation_mode and llm_config, then push to Celery
    for async processing
    """
    # 生成唯一的session_id
    session_id = str(uuid.uuid4())
    
    # 将任务推送到Celery
    task_id = await task_queue.push_query_task(session_id, req)
    
    return {
        "session_id": session_id,
        "task_id": task_id,
        "status": "queued",
        "message": "Query task has been queued for processing"
    }

@router.get("/query/status/{session_id}")
async def query_status(session_id: str):
    """
    Get the status and result of a query task
    """
    try:
        status = await task_queue.get_task_status(session_id)
        result = await task_queue.get_query_result(session_id)
        
        # 任务还在处理中
        if result is None:
            return {
                "session_id": session_id,
                "status": status.lower(),
                "message": "Task is still being processed"
            }
        
        # 检查任务是否失败
        if isinstance(result, dict) and result.get("success") == False:
            return {
                "session_id": session_id,
                "status": "failed",
                "error": result.get("error", "Unknown error"),
                "message": "Task failed to complete"
            }
        
        # 任务成功完成，返回QueryResponse结果
        return {
            "session_id": session_id,
            "status": "completed",
            "result": result,  # 这里包含完整的QueryResponse数据
            "message": "Task completed successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving task status: {str(e)}")

@router.get("/query/result/{session_id}")
async def query_result(session_id: str):
    """
    Get the final result of a completed query task
    """
    try:
        result = await task_queue.get_query_result(session_id)
        
        if result is None:
            raise HTTPException(status_code=404, detail="Task not found or still processing")
        
        # 检查任务是否失败
        if isinstance(result, dict) and result.get("success") == False:
            raise HTTPException(
                status_code=400, 
                detail=f"Task failed: {result.get('error', 'Unknown error')}"
            )
        
        # 返回完整的QueryResponse结果
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving result: {str(e)}")

@router.get("/query/info/{session_id}")
async def query_task_info(session_id: str):
    """
    Get comprehensive task information including status, result, and errors
    """
    try:
        task_info = await task_queue.get_task_info(session_id)
        return task_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving task info: {str(e)}")
