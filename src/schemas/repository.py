from pydantic import BaseModel

class EmbeddingConfig(BaseModel):
    provider: str
    model_name: str
    api_key: str | None = None

class LMMConfig(BaseModel):
    provider: str
    model_name: str
    api_key: str | None = None

class AnalyzeRequest(BaseModel):
    repo_url: str
    embedding_config: EmbeddingConfig

class QueryRequest(BaseModel):
    session_id: str
    question: str
    generation_mode: str
    llm_config: LMMConfig | None = None

class QueryResponse(BaseModel):
    answer: str | None = None
    retrieved_context: str | None = None