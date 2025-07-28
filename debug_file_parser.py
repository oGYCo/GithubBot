#!/usr/bin/env python3
"""
调试文件解析器
检查FileParser的配置和文件过滤逻辑
"""

import os
import sys
sys.path.append('src')

from utils.file_parser import FileParser
from core.config import settings

def main():
    print("=== 调试文件解析器 ===")
    
    # 检查配置
    print(f"\n配置信息:")
    print(f"ALLOWED_FILE_EXTENSIONS: {settings.ALLOWED_FILE_EXTENSIONS}")
    print(f"EXCLUDED_DIRECTORIES: {settings.EXCLUDED_DIRECTORIES}")
    
    # 创建FileParser实例
    parser = FileParser()
    
    print(f"\nFileParser实例信息:")
    print(f"allowed_extensions: {parser.allowed_extensions}")
    print(f"excluded_dirs: {parser.excluded_dirs}")
    
    # 检查.py是否在允许的扩展名中
    print(f"\n扩展名检查:")
    print(f".py in allowed_extensions: {'.py' in parser.allowed_extensions}")
    
    # 测试具体的Python文件
    test_files = [
        "src/api/v1/endpoints/repositories.py",
        "src/schemas/repository.py", 
        "src/worker/tasks.py",
        "src/utils/file_parser.py"
    ]
    
    repo_path = os.getcwd()
    print(f"\n仓库路径: {repo_path}")
    
    # 加载.gitignore
    parser.load_gitignore(repo_path)
    print(f"gitignore规则数量: {len(parser.gitignore_patterns)}")
    
    print(f"\n文件处理检查:")
    for test_file in test_files:
        full_path = os.path.join(repo_path, test_file)
        if os.path.exists(full_path):
            should_process = parser.should_process_file(full_path, repo_path)
            file_type, language = parser.get_file_type_and_language(full_path)
            
            print(f"\n文件: {test_file}")
            print(f"  存在: True")
            print(f"  应该处理: {should_process}")
            print(f"  文件类型: {file_type}")
            print(f"  语言: {language}")
            
            # 详细检查为什么不处理
            if not should_process:
                file_name = os.path.basename(full_path)
                file_ext = os.path.splitext(file_name)[1].lower()
                
                print(f"  文件扩展名: {file_ext}")
                print(f"  被gitignore忽略: {parser.is_ignored_by_gitignore(full_path, repo_path)}")
                print(f"  是二进制文件: {file_ext in parser.BINARY_EXTENSIONS}")
                print(f"  扩展名在白名单: {file_ext in parser.allowed_extensions}")
        else:
            print(f"\n文件: {test_file}")
            print(f"  存在: False")
    
    # 检查FILE_TYPE_MAPPING
    print(f"\nFILE_TYPE_MAPPING中的.py:")
    if '.py' in parser.FILE_TYPE_MAPPING:
        print(f"  .py -> {parser.FILE_TYPE_MAPPING['.py']}")
    else:
        print(f"  .py 不在 FILE_TYPE_MAPPING 中")

if __name__ == "__main__":
    main()