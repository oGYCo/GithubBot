"""
AST解析器测试
"""

import os
import sys
import tempfile
import textwrap
import time
import unittest
from typing import List

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.utils.ast_parser import AstParser


class TestAstParser(unittest.TestCase):
    """AST解析器测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.parser = AstParser()
        self.temp_files = []
    
    def tearDown(self):
        """测试后清理"""
        for file_path in self.temp_files:
            try:
                os.unlink(file_path)
            except:
                pass
    
    def create_test_file(self, content: str, suffix: str) -> str:
        """创建临时测试文件"""
        with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False, encoding='utf-8') as f:
            f.write(content)
            self.temp_files.append(f.name)
            return f.name
    
    def test_supported_languages(self):
        """测试支持的语言"""
        print("\n🌐 测试支持的语言列表:")
        
        supported = self.parser.get_supported_languages()
        
        self.assertIsInstance(supported, list)
        if supported:
            print(f"  ✅ 支持 {len(supported)} 种语言:")
            for lang in sorted(supported):
                extensions = self.parser.get_language_extensions(lang)
                ext_str = ", ".join(sorted(extensions))
                print(f"    - {lang}: {ext_str}")
                self.assertIsInstance(extensions, set)
        else:
            print("  ⚠️ 没有支持的语言")
    
    def test_python_parsing(self):
        """测试Python代码解析"""
        print("\n🐍 测试Python代码解析:")
        
        python_code = textwrap.dedent("""
        import os
        from typing import List, Dict
        
        class DataProcessor:
            '''数据处理器类'''
            
            def __init__(self, name: str):
                self.name = name
                self.data = []
            
            @property
            def size(self) -> int:
                return len(self.data)
            
            def process_data(self, items: List[str]) -> Dict[str, int]:
                '''处理数据并返回统计信息'''
                result = {}
                for item in items:
                    result[item] = len(item)
                return result
        
        # 模块级变量
        DEFAULT_CONFIG = {"timeout": 30, "retries": 3}
        
        def main():
            processor = DataProcessor("test")
            data = ["hello", "world", "python"]
            result = processor.process_data(data)
            print(result)
        
        if __name__ == "__main__":
            main()
        """)
        
        file_path = self.create_test_file(python_code, '.py')
        
        documents = self.parser.parse_with_ast(python_code, file_path, 'python')
        print(f"  ✅ 解析出 {len(documents)} 个代码元素:")
        
        self.assertIsInstance(documents, list)
        self.assertGreater(len(documents), 0)
        
        for doc in documents:
            meta = doc.metadata
            print(f"    - {meta['element_type']}: {meta['element_name']} "
                  f"(行 {meta['start_line']}-{meta['end_line']})")
            
            # 验证元数据
            self.assertIn('element_type', meta)
            self.assertIn('element_name', meta)
            self.assertIn('start_line', meta)
            self.assertIn('end_line', meta)
            self.assertIn('language', meta)
    
    def test_javascript_parsing(self):
        """测试JavaScript代码解析"""
        print("\n📜 测试JavaScript代码解析:")
        
        js_code = textwrap.dedent("""
        import { Component } from 'react';
        import axios from 'axios';
        
        class UserManager extends Component {
            constructor(props) {
                super(props);
                this.state = { users: [] };
            }
            
            async fetchUsers() {
                try {
                    const response = await axios.get('/api/users');
                    this.setState({ users: response.data });
                } catch (error) {
                    console.error('Failed to fetch users:', error);
                }
            }
            
            render() {
                return (
                    <div>
                        {this.state.users.map(user => (
                            <div key={user.id}>{user.name}</div>
                        ))}
                    </div>
                );
            }
        }
        
        const API_BASE_URL = 'https://api.example.com';
        
        export const createUser = async (userData) => {
            const response = await fetch(`${API_BASE_URL}/users`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(userData)
            });
            return response.json();
        };
        
        export default UserManager;
        """)
        
        file_path = self.create_test_file(js_code, '.js')
        
        documents = self.parser.parse_with_ast(js_code, file_path, 'javascript')
        print(f"  ✅ 解析出 {len(documents)} 个代码元素:")
        
        self.assertIsInstance(documents, list)
        
        for doc in documents:
            meta = doc.metadata
            print(f"    - {meta['element_type']}: {meta['element_name']} "
                  f"(行 {meta['start_line']}-{meta['end_line']})")
    
    def test_java_parsing(self):
        """测试Java代码解析"""
        print("\n☕ 测试Java代码解析:")
        
        java_code = textwrap.dedent("""
        package com.example.service;
        
        import java.util.List;
        import java.util.ArrayList;
        import java.util.concurrent.CompletableFuture;
        
        public class UserService {
            private final UserRepository userRepository;
            private static final int MAX_RETRIES = 3;
            
            public UserService(UserRepository userRepository) {
                this.userRepository = userRepository;
            }
            
            public List<User> getAllUsers() {
                return userRepository.findAll();
            }
            
            public CompletableFuture<User> createUserAsync(User user) {
                return CompletableFuture.supplyAsync(() -> {
                    validateUser(user);
                    return userRepository.save(user);
                });
            }
            
            private void validateUser(User user) {
                if (user.getName() == null || user.getName().isEmpty()) {
                    throw new IllegalArgumentException("User name cannot be empty");
                }
            }
        }
        
        interface UserRepository {
            List<User> findAll();
            User save(User user);
            User findById(Long id);
        }
        """)
        
        file_path = self.create_test_file(java_code, '.java')
        
        documents = self.parser.parse_with_ast(java_code, file_path, 'java')
        print(f"  ✅ 解析出 {len(documents)} 个代码元素:")
        
        self.assertIsInstance(documents, list)
        
        for doc in documents:
            meta = doc.metadata
            print(f"    - {meta['element_type']}: {meta['element_name']} "
                  f"(行 {meta['start_line']}-{meta['end_line']})")
    
    def test_go_parsing(self):
        """测试Go代码解析"""
        print("\n🐹 测试Go代码解析:")
        
        go_code = textwrap.dedent("""
        package main
        
        import (
            "fmt"
            "net/http"
            "encoding/json"
        )
        
        type User struct {
            ID   int    `json:"id"`
            Name string `json:"name"`
            Email string `json:"email"`
        }
        
        type UserService struct {
            users []User
        }
        
        func NewUserService() *UserService {
            return &UserService{
                users: make([]User, 0),
            }
        }
        
        func (s *UserService) AddUser(user User) {
            s.users = append(s.users, user)
        }
        
        func (s *UserService) GetUsers() []User {
            return s.users
        }
        
        func handleUsers(w http.ResponseWriter, r *http.Request) {
            service := NewUserService()
            users := service.GetUsers()
            
            w.Header().Set("Content-Type", "application/json")
            json.NewEncoder(w).Encode(users)
        }
        
        var defaultPort = ":8080"
        
        func main() {
            http.HandleFunc("/users", handleUsers)
            fmt.Println("Server starting on port", defaultPort)
            http.ListenAndServe(defaultPort, nil)
        }
        """)
        
        file_path = self.create_test_file(go_code, '.go')
        
        documents = self.parser.parse_with_ast(go_code, file_path, 'go')
        print(f"  ✅ 解析出 {len(documents)} 个代码元素:")
        
        self.assertIsInstance(documents, list)
        
        for doc in documents:
            meta = doc.metadata
            print(f"    - {meta['element_type']}: {meta['element_name']} "
                  f"(行 {meta['start_line']}-{meta['end_line']})")
    
    def test_error_handling(self):
        """测试错误处理"""
        print("\n🚨 测试错误处理:")
        
        # 测试语法错误的代码
        invalid_python = "def broken_function(\n    # 缺少闭合括号"
        
        file_path = self.create_test_file(invalid_python, '.py')
        
        documents = self.parser.parse_with_ast(invalid_python, file_path, 'python')
        print(f"  ✅ 错误处理正常，返回 {len(documents)} 个文档")
        
        self.assertIsInstance(documents, list)
        if documents:
            meta = documents[0].metadata
            if 'ast_parsing_failed' in meta:
                print("    - 正确识别为AST解析失败")
        
        # 测试不支持的语言
        print("  测试不支持的语言:")
        unsupported_code = "print('hello')"
        file_path = self.create_test_file(unsupported_code, '.unknown')
        
        documents = self.parser.parse_with_ast(unsupported_code, file_path, 'unknown')
        print(f"  ✅ 不支持语言处理正常，返回 {len(documents)} 个文档")
        
        self.assertIsInstance(documents, list)
        if documents:
            meta = documents[0].metadata
            if 'unsupported_language' in meta:
                print("    - 正确识别为不支持的语言")
    
    def test_performance(self):
        """测试性能"""
        print("\n⚡ 测试性能:")
        
        # 生成较大的Python文件
        large_python = []
        large_python.append("import os, sys, json")
        
        for i in range(50):
            large_python.append(f"""
