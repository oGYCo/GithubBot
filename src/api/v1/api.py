from fastapi import APIRouter
from .endpoints import repositories # 假设你也有items.py

app = APIRouter()
app.include_router(repositories.router)