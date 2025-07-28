#!/usr/bin/env python3
"""
直接连接 ChromaDB 的调试脚本
使用端口 8000
"""

import sys
import chromadb
from chromadb.config import Settings

def debug_chromadb_connection():
    """直接测试 ChromaDB 连接"""
    # 尝试多种连接方式
    connection_configs = [
        {"host": "localhost", "port": 8000, "name": "localhost:8000"},
        {"host": "127.0.0.1", "port": 8000, "name": "127.0.0.1:8000"},
        {"host": "chromadb", "port": 8000, "name": "chromadb:8000"},
        {"host": "localhost", "port": 8001, "name": "localhost:8001"},
        {"host": "127.0.0.1", "port": 8001, "name": "127.0.0.1:8001"},
        {"host": "chromadb", "port": 8001, "name": "chromadb:8001"},
    ]
    
    successful_client = None
    successful_config = None
    
    for config in connection_configs:
        try:
            print(f"尝试连接 {config['name']}...")
            
            client = chromadb.HttpClient(
                host=config["host"],
                port=config["port"],
                settings=Settings(allow_reset=True)
            )
            
            # 测试连接是否有效
            collections = client.list_collections()
            print(f"✅ 连接成功！使用 {config['name']}")
            successful_client = client
            successful_config = config
            break
            
        except Exception as e:
            print(f"❌ 连接失败 {config['name']}: {e}")
            continue
    
    if successful_client is None:
        print("所有连接尝试都失败了")
        return False
    
    try:
        # 获取所有集合
        collections = successful_client.list_collections()
        print(f"\n找到 {len(collections)} 个集合:")
        
        for collection in collections:
            print(f"  - 集合名: {collection.name}")
            count = collection.count()
            print(f"    文档数量: {count}")
            
            if count > 0:
                # 获取一些样本数据
                results = collection.get(limit=3, include=["documents", "metadatas"])
                print(f"    样本文档:")
                for i, (doc, meta) in enumerate(zip(results['documents'], results['metadatas'])):
                    file_path = meta.get('file_path', 'Unknown')
                    content_preview = doc[:100] + "..." if len(doc) > 100 else doc
                    print(f"      {i+1}. 文件: {file_path}")
                    print(f"         内容预览: {content_preview}")
        
        return True, successful_client, successful_config
        
    except Exception as e:
        print(f"获取集合信息失败: {e}")
        return False, None, None

def debug_with_session_id(session_id, client=None, config=None):
    """使用会话 ID 调试特定集合"""
    try:
        print(f"\n调试会话 ID: {session_id}")
        
        if client is None:
            # 如果没有提供客户端，尝试重新连接
            result = debug_chromadb_connection()
            if isinstance(result, tuple) and result[0]:
                _, client, config = result
            else:
                print("无法建立连接")
                return
        
        print(f"使用连接: {config['name'] if config else 'Unknown'}")
        
        # 尝试获取指定会话的集合
        collection_name = session_id  # 直接使用会话ID作为集合名称
        try:
            collection = client.get_collection(name=collection_name)
            print(f"找到集合: {collection_name}")
            
            count = collection.count()
            print(f"文档数量: {count}")
            
            if count > 0:
                # 获取所有文档的元数据
                results = collection.get(include=["documents", "metadatas"])
                
                # 统计文件类型
                file_types = {}
                for meta in results['metadatas']:
                    file_path = meta.get('file_path', '')
                    if file_path:
                        ext = file_path.split('.')[-1].lower() if '.' in file_path else 'no_ext'
                        file_types[ext] = file_types.get(ext, 0) + 1
                
                print("\n文件类型统计:")
                for ext, count in sorted(file_types.items()):
                    print(f"  .{ext}: {count} 个文件")
                
                # 检查是否有 Python 文件
                python_files = [meta.get('file_path', '') for meta in results['metadatas'] 
                              if meta.get('file_path', '').endswith('.py')]
                
                if python_files:
                    print(f"\nPython文件列表:")
                    for py_file in python_files:
                        print(f"  - {py_file}")
                else:
                    print("\n⚠️ 未找到任何Python文件！")
                
                # 显示前5个文档的详细信息
                print(f"\n前5个文档详情:")
                for i, (doc, meta) in enumerate(zip(results['documents'][:5], results['metadatas'][:5])):
                    file_path = meta.get('file_path', 'Unknown')
                    content_preview = doc[:200] + "..." if len(doc) > 200 else doc
                    print(f"\n文档 {i+1}: {file_path}")
                    print(f"  内容长度: {len(doc)} 字符")
                    print(f"  内容预览: {content_preview}")
                    print(f"  元数据: {meta}")
                    
            else:
                print("集合为空，没有任何文档")
                
        except Exception as e:
            print(f"获取集合失败: {e}")
            
    except Exception as e:
        print(f"调试失败: {e}")

if __name__ == "__main__":
    print("ChromaDB 多端口连接调试工具")
    print("=" * 50)
    
    # 首先测试基本连接
    result = debug_chromadb_connection()
    
    if isinstance(result, tuple) and result[0]:
        success, client, config = result
        print(f"\n成功建立连接: {config['name']}")
        
        # 如果提供了会话 ID，进行详细调试
        if len(sys.argv) > 1:
            session_id = sys.argv[1]
            debug_with_session_id(session_id, client, config)
        else:
            print("\n用法: python debug_chromadb_8000.py <session_id>")
            print("例如: python debug_chromadb_8000.py 9e9d2066-b72a-472e-88cf-9b70f520df6b")
    else:
        print("\n❌ 无法连接到 ChromaDB")
        print("请检查:")
        print("1. ChromaDB 服务是否正常运行")
        print("2. 端口配置是否正确")
        print("3. 网络连接是否正常")