"""
向量数据库服务
负责与 ChromaDB 的交互，提供向量存储和检索功能
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.utils import embedding_functions
from langchain.schema import Document

from ..core.config import settings

logger = logging.getLogger(__name__)


class VectorStore:
    """向量数据库客户端"""

    def __init__(self):
        """初始化 ChromaDB 客户端"""
        self.client = None
        self._connect()

    def _connect(self):
        """连接到 ChromaDB"""
        try:
            # 根据配置选择连接方式
            if settings.CHROMADB_PERSISTENT_PATH:
                # 使用持久化存储
                self.client = chromadb.PersistentClient(
                    path=settings.CHROMADB_PERSISTENT_PATH,
                    settings=ChromaSettings(
                        anonymized_telemetry=False,
                        allow_reset=True
                    )
                )
                logger.info(f"已连接到持久化 ChromaDB: {settings.CHROMADB_PERSISTENT_PATH}")
            else:
                # 使用 HTTP 客户端
                self.client = chromadb.HttpClient(
                    host=settings.CHROMADB_HOST,
                    port=settings.CHROMADB_PORT,
                    settings=ChromaSettings(
                        anonymized_telemetry=False
                    )
                )
                logger.info(f"已连接到 ChromaDB 服务器: {settings.CHROMADB_HOST}:{settings.CHROMADB_PORT}")

        except Exception as e:
            logger.error(f"连接 ChromaDB 失败: {str(e)}")
            raise

    def create_collection(self, collection_name: str, embedding_function=None) -> bool:
        """
        创建某个git仓库的集合

        Args:
            collection_name: 集合名称
            embedding_function: 嵌入函数

        Returns:
            bool: 是否创建成功
        """
        try:
            # 检查集合是否已存在
            if self.collection_exists(collection_name):
                logger.info(f"集合 {collection_name} 已存在")
                return True

            # 创建新集合
            self.client.create_collection(
                name=collection_name,
                embedding_function=embedding_function,
                metadata={"created_by": "GithubBot"}
            )

            logger.info(f"成功创建集合: {collection_name}")
            return True

        except Exception as e:
            logger.error(f"创建集合失败 {collection_name}: {str(e)}")
            return False

    def delete_collection(self, collection_name: str) -> bool:
        """
        删除集合

        Args:
            collection_name: 集合名称

        Returns:
            bool: 是否删除成功
        """
        try:
            self.client.delete_collection(collection_name)
            logger.info(f"成功删除集合: {collection_name}")
            return True
        except Exception as e:
            logger.error(f"删除集合失败 {collection_name}: {str(e)}")
            return False

    def add_documents_to_collection(
            self,
            collection_name: str,
            documents: List[Document],
            embeddings: List[List[float]],
            batch_size: int = None
    ) -> bool:
        """
        向集合添加文档

        Args:
            collection_name: 集合名称
            documents: 文档列表
            embeddings: 嵌入向量列表
            batch_size: 批处理大小

        Returns:
            bool: 是否添加成功
        """
        try:
            collection = self.client.get_collection(collection_name)
            batch_size = batch_size or settings.EMBEDDING_BATCH_SIZE

            total_docs = len(documents)
            logger.info(f"开始向集合 {collection_name} 添加 {total_docs} 个文档")

            for i in range(0, total_docs, batch_size):
                batch_docs = documents[i:i + batch_size]
                batch_embeddings = embeddings[i:i + batch_size]

                # 准备批次数据
                ids = [f"chunk_{collection_name}_{i + j}" for j in range(len(batch_docs))]
                documents_content = [doc.page_content for doc in batch_docs]
                metadatas = []

                for doc in batch_docs:
                    metadata = doc.metadata.copy()
                    # 将文档内容也存入元数据（ChromaDB 最佳实践）
                    metadata["content"] = doc.page_content
                    metadatas.append(metadata)

                # 批量添加到 ChromaDB
                collection.add(
                    ids=ids,
                    embeddings=batch_embeddings,
                    documents=documents_content,
                    metadatas=metadatas
                )

                logger.info(f"已添加批次 {i // batch_size + 1}/{(total_docs + batch_size - 1) // batch_size}")

            logger.info(f"成功向集合 {collection_name} 添加了 {total_docs} 个文档")
            return True

        except Exception as e:
            logger.error(f"向集合添加文档失败 {collection_name}: {str(e)}")
            return False

    def query_collection(
            self,
            collection_name: str,
            query_embedding: List[float],
            n_results: int = 10,
            where: Optional[Dict[str, Any]] = None,
            include: List[str] = None
    ) -> Dict[str, Any]:
        """
        查询集合

        Args:
            collection_name: 集合名称
            query_embedding: 查询向量
            n_results: 返回结果数量
            where: 元数据过滤条件
            include: 包含的字段

        Returns:
            Dict[str, Any]: 查询结果
        """
        try:
            collection = self.client.get_collection(collection_name)

            include = include or ["metadatas", "documents", "distances"]

            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where,
                include=include
            )

            return results

        except Exception as e:
            logger.error(f"查询集合失败 {collection_name}: {str(e)}")
            return {"ids": [[]], "distances": [[]], "metadatas": [[]], "documents": [[]]}

    def get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        """
        获取集合统计信息

        Args:
            collection_name: 集合名称

        Returns:
            Dict[str, Any]: 统计信息
        """
        try:
            collection = self.client.get_collection(collection_name)
            count = collection.count()

            return {
                "name": collection_name,
                "count": count,
                "metadata": collection.metadata or {}
            }

        except Exception as e:
            logger.error(f"获取集合统计失败 {collection_name}: {str(e)}")
            return {"name": collection_name, "count": 0, "metadata": {}}

    def list_collections(self) -> List[str]:
        """
        列出所有集合

        Returns:
            List[str]: 集合名称列表
        """
        try:
            collections = self.client.list_collections()
            return [col.name for col in collections]
        except Exception as e:
            logger.error(f"列出集合失败: {str(e)}")
            return []

    def collection_exists(self, collection_name: str) -> bool:
        """
        检查集合是否存在

        Args:
            collection_name: 集合名称

        Returns:
            bool: 是否存在
        """
        try:
            self.client.get_collection(collection_name)
            return True
        except Exception:
            return False

    def get_all_documents_from_collection(self, collection_name: str) -> List[Dict[str, Any]]:
        """
        获取集合中的所有文档（用于 BM25 检索）

        Args:
            collection_name: 集合名称

        Returns:
            List[Dict[str, Any]]: 文档列表
        """
        try:
            collection = self.client.get_collection(collection_name)

            # 获取所有文档
            results = collection.get(
                include=["metadatas", "documents"]
            )

            documents = []
            for i, doc_id in enumerate(results["ids"]):
                documents.append({
                    "id": doc_id,
                    "content": results["documents"][i],
                    "metadata": results["metadatas"][i]
                })

            return documents

        except Exception as e:
            logger.error(f"获取集合所有文档失败 {collection_name}: {str(e)}")
            return []

    def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            Dict[str, Any]: 健康状态
        """
        try:
            # 尝试列出集合
            collections = self.list_collections()

            return {
                "status": "healthy",
                "collections_count": len(collections),
                "collections": collections[:5]  # 只返回前5个集合名
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }


# 全局向量存储实例
vector_store = VectorStore()