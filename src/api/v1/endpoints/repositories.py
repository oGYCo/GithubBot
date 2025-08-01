from fastapi import APIRouter, HTTPException, BackgroundTasks
from ....schemas.repository import *
import uuid
from ....services.task_queue import task_queue
from ....worker.tasks import process_repository_task
from ....db.session import get_db_session
from ....db.models import AnalysisSession, TaskStatus
from ....services.query_service import QueryService
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
        logger.info(f"🚀 [API请求] 收到仓库分析请求 - URL: {req.repo_url}")
        logger.info(f"⚙️ [请求配置] Embedding提供商: {req.embedding_config.provider}, 模型: {req.embedding_config.model_name}")
        
        # 生成唯一的会话ID
        session_id = str(uuid.uuid4())
        logger.info(f"🆔 [会话创建] 生成会话ID: {session_id}")
        
        # 将任务推送到 Celery
        logger.info(f"📤 [任务队列] 正在推送任务到Celery队列...")
        task = process_repository_task.delay(
            repo_url=req.repo_url,
            session_id=session_id,
            embedding_config=req.embedding_config.model_dump()
        )
        logger.info(f"✅ [任务队列] 任务推送成功 - 任务ID: {task.id}")
        
        # 创建数据库会话记录并保存 task_id（在同一个事务中）
        logger.info(f"💾 [数据库] 正在创建会话记录并保存任务ID...")
        db = get_db_session()
        try:
            analysis_session = AnalysisSession(
                session_id=session_id,
                repository_url=req.repo_url,
                status=TaskStatus.PENDING,
                embedding_config=req.embedding_config.model_dump(),
                created_at=datetime.now(timezone.utc),
                task_id=task.id  # 直接在创建时设置task_id
            )
            db.add(analysis_session)
            db.commit()
            logger.info(f"✅ [数据库] 会话记录创建成功，任务ID已保存: {session_id} -> {task.id}")
        except Exception as e:
            logger.error(f"❌ [数据库错误] 创建会话记录失败: {str(e)}")
            db.rollback()
            # 如果数据库操作失败，取消已创建的Celery任务
            try:
                task.revoke(terminate=True)
                logger.info(f"🛑 [任务取消] 由于数据库错误，已取消Celery任务: {task.id}")
            except Exception as revoke_error:
                logger.error(f"❌ [取消失败] 无法取消Celery任务: {revoke_error}")
            raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")
        finally:
            if db:
                db.close()
        
        response = {
            "session_id": session_id,
            "task_id": task.id,
            "status": "queued",
            "message": "Repository analysis has been queued for processing"
        }
        logger.info(f"🎉 [API响应] 分析请求处理完成 - 会话ID: {session_id}")
        return response
        
    except Exception as e:
        logger.error(f"💥 [API错误] 启动分析任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start analysis: {str(e)}")


