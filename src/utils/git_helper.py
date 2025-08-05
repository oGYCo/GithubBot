"""
Git 仓库操作工具
负责安全地克隆和管理 Git 仓库
"""

import os
import shutil
import logging
import hashlib
from typing import Optional, Tuple
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
    def generate_repository_identifier(url: str) -> str:
        """
        基于仓库URL生成唯一且持久的标识符
        用于ChromaDB Collection命名，确保同一仓库总是使用相同的Collection
        
        Args:
            url: GitHub 仓库 URL
            
        Returns:
            str: 仓库的唯一标识符
        """
        try:
            # 标准化URL格式
            url = url.strip().lower()
            
            # 如果没有协议，添加 https://
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            parsed = urlparse(url)
            path_parts = [part for part in parsed.path.strip('/').split('/') if part]
            
            if len(path_parts) < 2:
                raise ValueError("URL 路径格式无效")
            
            owner = path_parts[0]
            repo_name = path_parts[1]
            
            # 移除 .git 后缀
            if repo_name.endswith('.git'):
                repo_name = repo_name[:-4]
            
            # 生成标准化的仓库标识符：github_owner_repo
            repo_identifier = f"github_{owner}_{repo_name}"
            
            # 使用SHA256哈希确保标识符不会过长且唯一
            # 但保留可读性，前缀使用原始信息，后缀使用哈希
            hash_suffix = hashlib.sha256(f"{owner}/{repo_name}".encode()).hexdigest()[:8]
            final_identifier = f"{repo_identifier}_{hash_suffix}"
            
            return final_identifier
            
        except Exception as e:
            raise ValueError(f"生成仓库标识符失败: {str(e)}")
    
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
    def clone_repository(url: str, timeout: Optional[int] = None, force_update: bool = False) -> str:
        """
        克隆 Git 仓库到项目的固定目录
        如果仓库已存在，可选择是否强制更新
        Args:
            url: Git 仓库 URL
            timeout: 克隆超时时间（秒）
            force_update: 是否强制更新已存在的仓库
        Returns:
            str: 克隆到的本地目录路径
        Raises:
            GitCloneError: 克隆失败
        """
        if not GitHelper.validate_github_url(url):
            raise GitCloneError(f"无效的 GitHub URL: {url}")

        # 从 URL 提取仓库信息，用于创建目录名
        try:
            owner, repo_name = GitHelper.extract_repo_info(url)
            repo_dir_name = f"{owner}_{repo_name}"
        except ValueError as e:
            raise GitCloneError(f"解析仓库链接信息失败: {str(e)}")

        # 确保仓库存储目录存在
        repos_base_dir = settings.GIT_CLONE_DIR
        os.makedirs(repos_base_dir, exist_ok=True)

        # 目标目录路径
        target_dir = os.path.join(repos_base_dir, repo_dir_name)

        try:
            # 如果目录已存在
            if os.path.exists(target_dir):
                if force_update:
                    logger.info(f"强制更新模式，删除已存在的仓库目录: {target_dir}")
                    shutil.rmtree(target_dir)
                else:
                    # 验证是否为有效的 Git 仓库
                    try:
                        existing_repo = git.Repo(target_dir)
                        logger.info(f"仓库已存在，使用现有目录: {target_dir}")
                        return target_dir
                    except InvalidGitRepositoryError:
                        logger.warning(f"目录存在但不是有效的 Git 仓库，重新克隆: {target_dir}")
                        shutil.rmtree(target_dir)

            # 克隆仓库
            logger.info(f"📥 [开始克隆] 仓库: {url}")
            logger.info(f"📁 [目标目录] 路径: {target_dir}")
            logger.info(f"⚙️ [克隆配置] 浅克隆(depth=1), 单分支, 超时: {timeout or getattr(settings, 'CLONE_TIMEOUT', 300)}s")
            
            git_config = [
                'http.version=HTTP/1.1',
                'http.postBuffer=524288000', 
                'http.lowSpeedLimit=1000',
                'http.lowSpeedTime=300'
            ]
            
            # 注意：GitPython 的 timeout 参数可能不被所有版本支持
            # 使用基本的克隆参数，避免 timeout 导致的兼容性问题
            repo = git.Repo.clone_from(
                url=url,
                to_path=target_dir,
                depth=1,# 浅克隆，只获取最新提交
                single_branch=True,# 只克隆默认分支
                config=git_config
            )

            logger.info(f"✅ [克隆成功] 仓库已克隆到: {target_dir}")
            logger.info(f"📊 [仓库信息] 当前分支: {repo.active_branch.name}, 最新提交: {repo.head.commit.hexsha[:8]}")
            return target_dir

        except GitCommandError as e:
            error_msg = f"Git 命令执行失败: {str(e)}"
            logger.error(error_msg)
            # 如果克隆失败，清理可能创建的目录
            if os.path.exists(target_dir):
                try:
                    shutil.rmtree(target_dir)
                except Exception:
                    pass
            raise GitCloneError(error_msg)

        except Exception as e:
            error_msg = f"克隆仓库失败: {str(e)}"
            logger.error(error_msg)
            # 如果克隆失败，清理可能创建的目录
            if os.path.exists(target_dir):
                try:
                    shutil.rmtree(target_dir)
                except Exception:
                    pass
            raise GitCloneError(error_msg)

    @staticmethod
    def update_repository(repo_path: str, timeout: Optional[int] = None) -> bool:
        """
        更新已存在的仓库

        Args:
            repo_path: 仓库本地路径
            timeout: 更新超时时间（秒）

        Returns:
            bool: 是否有更新

        Raises:
            GitCloneError: 更新失败
        """
        try:
            repo = git.Repo(repo_path)

            # 获取更新前的提交 SHA
            old_commit = repo.head.commit.hexsha

            # 拉取最新更改
            logger.info(f"开始更新仓库: {repo_path}")
            origin = repo.remotes.origin
            origin.pull(timeout=timeout or getattr(settings, 'CLONE_TIMEOUT', 300))

            # 获取更新后的提交 SHA
            new_commit = repo.head.commit.hexsha

            if old_commit != new_commit:
                logger.info(f"仓库已更新: {old_commit[:8]} -> {new_commit[:8]}")
                return True
            else:
                logger.info("仓库已是最新版本")
                return False

        except GitCommandError as e:
            error_msg = f"Git 更新命令执行失败: {str(e)}"
            logger.error(error_msg)
            raise GitCloneError(error_msg)

        except Exception as e:
            error_msg = f"更新仓库失败: {str(e)}"
            logger.error(error_msg)
            raise GitCloneError(error_msg)

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


