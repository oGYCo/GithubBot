"""
文件解析器
负责智能文件过滤、内容解析和分块处理
"""

import os
import json
import logging
import fnmatch
from typing import List, Dict, Any, Optional, Iterator, Tuple
import chardet
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    Language,
)
from langchain_core.documents import Document

from ..core.config import settings

logger = logging.getLogger(__name__)


class FileType:
    """文件类型常量"""
    CODE = "code"
    DOCUMENT = "document"
    CONFIG = "config"
    DATA = "data"
    BINARY = "binary"
    UNKNOWN = "unknown"


class FileParser:
    """文件解析器"""
    
    # 文件类型映射
    FILE_TYPE_MAPPING = {
        # 代码文件
        '.py': (FileType.CODE, Language.PYTHON),
        '.js': (FileType.CODE, Language.JS),
        '.jsx': (FileType.CODE, Language.JS),
        '.ts': (FileType.CODE, Language.TS),
        '.tsx': (FileType.CODE, Language.TS),
        '.java': (FileType.CODE, Language.JAVA),
        '.cpp': (FileType.CODE, Language.CPP),
        '.cxx': (FileType.CODE, Language.CPP),
        '.cc': (FileType.CODE, Language.CPP),
        '.c': (FileType.CODE, Language.C),
        '.h': (FileType.CODE, Language.C),
        '.hpp': (FileType.CODE, Language.CPP),
        '.cs': (FileType.CODE, Language.CSHARP),
        '.php': (FileType.CODE, Language.PHP),
        '.rb': (FileType.CODE, Language.RUBY),
        '.go': (FileType.CODE, Language.GO),
        '.rs': (FileType.CODE, Language.RUST),
        '.swift': (FileType.CODE, Language.SWIFT),
        '.kt': (FileType.CODE, Language.KOTLIN),
        '.scala': (FileType.CODE, Language.SCALA),
        '.clj': (FileType.CODE, None),
        '.sh': (FileType.CODE, None),
        '.sql': (FileType.CODE, None),
        '.html': (FileType.CODE, Language.HTML),
        '.css': (FileType.CODE, None),
        '.vue': (FileType.CODE, Language.JS),
        
        # 文档文件
        '.md': (FileType.DOCUMENT, Language.MARKDOWN),
        '.txt': (FileType.DOCUMENT, None),
        '.rst': (FileType.DOCUMENT, Language.RST),
        '.tex': (FileType.DOCUMENT, Language.LATEX),
        '.adoc': (FileType.DOCUMENT, None),
        
        # 配置文件
        '.json': (FileType.CONFIG, None),
        '.yaml': (FileType.CONFIG, None),
        '.yml': (FileType.CONFIG, None),
        '.toml': (FileType.CONFIG, None),
        '.ini': (FileType.CONFIG, None),
        '.cfg': (FileType.CONFIG, None),
        '.conf': (FileType.CONFIG, None),
        '.env': (FileType.CONFIG, None),
        '.xml': (FileType.CONFIG, None),
        
        # 特殊文件
        'dockerfile': (FileType.CONFIG, None),
        'makefile': (FileType.CONFIG, None),
        'readme': (FileType.DOCUMENT, None),
        'license': (FileType.DOCUMENT, None),
        'changelog': (FileType.DOCUMENT, None),
        '.gitignore': (FileType.CONFIG, None),
        '.gitattributes': (FileType.CONFIG, None),
    }
    
    # 二进制文件扩展名
    BINARY_EXTENSIONS = {
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.ico',
        '.mp3', '.mp4', '.avi', '.mov', '.wav', '.zip', '.tar', '.gz',
        '.exe', '.dll', '.so', '.dylib', '.jar', '.class', '.pyc',
        '.o', '.obj', '.lib', '.a', '.bin', '.dat'
    }
    
    def __init__(self):
        self.gitignore_patterns = []
        self.excluded_dirs = set(settings.EXCLUDED_DIRECTORIES)
        self.allowed_extensions = set(settings.ALLOWED_FILE_EXTENSIONS)
    
    def load_gitignore(self, repo_path: str) -> None:
        """
        加载并解析 .gitignore 文件
        
        Args:
            repo_path: 仓库根目录路径
        """
        gitignore_path = os.path.join(repo_path, '.gitignore')
        self.gitignore_patterns = []
        
        if os.path.exists(gitignore_path):
            try:
                with open(gitignore_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        # 跳过空行和注释
                        if line and not line.startswith('#'):
                            self.gitignore_patterns.append(line)
                logger.info(f"加载了 {len(self.gitignore_patterns)} 条 .gitignore 规则")
            except Exception as e:
                logger.warning(f"读取 .gitignore 文件失败: {str(e)}")
    
    def is_ignored_by_gitignore(self, file_path: str, repo_path: str) -> bool:
        """
        检查文件是否被 .gitignore 忽略
        
        Args:
            file_path: 文件绝对路径
            repo_path: 仓库根目录路径
            
        Returns:
            bool: 是否被忽略
        """
        if not self.gitignore_patterns:
            return False
        
        # 获取相对路径
        try:
            rel_path = os.path.relpath(file_path, repo_path)
            # 使用 Unix 风格的路径分隔符
            rel_path = rel_path.replace(os.path.sep, '/')
        except ValueError:
            return False
        
        for pattern in self.gitignore_patterns:
            if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(os.path.basename(rel_path), pattern):
                return True
        
        return False
    
    def should_skip_directory(self, dir_name: str) -> bool:
        """
        检查目录是否应该跳过
        
        Args:
            dir_name: 目录名
            
        Returns:
            bool: 是否应该跳过
        """
        return dir_name in self.excluded_dirs or dir_name.startswith('.')
    
    def should_process_file(self, file_path: str, repo_path: str) -> bool:
        """
        检查文件是否应该处理
        
        Args:
            file_path: 文件路径
            repo_path: 仓库根目录路径
            
        Returns:
            bool: 是否应该处理
        """
        # 检查 .gitignore
        if self.is_ignored_by_gitignore(file_path, repo_path):
            return False
        
        file_name = os.path.basename(file_path)
        file_ext = os.path.splitext(file_name)[1].lower()
        
        # 检查是否为二进制文件
        if file_ext in self.BINARY_EXTENSIONS:
            return False
        
        # 检查文件扩展名白名单
        if file_ext:
            return file_ext in self.allowed_extensions
        
        # 检查特殊文件名（无扩展名）
        file_name_lower = file_name.lower()
        return any(
            file_name_lower == name.lower().lstrip('.')
            for name in self.allowed_extensions
            if not name.startswith('.')
        )
    
    def get_file_type_and_language(self, file_path: str) -> Tuple[str, Optional[Language]]:
        """
        获取文件类型和编程语言
        
        Args:
            file_path: 文件路径
            
        Returns:
            Tuple[str, Optional[Language]]: (文件类型, 编程语言)
        """
        file_name = os.path.basename(file_path).lower()
        file_ext = os.path.splitext(file_name)[1].lower()
        
        # 检查扩展名映射
        if file_ext in self.FILE_TYPE_MAPPING:
            return self.FILE_TYPE_MAPPING[file_ext]
        
        # 检查特殊文件名
        for special_name, (file_type, language) in self.FILE_TYPE_MAPPING.items():
            if not special_name.startswith('.') and file_name.startswith(special_name):
                return file_type, language
        
        return FileType.UNKNOWN, None
    
    def detect_encoding(self, file_path: str) -> str:
        """
        检测文件编码
        
        Args:
            file_path: 文件路径
            
        Returns:
            str: 编码名称
        """
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read(10240)  # 读取前 10KB
                result = chardet.detect(raw_data)
                return result.get('encoding', 'utf-8') or 'utf-8'
        except Exception:
            return 'utf-8'
    
    def read_file_content(self, file_path: str) -> Optional[str]:
        """
        安全地读取文件内容
        
        Args:
            file_path: 文件路径
            
        Returns:
            Optional[str]: 文件内容，失败时返回 None
        """
        try:
            encoding = self.detect_encoding(file_path)
            
            # 尝试多种编码方式读取文件
            encodings_to_try = [encoding, 'utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
            content = None
            
            for enc in encodings_to_try:
                try:
                    with open(file_path, 'r', encoding=enc, errors='strict') as f:
                        content = f.read()
                    break
                except (UnicodeDecodeError, UnicodeError):
                    continue
            
            if content is None:
                # 如果所有编码都失败，使用二进制模式读取并尝试解码
                with open(file_path, 'rb') as f:
                    raw_content = f.read()
                try:
                    content = raw_content.decode('utf-8', errors='replace')
                except Exception:
                    content = raw_content.decode('latin-1', errors='replace')
            
            # 检查文件大小（避免处理过大的文件）
            if len(content) > 1024 * 1024:  # 1MB
                logger.warning(f"文件过大，跳过: {file_path}")
                return None
            
            # 清理和规范化文本内容
            content = self._clean_text_content(content)
            
            return content
            
        except Exception as e:
            logger.error(f"读取文件失败 {file_path}: {str(e)}")
            return None
    
    def _clean_text_content(self, content: str) -> str:
        """
        清理和规范化文本内容
        
        Args:
            content: 原始文本内容
            
        Returns:
            str: 清理后的文本内容
        """
        import re
        import unicodedata
        
        # 移除或替换控制字符（保留换行符和制表符）
        content = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', content)
        
        # 规范化Unicode字符
        content = unicodedata.normalize('NFKC', content)
        
        # 确保内容是有效的UTF-8字符串
        try:
            content = content.encode('utf-8', errors='ignore').decode('utf-8')
        except Exception:
            # 如果编码失败，移除非ASCII字符
            content = re.sub(r'[^\x00-\x7F]+', ' ', content)
        
        # 规范化换行符
        content = content.replace('\r\n', '\n').replace('\r', '\n')
        
        # 移除多余的空白字符
        content = re.sub(r'\n{3,}', '\n\n', content)  # 最多保留两个连续换行
        content = re.sub(r'[ \t]+\n', '\n', content)  # 移除行尾空白
        
        return content.strip()
    


    def create_text_splitter(self, language: Optional[Language] = None) -> RecursiveCharacterTextSplitter:
        """
        创建文本分割器

        Args:
            language: 编程语言

        Returns:
            RecursiveCharacterTextSplitter: 文本分割器
        """
        chunk_size = settings.CHUNK_SIZE
        chunk_overlap = settings.CHUNK_OVERLAP

        # 扩展支持的语言列表
        supported_languages = [
            Language.PYTHON, Language.JS, Language.TS, Language.JAVA,
            Language.CPP, Language.C, Language.GO, Language.RUST,
            Language.HTML, Language.MARKDOWN, Language.LATEX, Language.RST,
            Language.PHP, Language.RUBY, Language.CSHARP, Language.SWIFT,
            Language.KOTLIN, Language.SCALA
        ]

        # 如果语言受支持，则使用语言特定的分割器
        if language and language in supported_languages:
            try:
                return RecursiveCharacterTextSplitter.from_language(
                    language=language,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap
                )
            except ValueError:
                # 如果 langchain 版本不支持某个语言，则回退
                pass

        # 否则，使用通用的分割器
        return RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", " ", ""]
        )
    
    def split_file_content(self, content: str, file_path: str, language: Optional[Language] = None) -> List[Document]:
        """
        分割文件内容为文档块
        
        Args:
            content: 文件内容
            file_path: 文件路径
            language: 编程语言
            
        Returns:
            List[Document]: 文档块列表
        """
        # 获取相对路径
        rel_path = file_path
        
        # 为内容添加文件路径前缀
        content_with_path = f"文件路径: {rel_path}\n\n{content}"
        
        # 创建分割器
        splitter = self.create_text_splitter(language)
        
        # 分割文档
        documents = splitter.create_documents(
            texts=[content_with_path],
            metadatas=[{
                "file_path": rel_path,
                "file_type": self.get_file_type_and_language(file_path)[0],
                "language": language.value if language and hasattr(language, 'value') else language,
                "source": file_path
            }]
        )
        
        # 为每个文档块添加行号信息
        for i, doc in enumerate(documents):
            # 计算起始行号（简单估算）
            start_line = i * (settings.CHUNK_SIZE // 50) + 1  # 假设平均每行 50 字符
            doc.metadata["start_line"] = start_line
            doc.metadata["chunk_index"] = i
        
        return documents
    
    def parse_special_files(self, file_path: str, content: str) -> Dict[str, Any]:
        """
        解析特殊文件（如 package.json, requirements.txt 等）
        
        Args:
            file_path: 文件路径
            content: 文件内容
            
        Returns:
            Dict[str, Any]: 解析结果
        """
        file_name = os.path.basename(file_path).lower()
        
        try:
            if file_name == 'package.json':
                data = json.loads(content)
                return {
                    "type": "package_json",
                    "name": data.get("name"),
                    "version": data.get("version"),
                    "description": data.get("description"),
                    "dependencies": data.get("dependencies", {}),
                    "devDependencies": data.get("devDependencies", {}),
                    "scripts": data.get("scripts", {})
                }
            
            elif file_name in ['requirements.txt', 'requirements-dev.txt']:
                dependencies = []
                for line in content.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('#'):
                        dependencies.append(line)
                return {
                    "type": "requirements",
                    "dependencies": dependencies
                }
            
            elif file_name == 'pyproject.toml':
                # 简单解析 TOML（可以使用 toml 库进行更好的解析）
                return {
                    "type": "pyproject_toml",
                    "content_summary": "Python 项目配置文件"
                }
            
            elif file_name.startswith('dockerfile'):
                instructions = []
                for line in content.split('\n'):
                    line = line.strip().upper()
                    if line and not line.startswith('#'):
                        if line.startswith(('FROM', 'RUN', 'COPY', 'ADD', 'WORKDIR', 'CMD', 'ENTRYPOINT')):
                            instructions.append(line)
                return {
                    "type": "dockerfile",
                    "instructions": instructions
                }
                
        except Exception as e:
            logger.warning(f"解析特殊文件失败 {file_path}: {str(e)}")
        
        return {"type": "unknown"}
    
    def scan_repository(self, repo_path: str) -> Iterator[Tuple[str, Dict[str, Any]]]:
        """
        扫描仓库中的所有文件
        
        Args:
            repo_path: 仓库路径
            
        Yields:
            Tuple[str, Dict[str, Any]]: (文件路径, 文件信息)
        """
        logger.info(f"开始扫描仓库文件: {repo_path}")
        
        # 加载 .gitignore 规则
        self.load_gitignore(repo_path)
        logger.info("已加载 .gitignore 规则")
        
        total_files_found = 0
        processed_files = 0
        skipped_files = 0
        
        for root, dirs, files in os.walk(repo_path):
            # 过滤目录
            original_dirs = len(dirs)
            dirs[:] = [d for d in dirs if not self.should_skip_directory(d)]
            filtered_dirs = len(dirs)
            
            if original_dirs > filtered_dirs:
                logger.debug(f"跳过 {original_dirs - filtered_dirs} 个目录在: {root}")
            
            total_files_found += len(files)
            
            for file_name in files:
                file_path = os.path.join(root, file_name)
                
                # 检查是否应该处理该文件
                if not self.should_process_file(file_path, repo_path):
                    skipped_files += 1
                    logger.debug(f"跳过文件: {os.path.relpath(file_path, repo_path)}")
                    continue
                
                # 获取文件相对路径
                rel_path = os.path.relpath(file_path, repo_path)
                
                # 获取文件信息
                try:
                    stat = os.stat(file_path)
                    file_type, language = self.get_file_type_and_language(file_path)
                    
                    file_info = {
                        "file_path": rel_path,
                        "full_path": file_path,
                        "file_type": file_type,
                        "language": language.value if language and hasattr(language, 'value') else language,
                        "file_size": stat.st_size,
                        "file_extension": os.path.splitext(file_name)[1].lower()
                    }
                    
                    processed_files += 1
                    if processed_files % 50 == 0:  # 每处理50个文件记录一次进度
                        logger.info(f"文件扫描进度: 已处理 {processed_files} 个文件")
                    
                    logger.debug(f"扫描到文件: {rel_path} (类型: {file_type}, 大小: {stat.st_size} bytes)")
                    yield file_path, file_info
                    
                except Exception as e:
                    logger.error(f"获取文件信息失败 {file_path}: {str(e)}")
                    continue
        
        logger.info(f"文件扫描完成 - 总计发现: {total_files_found} 个文件, 处理: {processed_files} 个, 跳过: {skipped_files} 个")