@router.get("/status/{session_id}")
async def status(session_id: str):
    """
    获取分析会话状态
    从数据库中获取指定会话的状态信息
    """
    try:
        logger.info(f"📊 [状态查询] 收到状态查询请求 - 会话ID: {session_id}")
        
        db = get_db_session()
        try:
            logger.debug(f"💾 [数据库查询] 正在查询会话状态...")
            session = db.query(AnalysisSession).filter(
                AnalysisSession.session_id == session_id
            ).first()
            
            if not session:
                logger.warning(f"⚠️ [会话不存在] 未找到会话: {session_id}")
                raise HTTPException(status_code=404, detail="Session not found")
            
            logger.info(f"✅ [状态获取] 会话状态: {session.status}, 仓库: {session.repository_url}")
            
            response = {
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
            
            logger.debug(f"📈 [进度统计] 处理文件: {session.processed_files}/{session.total_files}, 索引块: {session.indexed_chunks}/{session.total_chunks}")
            return response
            
        finally:
            if db:
                db.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [状态查询错误] 获取会话状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get session status: {str(e)}")

@router.post("/query")
async def query(req: QueryRequest):
    """
    Receive requests containing generation_mode and llm_config, then push to Celery
    for async processing
    """
    logger.info(f"🔍 [查询请求] 收到查询请求 - 目标会话: {req.session_id}")
    logger.info(f"❓ [查询内容] 问题: {req.question[:100]}{'...' if len(req.question) > 100 else ''}")
    logger.info(f"⚙️ [查询配置] 生成模式: {req.generation_mode}")
    
    if req.llm_config:
        logger.info(f"🤖 [LLM配置] 提供商: {req.llm_config.provider}, 模型: {req.llm_config.model_name}")
    
    # 生成唯一的session_id
    session_id = str(uuid.uuid4())
    logger.info(f"🆔 [任务会话] 生成查询任务会话ID: {session_id}")
    
    # 将任务推送到Celery
    logger.info(f"📤 [任务队列] 正在推送查询任务到队列...")
    task_id = await task_queue.push_query_task(session_id, req)
    logger.info(f"✅ [任务队列] 查询任务推送成功 - 任务ID: {task_id}")
    
    response = {
        "session_id": session_id,
        "task_id": task_id,
        "status": "queued",
        "message": "Query task has been queued for processing"
    }
    
    logger.info(f"🎉 [查询响应] 查询请求处理完成 - 任务会话ID: {session_id}")
    return response

@router.delete("/analyze/{session_id}")
async def cancel_analysis(session_id: str):
    """
    停止仓库分析任务
    """
    try:
        logger.info(f"🛑 [停止请求] 收到停止仓库分析请求 - 会话ID: {session_id}")
        
        # 从数据库获取任务信息
        db = get_db_session()
        try:
            analysis_session = db.query(AnalysisSession).filter(
                AnalysisSession.session_id == session_id
            ).first()
            
            if not analysis_session:
                logger.warning(f"⚠️ [会话不存在] 未找到会话 - 会话ID: {session_id}")
                raise HTTPException(status_code=404, detail="Analysis session not found")
            
            # 检查任务状态
            if analysis_session.status in [TaskStatus.SUCCESS, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                logger.info(f"ℹ️ [任务已完成] 任务已处于终态 - 状态: {analysis_session.status.value}")
                return {
                    "session_id": session_id,
                    "status": analysis_session.status.value,
                    "message": f"Task is already in final state: {analysis_session.status.value}"
                }
            
            # 获取 Celery 任务ID
            task_id = analysis_session.task_id
            if not task_id:
                logger.error(f"❌ [任务ID缺失] 会话缺少任务ID - 会话ID: {session_id}")
                raise HTTPException(status_code=400, detail="Task ID not found for this session")
            
            # 取消 Celery 任务
            logger.info(f"🛑 [取消任务] 正在取消Celery任务 - 任务ID: {task_id}")
            cancel_success = await task_queue.cancel_repository_task(task_id)
            
            if cancel_success:
                # 更新数据库状态为已取消
                analysis_session.status = TaskStatus.CANCELLED
                analysis_session.completed_at = datetime.now(timezone.utc)
                analysis_session.error_message = "Task cancelled by user request"
                db.commit()
                
                logger.info(f"✅ [取消成功] 仓库分析任务已成功取消 - 会话ID: {session_id}")
                return {
                    "session_id": session_id,
                    "status": "cancelled",
                    "message": "Repository analysis task has been cancelled successfully"
                }
            else:
                logger.error(f"❌ [取消失败] 无法取消Celery任务 - 任务ID: {task_id}")
                raise HTTPException(status_code=500, detail="Failed to cancel the task")
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ [数据库错误] 停止任务时发生数据库错误: {str(e)}")
            db.rollback()
            raise HTTPException(status_code=500, detail="Database error while cancelling task")
        finally:
            if db:
                db.close()
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"💥 [停止错误] 停止仓库分析任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel analysis: {str(e)}")


@router.get("/query/status/{session_id}")
async def query_status(session_id: str):
    """
    Get only the basic status information of a query task (without result data)
    Returns: task status, progress info, and basic metadata - optimized for frequent polling
    """
    try:
        logger.info(f"📊 [查询状态] 收到查询状态请求 - 任务会话ID: {session_id}")
        
        logger.debug(f"🔍 [状态检查] 正在获取任务状态...")
        status = await task_queue.get_task_status(session_id)
        
        # 获取基本任务信息（不包含完整结果）
        task_info = await task_queue.get_task_info(session_id)
        
        response = {
            "session_id": session_id,
            "status": status.lower(),
            "ready": task_info.get("ready", False),
            "successful": task_info.get("successful"),
            "message": {
                "PENDING": "Task is queued and waiting to be processed",
                "STARTED": "Task is currently being processed", 
                "SUCCESS": "Task completed successfully",
                "FAILURE": "Task failed to complete",
                "RETRY": "Task is being retried",
                "REVOKED": "Task was cancelled"
            }.get(status, "Task status unknown")
        }
        
        # 如果任务失败，包含错误信息但不包含完整结果
        if status == "FAILURE" and task_info.get("error"):
            response["error"] = task_info.get("error")
            logger.error(f"❌ [任务失败] 查询任务失败 - 错误: {task_info.get('error')}")
        
        logger.info(f"📈 [状态响应] 任务状态: {status}, 是否就绪: {task_info.get('ready', False)}")
        return response
        
    except Exception as e:
        logger.error(f"❌ [状态查询错误] 获取查询任务状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving task status: {str(e)}")

@router.get("/query/result/{session_id}")
async def query_result(session_id: str):
    """
    Get only the final result data of a completed query task
    Returns: the actual query response data (answer, retrieved_context, etc.) without status metadata
    """
    try:
        logger.info(f"📄 [结果获取] 收到查询结果请求 - 任务会话ID: {session_id}")
        
        result = await task_queue.get_query_result(session_id)
        
        if result is None:
            logger.warning(f"⚠️ [结果未找到] 任务结果不存在或仍在处理中 - 会话ID: {session_id}")
            raise HTTPException(status_code=404, detail="Task result not found or still processing")
        
        # 检查任务是否失败
        if isinstance(result, dict) and result.get("success") == False:
            error_msg = result.get('error', 'Unknown error')
            logger.error(f"❌ [任务失败] 查询任务失败 - 错误: {error_msg}")
            raise HTTPException(
                status_code=400, 
                detail=f"Task failed: {error_msg}"
            )
        
        # 只返回实际的查询数据，去除包装层
        if isinstance(result, dict) and "data" in result:
            query_data = result["data"]
            logger.info(f"✅ [结果返回] 成功返回查询数据 - 包含答案和上下文")
            return query_data
        else:
            logger.info(f"✅ [结果返回] 成功返回查询结果")
            return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [结果获取错误] 获取查询结果失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving result: {str(e)}")

@router.get("/query/info/{session_id}")
async def query_task_info(session_id: str):
    """
    Get comprehensive task information including status, result, timing, and debug info
    Returns: complete task metadata with execution details - ideal for debugging and monitoring
    """
    try:
        logger.info(f"🔍 [任务信息] 收到任务信息查询请求 - 任务会话ID: {session_id}")
        
        # 获取基础任务信息
        task_info = await task_queue.get_task_info(session_id)
        
        # 获取完整结果（如果可用）
        result = await task_queue.get_query_result(session_id)
        
        # 构建增强的任务信息响应
        enhanced_info = {
            "session": session_id,
            "status": task_info.get("status", "UNKNOWN"),
            "ready": task_info.get("ready", False),
            "successful": task_info.get("successful"),
            "execution_info": {
                "has_result": result is not None,
                "result_type": type(result).__name__ if result else None,
                "error": task_info.get("error"),
                "traceback": task_info.get("traceback")
            }
        }
        
        # 如果有结果，添加结果摘要信息
        if result and isinstance(result, dict):
            if result.get("success") and "data" in result:
                data = result["data"]
                enhanced_info["result_summary"] = {
                    "success": True,
                    "has_answer": "answer" in data if isinstance(data, dict) else False,
                    "context_chunks": len(data.get("retrieved_context", [])) if isinstance(data, dict) else 0,
                    "generation_mode": data.get("generation_mode") if isinstance(data, dict) else None,
                    "timing": {
                        "retrieval_time": data.get("retrieval_time") if isinstance(data, dict) else None,
                        "generation_time": data.get("generation_time") if isinstance(data, dict) else None,
                        "total_time": data.get("total_time") if isinstance(data, dict) else None
                    }
                }
            else:
                enhanced_info["result_summary"] = {
                    "success": False,
                    "error": result.get("error", "Unknown error")
                }
        
        # 如果需要完整结果，可以选择性包含
        # enhanced_info["full_result"] = result  # 可选：包含完整结果
        
        logger.info(f"📊 [信息汇总] 任务状态: {enhanced_info['status']}, 是否成功: {enhanced_info['successful']}, 有结果: {enhanced_info['execution_info']['has_result']}")
        return enhanced_info
        
    except Exception as e:
        logger.error(f"❌ [信息获取错误] 获取任务信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving task info: {str(e)}")

@router.delete("/cache")
async def clear_cache():
    """
    Clear BM25 cache to apply improved tokenization and file name matching logic
    """
    try:
        logger.info("🧹 [缓存清理] 收到清除BM25缓存请求")
        
        # 创建QueryService实例并清除缓存
        query_service = QueryService()
        query_service.clear_cache()
        
        logger.info("✅ [缓存清理] BM25缓存已成功清除")
        return {
            "status": "success",
            "message": "BM25 cache cleared successfully"
        }
        
    except Exception as e:
        logger.error(f"❌ [缓存清理错误] 清除BM25缓存失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")
