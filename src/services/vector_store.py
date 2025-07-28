"""
向量数据库服务
负责与 ChromaDB 的交互，提供向量存储和检索功能
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.utils import embedding_functions
from chromadb import Documents, EmbeddingFunction, Embeddings
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings as LangChainEmbeddings

from ..core.config import settings

logger = logging.getLogger(__name__)


class LangChainEmbeddingAdapter(EmbeddingFunction[Documents]):
    """LangChain Embeddings 到 ChromaDB EmbeddingFunction 的适配器"""
    
    def __init__(self, langchain_embedding: LangChainEmbeddings):
        self.langchain_embedding = langchain_embedding
    
    def __call__(self, input: Documents) -> Embeddings:
        """将文档转换为嵌入向量"""
        try:
            logger.debug(f"🔧 [适配器调用] 输入类型: {type(input)}, 输入内容: {input[:2] if isinstance(input, list) and len(input) > 0 else input}")
            
            # 确保输入是字符串列表
            if not isinstance(input, list):
                logger.warning(f"🔧 [输入格式] 输入不是列表类型: {type(input)}, 转换为列表")
                input = [str(input)]
            
            # 检查列表中的每个元素是否为字符串
            cleaned_input = []
            for i, item in enumerate(input):
                if not isinstance(item, str):
                    logger.warning(f"🔧 [元素格式] 第 {i} 个元素不是字符串: {type(item)}, 转换为字符串")
                    item = str(item) if item is not None else ""
                cleaned_input.append(item)
            
            logger.debug(f"🔧 [适配器处理] 清理后的输入长度: {len(cleaned_input)}")
            
            # 使用 LangChain 的 embed_documents 方法
            embeddings = self.langchain_embedding.embed_documents(cleaned_input)
            
            logger.debug(f"🔧 [适配器结果] 生成嵌入向量数量: {len(embeddings) if embeddings else 0}")
            return embeddings
            
        except Exception as e:
            logger.error(f"❌ [适配器失败] 嵌入向量生成失败: {str(e)}")
            logger.error(f"🔍 [错误详情] 输入类型: {type(input)}, 输入长度: {len(input) if hasattr(input, '__len__') else 'N/A'}")
            raise


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
            logger.info(f"🔍 [检查集合] 开始检查集合 {collection_name} 是否存在...")
            # 检查集合是否已存在
            if self.collection_exists(collection_name):
                logger.info(f"✅ [集合存在] 集合 {collection_name} 已存在")
                return True
            
            logger.info(f"📝 [集合不存在] 集合 {collection_name} 不存在，开始创建...")
            logger.info(f"🔧 [参数检查] embedding_function 类型: {type(embedding_function)}")

            # 处理 embedding_function
            chroma_embedding_function = None
            if embedding_function is not None:
                if isinstance(embedding_function, LangChainEmbeddings):
                    # 如果是 LangChain 的 Embeddings，使用适配器包装
                    logger.info(f"🔄 [适配器包装] 使用适配器包装 LangChain Embeddings")
                    chroma_embedding_function = LangChainEmbeddingAdapter(embedding_function)
                else:
                    # 如果已经是 ChromaDB 的 EmbeddingFunction，直接使用
                    chroma_embedding_function = embedding_function

            # 创建新集合
            logger.info(f"🚀 [调用 ChromaDB] 正在调用 client.create_collection...")
            self.client.create_collection(
                name=collection_name,
                embedding_function=chroma_embedding_function,
                metadata={"created_by": "GithubBot"}
            )
            logger.info(f"✅ [ChromaDB 调用完成] client.create_collection 执行成功")

            logger.info(f"🎉 [创建成功] 成功创建集合: {collection_name}")
            return True

        except Exception as e:
            logger.error(f"❌ [创建失败] 创建集合失败 {collection_name}: {str(e)}")
            logger.error(f"🔍 [错误详情] 异常类型: {type(e)}, 异常信息: {str(e)}")
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
            logger.info(f"💾 [存储开始] 集合: {collection_name} - 准备存储 {len(documents)} 个文档到向量数据库")
            collection = self.client.get_collection(collection_name)
            batch_size = batch_size or settings.EMBEDDING_BATCH_SIZE

            total_docs = len(documents)
            total_batches = (total_docs + batch_size - 1) // batch_size
            logger.info(f"📊 [存储配置] 集合: {collection_name} - 批次大小: {batch_size}, 总批次数: {total_batches}")

            for i in range(0, total_docs, batch_size):
                batch_num = i // batch_size + 1
                batch_docs = documents[i:i + batch_size]
                batch_embeddings = embeddings[i:i + batch_size]
                actual_batch_size = len(batch_docs)

                logger.debug(f"🔄 [批次准备] 集合: {collection_name} - 准备第 {batch_num}/{total_batches} 批次 ({actual_batch_size} 个文档)")

                # 准备批次数据
                ids = [f"chunk_{collection_name}_{i + j}" for j in range(len(batch_docs))]
                documents_content = [doc.page_content for doc in batch_docs]
                metadatas = []

                for j, doc in enumerate(batch_docs):
                    metadata = doc.metadata.copy()
                    # 将文档内容也存入元数据（ChromaDB 最佳实践）
                    metadata["content"] = doc.page_content
                    
                    # 确保所有元数据值都是 ChromaDB 支持的基本类型
                    cleaned_metadata = {}
                    for key, value in metadata.items():
                        if value is None:
                            cleaned_metadata[key] = None
                        elif isinstance(value, (str, int, float, bool)):
                            cleaned_metadata[key] = value
                        else:
                            # 将复杂类型转换为字符串
                            logger.debug(f"🔧 [类型转换] 字段 {key}: {type(value)} -> str, 原值: {value}")
                            cleaned_metadata[key] = str(value)
                    
                    # 记录清理后的元数据
                    if j == 0:  # 只记录第一个文档的元数据
                        logger.debug(f"🧹 [元数据清理] 原始: {metadata}")
                        logger.debug(f"🧹 [元数据清理] 清理后: {cleaned_metadata}")
                    
                    metadatas.append(cleaned_metadata)
                    
                    if j < 3:  # 只记录前3个文档的详细信息
                        logger.debug(f"📄 [文档信息] ID: {ids[j]}, 文件: {metadata.get('file_path', 'unknown')}, 大小: {len(doc.page_content)} 字符")

                # 批量添加到 ChromaDB
                logger.debug(f"💾 [写入数据库] 集合: {collection_name} - 正在写入第 {batch_num} 批次到 ChromaDB...")
                collection.add(
                    ids=ids,
                    embeddings=batch_embeddings,
                    documents=documents_content,
                    metadatas=metadatas
                )

                logger.info(f"✅ [批次完成] 集合: {collection_name} - 第 {batch_num}/{total_batches} 批次存储成功 ({actual_batch_size} 个文档)")

            logger.info(f"🎉 [存储完成] 集合: {collection_name} - 成功存储 {total_docs} 个文档到向量数据库")
            return True

        except Exception as e:
            logger.error(f"❌ [存储失败] 集合: {collection_name} - 向量数据库存储失败: {str(e)}")
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
            logger.info(f"🔍 [检查存在性] 正在调用 client.get_collection({collection_name})...")
            self.client.get_collection(collection_name)
            logger.info(f"✅ [集合存在] 集合 {collection_name} 存在")
            return True
        except Exception as e:
            logger.info(f"📝 [集合不存在] 集合 {collection_name} 不存在: {str(e)}")
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


# 全局向量存储实例（延迟初始化）
vector_store = None

def get_vector_store() -> VectorStore:
    """获取向量存储实例（延迟初始化）"""
    global vector_store
    if vector_store is None:
        vector_store = VectorStore()
    return vector_store