"""
AST解析器
负责抽象语法树（AST）的生成和分析
"""

import logging
import os
import re
import json
from typing import Any, Dict, List, Optional, Set, Callable, NamedTuple
from langchain_core.documents import Document
from tree_sitter import Language, Parser, Node

# 简单的伪节点类，用于大类分解
class MockNode(NamedTuple):
    start_byte: int
    end_byte: int
    type: str

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

    def __init__(self, 
                 chunk_size: int = 1000,
                 chunk_overlap: int = 200,
                 min_chunk_size: int = 100,
                 max_chunk_size: int = 2000,
                 class_decompose_threshold: float = 2.5):
        """初始化AST解析器
        
        Args:
            chunk_size: 目标块大小（非空白字符数）
            chunk_overlap: 块重叠大小
            min_chunk_size: 最小块大小
            max_chunk_size: 最大块大小
            class_decompose_threshold: 大类分解阈值倍数（相对于chunk_size）
        """
        self.parsers: Dict[str, Parser] = {}
        self._extension_to_language = {}
        self._element_extractors_cache = {}
        
        # 分块配置
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.class_decompose_threshold = class_decompose_threshold
        
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
            
            # 应用分块和合并策略
            processed_documents = self._process_documents_with_chunking(documents, file_path, actual_language)
            
            logger.debug(f"✅ AST解析完成: {file_path} ({actual_language}), 提取了 {len(documents)} 个代码元素，处理后 {len(processed_documents)} 个文档块")
            return processed_documents
            
        except Exception as e:
            logger.error(f"❌ AST解析失败: {file_path}, 错误: {str(e)}")
            return self._create_fallback_document(content, file_path, language, "ast_parsing_failed")

    def _count_non_whitespace_chars(self, text: str) -> int:
        """计算非空白字符数"""
        return len(re.sub(r'\s', '', text))

    def _process_documents_with_chunking(self, documents: List[Document], file_path: str, language: str) -> List[Document]:
        """
        对文档进行分块和合并处理
        
        Args:
            documents: 原始文档列表
            file_path: 文件路径
            language: 编程语言
            
        Returns:
            List[Document]: 处理后的文档列表
        """
        if not documents:
            return documents
            
        processed_docs = []
        
        # 首先处理需要分块的大文档
        for doc in documents:
            non_ws_count = self._count_non_whitespace_chars(doc.page_content)
            
            if non_ws_count > self.max_chunk_size:
                # 需要分块
                chunked_docs = self._chunk_large_document(doc, file_path, language)
                processed_docs.extend(chunked_docs)
            else:
                processed_docs.append(doc)
        
        # 然后合并小文档
        merged_docs = self._merge_small_documents(processed_docs, file_path, language)
        
        return merged_docs

    def _chunk_large_document(self, doc: Document, file_path: str, language: str) -> List[Document]:
        """
        分块大文档（语法感知优先，长度兜底）
        
        Args:
            doc: 要分块的文档
            file_path: 文件路径
            language: 编程语言
            
        Returns:
            List[Document]: 分块后的文档列表
        思路：
        1) 先用对应语言的 parser 解析 doc.page_content。
        2) 尽量在语法节点边界（语句、类成员、函数体语句等）进行切分并按 chunk_size 聚合。
        3) 如果语法不可用或失败，退化为原来的按行切分逻辑。
        4) 保持 chunk_overlap（按非空白字符数）作为上下文重叠。
        """
        content = doc.page_content
        chunks: List[Document] = []

        # 优先语法感知切分
        try:
            if language not in self.parsers:
                raise RuntimeError("parser_not_available")

            parser = self.parsers[language]
            source_bytes = content.encode("utf8")
            tree = parser.parse(source_bytes)
            root = tree.root_node

            # 获取候选语法单元（尽量是语句或成员），失败则抛出异常走兜底
            units = self._get_syntax_units_for_chunking(root, source_bytes, language)
            if not units:
                raise RuntimeError("no_syntax_units")

            # 基于语法单元聚合形成块
            current_parts: List[str] = []
            current_non_ws = 0
            chunk_idx = 0

            def flush_chunk():
                nonlocal current_parts, current_non_ws, chunk_idx
                if not current_parts:
                    return
                # 用换行符连接语法单元，保持代码结构
                chunk_text = "\n".join(current_parts)
                chunk_doc = self._create_chunk_document(
                    chunk_text, doc, chunk_idx, file_path, language
                )
                chunks.append(chunk_doc)
                chunk_idx += 1
                
                # 重叠策略：保留最后几个较小的语法单元作为下一块的开头
                overlap_parts = []
                overlap_non_ws = 0
                
                # 从后往前添加单元，直到接近重叠大小
                for part in reversed(current_parts):
                    part_non_ws = self._count_non_whitespace_chars(part)
                    if overlap_non_ws + part_non_ws <= self.chunk_overlap:
                        overlap_parts.insert(0, part)
                        overlap_non_ws += part_non_ws
                    else:
                        break
                
                current_parts = overlap_parts
                current_non_ws = overlap_non_ws

            for u_start, u_end in units:
                part = source_bytes[u_start:u_end].decode("utf8").strip()
                if not part:  # 跳过空内容
                    continue
                    
                part_len = self._count_non_whitespace_chars(part)

                # 处理超大单个语法单元：如果单个单元超过max_chunk_size，尝试进一步分解
                if part_len > self.max_chunk_size:
                    logger.debug(f"发现超大语法单元({part_len}字符)，尝试进一步分解")
                    # 先保存当前块
                    if current_parts:
                        flush_chunk()
                    
                    # 尝试分解超大单元
                    large_unit_chunks = self._decompose_large_unit(part, doc, len(chunks), file_path, language)
                    chunks.extend(large_unit_chunks)
                    continue

                # 改进的分块逻辑：
                # 1. 如果当前块已经足够大，且添加新单元会超过chunk_size，则分块
                # 2. 智能分块：考虑语法单元的重要性
                should_chunk = False
                
                if current_parts:  # 已有内容
                    if current_non_ws + part_len > self.chunk_size and current_non_ws >= self.min_chunk_size:
                        should_chunk = True
                    # 如果当前块已达到目标大小的80%，且新单元会使其明显超过，也分块
                    elif (current_non_ws >= self.chunk_size * 0.8 and 
                          current_non_ws + part_len > self.chunk_size * 1.2):
                        should_chunk = True
                    # 智能边界：如果是类或函数定义，倾向于在此分界
                    elif (current_non_ws >= self.chunk_size * 0.6 and 
                          self._is_major_boundary(part) and
                          current_non_ws + part_len > self.chunk_size * 1.5):
                        should_chunk = True
                
                if should_chunk:
                    flush_chunk()

                current_parts.append(part)
                current_non_ws += part_len

            # 最后一个块
            if current_parts:
                chunk_text = "\n".join(current_parts)
                chunk_doc = self._create_chunk_document(
                    chunk_text, doc, len(chunks), file_path, language
                )
                chunks.append(chunk_doc)

            logger.debug(
                f"📄 大文档分块(语法): {doc.metadata.get('element_name', 'Unknown')} -> {len(chunks)} 个块")
            if chunks:
                return chunks

        except Exception as e:
            # 改进的错误处理：记录具体错误但继续处理
            logger.debug(f"语法分块失败，回退到行分块: {str(e)}")
            pass

        # 兜底：按行切分（原逻辑）
        lines = content.split('\n')
        current_chunk_lines: List[str] = []
        current_non_ws_count = 0

        for line in lines:
            line_non_ws = self._count_non_whitespace_chars(line)

            if (current_non_ws_count + line_non_ws > self.chunk_size and
                    current_chunk_lines and
                    current_non_ws_count >= self.min_chunk_size):

                #创建当前块
                chunk_content = '\n'.join(current_chunk_lines)
                chunk_doc = self._create_chunk_document(
                    chunk_content, doc, len(chunks), file_path, language
                )
                chunks.append(chunk_doc)

                # 处理重叠
                overlap_lines = self._get_overlap_lines(current_chunk_lines)
                current_chunk_lines = overlap_lines + [line]
                current_non_ws_count = self._count_non_whitespace_chars('\n'.join(current_chunk_lines))
            else:
                current_chunk_lines.append(line)
                current_non_ws_count += line_non_ws
                
        #处理最后一个块
        if current_chunk_lines:
            chunk_content = '\n'.join(current_chunk_lines)
            chunk_doc = self._create_chunk_document(
                chunk_content, doc, len(chunks), file_path, language
            )
            chunks.append(chunk_doc)

        logger.debug(
            f"📄 大文档分块(行): {doc.metadata.get('element_name', 'Unknown')} -> {len(chunks)} 个块")
        return chunks

    def _get_text_overlap(self, text: str) -> str:
        """根据 chunk_overlap 从结尾回溯构造重叠文本（按非空白字符数，尽量在行边界）。"""
        if self.chunk_overlap <= 0 or not text:
            return ""
        
        lines = text.split('\n')
        overlap_lines = []
        total_non_ws = 0
        
        # 从末尾开始添加完整的行，直到接近重叠大小
        for line in reversed(lines):
            line_non_ws = self._count_non_whitespace_chars(line)
            if total_non_ws + line_non_ws <= self.chunk_overlap:
                overlap_lines.insert(0, line)
                total_non_ws += line_non_ws
            else:
                break
        
        return '\n'.join(overlap_lines) if overlap_lines else ""

    def _is_major_boundary(self, content: str) -> bool:
        """判断是否为主要语法边界（类、函数定义等）"""
        content_strip = content.strip()
        # Python
        if (content_strip.startswith('class ') or 
            content_strip.startswith('def ') or 
            content_strip.startswith('async def ') or
            content_strip.startswith('@')):
            return True
        # JavaScript/TypeScript
        if (content_strip.startswith('class ') or 
            content_strip.startswith('function ') or 
            content_strip.startswith('export ') or
            content_strip.startswith('import ') or
            content_strip.startswith('const ') or
            content_strip.startswith('let ') or
            content_strip.startswith('var ')):
            return True
        # Java/C#
        if (content_strip.startswith('public class ') or 
            content_strip.startswith('private class ') or 
            content_strip.startswith('protected class ') or
            content_strip.startswith('internal class ') or
            content_strip.startswith('public interface ') or
            content_strip.startswith('public struct ') or
            content_strip.startswith('public enum ') or
            content_strip.startswith('public ') or
            content_strip.startswith('private ') or
            content_strip.startswith('protected ') or
            content_strip.startswith('namespace ') or
            content_strip.startswith('using ')):
            return True
        # Go
        if (content_strip.startswith('func ') or 
            content_strip.startswith('type ') or 
            content_strip.startswith('var ') or
            content_strip.startswith('const ') or
            content_strip.startswith('package ') or
            content_strip.startswith('import ')):
            return True
        # Rust
        if (content_strip.startswith('fn ') or 
            content_strip.startswith('struct ') or 
            content_strip.startswith('enum ') or
            content_strip.startswith('impl ') or
            content_strip.startswith('trait ') or
            content_strip.startswith('mod ') or
            content_strip.startswith('use ') or
            content_strip.startswith('pub fn ') or
            content_strip.startswith('pub struct ') or
            content_strip.startswith('pub enum ') or
            content_strip.startswith('pub trait ') or
            content_strip.startswith('pub mod ')):
            return True
        # C/C++
        if (content_strip.startswith('class ') or 
            content_strip.startswith('struct ') or 
            content_strip.startswith('namespace ') or
            content_strip.startswith('template ') or
            content_strip.startswith('template<') or
            content_strip.startswith('#include ') or
            content_strip.startswith('#define ') or
            content_strip.startswith('extern ') or
            content_strip.startswith('static ') or
            content_strip.startswith('inline ') or
            content_strip.startswith('virtual ') or
            content_strip.startswith('public:') or
            content_strip.startswith('private:') or
            content_strip.startswith('protected:')):
            return True
        return False

    def _decompose_large_unit(self, content: str, original_doc: Document, 
                             start_chunk_idx: int, file_path: str, language: str) -> List[Document]:
        """分解超大的语法单元（如非常长的方法）"""
        # 对于超大单元，回退到行级分块
        lines = content.split('\n')
        sub_chunks = []
        current_lines = []
        current_non_ws = 0
        
        for line in lines:
            line_non_ws = self._count_non_whitespace_chars(line)
            
            if (current_non_ws + line_non_ws > self.chunk_size and 
                current_lines and 
                current_non_ws >= self.min_chunk_size):
                
                # 创建子块
                sub_content = '\n'.join(current_lines)
                sub_chunk = self._create_chunk_document(
                    sub_content, original_doc, start_chunk_idx + len(sub_chunks), file_path, language
                )
                sub_chunk.metadata['is_decomposed_unit'] = True
                sub_chunks.append(sub_chunk)
                
                # 处理重叠
                overlap_lines = self._get_overlap_lines(current_lines)
                current_lines = overlap_lines + [line]
                current_non_ws = self._count_non_whitespace_chars('\n'.join(current_lines))
            else:
                current_lines.append(line)
                current_non_ws += line_non_ws
        
        # 处理最后的子块
        if current_lines:
            sub_content = '\n'.join(current_lines)
            sub_chunk = self._create_chunk_document(
                sub_content, original_doc, start_chunk_idx + len(sub_chunks), file_path, language
            )
            sub_chunk.metadata['is_decomposed_unit'] = True
            sub_chunks.append(sub_chunk)
        
        logger.debug(f"超大单元分解: {len(content)} 字符 -> {len(sub_chunks)} 个子块")
        return sub_chunks

    def _get_syntax_units_for_chunking(self, root: Node, source_bytes: bytes, language: str) -> List[tuple]:
        """
        获取用于分块的语法单元区间列表（start_byte, end_byte）。
        会尽量定位到“语句列表/成员列表”，否则退化为 root 的命名子节点。
        """
        def node_spans_all(n: Node) -> bool:
            # 判断 n 是否几乎覆盖整个 root（避免选错容器）
            total = root.end_byte - root.start_byte
            span = n.end_byte - n.start_byte
            return span >= max(0, total - 1)  # 容忍 1 字节误差

        lang = language.lower()
        container = root

        # 尝试找到更合适的容器（函数/类整个作为内容时）
        if len(root.children) == 1 and root.children[0].is_named and node_spans_all(root.children[0]):
            container = root.children[0]

        def named_children(n: Node) -> List[Node]:
            return [c for c in n.children if c.is_named]

        # 语言特定：寻找语句/成员列表
        units_nodes: List[Node] = []

        try:
            if lang == 'python':
                # 如果容器是类定义，优先提取类内的方法和属性
                if container.type == 'class_definition':
                    # 找到类体 (block/suite)
                    class_body = None
                    for c in container.children:
                        if c.type in ('block', 'suite'):
                            class_body = c
                            break
                    if class_body:
                        units_nodes = [n for n in named_children(class_body)]
                    else:
                        units_nodes = [container]  # 回退到整个类
                else:
                    # 模块级别或其他容器
                    # function/class/decorated 的 block 里是语句列表
                    block = None
                    for c in container.children:
                        if c.type in ('block', 'suite'):
                            block = c
                            break
                    if block:
                        units_nodes = [n for n in named_children(block)]
                    else:
                        # 模块级别：直接取命名子节点，但如果有大的类定义，需要进一步分解
                        initial_units = [n for n in named_children(container)]
                        units_nodes = []
                        for unit in initial_units:
                            if unit.type == 'class_definition':
                                # 如果类很大，分解为类声明+方法
                                class_size = unit.end_byte - unit.start_byte
                                if class_size > self.chunk_size * self.class_decompose_threshold:
                                    # 添加类声明行
                                    class_header = None
                                    class_body = None
                                    for c in unit.children:
                                        if c.type == 'identifier' or c.type == ':':
                                            continue
                                        elif c.type in ('block', 'suite'):
                                            class_body = c
                                            break
                                    
                                    # 添加类头部（到冒号）
                                    if class_body:
                                        header_end = class_body.start_byte
                                        units_nodes.append(MockNode(
                                            start_byte=unit.start_byte,
                                            end_byte=header_end,
                                            type='class_header'
                                        ))
                                        # 添加类体内的各个方法
                                        for method in named_children(class_body):
                                            units_nodes.append(method)
                                    else:
                                        units_nodes.append(unit)
                                else:
                                    units_nodes.append(unit)
                            else:
                                units_nodes.append(unit)

            elif lang in ('javascript', 'typescript'):
                # 如果容器是类声明，优先提取类内的方法和属性
                if container.type in ('class_declaration', 'class'):
                    # 找到类体
                    class_body = None
                    for c in container.children:
                        if c.type in ('class_body', 'object_type'):
                            class_body = c
                            break
                    if class_body:
                        units_nodes = [n for n in named_children(class_body)]
                    else:
                        units_nodes = [container]  # 回退到整个类
                else:
                    # 模块级别：直接取命名子节点，但如果有大的类定义，需要进一步分解
                    initial_units = [n for n in named_children(container)]
                    units_nodes = []
                    for unit in initial_units:
                        if unit.type in ('class_declaration', 'class'):
                            # 如果类很大，分解为类声明+方法
                            class_size = unit.end_byte - unit.start_byte
                            if class_size > self.chunk_size * self.class_decompose_threshold:
                                # 找到类体
                                class_body = None
                                for c in unit.children:
                                    if c.type in ('class_body', 'object_type'):
                                        class_body = c
                                        break
                                
                                # 添加类头部（到大括号）
                                if class_body:
                                    header_end = class_body.start_byte
                                    units_nodes.append(MockNode(
                                        start_byte=unit.start_byte,
                                        end_byte=header_end,
                                        type='class_header'
                                    ))
                                    # 添加类体内的各个方法
                                    for method in named_children(class_body):
                                        units_nodes.append(method)
                                else:
                                    units_nodes.append(unit)
                            else:
                                units_nodes.append(unit)
                        else:
                            units_nodes.append(unit)

            elif lang in ('java', 'csharp'):
                # 如果容器是类/接口/结构体声明，优先提取内部成员
                if container.type in ('class_declaration', 'interface_declaration', 'struct_declaration'):
                    # 找到类体
                    body = None
                    for c in container.children:
                        if c.type in ('class_body', 'interface_body', 'struct_body'):
                            body = c
                            break
                    if body:
                        units_nodes = [n for n in named_children(body)]
                    else:
                        units_nodes = [container]  # 回退到整个类
                else:
                    # 模块级别：直接取命名子节点，但如果有大的类定义，需要进一步分解
                    initial_units = [n for n in named_children(container)]
                    units_nodes = []
                    for unit in initial_units:
                        if unit.type in ('class_declaration', 'interface_declaration', 'struct_declaration'):
                            # 如果类很大，分解为类声明+方法
                            class_size = unit.end_byte - unit.start_byte
                            if class_size > self.chunk_size * self.class_decompose_threshold:
                                # 找到类体
                                body = None
                                for c in unit.children:
                                    if c.type in ('class_body', 'interface_body', 'struct_body'):
                                        body = c
                                        break
                                
                                # 添加类头部（到大括号）
                                if body:
                                    header_end = body.start_byte
                                    units_nodes.append(MockNode(
                                        start_byte=unit.start_byte,
                                        end_byte=header_end,
                                        type='class_header'
                                    ))
                                    # 添加类体内的各个成员
                                    for member in named_children(body):
                                        units_nodes.append(member)
                                else:
                                    units_nodes.append(unit)
                            else:
                                units_nodes.append(unit)
                        else:
                            units_nodes.append(unit)

            elif lang == 'go':
                # Go语言的结构体和接口处理
                if container.type in ('type_declaration', 'source_file'):
                    initial_units = [n for n in named_children(container)]
                    units_nodes = []
                    for unit in initial_units:
                        if unit.type == 'type_declaration':
                            # 检查是否是大的结构体或接口
                            type_size = unit.end_byte - unit.start_byte
                            if type_size > self.chunk_size * self.class_decompose_threshold:
                                # 分解为类型声明+方法
                                units_nodes.append(unit)  # Go的类型声明相对简单，暂时不分解
                            else:
                                units_nodes.append(unit)
                        else:
                            units_nodes.append(unit)
                else:
                    units_nodes = [n for n in named_children(container)]
                    
            elif lang == 'rust':
                # Rust的结构体、枚举、impl块处理
                if container.type in ('source_file', 'mod_item'):
                    initial_units = [n for n in named_children(container)]
                    units_nodes = []
                    for unit in initial_units:
                        if unit.type in ('struct_item', 'enum_item', 'impl_item'):
                            # 如果结构体/枚举/impl很大，分解它
                            item_size = unit.end_byte - unit.start_byte
                            if item_size > self.chunk_size * self.class_decompose_threshold:
                                if unit.type == 'impl_item':
                                    # impl块可以分解为impl声明+各个方法
                                    impl_body = None
                                    for c in unit.children:
                                        if c.type == 'declaration_list':
                                            impl_body = c
                                            break
                                    
                                    if impl_body:
                                        header_end = impl_body.start_byte
                                        units_nodes.append(MockNode(
                                            start_byte=unit.start_byte,
                                            end_byte=header_end,
                                            type='impl_header'
                                        ))
                                        # 添加impl体内的各个方法
                                        for method in named_children(impl_body):
                                            units_nodes.append(method)
                                    else:
                                        units_nodes.append(unit)
                                else:
                                    units_nodes.append(unit)  # 结构体和枚举暂时不分解
                            else:
                                units_nodes.append(unit)
                        else:
                            units_nodes.append(unit)
                else:
                    units_nodes = [n for n in named_children(container)]
                    
            elif lang in ('cpp', 'c'):
                # C++的类和结构体处理
                if container.type in ('translation_unit',):
                    initial_units = [n for n in named_children(container)]
                    units_nodes = []
                    for unit in initial_units:
                        if unit.type in ('class_specifier', 'struct_specifier'):
                            # 如果类很大，分解为类声明+方法
                            class_size = unit.end_byte - unit.start_byte
                            if class_size > self.chunk_size * self.class_decompose_threshold:
                                # C++类体通常在field_declaration_list中
                                class_body = None
                                for c in unit.children:
                                    if c.type == 'field_declaration_list':
                                        class_body = c
                                        break
                                
                                if class_body:
                                    header_end = class_body.start_byte
                                    units_nodes.append(MockNode(
                                        start_byte=unit.start_byte,
                                        end_byte=header_end,
                                        type='class_header'
                                    ))
                                    # 添加类体内的各个成员
                                    for member in named_children(class_body):
                                        units_nodes.append(member)
                                else:
                                    units_nodes.append(unit)
                            else:
                                units_nodes.append(unit)
                        else:
                            units_nodes.append(unit)
                else:
                    units_nodes = [n for n in named_children(container)]

            else:
                # 通用处理：对于未知语言，尝试基本的大节点分解
                initial_units = [n for n in named_children(container)]
                units_nodes = []
                for unit in initial_units:
                    # 如果单个节点很大，尝试分解其子节点
                    unit_size = unit.end_byte - unit.start_byte
                    if unit_size > self.chunk_size * self.class_decompose_threshold:
                        children = named_children(unit)
                        if len(children) > 1:  # 有多个子节点可以分解
                            units_nodes.extend(children)
                        else:
                            units_nodes.append(unit)
                    else:
                        units_nodes.append(unit)

        except Exception:
            units_nodes = []

        # 过滤掉非常小或无意义的节点（如注释/空标记），确保序
        units_nodes = [n for n in units_nodes if n.end_byte > n.start_byte]
        units_nodes.sort(key=lambda n: n.start_byte)

        # 合并相邻被语法漏掉的空洞：用 root 的范围兜底
        if not units_nodes:
            return [(root.start_byte, root.end_byte)]

        ranges: List[tuple] = []
        prev_end = units_nodes[0].start_byte
        # 如果开头有空洞，填上
        if prev_end > root.start_byte:
            ranges.append((root.start_byte, prev_end))

        # 单元本身
        for n in units_nodes:
            ranges.append((n.start_byte, n.end_byte))
            prev_end = n.end_byte

        # 尾部空洞
        if prev_end < root.end_byte:
            ranges.append((prev_end, root.end_byte))

        # 去掉全是空白的段
        cleaned: List[tuple] = []
        for s, e in ranges:
            seg = source_bytes[s:e].decode('utf8')
            if self._count_non_whitespace_chars(seg) > 0:
                cleaned.append((s, e))

        return cleaned

    def _get_overlap_lines(self, lines: List[str]) -> List[str]:
        """获取重叠的行"""
        if not lines or self.chunk_overlap <= 0:
            return []
            
        overlap_chars = 0
        overlap_lines = []
        
        # 从末尾开始计算重叠
        for line in reversed(lines):
            line_non_ws = self._count_non_whitespace_chars(line)
            if overlap_chars + line_non_ws <= self.chunk_overlap:
                overlap_lines.insert(0, line)
                overlap_chars += line_non_ws
            else:
                break
                
        return overlap_lines

    def _create_chunk_document(self, content: str, original_doc: Document, 
                             chunk_index: int, file_path: str, language: str) -> Document:
        """创建分块文档"""
        metadata = original_doc.metadata.copy()
        metadata.update({
            "is_chunk": True,
            "chunk_index": chunk_index,
            "original_element_name": metadata.get("element_name", "Unknown"),
            "chunk_non_ws_chars": self._count_non_whitespace_chars(content)
        })
        
        return Document(
            page_content=content,
            metadata=metadata
        )

    def _merge_small_documents(self, documents: List[Document], file_path: str, language: str) -> List[Document]:
        """
        合并小文档
        
        Args:
            documents: 文档列表
            file_path: 文件路径
            language: 编程语言
            
        Returns:
            List[Document]: 合并后的文档列表
        """
        if not documents:
            return documents
            
        merged_docs = []
        current_merge_group = []
        current_merge_size = 0
        
        # 按元素类型分组，优先级：import < assignment < function < class
        element_priority = {
            "import": 1,
            "assignment": 2, 
            "function": 3,
            "decorated_definition": 3,
            "class": 4
        }
        
        # 按优先级和位置排序
        sorted_docs = sorted(documents, key=lambda doc: (
            element_priority.get(doc.metadata.get("element_type", "unknown"), 5),
            doc.metadata.get("start_line", 0)
        ))
        
        for doc in sorted_docs:
            non_ws_count = self._count_non_whitespace_chars(doc.page_content)
            
            # 如果文档已经足够大，直接添加
            if non_ws_count >= self.min_chunk_size:
                # 先处理当前合并组
                if current_merge_group:
                    merged_doc = self._create_merged_document(current_merge_group, file_path, language)
                    merged_docs.append(merged_doc)
                    current_merge_group = []
                    current_merge_size = 0
                
                merged_docs.append(doc)
                continue
            
            # 检查是否可以合并
            can_merge = self._can_merge_documents(current_merge_group, doc)
            
            if (can_merge and 
                current_merge_size + non_ws_count <= self.chunk_size):
                # 加入当前合并组
                current_merge_group.append(doc)
                current_merge_size += non_ws_count
            else:
                # 结束当前合并组，开始新的
                if current_merge_group:
                    merged_doc = self._create_merged_document(current_merge_group, file_path, language)
                    merged_docs.append(merged_doc)
                
                current_merge_group = [doc]
                current_merge_size = non_ws_count
        
        # 处理最后一个合并组
        if current_merge_group:
            merged_doc = self._create_merged_document(current_merge_group, file_path, language)
            merged_docs.append(merged_doc)
        
        logger.debug(f"🔗 文档合并: {len(documents)} -> {len(merged_docs)} 个文档")
        return merged_docs

    def _can_merge_documents(self, current_group: List[Document], new_doc: Document) -> bool:
        """判断文档是否可以合并"""
        if not current_group:
            return True
            
        # 相同类型的元素可以合并
        last_doc = current_group[-1]
        last_type = last_doc.metadata.get("element_type", "")
        new_type = new_doc.metadata.get("element_type", "")
        
        # 导入语句可以合并
        if last_type == "import" and new_type == "import":
            return True
            
        # 同类型的赋值可以合并
        if last_type == "assignment" and new_type == "assignment":
            return True
            
        # 小函数可以合并
        if (last_type in ["function", "decorated_definition"] and 
            new_type in ["function", "decorated_definition"]):
            last_size = self._count_non_whitespace_chars(last_doc.page_content)
            new_size = self._count_non_whitespace_chars(new_doc.page_content)
            if last_size < self.min_chunk_size and new_size < self.min_chunk_size:
                return True
        
        return False

    def _create_merged_document(self, docs: List[Document], file_path: str, language: str) -> Document:
        """创建合并文档"""
        if len(docs) == 1:
            return docs[0]
            
        # 合并内容
        contents = [doc.page_content for doc in docs]
        merged_content = '\n\n'.join(contents)
        
        # 合并元数据
        element_types = [doc.metadata.get("element_type", "") for doc in docs]
        element_names = [doc.metadata.get("element_name", "") for doc in docs]
        
        # 确定主要类型
        type_counts = {}
        for et in element_types:
            type_counts[et] = type_counts.get(et, 0) + 1
        main_type = max(type_counts, key=type_counts.get) if type_counts else "merged"
        
        # 创建合并的元数据
        merged_metadata = {
            "file_path": file_path,
            "language": language,
            "element_type": main_type,
            "element_name": f"merged_{main_type}",
            "is_merged": True,
            "merged_count": len(docs),
            "merged_elements": json.dumps(element_names),
            "start_line": min(doc.metadata.get("start_line", 0) for doc in docs),
            "end_line": max(doc.metadata.get("end_line", 0) for doc in docs),
            "merged_non_ws_chars": self._count_non_whitespace_chars(merged_content)
        }
        
        return Document(
            page_content=merged_content,
            metadata=merged_metadata
        )

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