class TestClass{i}:
    def __init__(self):
        self.value = {i}
    
    def method_{i}(self, param):
        return param * {i}
    
    def another_method_{i}(self):
        data = [x for x in range({i * 10})]
        return sum(data)
""")
        
        large_code = "\n".join(large_python)
        
        file_path = self.create_test_file(large_code, '.py')
        
        start_time = time.time()
        documents = self.parser.parse_with_ast(large_code, file_path, 'python')
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"  ✅ 大文件解析完成:")
        print(f"    - 文件大小: {len(large_code):,} 字符")
        print(f"    - 解析时间: {duration:.2f} 秒")
        print(f"    - 提取元素: {len(documents)} 个")
        
        self.assertIsInstance(documents, list)
        self.assertGreater(len(documents), 0)
        self.assertLess(duration, 10.0)  # 应该在10秒内完成


class TestAstParserIntegration(unittest.TestCase):
    """AST解析器集成测试"""
    
    def test_all_supported_languages(self):
        """测试所有支持的语言"""
        parser = AstParser()
        supported_languages = parser.get_supported_languages()
        
        # 简单的代码示例
        test_codes = {
            'python': 'def hello(): pass',
            'javascript': 'function hello() {}',
            'java': 'public class Test {}',
            'go': 'func main() {}',
            'typescript': 'function hello(): void {}',
        }
        
        for lang in supported_languages:
            if lang in test_codes:
                with self.subTest(language=lang):
                    code = test_codes[lang]
                    with tempfile.NamedTemporaryFile(mode='w', suffix=f'.{lang}', delete=False) as f:
                        f.write(code)
                        temp_path = f.name
                    
                    try:
                        documents = parser.parse_with_ast(code, temp_path, lang)
                        self.assertIsInstance(documents, list)
                    finally:
                        os.unlink(temp_path)


def run_comprehensive_test():
    """运行综合测试（非unittest格式）"""
    print("🔧 AST解析器综合测试开始")
    print("=" * 50)
    
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加测试类
    suite.addTests(loader.loadTestsFromTestCase(TestAstParser))
    suite.addTests(loader.loadTestsFromTestCase(TestAstParserIntegration))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "=" * 50)
    if result.wasSuccessful():
        print("🎉 所有测试完成!")
    else:
        print(f"❌ 测试失败: {len(result.failures)} 个失败, {len(result.errors)} 个错误")
    
    return result


if __name__ == "__main__":
    # 运行综合测试
    run_comprehensive_test()