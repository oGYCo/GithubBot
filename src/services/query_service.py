"""
查询服务
实现混合检索（向量检索 + BM25 关键词检索）和重排序
"""

import time
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from rank_bm25 import BM25Okapi

from ..core.config import settings
from ..db.session import get_db_session
from ..db.models import AnalysisSession, QueryLog, TaskStatus
from ..services.embedding_manager import EmbeddingManager, EmbeddingConfig
from ..services.llm_manager import LLMManager, LLMConfig
from ..services.vector_store import vector_store
from ..schemas.repository import (
    QueryRequest, QueryResponse, RetrievedChunk,
    GenerationMode, LLMConfig as LLMConfigSchema
)

logger = logging.getLogger(__name__)


class QueryService:
    """查询服务"""

    def __init__(self):
        self._bm25_cache = {}  # 缓存 BM25 索引
        self._documents_cache = {}  # 缓存文档内容

    def query(self, request: QueryRequest) -> QueryResponse:
        """
        处理查询请求

        Args:
            request: 查询请求

        Returns:
            QueryResponse: 查询响应
        """
        start_time = time.time()
        db = get_db_session()

        try:
            # 验证会话
            session = self._validate_session(db, request.session_id)
            if not session:
                return QueryResponse(
                    answer="会话不存在或分析未完成",
                    generation_mode=request.generation_mode
                )

            # 执行混合检索
            retrieval_start = time.time()
            retrieved_chunks = self._hybrid_retrieval(
                session.session_id,
                session.embedding_config,
                request.question
            )
            retrieval_time = int((time.time() - retrieval_start) * 1000)

            # 准备响应
            response = QueryResponse(
                retrieved_context=retrieved_chunks,
                generation_mode=request.generation_mode,
                retrieval_time=retrieval_time
            )

            # 根据生成模式处理
            if request.generation_mode == GenerationMode.SERVICE and request.llm_config:
                # 服务端生成答案
                generation_start = time.time()
                answer = self._generate_answer(
                    request.question,
                    retrieved_chunks,
                    request.llm_config
                )
                generation_time = int((time.time() - generation_start) * 1000)

                response.answer = answer
                response.generation_time = generation_time

            response.total_time = int((time.time() - start_time) * 1000)

            # 记录查询日志
            self._log_query(
                db, request, response, retrieved_chunks
            )

            return response

        except Exception as e:
            logger.error(f"查询处理失败: {str(e)}")
            return QueryResponse(
                answer=f"查询处理失败: {str(e)}",
                generation_mode=request.generation_mode,
                total_time=int((time.time() - start_time) * 1000)
            )

        finally:
            db.close()

    def _validate_session(self, db: Session, session_id: str) -> Optional[AnalysisSession]:
        """
        验证会话状态

        Args:
            db: 数据库会话
            session_id: 会话 ID

        Returns:
            Optional[AnalysisSession]: 会话对象或 None
        """
        session = db.query(AnalysisSession).filter(
            AnalysisSession.session_id == session_id
        ).first()

        if not session:
            logger.warning(f"会话不存在: {session_id}")
            return None

        if session.status != TaskStatus.SUCCESS:
            logger.warning(f"会话分析未完成: {session_id}, 状态: {session.status}")
            return None

        return session

    def _hybrid_retrieval(
            self,
            session_id: str,
            embedding_config: Dict[str, Any],
            question: str
    ) -> List[RetrievedChunk]:
        """
        混合检索：向量检索 + BM25 关键词检索

        Args:
            session_id: 会话 ID
            embedding_config: Embedding 配置
            question: 用户问题

        Returns:
            List[RetrievedChunk]: 检索结果
        """
        # 1. 向量检索
        vector_results = self._vector_search(session_id, embedding_config, question)

        # 2. BM25 关键词检索
        bm25_results = self._bm25_search(session_id, question)

        # 3. RRF 融合
        final_results = self._reciprocal_rank_fusion(vector_results, bm25_results)

        # 4. 取前 N 个结果
        return final_results[:settings.FINAL_CONTEXT_TOP_K]

    def _vector_search(
            self,
            session_id: str,
            embedding_config: Dict[str, Any],
            question: str
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        """
        向量检索

        Args:
            session_id: 会话 ID
            embedding_config: Embedding 配置
            question: 用户问题

        Returns:
            List[Tuple[str, float, Dict[str, Any]]]: (文档ID, 分数, 元数据)
        """
        try:
            # 创建 embedding 配置对象
            embedding_cfg = EmbeddingConfig(
                provider=embedding_config["provider"],
                model_name=embedding_config["model_name"],
                api_key=embedding_config.get("api_key"),
                api_base=embedding_config.get("api_base"),
                api_version=embedding_config.get("api_version"),
                deployment_name=embedding_config.get("deployment_name"),
                **embedding_config.get("extra_params", {})
            )

            # 加载 embedding 模型
            embedding_model = EmbeddingManager.get_embedding_model(embedding_cfg)

            # 向量化问题
            question_embedding = embedding_model.embed_query(question)

            # 在向量数据库中搜索
            results = vector_store.query_collection(
                collection_name=session_id,
                query_embedding=question_embedding,
                n_results=settings.VECTOR_SEARCH_TOP_K
            )

            # 转换结果格式
            vector_results = []
            if results["ids"] and results["ids"][0]:
                for i, doc_id in enumerate(results["ids"][0]):
                    distance = results["distances"][0][i]
                    # 将距离转换为相似度分数（距离越小，分数越高）
                    score = 1.0 / (1.0 + distance)
                    metadata = results["metadatas"][0][i]
                    vector_results.append((doc_id, score, metadata))

            return vector_results

        except Exception as e:
            logger.error(f"向量检索失败: {str(e)}")
            return []

    def _bm25_search(
            self,
            session_id: str,
            question: str
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        """
        BM25 关键词检索

        Args:
            session_id: 会话 ID
            question: 用户问题

        Returns:
            List[Tuple[str, float, Dict[str, Any]]]: (文档ID, 分数, 元数据)
        """
        try:
            # 获取或构建 BM25 索引
            bm25_index = self._get_bm25_index(session_id)
            if not bm25_index:
                return []

            # 分词（简单空格分割）
            query_tokens = question.lower().split()

            # BM25 搜索
            doc_scores = bm25_index.get_scores(query_tokens)

            # 获取文档信息
            documents = self._documents_cache.get(session_id, [])

            # 排序并取前 N 个
            scored_docs = [
                (documents[i]["id"], score, documents[i]["metadata"])
                for i, score in enumerate(doc_scores)
                if score > 0
            ]
            scored_docs.sort(key=lambda x: x[1], reverse=True)

            return scored_docs[:settings.BM25_SEARCH_TOP_K]

        except Exception as e:
            logger.error(f"BM25 检索失败: {str(e)}")
            return []

    def _get_bm25_index(self, session_id: str):
        """
        获取或构建 BM25 索引

        Args:
            session_id: 会话 ID

        Returns:
            BM25Okapi 索引或 None
        """
        # 检查缓存
        if session_id in self._bm25_cache:
            return self._bm25_cache[session_id]

        try:
            # 获取所有文档
            documents = vector_store.get_all_documents_from_collection(session_id)
            if not documents:
                return None

            # 准备文档文本
            doc_texts = []
            for doc in documents:
                # 使用元数据中的内容
                content = doc["metadata"].get("content", doc["content"])
                doc_texts.append(content.lower().split())

            # 构建 BM25 索引
            bm25_index = BM25Okapi(doc_texts)

            # 缓存索引和文档
            self._bm25_cache[session_id] = bm25_index
            self._documents_cache[session_id] = documents

            logger.info(f"为会话 {session_id} 构建了 BM25 索引，包含 {len(documents)} 个文档")
            return bm25_index

        except Exception as e:
            logger.error(f"构建 BM25 索引失败: {str(e)}")
            return None

    def _reciprocal_rank_fusion(
            self,
            vector_results: List[Tuple[str, float, Dict[str, Any]]],
            bm25_results: List[Tuple[str, float, Dict[str, Any]]],
            k: int = 60
    ) -> List[RetrievedChunk]:
        """
        RRF (Reciprocal Rank Fusion) 算法融合两个检索结果

        Args:
            vector_results: 向量检索结果
            bm25_results: BM25 检索结果
            k: RRF 参数

        Returns:
            List[RetrievedChunk]: 融合后的结果
        """
        # 创建文档 ID 到信息的映射
        doc_info = {}

        # 处理向量检索结果
        for rank, (doc_id, score, metadata) in enumerate(vector_results):
            if doc_id not in doc_info:
                doc_info[doc_id] = {
                    "metadata": metadata,
                    "content": metadata.get("content", ""),
                    "vector_rank": rank + 1,
                    "bm25_rank": None,
                    "rrf_score": 0.0
                }
            doc_info[doc_id]["rrf_score"] += 1.0 / (k + rank + 1)

        # 处理 BM25 检索结果
        for rank, (doc_id, score, metadata) in enumerate(bm25_results):
            if doc_id not in doc_info:
                doc_info[doc_id] = {
                    "metadata": metadata,
                    "content": metadata.get("content", ""),
                    "vector_rank": None,
                    "bm25_rank": rank + 1,
                    "rrf_score": 0.0
                }
            else:
                doc_info[doc_id]["bm25_rank"] = rank + 1
            doc_info[doc_id]["rrf_score"] += 1.0 / (k + rank + 1)

        # 按 RRF 分数排序
        sorted_docs = sorted(
            doc_info.items(),
            key=lambda x: x[1]["rrf_score"],
            reverse=True
        )

        # 转换为 RetrievedChunk 格式
        retrieved_chunks = []
        for doc_id, info in sorted_docs:
            chunk = RetrievedChunk(
                id=doc_id,
                content=info["content"],
                file_path=info["metadata"].get("file_path", ""),
                start_line=info["metadata"].get("start_line"),
                score=info["rrf_score"],
                metadata=info["metadata"]
            )
            retrieved_chunks.append(chunk)

        return retrieved_chunks

    def _generate_answer(
            self,
            question: str,
            retrieved_chunks: List[RetrievedChunk],
            llm_config: LLMConfigSchema
    ) -> str:
        """
        使用 LLM 生成答案

        Args:
            question: 用户问题
            retrieved_chunks: 检索到的上下文
            llm_config: LLM 配置

        Returns:
            str: 生成的答案
        """
        try:
            # 创建 LLM 配置对象
            llm_cfg = LLMConfig(
                provider=llm_config.provider,
                model_name=llm_config.model_name,
                api_key=llm_config.api_key,
                api_base=llm_config.api_base,
                api_version=llm_config.api_version,
                deployment_name=llm_config.deployment_name,
                temperature=llm_config.temperature,
                max_tokens=llm_config.max_tokens,
                **llm_config.extra_params
            )

            # 加载 LLM 模型
            llm = LLMManager.get_llm(llm_cfg)

            # 构建 prompt
            context = self._build_context(retrieved_chunks)
            prompt = self._build_prompt(question, context)

            # 生成答案
            response = llm.invoke(prompt)

            # 提取答案文本
            if hasattr(response, 'content'):
                return response.content
            else:
                return str(response)

        except Exception as e:
            logger.error(f"生成答案失败: {str(e)}")
            return f"生成答案失败: {str(e)}"

    def _build_context(self, retrieved_chunks: List[RetrievedChunk]) -> str:
        """
        构建上下文字符串

        Args:
            retrieved_chunks: 检索到的文档块

        Returns:
            str: 格式化的上下文
        """
        context_parts = []

        for i, chunk in enumerate(retrieved_chunks):
            context_part = f"[文档 {i+1}] 文件: {chunk.file_path}"
            if chunk.start_line:
                context_part += f" (行 {chunk.start_line})"
            context_part += f"\n{chunk.content}\n"
            context_parts.append(context_part)

        return "\n".join(context_parts)

    def _build_prompt(self, question: str, context: str) -> str:
        """
        构建 LLM prompt

        Args:
            question: 用户问题
            context: 上下文

        Returns:
            str: 完整的 prompt
        """
        prompt = f"""你是一个专业的代码分析助手，请根据提供的代码仓库内容回答用户问题。

上下文信息：
{context}

用户问题：{question}

请根据上述上下文信息回答问题。如果上下文中没有相关信息，请明确说明。回答时请：
1. 提供准确、具体的信息
2. 引用相关的文件名和行号
3. 解释代码的功能和逻辑
4. 如果涉及多个文件，请说明它们之间的关系

回答："""

        return prompt

    def _log_query(
            self,
            db: Session,
            request: QueryRequest,
            response: QueryResponse,
            retrieved_chunks: List[RetrievedChunk]
    ):
        """
        记录查询日志

        Args:
            db: 数据库会话
            request: 查询请求
            response: 查询响应
            retrieved_chunks: 检索结果
        """
        try:
            query_log = QueryLog(
                session_id=request.session_id,
                question=request.question,
                answer=response.answer,
                retrieved_chunks_count=len(retrieved_chunks),
                generation_mode=request.generation_mode.value,
                llm_config=request.llm_config.dict() if request.llm_config else None,
                retrieval_time=response.retrieval_time,
                generation_time=response.generation_time,
                total_time=response.total_time
            )

            db.add(query_log)
            db.commit()

        except Exception as e:
            logger.error(f"记录查询日志失败: {str(e)}")
            db.rollback()


# 全局服务实例
query_service = QueryService()