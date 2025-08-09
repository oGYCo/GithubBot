#!/usr/bin/env python3
"""
使用真实的复杂 Python 类测试语法感知分块功能
"""

import os
import sys
import re
import textwrap
from typing import List

# 添加项目根目录到Python路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# 提供Document的兜底实现
try:
    from langchain_core.documents import Document
except ImportError:
    class Document:
        def __init__(self, page_content: str, metadata: dict = None):
            self.page_content = page_content
            self.metadata = metadata or {}

from src.utils.ast_parser import AstParser


def get_real_class_code() -> str:
    """返回真实的复杂Python类代码"""
    return '''@register("RepoInsight", "oGYCo", "GitHub仓库智能问答插件,支持仓库分析和智能问答", "1.0.0")
class Main(Star):
    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)

        # 初始化配置
        self.plugin_config = config or {}
        self.astrbot_config = config

        # 输出调试信息
        logger.info("=== RepoInsight插件开始初始化 ===")
        logger.info(f"配置信息: {self.plugin_config}")

        # 获取配置参数
        self.api_base_url = self.plugin_config.get("api_base_url", "http://api:8000") if self.plugin_config else "http://api:8000"
        self.timeout = self.plugin_config.get("timeout", 30) if self.plugin_config else 30
        self.query_timeout = self.plugin_config.get("query_timeout", 600) if self.plugin_config else 600  # 查询超时设为10分钟
        self.poll_interval = self.plugin_config.get("poll_interval", 5) if self.plugin_config else 5

        # Embedding配置 - 使用平级配置格式
        self.embedding_config = {
            'provider': self.plugin_config.get("embedding_provider", "qwen") if self.plugin_config else "qwen",
            'model_name': self.plugin_config.get("embedding_model", "text-embedding-v4") if self.plugin_config else "text-embedding-v4",
            'api_key': self.plugin_config.get("embedding_api_key", "") if self.plugin_config else ""
        }

        # LLM配置 - 使用平级配置格式
        self.llm_config = {
            'provider': self.plugin_config.get("llm_provider", "qwen") if self.plugin_config else "qwen",
            'model_name': self.plugin_config.get("llm_model", "qwen-plus") if self.plugin_config else "qwen-plus",
            'api_key': self.plugin_config.get("llm_api_key", "") if self.plugin_config else "",
            'temperature': self.plugin_config.get("llm_temperature", 0.7) if self.plugin_config else 0.7,
            'max_tokens': self.plugin_config.get("llm_max_tokens", 9000) if self.plugin_config else 9000
        }

        # 初始化状态管理器
        self.state_manager = StateManager()

        # 启动时恢复未完成的任务
        asyncio.create_task(self._restore_pending_tasks())

        logger.info("RepoInsight插件已初始化")

    async def _restore_pending_tasks(self):
        """恢复插件重启前未完成的任务"""
        try:
            pending_tasks = await self.state_manager.get_all_pending_tasks()
            for task in pending_tasks:
                logger.info(f"恢复任务: {task['session_id']} - {task['repo_url']}")
                # 这里可以添加恢复逻辑,比如重新检查任务状态
        except Exception as e:
            logger.error(f"恢复任务失败: {e}")

    @filter.command("repo_qa")
    async def repo_qa_session(self, event: AstrMessageEvent):
        """启动仓库问答会话"""
        try:
            logger.info("=== 收到 /repo_qa 命令,启动仓库问答会话 ===")
            logger.info(f"用户: {event.unified_msg_origin}")
            logger.info(f"消息内容: {event.message_str}")

            # 发送初始消息
            await event.send(event.plain_result("请发送您要分析的 GitHub 仓库 URL\\n💡 分析完成后,您可以随时发送新的仓库URL或 '/repo_qa' 命令来切换仓库"))

            # 使用正确的session_waiter模式
            @session_waiter(timeout=7200)
            async def session_handler(controller: SessionController, event: AstrMessageEvent):
                """处理会话的函数 - 使用状态管理的事件驱动模式"""
                logger.info(f"进入session_handler,当前状态: {self.state_manager.user_states}")

                # 获取或初始化当前用户的状态
                user_id = event.unified_msg_origin
                user_state = await self.state_manager.get_user_state(user_id)

                # 重要:禁止AstrBot默认的LLM调用,避免冲突
                event.should_call_llm(False)

                user_input = event.message_str.strip()

                # 检查是否为空消息
                if not user_input:
                    if user_state.get('current_repo_url'):
                        await event.send(event.plain_result("请输入您的问题,或发送 '退出' 结束会话,或发送 '/repo_qa' 切换仓库"))
                    else:
                        await event.send(event.plain_result("请发送您要分析的 GitHub 仓库 URL"))
                    return

                # 检查是否为退出命令
                if user_input.lower() in ['退出', 'exit', 'quit', '取消']:
                    await event.send(event.plain_result("👋 感谢使用 RepoInsight!"))
                    if user_state.get('analysis_session_id'):
                        await self.state_manager.remove_task(user_state['analysis_session_id'])
                    await self.state_manager.clear_user_state(user_id)
                    controller.stop()
                    return

                # 检查是否为切换仓库命令
                if user_input.lower().startswith('/repo_qa') or user_input.lower().startswith('repo_qa'):
                    await event.send(event.plain_result("🔄 请发送您要分析的新 GitHub 仓库 URL:"))
                    # 重置状态
                    await self.state_manager.clear_user_state(user_id)
                    return

                # 如果还没有分析仓库,或者用户输入了新的GitHub URL
                if not user_state.get('current_repo_url') or self._is_valid_github_url(user_input):
                    # 验证GitHub URL
                    if not self._is_valid_github_url(user_input):
                        await event.send(event.plain_result(
                            "❌ 请输入有效的 GitHub 仓库 URL\\n\\n"
                            "示例: https://github.com/user/repo\\n\\n"
                            "或发送 '退出' 结束会话"
                        ))
                        return

                    repo_url = user_input
                    logger.info(f"开始处理仓库URL: {repo_url}")

                    # 如果是切换到新仓库
                    current_repo_url = user_state.get('current_repo_url')
                    if current_repo_url and repo_url != current_repo_url:
                        await event.send(event.plain_result(f"🔄 检测到新仓库URL,正在切换分析...\\n\\n🔗 新仓库: {repo_url}"))
                    else:
                        await event.send(event.plain_result(f"🔍 开始分析仓库,⏳请稍候..."))

                    try:
                        # 启动仓库分析
                        logger.info(f"启动仓库分析: {repo_url}")
                        new_analysis_session_id = await self._start_repository_analysis(repo_url)
                        logger.info(f"分析会话ID: {new_analysis_session_id}")

                        if not new_analysis_session_id:
                            logger.error("启动仓库分析失败")
                            await event.send(event.plain_result("❌ 启动仓库分析失败,请稍后重试或尝试其他仓库"))
                            return

                        # 保存任务状态
                        await self.state_manager.add_task(new_analysis_session_id, repo_url, user_id)

                        # 轮询分析状态
                        analysis_result = await self._poll_analysis_status(new_analysis_session_id, event)
                        if not analysis_result:
                            await self.state_manager.remove_task(new_analysis_session_id)
                            await event.send(event.plain_result("❌ 仓库分析失败,请稍后重试或尝试其他仓库"))
                            return

                        # 分析成功,更新用户状态
                        await self.state_manager.set_user_state(user_id, {
                            'current_repo_url': repo_url,
                            'analysis_session_id': new_analysis_session_id,
                            'processing_questions': set()
                        })

                        await event.send(event.plain_result(
                            f"✅ 仓库分析完成!现在您可以开始提问了!\\n"
                            f"💡 **提示:**\\n"
                            f"• 发送问题进行仓库问答\\n"
                            f"• 发送新的仓库URL可以快速切换\\n"
                            f"• 发送 '/repo_qa' 切换到新仓库\\n"
                            f"• 发送 '退出' 结束会话"
                        ))
                        return

                    except Exception as e:
                        logger.error(f"仓库处理过程出错: {e}")
                        await event.send(event.plain_result(f"❌ 处理过程出错: {str(e)}"))
                        return

                # 如果已经有分析好的仓库,处理用户问题
                elif user_state.get('current_repo_url') and user_state.get('analysis_session_id'):
                    user_question = user_input
                    current_repo_url = user_state['current_repo_url']
                    analysis_session_id = user_state['analysis_session_id']
                    processing_questions = user_state.get('processing_questions', set())

                    # 检查是否正在处理相同问题(防止并发处理)
                    question_hash = hash(user_question)

                    if question_hash in processing_questions:
                        logger.info(f"问题正在处理中: {user_question}")
                        await event.send(event.plain_result("此问题正在处理中,请稍候..."))
                        return

                    # 标记问题为正在处理
                    processing_questions.add(question_hash)
                    await self.state_manager.set_user_state(user_id, {
                        **user_state,
                        'processing_questions': processing_questions
                    })

                    logger.info(f"开始处理问题: {user_question[:50]}... - 仓库: {current_repo_url}")

                    try:
                        # 提交查询请求,使用仓库URL作为session_id
                        query_session_id = await self._submit_query(analysis_session_id, user_question)
                        if not query_session_id:
                            await event.send(event.plain_result("❌ 提交问题失败,请重试"))
                            return

                        # 轮询查询结果
                        answer = await self._poll_query_result(query_session_id, event)
                        if answer:
                            # 智能分段发送长回答
                            await self._send_long_message(event, f"💡 **回答:**\\n\\n{answer}")
                        else:
                            await event.send(event.plain_result("❌ 获取答案失败,请重试"))

                        return

                    except Exception as e:
                        logger.error(f"处理问题时出错: {e}")
                        await event.send(event.plain_result(f"❌ 处理问题时出错: {str(e)}"))
                        return
                    finally:
                        # 无论成功还是失败,都要移除正在处理标记
                        processing_questions.discard(question_hash)
                        await self.state_manager.set_user_state(user_id, {
                            **user_state,
                            'processing_questions': processing_questions
                        })

                else:
                    # 应该不会到达这里,但保险起见
                    await event.send(event.plain_result("请发送您要分析的 GitHub 仓库 URL"))
                    return

            # 启动会话处理器
            try:
                await session_handler(event)
            except TimeoutError:
                await event.send(event.plain_result("⏰ 会话超时,请重新发送 /repo_qa 命令开始新的会话"))
            except Exception as e:
                logger.error(f"会话处理器异常: {e}")
                await event.send(event.plain_result(f"❌ 会话异常: {str(e)}"))
            finally:
                # 清理会话状态
                event.stop_event()

        except Exception as e:
            logger.error(f"启动仓库问答会话失败: {e}")
            await event.send(event.plain_result(f"❌ 启动会话失败: {str(e)}"))

    def _is_valid_github_url(self, url: str) -> bool:
        """验证GitHub URL格式"""
        github_pattern = r'^https://github\.com/[\\w\\.-]+/[\\w\\.-]+/?$'
        return bool(re.match(github_pattern, url))

    async def _start_repository_analysis(self, repo_url: str):
        """启动仓库分析"""
        # 省略具体实现以节省空间
        pass

    async def _poll_analysis_status(self, session_id: str, event):
        """轮询分析状态"""
        # 省略具体实现以节省空间
        pass

    async def _submit_query(self, session_id: str, question: str):
        """提交查询请求"""
        # 省略具体实现以节省空间  
        pass

    async def _poll_query_result(self, query_session_id: str, event):
        """轮询查询结果"""
        # 省略具体实现以节省空间
        pass

    async def _send_long_message(self, event, message: str, max_length: int = 1800):
        """智能分段发送长消息,确保完整性和内容不丢失"""
        # 省略具体实现以节省空间
        pass

    async def _generate_answer_from_context(self, context_list: list, question: str) -> str:
        """基于检索到的上下文生成答案"""
        # 省略具体实现以节省空间
        pass

    @filter.command("repo_test")
    async def test_plugin(self, event):
        """测试插件是否正常工作"""
        pass

    @filter.command("repo_status")
    async def check_repo_status(self, event):
        """查看当前用户的仓库分析状态"""
        pass

    @filter.command("repo_config")
    async def show_config(self, event):
        """显示当前配置"""
        pass

    async def terminate(self):
        """插件终止时的清理工作"""
        pass'''


