"""
Git 仓库操作工具
负责安全地克隆和管理 Git 仓库
"""

import os
import shutil
import tempfile
import logging
from typing import Optional, Tuple
from contextlib import contextmanager
from urllib.parse import urlparse
import git
from git.exc import GitCommandError, InvalidGitRepositoryError

from ..core.config import settings

logger = logging.getLogger(__name__)

class GitCloneError(Exception):
    """Git 克隆异常"""
    pass

class GitHelper:
    """Git 操作助手类"""
    
    @staticmethod
    def validate_github_url(url: str) -> bool:
        """
        验证是否为有效的 GitHub URL
        
        Args:
            url: Git 仓库 URL
            
        Returns:
            bool: 是否为有效的 GitHub URL
        """
        try:
            url = url.strip()
            
            # 如果没有协议，添加 https://
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            parsed = urlparse(url)
            
            # 检查协议
            if parsed.scheme not in ['http', 'https']:
                return False
            
            # 检查域名
            if parsed.netloc not in ['github.com', 'www.github.com']:
                return False
            
            # 检查路径
            path_parts = [part for part in parsed.path.strip('/').split('/') if part]
            
            # 至少需要 owner/repo 两个部分
            if len(path_parts) < 2:
                return False
            
            # 检查 owner 和 repo 名称是否有效（基本检查）
            owner, repo = path_parts[0], path_parts[1]
            
            # 移除可能的 .git 后缀和 # 片段
            repo_clean = repo.split('#')[0]  # 移除 # 后的部分
            if repo_clean.endswith('.git'):
                repo_clean = repo_clean[:-4]
        
            # 基本的名称验证（不能为空）
            if not owner or not repo_clean:
                return False
        
            return True
            
        except Exception:
            return False
    
    @staticmethod
    def extract_repo_info(url: str) -> Tuple[str, str]:
        """
        从 GitHub URL 提取仓库信息
        
        Args:
            url: GitHub 仓库 URL
            
        Returns:
            Tuple[str, str]: (owner, repo_name)
            
        Raises:
            ValueError: URL 格式无效
        """
        if not GitHelper.validate_github_url(url):
            raise ValueError(f"无效的 GitHub URL: {url}")
        
        try:
            url = url.strip()
            
            # 如果没有协议，添加 https://
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
                
            parsed = urlparse(url)
            path_parts = [part for part in parsed.path.strip('/').split('/') if part]
            
            if len(path_parts) < 2:
                raise ValueError("URL 路径格式无效")
            
            owner = path_parts[0]
            repo_name = path_parts[1]
            
            # 移除 .git 后缀和 # 片段
            repo_name = repo_name.split('#')[0]
            if repo_name.endswith('.git'):
                repo_name = repo_name[:-4]
            
            return owner, repo_name
            
        except Exception as e:
            raise ValueError(f"解析 GitHub URL 失败: {str(e)}")
    
    @staticmethod
    @contextmanager
    def clone_repository(url: str, timeout: Optional[int] = None):
        """
        安全地克隆 Git 仓库的上下文管理器
        自动管理临时目录的创建和清理
        
        Args:
            url: Git 仓库 URL
            timeout: 克隆超时时间（秒）
            
        Yields:
            str: 克隆到的本地目录路径
            
        Raises:
            GitCloneError: 克隆失败
        """
        if not GitHelper.validate_github_url(url):
            raise GitCloneError(f"无效的 GitHub URL: {url}")
        
        # 确保临时目录存在
        os.makedirs(settings.TEMP_DIR, exist_ok=True)
        
        # 创建唯一的临时目录
        temp_dir = None
        try:
            temp_dir = tempfile.mkdtemp(dir=settings.TEMP_DIR, prefix="repo_clone_")
            logger.info(f"开始克隆仓库 {url} 到 {temp_dir}")
            
            # 克隆仓库
            repo = git.Repo.clone_from(
                url=url,
                to_path=temp_dir,
                depth=1,  # 浅克隆，只获取最新提交
                single_branch=True,  # 只克隆默认分支
                timeout=timeout or settings.CLONE_TIMEOUT
            )
            
            logger.info(f"成功克隆仓库到 {temp_dir}")
            yield temp_dir
            
        except GitCommandError as e:
            error_msg = f"Git 命令执行失败: {str(e)}"
            logger.error(error_msg)
            raise GitCloneError(error_msg)
        
        except Exception as e:
            error_msg = f"克隆仓库失败: {str(e)}"
            logger.error(error_msg)
            raise GitCloneError(error_msg)
        
        finally:
            # 清理临时目录
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                    logger.info(f"已清理临时目录: {temp_dir}")
                except Exception as e:
                    logger.warning(f"清理临时目录失败: {str(e)}")
    
    @staticmethod
    def get_repository_info(repo_path: str) -> dict:
        """
        获取仓库的基本信息
        
        Args:
            repo_path: 仓库本地路径
            
        Returns:
            dict: 仓库信息
            
        Raises:
            InvalidGitRepositoryError: 无效的 Git 仓库
        """
        try:
            repo = git.Repo(repo_path)
            
            # 获取远程 URL
            remote_url = None
            if repo.remotes:
                remote_url = repo.remotes.origin.url
            
            # 获取最新提交信息
            latest_commit = repo.head.commit
            
            # 获取分支信息
            current_branch = repo.active_branch.name if repo.active_branch else None
            
            # 统计文件数量
            total_files = 0
            for root, dirs, files in os.walk(repo_path):
                # 跳过 .git 目录
                if '.git' in dirs:
                    dirs.remove('.git')
                total_files += len(files)
            
            return {
                "remote_url": remote_url,
                "current_branch": current_branch,
                "latest_commit": {
                    "sha": latest_commit.hexsha,
                    "message": latest_commit.message.strip(),
                    "author": str(latest_commit.author),
                    "date": latest_commit.committed_datetime.isoformat()
                },
                "total_files": total_files
            }
            
        except InvalidGitRepositoryError:
            raise InvalidGitRepositoryError(f"无效的 Git 仓库: {repo_path}")
        
        except Exception as e:
            logger.error(f"获取仓库信息失败: {str(e)}")
            raise


def clone_and_get_info(url: str) -> Tuple[str, dict]:
    """
    便捷函数：克隆仓库并获取信息
    
    Args:
        url: GitHub 仓库 URL
        
    Returns:
        Tuple[str, dict]: (本地路径, 仓库信息)
    """
    with GitHelper.clone_repository(url) as repo_path:
        repo_info = GitHelper.get_repository_info(repo_path)
        return repo_path, repo_info