def clone_and_get_info(url: str, force_update: bool = False) -> Tuple[str, dict]:
    """
    便捷函数：克隆仓库并获取信息

    Args:
        url: GitHub 仓库 URL
        force_update: 是否强制更新已存在的仓库

    Returns:
        Tuple[str, dict]: (本地路径, 仓库信息)
    """
    repo_path = GitHelper.clone_repository(url, force_update=force_update)
    repo_info = GitHelper.get_repository_info(repo_path)
    return repo_path, repo_info


def get_repository_list() -> list:
    """
    获取所有已克隆的仓库列表

    Returns:
        list: 仓库目录列表
    """
    repos_base_dir = settings.GIT_CLONE_DIR
    if not os.path.exists(repos_base_dir):
        return []

    repositories = []
    for item in os.listdir(repos_base_dir):
        repo_path = os.path.join(repos_base_dir, item)
        if os.path.isdir(repo_path):
            try:
                # 验证是否为有效的 Git 仓库
                git.Repo(repo_path)
                repositories.append({
                    "name": item,
                    "path": repo_path
                })
            except InvalidGitRepositoryError:
                logger.warning(f"发现无效的 Git 仓库目录: {repo_path}")
                continue

    return repositories


def cleanup_repository(url: str) -> bool:
    """
    清理指定仓库的本地克隆

    Args:
        url: GitHub 仓库 URL

    Returns:
        bool: 是否成功删除
    """
    try:
        owner, repo_name = GitHelper.extract_repo_info(url)
        repo_dir_name = f"{owner}_{repo_name}"
        target_dir = os.path.join(settings.GIT_CLONE_DIR, repo_dir_name)

        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)
            logger.info(f"已删除仓库目录: {target_dir}")
            return True
        else:
            logger.warning(f"仓库目录不存在: {target_dir}")
            return False

    except Exception as e:
        logger.error(f"删除仓库目录失败: {str(e)}")
        return False