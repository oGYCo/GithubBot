"""
AST解析器
负责抽象语法树（AST）的生成和分析
"""

import logging
import os
from typing import Any, Dict, List, Optional, Set, Callable
from langchain_core.documents import Document
from tree_sitter import Language, Parser, Node

# 动态导入语言解析器
AVAILABLE_PARSERS = {}

# 语言模块映射
LANGUAGE_MODULES = {
    'python': 'tree_sitter_python',
    'javascript': 'tree_sitter_javascript',
    'typescript': 'tree_sitter_typescript', 
    'java': 'tree_sitter_java',
    'cpp': 'tree_sitter_cpp',
    'go': 'tree_sitter_go',
    'rust': 'tree_sitter_rust',
    'csharp': 'tree_sitter_c_sharp'
}

# 动态加载可选语言解析器
for lang, module_name in LANGUAGE_MODULES.items():
    try:
        module = __import__(module_name, fromlist=[module_name])
        AVAILABLE_PARSERS[lang] = module
    except ImportError:
        pass

# 在文件顶部添加更好的导入处理
try:
    from .file_parser import FileType
    from ..core.config import settings
except ImportError:
    # 直接运行时的回退
    class FileType:
        CODE = "code"
        TEXT = "text"
        BINARY = "binary"
    
    class Settings:
        AST_MAX_FILE_SIZE = 1024 * 1024
        AST_SUPPORTED_LANGUAGES = []
    
    settings = Settings()

logger = logging.getLogger(__name__)

