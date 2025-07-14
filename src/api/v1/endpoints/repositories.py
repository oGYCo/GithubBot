from fastapi import APIRouter
from ....schemas.repository import *
from ....services.query_service import query_service

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
    Receive session_id from frontend, return the status of this session, i.e. whether
    this task is completed or not
    """
    return {"message": "Hello World"}

@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    """
    Receive requests containing generation_mode and llm_config, then perform the
    query operation
    """
    query_response = await query_service.query(req)
    return query_response
