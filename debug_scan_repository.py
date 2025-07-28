#!/usr/bin/env python3
"""
调试仓库扫描过程
模拟完整的文件扫描和处理流程
"""

import os
import sys
sys.path.append('src')

from src.utils.file_parser import FileParser
from src.core.config import settings

def main():
    print("=== 调试仓库扫描过程 ===")
    
    # 创建FileParser实例
    parser = FileParser()
    repo_path = os.getcwd()
    
    print(f"\n仓库路径: {repo_path}")
    print(f"允许的扩展名: {parser.allowed_extensions}")
    print(f"排除的目录: {parser.excluded_dirs}")
    
    # 统计信息
    total_found = 0
    total_processed = 0
    python_files_found = 0
    python_files_processed = 0
    
    print(f"\n开始扫描仓库...")
    
    # 模拟scan_repository的逻辑
    parser.load_gitignore(repo_path)
    print(f"加载了 {len(parser.gitignore_patterns)} 条 .gitignore 规则")
    
    for root, dirs, files in os.walk(repo_path):
        # 过滤目录
        original_dirs = dirs.copy()
        dirs[:] = [d for d in dirs if not parser.should_skip_directory(d)]
        
        if len(original_dirs) > len(dirs):
            skipped_dirs = [d for d in original_dirs if d not in dirs]
            print(f"\n跳过目录: {skipped_dirs} 在 {root}")
        
        for file_name in files:
            file_path = os.path.join(root, file_name)
            rel_path = os.path.relpath(file_path, repo_path)
            
            total_found += 1
            
            # 检查是否是Python文件
            if file_name.endswith('.py'):
                python_files_found += 1
                print(f"\n发现Python文件: {rel_path}")
                
                # 详细检查处理逻辑
                should_process = parser.should_process_file(file_path, repo_path)
                print(f"  应该处理: {should_process}")
                
                if not should_process:
                    # 详细分析为什么不处理
                    file_ext = os.path.splitext(file_name)[1].lower()
                    is_gitignored = parser.is_ignored_by_gitignore(file_path, repo_path)
                    is_binary = file_ext in parser.BINARY_EXTENSIONS
                    in_whitelist = file_ext in parser.allowed_extensions
                    
                    print(f"  文件扩展名: {file_ext}")
                    print(f"  被gitignore忽略: {is_gitignored}")
                    print(f"  是二进制文件: {is_binary}")
                    print(f"  在扩展名白名单: {in_whitelist}")
                    
                    if is_gitignored:
                        # 找出匹配的gitignore规则
                        for pattern in parser.gitignore_patterns:
                            import fnmatch
                            rel_path_unix = rel_path.replace(os.path.sep, '/')
                            if fnmatch.fnmatch(rel_path_unix, pattern) or fnmatch.fnmatch(os.path.basename(rel_path_unix), pattern):
                                print(f"  匹配的gitignore规则: {pattern}")
                                break
                else:
                    python_files_processed += 1
                    file_type, language = parser.get_file_type_and_language(file_path)
                    print(f"  文件类型: {file_type}")
                    print(f"  语言: {language}")
                    
                    # 测试文件内容读取
                    try:
                        content = parser.read_file_content(file_path)
                        if content:
                            print(f"  内容长度: {len(content)} 字符")
                            print(f"  行数: {len(content.split('\n'))} 行")
                            
                            # 测试文档分割
                            documents = parser.split_file_content(content, rel_path, language)
                            print(f"  生成文档块: {len(documents)} 个")
                            
                            if documents:
                                print(f"  第一个块元数据: {documents[0].metadata}")
                        else:
                            print(f"  内容为空或读取失败")
                    except Exception as e:
                        print(f"  读取文件失败: {e}")
            
            # 检查是否应该处理该文件
            if parser.should_process_file(file_path, repo_path):
                total_processed += 1
    
    print(f"\n=== 扫描结果统计 ===")
    print(f"总文件数: {total_found}")
    print(f"应处理文件数: {total_processed}")
    print(f"Python文件发现: {python_files_found}")
    print(f"Python文件处理: {python_files_processed}")
    print(f"处理率: {total_processed/total_found*100:.1f}%")
    print(f"Python文件处理率: {python_files_processed/python_files_found*100:.1f}%" if python_files_found > 0 else "Python文件处理率: N/A")

if __name__ == "__main__":
    main()