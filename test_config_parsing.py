#!/usr/bin/env python3
"""
测试配置解析脚本
检查ALLOWED_FILE_EXTENSIONS和EXCLUDED_DIRECTORIES的解析是否正确
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.core.config import settings

def test_config_parsing():
    """测试配置解析"""
    print("=== 配置解析测试 ===")
    
    print(f"\n1. ALLOWED_FILE_EXTENSIONS (共 {len(settings.ALLOWED_FILE_EXTENSIONS)} 个):")
    for i, ext in enumerate(settings.ALLOWED_FILE_EXTENSIONS, 1):
        print(f"   {i:2d}. {ext}")
    
    print(f"\n2. EXCLUDED_DIRECTORIES (共 {len(settings.EXCLUDED_DIRECTORIES)} 个):")
    for i, dir_name in enumerate(settings.EXCLUDED_DIRECTORIES, 1):
        print(f"   {i:2d}. {dir_name}")
    
    # 检查关键文件扩展名
    print("\n3. 关键文件扩展名检查:")
    key_extensions = ['.py', '.js', '.java', '.cpp', '.md']
    for ext in key_extensions:
        status = "✓" if ext in settings.ALLOWED_FILE_EXTENSIONS else "✗"
        print(f"   {status} {ext}")
    
    # 检查ChromaDB配置
    print("\n4. ChromaDB配置:")
    print(f"   Host: {settings.CHROMADB_HOST}")
    print(f"   Port: {settings.CHROMADB_PORT}")
    
    # 检查是否包含Python文件
    has_python = '.py' in settings.ALLOWED_FILE_EXTENSIONS
    print(f"\n5. Python文件支持: {'✓ 已启用' if has_python else '✗ 未启用'}")
    
    if not has_python:
        print("   ⚠️  警告: .py 文件未在允许列表中，这可能是导致只有10个文件被处理的原因！")
    
    return has_python

if __name__ == "__main__":
    try:
        has_python = test_config_parsing()
        if has_python:
            print("\n✓ 配置解析正常，Python文件应该可以被处理")
        else:
            print("\n✗ 配置有问题，需要修复ALLOWED_FILE_EXTENSIONS")
    except Exception as e:
        print(f"\n✗ 配置解析失败: {e}")
        import traceback
        traceback.print_exc()