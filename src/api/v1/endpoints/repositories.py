from fastapi import APIRouter

router = APIRouter(
    prefix="/repos",
    tags=["repos"],
    responses={404: {"description": "Not found"}},
)


@router.get("/analyze")
async def analyze():
    """
    Receive requests containing embedding_config, then push to Redis queue a task
    to analyze the embeddings
    """
    return {"message": "Hello World"}

@router.get("/status/{session_id}")
async def status(session_id: int):
    """
    Receive session_id from frontend, return the status of this session, i.e. whether
    this task is completed or not
    """
    return {"message": "Hello World"}

@router.get("/query")
async def query():
    """
    Receive requests containing generation_mode and llm_config, then perform the
    query operation
    """
    return {"message": "Hello World"}