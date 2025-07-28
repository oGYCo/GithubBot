#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试文件处理功能
验证Python文件是否能被正确识别和处理
"""

import os
import sys
import tempfile
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.file_parser import FileParser
from src.core.config import settings

def test_python_file_processing():
    """
    测试Python文件处理功能
    """
    print("🧪 测试Python文件处理功能")
    print("=" * 50)
    
    # 创建文件解析器实例
    file_parser = FileParser()
    
    # 测试文件类型识别
    test_files = [
        "test.py",
        "main.py", 
        "__init__.py",
        "setup.py",
        "requirements.txt",
        "README.md",
        "config.json"
    ]
    
    print("📋 文件类型识别测试:")
    for test_file in test_files:
        file_type, language = file_parser.get_file_type_and_language(test_file)
        language_str = language.value if language and hasattr(language, 'value') else str(language)
        print(f"  {test_file:15} -> 类型: {file_type:8}, 语言: {language_str}")
    
    # 创建临时Python文件进行完整测试
    print("\n🐍 Python文件完整处理测试:")
    
    # 创建临时目录和文件
    with tempfile.TemporaryDirectory() as temp_dir:
        # 创建测试Python文件
        test_py_file = os.path.join(temp_dir, "test_module.py")
        test_content = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试模块
这是一个用于测试的Python模块
"""

import os
import sys
from typing import List, Dict, Any

class TestClass:
    """测试类"""
    
    def __init__(self, name: str):
        self.name = name
    
    def greet(self) -> str:
        """问候方法"""
        return f"Hello, {self.name}!"

def main():
    """主函数"""
    test_obj = TestClass("World")
    print(test_obj.greet())

if __name__ == "__main__":
    main()
'''
        
        with open(test_py_file, 'w', encoding='utf-8') as f:
            f.write(test_content)
        
        # 测试文件是否应该被处理
        should_process = file_parser.should_process_file(test_py_file, temp_dir)
        print(f"  文件是否应该被处理: {should_process}")
        
        if should_process:
            # 测试文件类型识别
            file_type, language = file_parser.get_file_type_and_language(test_py_file)
            language_str = language.value if language and hasattr(language, 'value') else str(language)
            print(f"  文件类型: {file_type}")
            print(f"  编程语言: {language_str}")
            
            # 测试文件内容读取
            content = file_parser.read_file_content(test_py_file)
            if content:
                print(f"  文件内容长度: {len(content)} 字符")
                print(f"  文件行数: {len(content.split('\n'))} 行")
                
                # 测试文档分割
                documents = file_parser.split_file_content(
                    content, 
                    "test_module.py", 
                    language=language
                )
                
                print(f"  生成文档块数量: {len(documents)}")
                
                if documents:
                    print("  第一个文档块信息:")
                    first_doc = documents[0]
                    print(f"    内容长度: {len(first_doc.page_content)} 字符")
                    print(f"    元数据: {first_doc.metadata}")
                    print(f"    内容预览: {first_doc.page_content[:200]}...")
                    
                    # 检查language字段
                    doc_language = first_doc.metadata.get('language')
                    if doc_language == 'python':
                        print("  ✅ language字段正确设置为'python'")
                    else:
                        print(f"  ❌ language字段错误: {doc_language}")
                else:
                    print("  ❌ 未生成任何文档块")
            else:
                print("  ❌ 无法读取文件内容")
        else:
            print("  ❌ 文件不应该被处理")
    
    print("\n📊 配置信息:")
    print(f"  允许的文件扩展名数量: {len(settings.ALLOWED_FILE_EXTENSIONS)}")
    print(f"  .py是否在允许列表中: {'.py' in settings.ALLOWED_FILE_EXTENSIONS}")
    print(f"  排除的目录数量: {len(settings.EXCLUDED_DIRECTORIES)}")
    print(f"  块大小: {settings.CHUNK_SIZE}")
    print(f"  块重叠: {settings.CHUNK_OVERLAP}")
    
if __name__ == "__main__":
    try:
        test_python_file_processing()
        print("\n✅ 测试完成")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()