#!/usr/bin/env python3
"""
调试向量存储的完整流程
检查ChromaDB连接、集合创建、文档存储和查询
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 设置环境变量
os.environ.setdefault('PYTHONPATH', str(project_root))

from src.core.config import settings
from src.services.vector_store import get_vector_store
from src.utils.file_parser import FileParser
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_vector_store_flow():
    """测试完整的向量存储流程"""
    
    print("=== 调试向量存储流程 ===")
    print(f"ChromaDB配置:")
    print(f"  - CHROMADB_PERSISTENT_PATH: {settings.CHROMADB_PERSISTENT_PATH}")
    print(f"  - CHROMADB_HOST: {settings.CHROMADB_HOST}")
    print(f"  - CHROMADB_PORT: {settings.CHROMADB_PORT}")
    print()
    
    # 1. 测试向量存储连接
    print("1. 测试向量存储连接...")
    try:
        vector_store = get_vector_store()
        print("✅ 向量存储连接成功")
        
        # 健康检查
        health = vector_store.health_check()
        print(f"   健康状态: {health}")
        
        # 列出现有集合
        collections = vector_store.list_collections()
        print(f"   现有集合: {collections}")
        
    except Exception as e:
        print(f"❌ 向量存储连接失败: {e}")
        return
    
    # 2. 测试集合创建
    test_collection = "test_python_files"
    print(f"\n2. 测试集合创建: {test_collection}")
    
    try:
        # 删除测试集合（如果存在）
        if vector_store.collection_exists(test_collection):
            print(f"   删除现有测试集合...")
            vector_store.delete_collection(test_collection)
        
        # 创建嵌入模型
        print("   创建嵌入模型...")
        embedding_model = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={'device': 'cpu'}
        )
        
        # 创建集合
        print(f"   创建集合 {test_collection}...")
        success = vector_store.create_collection(test_collection, embedding_model)
        if success:
            print("✅ 集合创建成功")
        else:
            print("❌ 集合创建失败")
            return
            
    except Exception as e:
        print(f"❌ 集合创建异常: {e}")
        return
    
    # 3. 测试文档处理和存储
    print("\n3. 测试Python文件处理和存储...")
    
    try:
        # 创建文件解析器
        file_parser = FileParser()
        
        # 查找一些Python文件
        repo_path = project_root
        python_files = []
        
        for file_path in repo_path.rglob("*.py"):
            if file_parser.should_process_file(file_path, repo_path):
                python_files.append(file_path)
                if len(python_files) >= 3:  # 只测试前3个文件
                    break
        
        print(f"   找到 {len(python_files)} 个Python文件用于测试")
        
        all_documents = []
        
        for file_path in python_files:
            print(f"   处理文件: {file_path.name}")
            
            # 读取文件内容
            content = file_parser.read_file_content(file_path)
            if not content:
                print(f"     ⚠️ 文件内容为空，跳过")
                continue
            
            # 获取文件类型和语言
            file_type, language = file_parser.get_file_type_and_language(file_path)
            print(f"     文件类型: {file_type}, 语言: {language}")
            
            # 分割文档
            documents = file_parser.split_file_content(
                content, 
                str(file_path.relative_to(repo_path)),
                language=language
            )
            
            print(f"     生成文档块数量: {len(documents)}")
            
            # 检查文档元数据
            if documents:
                first_doc = documents[0]
                print(f"     第一个文档块元数据: {first_doc.metadata}")
                print(f"     第一个文档块内容长度: {len(first_doc.page_content)}")
                
                # 检查语言字段
                doc_language = first_doc.metadata.get('language')
                print(f"     文档块语言字段: {doc_language} (类型: {type(doc_language)})")
                
                all_documents.extend(documents)
        
        print(f"   总共生成 {len(all_documents)} 个文档块")
        
        if not all_documents:
            print("❌ 没有生成任何文档块")
            return
        
        # 4. 测试向量化和存储
        print("\n4. 测试向量化和存储...")
        
        # 准备文档文本
        texts = [doc.page_content for doc in all_documents]
        print(f"   准备向量化 {len(texts)} 个文档")
        
        # 生成嵌入向量
        print("   生成嵌入向量...")
        embeddings = embedding_model.embed_documents(texts)
        print(f"   生成了 {len(embeddings)} 个嵌入向量")
        
        # 存储到向量数据库
        print("   存储到向量数据库...")
        success = vector_store.add_documents_to_collection(
            test_collection, all_documents, embeddings
        )
        
        if success:
            print("✅ 文档存储成功")
        else:
            print("❌ 文档存储失败")
            return
        
    except Exception as e:
        print(f"❌ 文档处理和存储异常: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 5. 验证存储结果
    print("\n5. 验证存储结果...")
    
    try:
        # 获取集合统计
        stats = vector_store.get_collection_stats(test_collection)
        print(f"   集合统计: {stats}")
        
        # 查询测试
        if stats.get('count', 0) > 0:
            print("   执行查询测试...")
            query_text = "python function"
            query_embedding = embedding_model.embed_query(query_text)
            
            results = vector_store.query_collection(
                test_collection, query_embedding, n_results=3
            )
            
            print(f"   查询结果数量: {len(results.get('ids', [[]])[0])}")
            
            # 检查结果中的文件类型
            if results.get('metadatas') and results['metadatas'][0]:
                file_types = {}
                languages = {}
                
                for metadata in results['metadatas'][0]:
                    file_type = metadata.get('file_type', 'unknown')
                    language = metadata.get('language', 'unknown')
                    
                    file_types[file_type] = file_types.get(file_type, 0) + 1
                    languages[language] = languages.get(language, 0) + 1
                
                print(f"   查询结果文件类型分布: {file_types}")
                print(f"   查询结果语言分布: {languages}")
                
                # 显示第一个结果的详细信息
                if results['metadatas'][0]:
                    first_result = results['metadatas'][0][0]
                    print(f"   第一个结果元数据: {first_result}")
        
    except Exception as e:
        print(f"❌ 验证存储结果异常: {e}")
        import traceback
        traceback.print_exc()
    
    # 6. 清理测试集合
    print("\n6. 清理测试集合...")
    try:
        vector_store.delete_collection(test_collection)
        print("✅ 测试集合已删除")
    except Exception as e:
        print(f"⚠️ 删除测试集合失败: {e}")
    
    print("\n=== 调试完成 ===")

if __name__ == "__main__":
    test_vector_store_flow()