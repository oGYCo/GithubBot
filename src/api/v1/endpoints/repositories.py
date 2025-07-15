from fastapi import APIRouter, HTTPException
from ....schemas.repository import *
import uuid
from ....services.task_queue import task_queue

router = APIRouter(
    prefix="/repos",
    tags=["repos"],
    responses={404: {"description": "Not found"}},
)


@router.post("/analyze")
async def analyze(req: RepoAnalyzeRequest):
    """
    Receive requests containing embedding_config, then push to Redis queue a task
    to analyze the embeddings
    """
    return {"message": "Hello World"}

@router.get("/status/{session_id}")
async def status(session_id: str):
    """
    Receive session_id from frontend, return the status of this session
    """
    return {"message": "Hello World"}

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
