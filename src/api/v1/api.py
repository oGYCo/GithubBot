from fastapi import APIRouter
from .endpoints import repositories # 假设你也有items.py

api = APIRouter()
api.include_router(repositories.router)