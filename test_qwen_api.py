#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试阿里云 Qwen Embedding API 连接性
"""

import os
import sys
import requests
import json
from typing import List

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def test_qwen_embedding_api(api_key: str, test_texts: List[str] = None) -> bool:
    """
    测试 Qwen Embedding API
    
    Args:
        api_key: 阿里云 API Key
        test_texts: 测试文本列表
        
    Returns:
        bool: API 是否可用
    """
    if test_texts is None:
        test_texts = [
            "这是一个测试文本",
            "Hello, this is a test text",
            "测试中文和英文混合的文本 with mixed languages"
        ]
    
    url = "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "text-embedding-v4",
        "input": test_texts,
        "encoding_format": "float"
    }
    
    print(f"🔍 测试 Qwen Embedding API...")
    print(f"📝 测试文本数量: {len(test_texts)}")
    print(f"🌐 API 端点: {url}")
    print(f"🔑 API Key: {api_key[:10]}...{api_key[-4:]}")
    print("-" * 50)
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        print(f"📊 HTTP 状态码: {response.status_code}")
        print(f"📋 响应头: {dict(response.headers)}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ API 调用成功!")
            print(f"📈 返回数据结构:")
            print(f"   - object: {result.get('object', 'N/A')}")
            print(f"   - model: {result.get('model', 'N/A')}")
            print(f"   - usage: {result.get('usage', 'N/A')}")
            
            embeddings = result.get('data', [])
            print(f"   - embeddings 数量: {len(embeddings)}")
            
            if embeddings:
                first_embedding = embeddings[0].get('embedding', [])
                print(f"   - 第一个向量维度: {len(first_embedding)}")
                print(f"   - 向量前5个值: {first_embedding[:5]}")
            
            return True
            
        else:
            print(f"❌ API 调用失败!")
            print(f"📄 错误响应: {response.text}")
            
            try:
                error_data = response.json()
                print(f"🔍 错误详情:")
                print(f"   - 错误码: {error_data.get('error', {}).get('code', 'N/A')}")
                print(f"   - 错误消息: {error_data.get('error', {}).get('message', 'N/A')}")
                print(f"   - 错误类型: {error_data.get('error', {}).get('type', 'N/A')}")
            except:
                pass
                
            return False
            
    except requests.exceptions.Timeout:
        print(f"⏰ 请求超时 (30秒)")
        return False
    except requests.exceptions.ConnectionError:
        print(f"🌐 网络连接错误")
        return False
    except Exception as e:
        print(f"💥 未知错误: {str(e)}")
        return False

def test_with_langchain_openai():
    """
    使用 LangChain 的 OpenAIEmbeddings 测试
    """
    try:
        from langchain_openai import OpenAIEmbeddings
        
        print(f"\n🔧 使用 LangChain OpenAIEmbeddings 测试...")
        print("-" * 50)
        
        # 从环境变量或直接设置 API Key
        api_key = "sk-8bac0158a9ee415ba246ccb2b120f733"
        
        # 设置环境变量
        os.environ["OPENAI_API_KEY"] = api_key
        os.environ["OPENAI_API_BASE"] = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        
        # 尝试不同的配置方式
        try:
            embeddings = OpenAIEmbeddings(
                model="text-embedding-v4",
                api_key=api_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                tiktoken_enabled=False,
                show_progress_bar=False,
                check_embedding_ctx_length=False
            )
        except Exception as e1:
            print(f"⚠️ 第一次尝试失败: {str(e1)}")
            print(f"🔄 尝试使用标准OpenAI模型名称...")
            # 尝试使用更标准的模型名称
            embeddings = OpenAIEmbeddings(
                model="text-embedding-ada-002",  # 使用标准OpenAI模型名称
                api_key=api_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                tiktoken_enabled=False,
                show_progress_bar=False,
                check_embedding_ctx_length=False
            )
        
        test_texts = [
            "这是一个测试文本",
            "Hello, this is a test text"
        ]
        
        print(f"📝 测试文本: {test_texts}")
        
        # 测试 embed_documents
        vectors = embeddings.embed_documents(test_texts)
        
        print(f"✅ LangChain 测试成功!")
        print(f"📊 向量数量: {len(vectors)}")
        print(f"📏 向量维度: {len(vectors[0]) if vectors else 0}")
        print(f"🔢 第一个向量前5个值: {vectors[0][:5] if vectors else []}")
        
        return True
        
    except ImportError:
        print(f"⚠️ 未安装 langchain_openai，跳过 LangChain 测试")
        return False
    except Exception as e:
        print(f"❌ LangChain 测试失败: {str(e)}")
        return False

def main():
    """
    主测试函数
    """
    print("🚀 阿里云 Qwen Embedding API 测试")
    print("=" * 60)
    
    # API Key (从 STARTUP_GUIDE.md 中获取)
    api_key = "sk-8bac0158a9ee415ba246ccb2b120f733"
    
    # 测试1: 直接 HTTP 请求
    print("\n📡 测试1: 直接 HTTP 请求")
    success1 = test_qwen_embedding_api(api_key)
    
    # 测试2: LangChain 集成
    print("\n🔗 测试2: LangChain 集成")
    success2 = test_with_langchain_openai()
    
    # 总结
    print("\n" + "=" * 60)
    print("📋 测试总结:")
    print(f"   - 直接 HTTP 请求: {'✅ 成功' if success1 else '❌ 失败'}")
    print(f"   - LangChain 集成: {'✅ 成功' if success2 else '❌ 失败'}")
    
    if success1 and success2:
        print(f"\n🎉 恭喜! 你的阿里云 API Key 可以正常使用!")
    elif success1:
        print(f"\n⚠️ API Key 可用，但 LangChain 集成有问题")
    else:
        print(f"\n❌ API Key 不可用，请检查:")
        print(f"   1. API Key 是否正确")
        print(f"   2. 账户余额是否充足")
        print(f"   3. 网络连接是否正常")
        print(f"   4. API 服务是否可用")

if __name__ == "__main__":
    main()