class AstParser:
    # 语言配置缓存
    _LANGUAGE_CONFIGS = {
        'python': {'extensions': {'.py'}, 'node_types': {
            'class_definition', 'function_definition', 'assignment', 
            'decorated_definition', 'import_statement', 'import_from_statement'
        }},
        'javascript': {'extensions': {'.js', '.jsx', '.mjs'}, 'node_types': {
            'class_declaration', 'function_declaration', 'method_definition',
            'arrow_function', 'variable_declaration', 'import_statement', 'export_statement'
        }},
        'typescript': {'extensions': {'.ts', '.tsx'}, 'node_types': {
            'class_declaration', 'function_declaration', 'method_definition',
            'arrow_function', 'variable_declaration', 'import_statement', 'export_statement'
        }},
        'java': {'extensions': {'.java'}, 'node_types': {
            'class_declaration', 'interface_declaration', 'method_declaration',
            'field_declaration', 'import_declaration', 'package_declaration'
        }},
        'cpp': {'extensions': {'.cpp', '.cc', '.cxx', '.c++', '.hpp', '.h'}, 'node_types': {
            'class_specifier', 'struct_specifier', 'function_definition',
            'declaration', 'preproc_include'
        }},
        'go': {'extensions': {'.go'}, 'node_types': {
            'type_declaration', 'function_declaration', 'method_declaration',
            'var_declaration', 'import_declaration', 'package_clause'
        }},
        'rust': {'extensions': {'.rs'}, 'node_types': {
            'struct_item', 'enum_item', 'impl_item', 'function_item',
            'let_declaration', 'use_declaration'
        }},
        'csharp': {'extensions': {'.cs'}, 'node_types': {
            'class_declaration', 'interface_declaration', 'struct_declaration',
            'method_declaration', 'property_declaration', 'field_declaration', 'using_directive'
        }}
    }

    def __init__(self):
        """初始化AST解析器"""
        self.parsers: Dict[str, Parser] = {}
        self._extension_to_language = {}
        self._element_extractors_cache = {}
        self._init_languages()

    def _init_languages(self):
        """初始化支持的编程语言"""
        initialized_count = 0
        
        for lang_name, config in self._LANGUAGE_CONFIGS.items():
            if lang_name not in AVAILABLE_PARSERS:
                logger.debug(f"⚠️ {lang_name} 解析器模块未安装，跳过初始化")
                continue
                
            try:
                module = AVAILABLE_PARSERS[lang_name]
                
                # 获取语言对象
                language = None

                if lang_name == 'typescript' and hasattr(module, 'language_typescript'):
                    language = Language(module.language_typescript())
                elif lang_name == 'typescript' and hasattr(module, 'typescript'):
                    language = Language(module.typescript())
                else:
                    language = Language(module.language())

                parser = Parser(language)
                
                self.parsers[lang_name] = parser
                
                # 构建扩展名映射
                for ext in config['extensions']:
                    self._extension_to_language[ext] = lang_name
                
                initialized_count += 1
                logger.debug(f"✅ 初始化 {lang_name} 解析器成功")
                
            except Exception as e:
                logger.warning(f"⚠️ 初始化 {lang_name} 解析器失败: {e}")

        logger.info(f"🔧 AST解析器初始化完成，支持 {initialized_count} 种语言: {list(self.parsers.keys())}")

    def _detect_language_from_extension(self, file_path: str) -> Optional[str]:
        """根据文件扩展名检测编程语言"""
        ext = os.path.splitext(file_path)[1].lower()
        return self._extension_to_language.get(ext)

    def should_use_ast_parsing(self, file_info: Dict[str, Any], language: str) -> bool:
        """
        判断是否应该使用AST解析
        
        Args:
            file_info: 文件信息
            language: 编程语言
            
        Returns:
            bool: 是否使用AST解析
        """
        # 只对代码文件使用AST解析
        if file_info.get("file_type") != FileType.CODE:
            return False
        
        # 检查文件大小限制
        max_size = getattr(settings, 'AST_MAX_FILE_SIZE', 1024 * 1024)  # 1MB
        if file_info.get("file_size", 0) > max_size:
            logger.debug(f"⚠️ 文件过大，跳过AST解析: {file_info.get('file_path')}")
            return False
        
        # 检查语言支持
        detected_lang = self._detect_language_from_extension(file_info.get('file_path', ''))
        return (detected_lang in self.parsers or 
                language.lower() in self.parsers)

    def parse_with_ast(self, content: str, file_path: str, language: str) -> List[Document]:
        """
        使用AST解析文件内容

        Args:
            content: 文件内容
            file_path: 文件路径
            language: 编程语言

        Returns:
            List[Document]: 解析得到的文档列表
        """
        # 确定实际使用的语言
        actual_language = self._determine_language(file_path, language)
        if not actual_language:
            return self._create_fallback_document(content, file_path, language, "unsupported_language")

        try:
            # 使用对应语言的解析器
            parser = self.parsers[actual_language]
            tree = parser.parse(content.encode('utf8'))
            
            if tree.root_node.has_error:
                logger.warning(f"⚠️ AST包含语法错误: {file_path}")
            
            documents = []
            source_bytes = content.encode('utf8')
            
            # 提取代码元素
            self._extract_code_elements(tree.root_node, source_bytes, file_path, documents, actual_language)
            
            logger.debug(f"✅ AST解析完成: {file_path} ({actual_language}), 提取了 {len(documents)} 个代码元素")
            return documents
            
        except Exception as e:
            logger.error(f"❌ AST解析失败: {file_path}, 错误: {str(e)}")
            return self._create_fallback_document(content, file_path, language, "ast_parsing_failed")

    def _determine_language(self, file_path: str, language: str) -> Optional[str]:
        """确定要使用的编程语言"""
        # 优先使用文件扩展名检测
        detected_lang = self._detect_language_from_extension(file_path)
        if detected_lang and detected_lang in self.parsers:
            return detected_lang
        
        # 其次使用传入的语言参数
        normalized_lang = language.lower()
        if normalized_lang in self.parsers:
            return normalized_lang
            
        return None

    def _create_fallback_document(self, content: str, file_path: str, language: str, error_type: str) -> List[Document]:
        """创建回退文档"""
        if error_type == "unsupported_language":
            logger.warning(f"⚠️ 不支持的语言: {language}, 文件: {file_path}")
        
        return [Document(
            page_content=content,
            metadata={
                "file_path": file_path,
                "language": language,
                "element_type": "file",
                error_type: True
            }
        )]

    def _extract_code_elements(self, node: Node, source_bytes: bytes, file_path: str, 
                             documents: List[Document], language: str):
        """
        递归提取代码元素
        
        Args:
            node: AST节点
            source_bytes: 源代码字节
            file_path: 文件路径
            documents: 文档列表
            language: 编程语言
        """
        # 获取元素提取器（使用缓存）
        extractors = self._get_element_extractors_cached(language)
        
        # 如果当前节点是目标类型，提取它
        if node.type in extractors:
            try:
                doc = extractors[node.type](node, source_bytes, file_path, language)
                if doc:
                    documents.append(doc)
            except Exception as e:
                logger.warning(f"⚠️ 提取节点失败: {node.type} in {file_path}, 错误: {str(e)}")
        
        # 递归处理子节点
        for child in node.children:
            self._extract_code_elements(child, source_bytes, file_path, documents, language)

    def _get_element_extractors_cached(self, language: str) -> Dict[str, Callable]:
        """获取元素提取器（带缓存）"""
        if language not in self._element_extractors_cache:
            self._element_extractors_cache[language] = self._build_element_extractors(language)
        return self._element_extractors_cache[language]

    def _build_element_extractors(self, language: str) -> Dict[str, Callable]:
        """构建元素提取器映射"""
        # 基础提取器
        extractors = {}
        
        # 根据语言配置添加提取器
        config = self._LANGUAGE_CONFIGS.get(language, {})
        node_types = config.get('node_types', set())
        
        for node_type in node_types:
            if 'class' in node_type or 'struct' in node_type or 'interface' in node_type or 'enum' in node_type:
                extractors[node_type] = self._extract_class
            elif 'function' in node_type or 'method' in node_type:
                extractors[node_type] = self._extract_function
            elif 'import' in node_type or 'export' in node_type or 'package' in node_type or 'using' in node_type or 'use_declaration' in node_type:
                extractors[node_type] = self._extract_import
            elif 'assignment' in node_type or 'declaration' in node_type or 'var_' in node_type or 'let_' in node_type or 'field_' in node_type or 'property_' in node_type:
                extractors[node_type] = self._extract_assignment
            elif 'decorated' in node_type:
                extractors[node_type] = self._extract_decorated_definition
                
        return extractors

    def _extract_class(self, node: Node, source_bytes: bytes, file_path: str, language: str = "python") -> Document:
        """提取类定义"""
        content = source_bytes[node.start_byte:node.end_byte].decode('utf8')
        
        # 提取类名 - 根据语言调整
        class_name = self._extract_identifier(node, source_bytes, language)
        
        return Document(
            page_content=content,
            metadata={
                "file_path": file_path,
                "element_type": "class",
                "element_name": class_name,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "language": language
            }
        )

    def _extract_function(self, node: Node, source_bytes: bytes, file_path: str, language: str = "python") -> Document:
        """提取函数定义"""
        content = source_bytes[node.start_byte:node.end_byte].decode('utf8')
        
        # 提取函数名
        function_name = self._extract_identifier(node, source_bytes, language)
        
        return Document(
            page_content=content,
            metadata={
                "file_path": file_path,
                "element_type": "function",
                "element_name": function_name,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "language": language
            }
        )

    def _extract_import(self, node: Node, source_bytes: bytes, file_path: str, language: str = "python") -> Document:
        """提取导入语句"""
        content = source_bytes[node.start_byte:node.end_byte].decode('utf8')
        
        return Document(
            page_content=content,
            metadata={
                "file_path": file_path,
                "element_type": "import",
                "element_name": content.strip(),
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "language": language
            }
        )

    def _extract_assignment(self, node: Node, source_bytes: bytes, file_path: str, language: str = "python") -> Document:
        """提取变量赋值"""
        content = source_bytes[node.start_byte:node.end_byte].decode('utf8')
        
        # 检查是否为模块级别的赋值
        if language == 'python':
            parent = node.parent
            while parent:
                if parent.type in ['function_definition', 'class_definition']:
                    return None
                parent = parent.parent
        
        # 提取变量名
        variable_name = self._extract_variable_name(node, source_bytes, language)
        
        return Document(
            page_content=content,
            metadata={
                "file_path": file_path,
                "element_type": "assignment",
                "element_name": variable_name,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "language": language
            }
        )

    def _extract_decorated_definition(self, node: Node, source_bytes: bytes, file_path: str, language: str = "python") -> Document:
        """提取装饰器定义"""
        content = source_bytes[node.start_byte:node.end_byte].decode('utf8')
        
        # 查找被装饰的定义
        definition_name = self._extract_identifier(node, source_bytes, language)
        
        return Document(
            page_content=content,
            metadata={
                "file_path": file_path,
                "element_type": "decorated_definition",
                "element_name": definition_name,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "language": language
            }
        )

    def _extract_identifier(self, node: Node, source_bytes: bytes, language: str) -> str:
        """提取标识符名称"""
        # 语言特定的标识符提取策略
        if language == 'javascript' or language == 'typescript':
            return self._extract_js_identifier(node, source_bytes)
        elif language == 'java':
            return self._extract_java_identifier(node, source_bytes)
        elif language == 'python':
            return self._extract_python_identifier(node, source_bytes)
        else:
            # 通用提取逻辑
            return self._extract_generic_identifier(node, source_bytes)

    def _extract_js_identifier(self, node: Node, source_bytes: bytes) -> str:
        """提取JavaScript/TypeScript标识符"""
        # JavaScript方法定义的特殊处理
        if node.type == 'method_definition':
            # 查找property_identifier节点
            for child in node.children:
                if child.type == 'property_identifier':
                    return source_bytes[child.start_byte:child.end_byte].decode('utf8')
        
        # 函数声明和箭头函数
        if node.type in ['function_declaration', 'arrow_function']:
            for child in node.children:
                if child.type == 'identifier':
                    return source_bytes[child.start_byte:child.end_byte].decode('utf8')
        
        # 变量声明
        if node.type == 'variable_declaration':
            for child in node.children:
                if child.type == 'variable_declarator':
                    for grandchild in child.children:
                        if grandchild.type == 'identifier':
                            return source_bytes[grandchild.start_byte:grandchild.end_byte].decode('utf8')
        
        # 通用查找
        return self._extract_generic_identifier(node, source_bytes)

    def _extract_python_identifier(self, node: Node, source_bytes: bytes) -> str:
        """提取Python标识符"""
        # 直接查找identifier节点
        for child in node.children:
            if child.type == "identifier":
                return source_bytes[child.start_byte:child.end_byte].decode('utf8')
        
        # 递归查找
        return self._extract_identifier_recursive(node, source_bytes, max_depth=2)

    def _extract_java_identifier(self, node: Node, source_bytes: bytes) -> str:
        """提取Java标识符"""
        # Java特定的标识符提取
        for child in node.children:
            if child.type == "identifier":
                return source_bytes[child.start_byte:child.end_byte].decode('utf8')
        
        return self._extract_generic_identifier(node, source_bytes)

    def _extract_generic_identifier(self, node: Node, source_bytes: bytes) -> str:
        """通用标识符提取"""
        # 直接查找identifier节点
        for child in node.children:
            if child.type == "identifier":
                return source_bytes[child.start_byte:child.end_byte].decode('utf8')
        
        # 递归查找（限制深度）
        return self._extract_identifier_recursive(node, source_bytes, max_depth=3)

    def _extract_identifier_recursive(self, node: Node, source_bytes: bytes, max_depth: int = 2) -> str:
        """递归提取标识符（限制深度）"""
        if max_depth <= 0:
            return "Unknown"
            
        for child in node.children:
            if child.type in ["identifier", "property_identifier"]:
                return source_bytes[child.start_byte:child.end_byte].decode('utf8')
            
            # 递归查找
            result = self._extract_identifier_recursive(child, source_bytes, max_depth - 1)
            if result != "Unknown":
                return result
        
        return "Unknown"

    def _extract_variable_name(self, node: Node, source_bytes: bytes, language: str) -> str:
        """提取变量名"""
        # 快速路径：Python简单赋值
        if language == 'python':
            content = source_bytes[node.start_byte:node.end_byte].decode('utf8')
            if '=' in content:
                return content.split('=')[0].strip()
        
        # 通用方法：查找variable_declarator或identifier
        for child in node.children:
            if child.type == 'variable_declarator':
                identifier = self._extract_identifier(child, source_bytes, language)
                if identifier != "Unknown":
                    return identifier
            elif child.type == 'identifier':
                return source_bytes[child.start_byte:child.end_byte].decode('utf8')
        
        return "Unknown"

    def get_supported_languages(self) -> List[str]:
        """获取支持的语言列表"""
        return list(self.parsers.keys())

    def get_language_extensions(self, language: str) -> Set[str]:
        """获取语言支持的文件扩展名"""
        config = self._LANGUAGE_CONFIGS.get(language, {})
        return config.get('extensions', set())