def test_syntax_aware_chunking():
    """测试语法感知分块功能"""
    print("=" * 60)
    print("🧪 测试语法感知分块功能")
    print("=" * 60)
    
    # 获取真实的复杂Python类代码
    code = get_real_class_code()
    
    print(f"📄 原始代码总长度: {len(code)} 字符")
    non_ws_count = len(re.sub(r'\s', '', code))
    print(f"📄 非空白字符数: {non_ws_count}")
    print(f"📄 代码行数: {len(code.splitlines())}")
    print()
    
    # 检查是否应该分块
    print(f"🔍 分块触发检查:")
    print(f"   ├─ 非空白字符数: {non_ws_count}")
    print(f"   ├─ max_chunk_size: 2000")
    print(f"   └─ 需要分块: {'是' if non_ws_count > 2000 else '否'}")
    print()
    
    # 创建Document对象（模拟一个大的类元素）
    doc = Document(
        page_content=code,
        metadata={
            "file_path": "/tmp/Main.py",
            "language": "python", 
            "element_type": "class",
            "element_name": "Main",
            "start_line": 1,
            "end_line": len(code.splitlines()),
        }
    )
    
    # 使用相对较小的chunk_size来触发分块
    parser = AstParser(
        chunk_size=800,      # 目标块大小（非空白字符）
        chunk_overlap=150,   # 重叠大小
        min_chunk_size=200,  # 最小块大小
        max_chunk_size=1500  # 最大块大小 - 进一步降低来触发分块
    )
    
    print(f"⚙️  分块配置:")
    print(f"   - chunk_size: {parser.chunk_size}")
    print(f"   - chunk_overlap: {parser.chunk_overlap}")
    print(f"   - min_chunk_size: {parser.min_chunk_size}")
    print(f"   - max_chunk_size: {parser.max_chunk_size}")
    print()
    
    # 执行分块
    print("🔄 开始执行分块...")
    
    # 调试：先看看语法单元
    if 'python' in parser.parsers:
        parser_obj = parser.parsers['python']
        source_bytes = code.encode('utf8')
        tree = parser_obj.parse(source_bytes)
        root = tree.root_node
        
        try:
            units = parser._get_syntax_units_for_chunking(root, source_bytes, 'python')
            print(f"🧩 语法单元分析: {len(units)} 个单元")
            for i, (start, end) in enumerate(units[:3]):  # 只显示前3个
                content = source_bytes[start:end].decode('utf8')
                non_ws = parser._count_non_whitespace_chars(content)
                lines = content.strip().split('\n')
                first_line = lines[0][:50] + "..." if len(lines[0]) > 50 else lines[0]
                print(f"   单元 #{i}: {non_ws} 字符, 开始: {first_line}")
        except Exception as e:
            print(f"   语法单元分析失败: {e}")
    
    chunks = parser._chunk_large_document(doc, "/tmp/Main.py", "python")
    
    
    print(f"✅ 分块完成! 共生成 {len(chunks)} 个块")
    for chunk in chunks:
        print("================================================\n")
        print(chunk)
    
    # 分析分块结果
    method_pattern = re.compile(r'^\s*(def|async\s+def)\s+(\w+)\s*\(', re.MULTILINE)
    decorator_pattern = re.compile(r'^\s*@\w+', re.MULTILINE)
    
    total_chars = 0
    total_non_ws = 0
    
    for i, chunk in enumerate(chunks):
        meta = chunk.metadata
        content = chunk.page_content
        
        # 统计字符数
        chunk_chars = len(content)
        chunk_non_ws = meta.get("chunk_non_ws_chars", 0)
        total_chars += chunk_chars
        total_non_ws += chunk_non_ws
        
        # 查找方法定义
        methods = method_pattern.findall(content)
        decorators = decorator_pattern.findall(content)
        
        print(f"📦 Chunk #{meta.get('chunk_index', i)}:")
        print(f"   ├─ 总字符数: {chunk_chars}")
        print(f"   ├─ 非空白字符数: {chunk_non_ws}")
        print(f"   ├─ 包含方法: {len(methods)} 个")
        if methods:
            method_names = [method[1] if isinstance(method, tuple) else method for method in methods]
            print(f"   │  └─ {', '.join(method_names[:3])}{'...' if len(method_names) > 3 else ''}")
        print(f"   ├─ 包含装饰器: {len(decorators)} 个")
        
        # 显示内容片段
        lines = [line for line in content.splitlines() if line.strip()]
        if lines:
            print(f"   ├─ 开始: {lines[0][:60]}...")
            print(f"   └─ 结束: {lines[-1][:60]}...")
        print()
    
    # 验证分块完整性
    print("🔍 分块完整性验证:")
    original_non_ws = len(re.sub(r'\s', '', code))
    print(f"   ├─ 原始非空白字符数: {original_non_ws}")
    print(f"   ├─ 分块后总非空白字符数: {total_non_ws}")
    print(f"   └─ 完整性: {'✅ 通过' if abs(original_non_ws - total_non_ws) <= len(chunks) * parser.chunk_overlap else '❌ 失败'}")
    print()
    
    # 验证语法感知效果
    print("🧠 语法感知效果分析:")
    syntax_boundaries = 0
    for i, chunk in enumerate(chunks[:-1]):  # 除了最后一个块
        content = chunk.page_content
        # 检查块是否在方法边界结束
        lines = content.rstrip().splitlines()
        if lines:
            last_line = lines[-1].strip()
            # 如果最后一行是方法的结束（简单判断）
            if (last_line == '' or 
                last_line.startswith('def ') or 
                last_line.startswith('async def ') or
                last_line.startswith('@') or
                'return' in last_line):
                syntax_boundaries += 1
    
    syntax_rate = (syntax_boundaries / max(len(chunks) - 1, 1)) * 100
    print(f"   ├─ 语法边界切分率: {syntax_rate:.1f}% ({syntax_boundaries}/{len(chunks)-1})")
    print(f"   └─ 分块策略: {'🧠 语法感知优先' if syntax_rate > 50 else '📏 长度优先'}")
    print()
    
    # 重叠检查
    print("🔗 重叠效果检查:")
    overlaps_found = 0
    for i in range(len(chunks) - 1):
        current_chunk = chunks[i].page_content
        next_chunk = chunks[i + 1].page_content
        
        # 检查是否有重叠内容
        current_tail = current_chunk[-200:].strip()
        next_head = next_chunk[:200].strip()
        
        # 简单检查：看是否有相同的行
        current_lines = set(line.strip() for line in current_tail.splitlines() if line.strip())
        next_lines = set(line.strip() for line in next_head.splitlines() if line.strip())
        
        if current_lines & next_lines:  # 有交集
            overlaps_found += 1
    
    overlap_rate = (overlaps_found / max(len(chunks) - 1, 1)) * 100
    print(f"   ├─ 检测到重叠: {overlaps_found}/{len(chunks)-1} 个相邻块对")
    print(f"   └─ 重叠率: {overlap_rate:.1f}%")
    
    print("=" * 60)
    print("🎉 测试完成!")
    return chunks


if __name__ == "__main__":
    chunks = test_syntax_aware_chunking()
