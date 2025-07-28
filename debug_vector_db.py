#!/usr/bin/env python3
"""
调试向量数据库内容
检查指定会话ID的向量数据库中存储了哪些文档
"""

import sys
import os
sys.path.append('src')

from services.vector_store import get_vector_store
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_vector_db(session_id: str):
    """
    调试向量数据库中的文档内容
    
    Args:
        session_id: 会话ID
    """
    try:
        vector_store = get_vector_store()
        
        # 获取集合中的所有文档
        logger.info(f"正在检查会话 {session_id} 的向量数据库内容...")
        
        # 查询所有文档（使用一个虚拟向量）
        # 先获取集合信息
        collection = vector_store.client.get_collection(session_id)
        count = collection.count()
        logger.info(f"集合中共有 {count} 个文档")
        
        if count > 0:
            # 获取所有文档的元数据
            results = collection.get(
                include=["metadatas", "documents"]
            )
            
            logger.info(f"\n=== 向量数据库中的文档列表 ===")
            
            file_types = {}
            for i, (doc_id, metadata, document) in enumerate(zip(
                results["ids"], 
                results["metadatas"], 
                results["documents"]
            )):
                file_path = metadata.get('file_path', 'unknown')
                file_ext = os.path.splitext(file_path)[1].lower()
                
                # 统计文件类型
                if file_ext not in file_types:
                    file_types[file_ext] = 0
                file_types[file_ext] += 1
                
                # 显示前10个文档的详细信息
                if i < 10:
                    logger.info(f"文档 {i+1}: {file_path}")
                    logger.info(f"  - 文件扩展名: {file_ext}")
                    logger.info(f"  - 内容长度: {len(document)} 字符")
                    logger.info(f"  - 内容预览: {document[:100]}...")
                    logger.info(f"  - 元数据: {metadata}")
                    logger.info("")
            
            logger.info(f"\n=== 文件类型统计 ===")
            for ext, count in sorted(file_types.items()):
                logger.info(f"{ext or '无扩展名'}: {count} 个文档")
            
            # 检查是否有Python文件
            python_files = [metadata.get('file_path', '') for metadata in results["metadatas"] 
                          if metadata.get('file_path', '').endswith('.py')]
            
            if python_files:
                logger.info(f"\n=== Python文件列表 ===")
                for py_file in python_files:
                    logger.info(f"  - {py_file}")
            else:
                logger.warning("\n⚠️ 未找到任何Python文件！")
                
        else:
            logger.warning("集合为空，没有任何文档")
            
    except Exception as e:
        logger.error(f"调试失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python debug_vector_db.py <session_id>")
        print("例如: python debug_vector_db.py 5afcd74c-15ae-4c11-9386-2cecab37b3af")
        sys.exit(1)
    
    session_id = sys.argv[1]
    debug_vector_db(session_id)