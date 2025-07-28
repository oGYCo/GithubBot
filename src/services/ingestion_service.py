"""
数据注入服务
负责完整的仓库分析流水线：克隆 -> 解析 -> 分块 -> 向量化 -> 存储
"""

import os
import time
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_exponential
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from datetime import datetime, timezone

from ..core.config import settings
from ..db.session import get_db_session
from ..db.models import AnalysisSession, FileMetadata, TaskStatus
from ..utils.git_helper import GitHelper
from ..utils.file_parser import FileParser
from ..services.embedding_manager import EmbeddingManager, EmbeddingConfig
from ..services.vector_store import get_vector_store

logger = logging.getLogger(__name__)


class IngestionService:
    """数据注入服务"""

    def __init__(self):
        self.file_parser = FileParser()
        self.git_helper = GitHelper()

    def process_repository(
            self,
            repo_url: str,
            session_id: str,
            embedding_config: Dict[str, Any],
            task_instance=None
    ) -> bool:
        """
        处理仓库的完整流水线

        Args:
            repo_url: 仓库 URL
            session_id: 会话 ID
            embedding_config: Embedding 配置

        Returns:
            bool: 是否处理成功
        """
        db = get_db_session()

        try:
            # 更新任务状态为处理中
            logger.info(f"📊 [状态更新] 会话ID: {session_id} - 任务状态设置为处理中")
            self._update_session_status(db, session_id, TaskStatus.PROCESSING, started_at=datetime.now(timezone.utc))
            self._update_task_progress(task_instance, 5, "任务初始化完成")

            # 创建 embedding 配置对象
            logger.info(f"⚙️ [配置加载] 会话ID: {session_id} - 创建Embedding配置")
            embedding_cfg = EmbeddingConfig(
                provider=embedding_config["provider"],
                model_name=embedding_config["model_name"],
                api_key=embedding_config.get("api_key"),
                api_base=embedding_config.get("api_base"),
                api_version=embedding_config.get("api_version"),
                deployment_name=embedding_config.get("deployment_name"),
                extra_params=embedding_config.get("extra_params") or {}
            )
            self._update_task_progress(task_instance, 10, "配置加载完成")

            # 加载 embedding 模型
            logger.info(f"🤖 [模型加载] 会话ID: {session_id} - 正在加载 {embedding_cfg.provider}/{embedding_cfg.model_name} 模型")
            embedding_model = EmbeddingManager.get_embedding_model(embedding_cfg)
            logger.info(f"✅ [模型就绪] 会话ID: {session_id} - Embedding模型加载成功")
            self._update_task_progress(task_instance, 15, "Embedding模型加载完成")

            # 创建向量数据库集合
            logger.info(f"🗄️ [数据库] 会话ID: {session_id} - 创建向量数据库集合")
            logger.info(f"🔧 [调试] 会话ID: {session_id} - embedding_model 类型: {type(embedding_model)}, 值: {embedding_model}")
            
            # 先测试 ChromaDB 连接
            try:
                vector_store = get_vector_store()
                health_status = vector_store.health_check()
                logger.info(f"🏥 [健康检查] 会话ID: {session_id} - ChromaDB 状态: {health_status}")
            except Exception as health_e:
                logger.error(f"❌ [健康检查失败] 会话ID: {session_id} - ChromaDB 连接异常: {str(health_e)}")
                raise Exception(f"ChromaDB 连接失败: {str(health_e)}")
            
            # 创建集合
            logger.info(f"🔄 [开始创建] 会话ID: {session_id} - 正在调用 create_collection...")
            if not vector_store.create_collection(session_id, embedding_model):
                raise Exception("创建向量数据库集合失败")
            logger.info(f"✅ [数据库就绪] 会话ID: {session_id} - 向量数据库集合创建成功")
            self._update_task_progress(task_instance, 20, "向量数据库集合创建完成")

            # 克隆仓库并处理
            logger.info(f"📥 [仓库克隆] 会话ID: {session_id} - 开始克隆仓库: {repo_url}")
            repo_path = self.git_helper.clone_repository(repo_url)
            logger.info(f"✅ [克隆完成] 会话ID: {session_id} - 仓库克隆到: {repo_path}")
            self._update_task_progress(task_instance, 30, "仓库克隆完成")

            # 获取仓库信息
            logger.info(f"📋 [仓库信息] 会话ID: {session_id} - 解析仓库信息")
            repo_info = self.git_helper.get_repository_info(repo_path)
            owner, repo_name = self.git_helper.extract_repo_info(repo_url)
            logger.info(f"📝 [仓库详情] 会话ID: {session_id} - 仓库: {owner}/{repo_name}")

            # 更新会话信息
            self._update_session_repo_info(db, session_id, repo_name, owner)
            self._update_task_progress(task_instance, 35, "仓库信息解析完成")

            # 扫描和处理文件，获取所有待处理的文档
            logger.info(f"📁 [文件扫描] 会话ID: {session_id} - 开始扫描和处理仓库文件")
            processed_files, total_chunks, all_documents = self._process_repository_files(
                db, session_id, repo_path, task_instance
            )
            logger.info(f"📊 [扫描结果] 会话ID: {session_id} - 处理文件: {processed_files}, 生成块: {total_chunks}")
            self._update_task_progress(task_instance, 70, f"文件处理完成: {processed_files}个文件, {total_chunks}个块")

            # 向量化和存储文档
            if all_documents:
                logger.info(f"🔄 [向量化] 会话ID: {session_id} - 开始向量化 {len(all_documents)} 个文档块")
                self._vectorize_and_store_documents(db, session_id, all_documents, embedding_model, task_instance)
                logger.info(f"✅ [向量化完成] 会话ID: {session_id} - 所有文档向量化并存储完成")
            else:
                logger.warning(f"⚠️ [无文档] 会话ID: {session_id} - 仓库没有生成任何文档块")
            self._update_task_progress(task_instance, 95, "向量化和存储完成")

            # 标记任务完成
            logger.info(f"🏁 [任务完成] 会话ID: {session_id} - 标记任务为成功状态")
            self._update_session_status(
                db, session_id, TaskStatus.SUCCESS,
                completed_at=datetime.now(timezone.utc)
            )
            self._update_task_progress(task_instance, 100, "任务完成")

            logger.info(f"🎉 [处理成功] 会话ID: {session_id} - 仓库 {repo_url} 分析完成")
            return True

        except Exception as e:
            error_msg = str(e)
            logger.error(f"处理仓库失败 {repo_url}: {error_msg}")

            # 标记任务失败
            self._update_session_status(
                db, session_id, TaskStatus.FAILED,
                error_message=error_msg,
                completed_at=datetime.now(timezone.utc)
            )

            return False

        finally:
            if db:
                db.close()

    def _process_repository_files(
            self,
            db: Session,
            session_id: str,
            repo_path: str,
            task_instance=None
    ) -> Tuple[int, int, List[Document]]:
        """
        处理仓库中的所有文件

        Args:
            db: 数据库会话
            session_id: 会话 ID
            repo_path: 仓库路径

        Returns:
            Tuple[int, int, List[Document]]: (处理的文件数, 总块数, 所有文档块)
        """
        total_files = 0
        total_chunks = 0
        processed_files = 0

        # 收集所有文档块和元数据
        all_documents = []
        all_file_metadata = []

        # 扫描仓库文件
        logger.info(f"🔍 [文件扫描] 会话ID: {session_id} - 开始扫描仓库文件")
        files_to_process = list(self.file_parser.scan_repository(repo_path))
        total_files = len(files_to_process)
        logger.info(f"📋 [扫描完成] 会话ID: {session_id} - 发现 {total_files} 个文件待处理")
        self._update_session_stats(db, session_id, total_files=total_files)  # 初始更新总文件数

        for file_index, (file_path, file_info) in enumerate(files_to_process, 1):
            # 使用统一的文件路径变量名
            relative_file_path = file_info["file_path"]
            
            # 创建文件元数据记录
            file_metadata = FileMetadata(
                session_id=session_id,
                file_path=relative_file_path,
                file_type=file_info["file_type"],
                file_extension=file_info.get("file_extension"),
                file_size=file_info["file_size"],
                is_processed="pending"
            )

            try:
                # 显示当前处理进度
                if file_index % 10 == 1 or file_index <= 5:  # 前5个文件和每10个文件显示一次
                    logger.info(f"📄 [文件处理] 会话ID: {session_id} - 处理第 {file_index}/{total_files} 个文件: {relative_file_path}")
                
                # 更新任务进度 (35% 到 70% 之间)
                progress = 35 + int((file_index / total_files) * 35)
                self._update_task_progress(task_instance, progress, f"处理文件 {file_index}/{total_files}: {relative_file_path}")

                # 读取文件内容
                content = self.file_parser.read_file_content(file_path)
                if not content:
                    file_metadata.is_processed = "skipped"
                    file_metadata.error_message = "无法读取文件内容或文件为空"
                    logger.debug(f"⏭️ [跳过文件] 会话ID: {session_id} - 文件为空: {relative_file_path}")
                    continue

                # 计算行数
                file_metadata.line_count = len(content.split('\n'))
                logger.debug(f"📊 [文件信息] 会话ID: {session_id} - {relative_file_path}: {file_metadata.line_count} 行, {file_info['file_size']} 字节")

                # 解析特殊文件
                if file_info["file_type"] in ["config", "document"]:
                    special_info = self.file_parser.parse_special_files(file_path, content)
                    if special_info.get("type") != "unknown":
                        file_metadata.content_summary = f"{special_info.get('type', '')} 文件"
                        if "dependencies" in special_info:
                            file_metadata.dependencies = special_info["dependencies"]
                        logger.debug(f"🔧 [特殊文件] 会话ID: {session_id} - {relative_file_path}: {special_info.get('type', '')}")

                # 分割文档
                documents = self.file_parser.split_file_content(
                    content,
                    relative_file_path,
                    language=None
                )

                if documents:
                    # 为每个文档块添加全局索引
                    for i, doc in enumerate(documents):
                        doc.metadata['chunk_index'] = total_chunks + i

                    all_documents.extend(documents)
                    file_metadata.chunk_count = len(documents)
                    total_chunks += len(documents)
                    file_metadata.is_processed = "success"
                    processed_files += 1
                    
                    if len(documents) > 1:
                        logger.debug(f"✂️ [文档分块] 会话ID: {session_id} - {relative_file_path}: 生成 {len(documents)} 个块")
                else:
                    file_metadata.is_processed = "skipped"
                    file_metadata.error_message = "未生成文档块"
                    logger.debug(f"⚠️ [无块生成] 会话ID: {session_id} - {relative_file_path}: 未生成文档块")

            except (IOError, UnicodeDecodeError) as e:
                logger.error(f"💥 [读取失败] 会话ID: {session_id} - 文件 {relative_file_path}: {str(e)}")
                file_metadata.is_processed = "failed"
                file_metadata.error_message = f"文件读取错误: {str(e)}"
            except Exception as e:
                logger.error(f"💥 [处理失败] 会话ID: {session_id} - 文件 {relative_file_path}: {str(e)}")
                file_metadata.is_processed = "failed"
                file_metadata.error_message = str(e)

            all_file_metadata.append(file_metadata)

            if len(all_file_metadata) % 50 == 0:
                self._update_session_stats(
                    db, session_id, processed_files=processed_files, total_chunks=total_chunks
                )
                logger.info(f"已扫描 {len(all_file_metadata)}/{total_files} 个文件，生成 {total_chunks} 个块")

        # 批量保存文件元数据
        try:
            db.add_all(all_file_metadata)
            db.commit()
            logger.info(f"已保存 {len(all_file_metadata)} 个文件的元数据")
        except Exception as e:
            logger.error(f"保存文件元数据失败: {str(e)}")
            db.rollback()

        # 更新最终的文件处理和分块统计
        self._update_session_stats(
            db, session_id, processed_files=processed_files, total_chunks=total_chunks
        )
        logger.info(f"文件扫描完成。总文件数: {total_files}, 已处理: {processed_files}, 总块数: {total_chunks}")

        return processed_files, total_chunks, all_documents

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def _vectorize_and_store_documents(
            self,
            db: Session,
            session_id: str,
            documents: List[Document],
            embedding_model: Embeddings,
            task_instance=None,
            batch_size: int = None
    ):
        """
        向量化文档并存储到向量数据库

        Args:
            db: 数据库会话
            session_id: 会话 ID
            documents: 文档列表
            embedding_model: Embedding 模型
            batch_size: 批处理大小
        """
        batch_size = batch_size or settings.EMBEDDING_BATCH_SIZE
        total_docs = len(documents)
        total_batches = (total_docs + batch_size - 1) // batch_size

        logger.info(f"🔄 [向量化开始] 会话ID: {session_id} - 开始向量化 {total_docs} 个文档块，批次大小: {batch_size}")
        logger.info(f"📊 [批次信息] 会话ID: {session_id} - 总共需要处理 {total_batches} 个批次")

        for i in range(0, total_docs, batch_size):
            batch_num = i // batch_size + 1
            batch_docs = documents[i:i + batch_size]
            batch_texts = [doc.page_content for doc in batch_docs]
            actual_batch_size = len(batch_docs)

            try:
                logger.info(f"⚡ [批次处理] 会话ID: {session_id} - 处理第 {batch_num}/{total_batches} 批次 ({actual_batch_size} 个文档)")
                
                # 清理和验证文本
                cleaned_texts = []
                for text in batch_texts:
                    # 确保是字符串类型
                    if not isinstance(text, str):
                        text = str(text)
                    
                    # 跳过空文档
                    if not text.strip():
                        continue
                        
                    cleaned_texts.append(text)
                
                if not cleaned_texts:
                    logger.warning(f"⚠️ [空批次] 会话ID: {session_id} - 批次中没有有效文档")
                    continue
                
                # 向量化文本
                start_time = time.time()
                logger.debug(f"🧠 [向量化中] 会话ID: {session_id} - 正在生成向量...")
                embeddings = embedding_model.embed_documents(cleaned_texts)
                embedding_time = time.time() - start_time
                logger.debug(f"✅ [向量生成] 会话ID: {session_id} - 向量化完成，耗时 {embedding_time:.2f}s")

                # 存储到向量数据库
                logger.debug(f"💾 [存储中] 会话ID: {session_id} - 正在存储到向量数据库...")
                success = get_vector_store().add_documents_to_collection(
                    session_id, batch_docs, embeddings, len(batch_docs)
                )

                if not success:
                    raise Exception("向量数据库存储失败")
                logger.debug(f"✅ [存储完成] 会话ID: {session_id} - 批次数据存储成功")

                # 更新进度
                indexed_chunks = min(i + batch_size, total_docs)
                self._update_session_stats(
                    db, session_id, None, None, None, indexed_chunks
                )
                
                # 更新任务进度 (70% 到 95% 之间)
                progress = 70 + int((batch_num / total_batches) * 25)
                self._update_task_progress(task_instance, progress, f"向量化批次 {batch_num}/{total_batches}")

                logger.info(
                    f"✅ [批次完成] 会话ID: {session_id} - 批次 {batch_num}/{total_batches} 完成，"
                    f"向量化耗时 {embedding_time:.2f}s，已处理 {indexed_chunks}/{total_docs} 个文档"
                )

            except Exception as e:
                logger.error(f"💥 [批次失败] 会话ID: {session_id} - 向量化批次 {batch_num} 失败 (文档 {i}-{i + actual_batch_size}): {str(e)}")
                # 重试机制会自动处理
                raise

        logger.info(f"🎉 [向量化完成] 会话ID: {session_id} - 所有文档向量化完成，共处理 {total_docs} 个文档块")

    def _update_session_status(
            self,
            db: Session,
            session_id: str,
            status: TaskStatus,
            error_message: str = None,
            started_at: datetime = None,
            completed_at: datetime = None
    ):
        """更新会话状态"""
        try:
            session = db.query(AnalysisSession).filter(
                AnalysisSession.session_id == session_id
            ).first()

            if session:
                session.status = status
                if error_message:
                    session.error_message = error_message
                if started_at:
                    session.started_at = started_at
                if completed_at:
                    session.completed_at = completed_at

                db.commit()

        except Exception as e:
            logger.error(f"更新会话状态失败: {str(e)}")
            db.rollback()

    def _update_session_repo_info(
            self,
            db: Session,
            session_id: str,
            repo_name: str,
            repo_owner: str
    ):
        """更新会话仓库信息"""
        try:
            session = db.query(AnalysisSession).filter(
                AnalysisSession.session_id == session_id
            ).first()

            if session:
                session.repository_name = repo_name
                session.repository_owner = repo_owner
                db.commit()

        except Exception as e:
            logger.error(f"更新会话仓库信息失败: {str(e)}")
            db.rollback()

    def _update_session_stats(
            self,
            db: Session,
            session_id: str,
            total_files: Optional[int] = None,
            processed_files: Optional[int] = None,
            total_chunks: Optional[int] = None,
            indexed_chunks: Optional[int] = None
    ):
        """更新会话统计信息"""
        try:
            session = db.query(AnalysisSession).filter(
                AnalysisSession.session_id == session_id
            ).first()

            if session:
                if total_files is not None:
                    session.total_files = total_files
                if processed_files is not None:
                    session.processed_files = processed_files
                if total_chunks is not None:
                    session.total_chunks = total_chunks
                if indexed_chunks is not None:
                    session.indexed_chunks = indexed_chunks

                db.commit()

        except Exception as e:
            logger.error(f"更新会话统计失败: {str(e)}")
            db.rollback()

    def _update_task_progress(self, task_instance, progress: int, status: str):
        """更新Celery任务进度"""
        if task_instance:
            try:
                task_instance.update_state(
                    state='PROGRESS',
                    meta={
                        'current': progress,
                        'total': 100,
                        'status': status
                    }
                )
            except Exception as e:
                logger.debug(f"更新任务进度失败: {str(e)}")


# 全局服务实例
ingestion_service = IngestionService()