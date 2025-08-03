<div align="center">
  <pre style="line-height:1.2; font-family:'Courier New', monospace; text-align:center; display:inline-block; margin-top:20px; background:#0d1117;">
<span style="color:#3382FF;">██████╗  ██╗████████╗██╗  ██╗██╗   ██╗██████╗ ██████╗  ██████╗ ████████╗</span>
<span style="color:#3E87FF;">██╔════╝ ██║╚══██╔══╝██║  ██║██║   ██║██╔══██╗██╔══██╗██╔═══██╗╚══██╔══╝</span>
<span style="color:#498DFF;">██║  ███╗██║   ██║   ███████║██║   ██║██████╔╝██████╔╝██║   ██║   ██║   </span>
<span style="color:#5493FF;">██║   ██║██║   ██║   ██╔══██║██║   ██║██╔══██╗██╔══██╗██║   ██║   ██║   </span>
<span style="color:#5F99FF;">██████╔╝ ██║   ██║   ██║  ██║╚██████╔╝██████╔╝██████╔╝╚██████╔╝   ██║   </span>
<span style="color:#699FFF;">╚═════╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═════╝  ╚═════╝    ╚═╝   </span>
  </pre>
  <p><strong>一个开源的、基于 LLM 的 GitHub 仓库智能分析机器人</strong></p>
  <p>与您的代码库进行对话、获取深度洞见、自动化代码理解</p>
  <p>
    <a href="https://github.com/oGYCo/GithubBot/blob/main/LICENSE"><img src="https://img.shields.io/github/license/oGYCo/GithubBot" alt="License"></a>
    <a href="https://python.org"><img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python" alt="Python Version"></a>
    <a href="https://fastapi.tiangolo.com/"><img src="https://img.shields.io/badge/FastAPI-0.116.1-blueviolet?logo=fastapi" alt="FastAPI"></a>
    <a href="https://www.langchain.com/"><img src="https://img.shields.io/badge/LangChain-0.3.26-green?logo=langchain" alt="LangChain"></a>
    <a href="https://www.docker.com/"><img src="https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white" alt="Docker"></a>
</p>
</div>
---
**请注意，目前项目仍在开发中，还无法正常使用**

**GithubBot** 是一个功能强大的 AI 框架，旨在彻底改变开发者与代码库的交互方式。它能够自动“学习”一个 GitHub 仓库的全部代码和文档，并通过一个智能聊天机器人，用自然语言回答关于该仓库的任何问题——从“这个函数是做什么的？”到“如何实现一个新功能？”。

## 🚀 核心功能

- **🤖 智能代码问答**: 基于检索增强生成（RAG）技术，提供精准的、上下文感知的代码解释和建议。
- **⚡️ 全自动处理**: 只需提供一个 GitHub 仓库 URL，即可自动完成代码克隆、解析、分块、向量化和索引。
- **🔌 高度可扩展**: 轻松更换或扩展 LLM、Embedding 模型和向量数据库，支持 OpenAI、Azure、Cohere、HuggingFace 等多种模型。
- **🔍 混合搜索**: 结合了向量搜索和 BM25 关键字搜索，确保在不同类型的查询下都能获得最佳的上下文检索效果。
- **⚙️ 异步任务处理**: 使用 Celery 和 Redis 处理耗时的仓库索引任务，确保 API 服务的响应速度和稳定性。
- **🐳 一键部署**: 完整的 Docker-Compose 配置，一行命令即可启动所有服务（API、Worker、数据库等）。

## 🏗️ 架构概览

GithubBot 采用现代化的微服务架构，确保系统的可伸缩性和可维护性。核心流程分为 **“数据注入”** 和 **“查询应答”** 两个阶段。

<div align="center" style="font-family: sans-serif; background-color: #0d1117; padding: 16px; border-radius: 8px;">
    <table style="width: 100%; border-collapse: collapse; background-color: #0d1117;">
        <thead>
            <tr>
                <th style="width: 50%; text-align: center; padding-bottom: 16px; font-size: 18px;">📥 数据注入流程</th>
                <th style="width: 50%; text-align: center; padding-bottom: 16px; font-size: 18px;">💬 查询应答流程</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td style="vertical-align: top; padding-right: 12px; border-right: 1px solid #30363d;">
                    <!-- Ingestion Flow Table -->
                    <table style="width: 100%; border-spacing: 0 8px; border-collapse: separate;">
                        <tr><td align="center"><div style="border: 1px solid #21262d; border-radius: 6px; padding: 8px 12px; width: 95%; text-align: center; background-color: #161b22;">1. 用户通过 API 提交仓库 URL</div></td></tr>
                        <tr><td align="center" style="color: #8b949e; line-height: 1;">↓</td></tr>
                        <tr><td align="center"><div style="border: 1px solid #21262d; border-radius: 6px; padding: 8px 12px; width: 95%; text-align: center; background-color: #161b22;">2. API 服务创建 <strong>Celery</strong> 异步任务</div></td></tr>
                        <tr><td align="center" style="color: #8b949e; line-height: 1;">↓</td></tr>
                        <tr><td align="center"><div style="border: 1px solid #21262d; border-radius: 6px; padding: 8px 12px; width: 95%; text-align: center; background-color: #161b22;">3. 任务进入 <strong>Redis</strong> 消息队列</div></td></tr>
                        <tr><td align="center" style="color: #8b949e; line-height: 1;">↓</td></tr>
                        <tr><td align="center"><div style="border: 1px solid #21262d; border-radius: 6px; padding: 8px 12px; width: 95%; text-align: center; background-color: #161b22;">4. <strong>Celery Worker</strong> 执行 `ingestion_service`</div></td></tr>
                        <tr><td align="center" style="color: #8b949e; line-height: 1;">↓</td></tr>
                        <tr><td align="center"><div style="border: 2px solid #388bfd; border-radius: 6px; padding: 12px; width: 95%; text-align: left; background-color: #161b22;">
                            <div style="text-align: center; font-weight: bold; margin-bottom: 8px;">处理步骤:</div>
                            • Git Helper: 克隆仓库<br>
                            • File Parser: 解析/分块<br>
                            • Embedding Manager: 生成向量
                        </div></td></tr>
                        <tr><td align="center" style="color: #8b949e; line-height: 1;">↓</td></tr>
                        <tr><td align="center"><div style="border: 1px solid #21262d; border-radius: 6px; padding: 8px 12px; width: 95%; text-align: center; background-color: #161b22;">5. 存入 <strong>ChromaDB</strong> (向量) & <strong>PostgreSQL</strong> (元数据)</div></td></tr>
                    </table>
                </td>
                <td style="vertical-align: top; padding-left: 12px;">
                    <!-- Query Flow Table -->
                    <table style="width: 100%; border-spacing: 0 8px; border-collapse: separate;">
                        <tr><td align="center"><div style="border: 1px solid #21262d; border-radius: 6px; padding: 8px 12px; width: 95%; text-align: center; background-color: #161b22;">1. 用户通过 API 提问</div></td></tr>
                        <tr><td align="center" style="color: #8b949e; line-height: 1;">↓</td></tr>
                        <tr><td align="center"><div style="border: 1px solid #21262d; border-radius: 6px; padding: 8px 12px; width: 95%; text-align: center; background-color: #161b22;">2. API 服务调用 `query_service`</div></td></tr>
                        <tr><td align="center" style="color: #8b949e; line-height: 1;">↓</td></tr>
                        <tr><td align="center"><div style="border: 2px solid #388bfd; border-radius: 6px; padding: 12px; width: 95%; text-align: left; background-color: #161b22;">
                            <div style="text-align: center; font-weight: bold; margin-bottom: 8px;">混合搜索:</div>
                            • 从 <strong>ChromaDB</strong> 进行向量检索<br>
                            • 从内存进行 <strong>BM25</strong> 关键词检索
                        </div></td></tr>
                        <tr><td align="center" style="color: #8b949e; line-height: 1;">↓</td></tr>
                        <tr><td align="center"><div style="border: 1px solid #21262d; border-radius: 6px; padding: 8px 12px; width: 95%; text-align: center; background-color: #161b22;">3. 整合并重排检索结果</div></td></tr>
                        <tr><td align="center" style="color: #8b949e; line-height: 1;">↓</td></tr>
                        <tr><td align="center"><div style="border: 1px solid #21262d; border-radius: 6px; padding: 8px 12px; width: 95%; text-align: center; background-color: #161b22;">4. <strong>LLM Manager</strong> 构建 Prompt 并调用 LLM</div></td></tr>
                        <tr><td align="center" style="color: #8b949e; line-height: 1;">↓</td></tr>
                        <tr><td align="center"><div style="border: 1px solid #21262d; border-radius: 6px; padding: 8px 12px; width: 95%; text-align: center; background-color: #161b22;">5. 通过 API 返回最终答案</div></td></tr>
                    </table>
                </td>
            </tr>
        </tbody>
    </table>
</div>

## 🛠️ 技术栈

- **后端**: FastAPI, Python 3.10+
- **AI / RAG**: LangChain, OpenAI, Cohere, HuggingFace (可扩展)
- **数据库**: PostgreSQL (元数据), ChromaDB (向量存储)
- **任务队列**: Celery, Redis
- **容器化**: Docker, Docker Compose
- **数据校验**: Pydantic

## 🚀 快速开始

通过 Docker，您可以在几分钟内启动并运行 GithubBot。

### 1. 环境准备

- **Docker**: [安装 Docker](https://docs.docker.com/get-docker/)
- **Docker Compose**: 通常随 Docker Desktop 一起安装。
- **Git**: 用于克隆本项目。

### 2. 克隆项目

```bash
git clone https://github.com/oGYCo/GithubBot.git
cd GithubBot
```

### 3. 环境配置

项目通过 `.env` 文件管理敏感信息和配置。 **请注意：项目中已经包含了 `.env.example` 文件，您需要手动创建 `.env` 文件。**

```bash
cp .env.example .env
```

然后，编辑 `.env` 文件，至少填入您的 OpenAI API 密钥：

```dotenv
# .env

# --- LLM 和 Embedding 模型 API Keys ---
# 至少需要提供一个模型的 Key
OPENAI_API_KEY="sk-..."
# AZURE_OPENAI_API_KEY=
# ANTHROPIC_API_KEY=
# ... 其他 API Keys
```

### 4. 启动服务

#### 选项A: 一键启动 (推荐)

**Linux/macOS:**
```bash
chmod +x start.sh
./start.sh
```

**Windows:**
- **方法1 (批处理文件)**: 双击 `start.bat` 或在命令提示符中运行:
  ```cmd
  start.bat
  ```

- **方法2 (PowerShell)**: 右击 `start.ps1` → "用PowerShell运行" 或在PowerShell中运行:
  ```powershell
  .\start.ps1
  ```

#### 选项B: 手动Docker Compose

手动构建并启动所有服务:

```bash
docker compose up --build -d
```

该命令会启动 API 服务、Celery Worker、PostgreSQL、Redis 和 ChromaDB。

### 5. 检查状态

等待片刻让服务初始化，然后检查所有容器是否正常运行：

```bash
docker compose ps
```

您应该能看到所有服务的状态为 `running` 或 `healthy`。

### 6. 访问服务

所有服务运行后，您可以访问：

- **API 文档**: http://localhost:8000/docs
- **API 根路径**: http://localhost:8000
- **Flower (任务监控)**: http://localhost:5555
- **健康检查**: http://localhost:8000/health

## 📊 服务监控

| 服务 | 端口 | 监控 URL | 说明 |
|------|------|----------|------|
| API 服务 | 8000 | http://localhost:8000/health | 主要 API 接口 |
| API 文档 | 8000 | http://localhost:8000/docs | Swagger 文档 |
| Flower | 5555 | http://localhost:5555 | 任务队列监控 |
| PostgreSQL | 5432 | - | 数据库服务 |
| Redis | 6380 | - | 缓存和消息队列 |
| ChromaDB | 8001 | - | 向量数据库 (主机端口，容器内部8000) |

## 🛑 停止服务

```bash
docker compose down
```

## 🔄 重启服务

```bash
docker compose restart
```

## 📝 查看日志

```bash
# 查看所有服务日志
docker compose logs -f

# 查看特定服务日志
docker compose logs -f api
docker compose logs -f worker
```

## 🔧 常见问题

### 通用问题

1. **API 密钥未设置**
   - 确保 `.env` 文件中至少设置了一个 LLM API 密钥
   - 推荐设置 `OPENAI_API_KEY`

2. **端口冲突**
   - 检查端口 8000、5555、5432、6380、8001 是否被占用
   - 使用 `netstat -an | grep :8000` 检查端口状态

3. **Docker 未运行**
   - 确保 Docker Desktop 正在运行
   - 检查系统托盘中的 Docker 图标

4. **内存不足**
   - 确保系统有足够的内存运行所有容器
   - 推荐至少 4GB 可用内存

5. **网络连接问题**
   - 确保能够访问 Docker Hub
   - 在中国大陆可能需要配置 Docker 镜像加速器

### Windows 特有问题

1. **Docker Desktop 未启动**
   - 确保 Docker Desktop 正在运行
   - 检查系统托盘中的 Docker 图标

2. **WSL2 未启用**
   - Docker Desktop 需要 WSL2 支持
   - 参考 [WSL2 安装指南](https://docs.microsoft.com/en-us/windows/wsl/install)

3. **防火墙阻止**
   - 确保 Windows 防火墙允许 Docker 网络访问

## 📖 API 使用示例

服务启动后，API 将在 `http://localhost:8000` 上可用。您可以访问 `http://localhost:8000/docs` 查看交互式 API 文档 (Swagger UI)。

### 1. 索引一个新的仓库

向以下端点发送 `POST` 请求，开始分析一个仓库。这是一个异步操作，API 会立即返回一个任务 ID。

- **URL**: `/api/v1/repos/analyze`
- **Method**: `POST`
- **Body**:

```json
{
  "repo_url": "https://github.com/tiangolo/fastapi",
  "embedding_config": {
    "provider": "openai",
    "model_name": "text-embedding-3-small",
    "api_key": "your-openai-api-key"
  }
}
```

**示例 (使用 cURL):**

```bash
curl -X 'POST' \
  'http://localhost:8000/api/v1/repos/analyze' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "repo_url": "https://github.com/tiangolo/fastapi",
  "embedding_config": {
    "provider": "openai",
    "model_name": "text-embedding-3-small",
    "api_key": "your-openai-api-key"
  }
}'
```

### 2. 查询分析状态

使用上一步返回的 `session_id` 来检查仓库的分析进度。

- **URL**: `/api/v1/repos/status/{session_id}`
- **Method**: `GET`

### 3. 与仓库对话

一旦仓库状态变为 `SUCCESS`，您就可以开始提问了。

- **URL**: `/api/v1/repos/query`
- **Method**: `POST`
- **Body**:

```json
{
  "session_id": "your-session-id",
  "question": "如何在 FastAPI 中处理 CORS？",
  "generation_mode": "service",
  "llm_config": {
    "provider": "openai",
    "model_name": "gpt-4",
    "api_key": "your-openai-api-key",
    "temperature": 0.7,
    "max_tokens": 1000
  }
}
```

**示例 (使用 cURL):**

```bash
curl -X 'POST' \
  'http://localhost:8000/api/v1/repos/query' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "session_id": "your-session-id",
  "question": "如何在 FastAPI 中处理 CORS？",
  "generation_mode": "service"
}'
```

- **URL**: `/api/v1/repos/status/{session_id}`
- **Method**: `GET`

### 3. 与仓库对话

当仓库状态变为 `SUCCESS` 后，您就可以开始提问了。

- **URL**: `/api/v1/repos/query`
- **Method**: `POST`
- **Body**:

```json
{
  "session_id": "your-session-id",
  "question": "How to handle CORS in FastAPI?",
  "generation_mode": "service",
  "llm_config": {
    "provider": "openai",
    "model_name": "gpt-4",
    "api_key": "your-openai-api-key",
    "temperature": 0.7,
    "max_tokens": 1000
  }
}
```

**示例 (使用 cURL):**

```bash
curl -X 'POST' \
  'http://localhost:8000/api/v1/repos/query' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "session_id": "your-session-id",
  "question": "How to handle CORS in FastAPI?",
  "generation_mode": "service",
  "llm_config": {
    "provider": "openai",
    "model_name": "gpt-4",
    "api_key": "your-openai-api-key",
    "temperature": 0.7,
    "max_tokens": 1000
  }
}'
```

## ⚙️ 环境配置详解

您可以在 `.env` 文件中自定义应用的几乎所有方面。

### 核心配置

| 变量名 | 描述 | 默认值 |
| :--- | :--- | :--- |
| `APP_NAME` | 应用名称 | `"GithubBot"` |
| `APP_VERSION` | 应用版本 | `"0.1.0"` |
| `DEBUG` | 调试模式 | `False` |
| `LOG_LEVEL` | 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL) | `"INFO"` |
| `API_KEY` | API 访问密钥 (可选) | `""` |
| `CORS_ORIGINS` | 允许的跨域请求源 (逗号分隔) | `"http://localhost:3000,http://127.0.0.1:3000"` |
| `BM25_SEARCH_TOP_K` | BM25 搜索返回的文档数 | `10` |
| `ALLOWED_FILE_EXTENSIONS` | 允许处理的文件扩展名列表 | (见 `config.py`) |
| `EXCLUDED_DIRECTORIES` | 忽略的目录列表 | `.git,node_modules,...` |

### 服务端口

| 变量名 | 描述 | 默认值 |
| :--- | :--- | :--- |
| `API_HOST` | API 主机地址 | `"0.0.0.0"` |
| `API_PORT` | API 服务监听的端口 | `8000` |

### 数据库配置 (PostgreSQL)

| 变量名 | 描述 | 默认值 |
| :--- | :--- | :--- |
| `DATABASE_URL` | 完整的 PostgreSQL 连接 URL | `"postgresql+psycopg2://user:password@postgres:5432/repoinsight"` |
| `POSTGRES_USER` | PostgreSQL 用户名 | `"user"` |
| `POSTGRES_PASSWORD` | PostgreSQL 密码 | `"password"` |
| `POSTGRES_DB` | PostgreSQL 数据库名 | `"repoinsight"` |
| `POSTGRES_HOST` | PostgreSQL 主机 | `"postgres"` |
| `POSTGRES_PORT` | PostgreSQL 端口 | `5432` |

### Redis 配置

| 变量名 | 描述 | 默认值 |
| :--- | :--- | :--- |
| `REDIS_URL` | 完整的 Redis 连接 URL | `"redis://redis:6379/0"` |
| `REDIS_HOST` | Redis 服务地址 | `"redis"` |
| `REDIS_PORT` | Redis 端口 | `6379` |

### ChromaDB 配置

| 变量名 | 描述 | 默认值 |
| :--- | :--- | :--- |
| `CHROMADB_HOST` | ChromaDB 主机 | `"chromadb"` |
| `CHROMADB_PORT` | ChromaDB 端口 | `8000` |
| `CHROMADB_CLIENT_TIMEOUT` | ChromaDB 客户端超时时间 (秒) | `120` |
| `CHROMADB_SERVER_TIMEOUT` | ChromaDB 服务器超时时间 (秒) | `120` |
| `CHROMADB_MAX_RETRIES` | ChromaDB 连接最大重试次数 | `5` |
| `CHROMADB_RETRY_DELAY` | ChromaDB 连接重试延迟 (秒) | `3` |

### LLM 和 Embedding 模型 API Keys

| 变量名 | 描述 |
| :--- | :--- |
| `OPENAI_API_KEY` | OpenAI API 密钥 |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API 密钥 |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI 端点 |
| `ANTHROPIC_API_KEY` | Anthropic API 密钥 |
| `COHERE_API_KEY` | Cohere API 密钥 |
| `GOOGLE_API_KEY` | Google API 密钥 |
| `HUGGINGFACE_HUB_API_TOKEN` | HuggingFace API 令牌 |
| `MISTRAL_API_KEY` | Mistral API 密钥 |
| `QWEN_API_KEY` | Qwen API 密钥 |
| `DASHSCOPE_API_KEY` | DashScope API 密钥 |

### 处理配置

| 变量名 | 描述 | 默认值 |
| :--- | :--- | :--- |
| `GIT_CLONE_DIR` | Git 仓库克隆目录 | `"/repo_clones"` |
| `CHUNK_SIZE` | 文本分块的最大尺寸 | `1000` |
| `CHUNK_OVERLAP` | 文本分块之间的重叠尺寸 | `200` |
| `EMBEDDING_BATCH_SIZE` | 嵌入处理批次大小 | `32` |
| `VECTOR_SEARCH_TOP_K` | 向量搜索返回的文档数 | `10` |
| `BM25_SEARCH_TOP_K` | BM25 搜索返回的文档数 | `10` |

### 文件处理

| 变量名 | 描述 | 默认值 |
| :--- | :--- | :--- |
| `ALLOWED_FILE_EXTENSIONS` | 允许的文件扩展名列表 (JSON 数组) | `[".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".cpp", ".c", ".h", ".hpp", ".cs", ".php", ".rb", ".go", ".rs", ".swift", ".kt", ".scala", ".md", ".txt", ".rst", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".sh", ".sql", ".html", ".css", ".vue", "dockerfile", "makefile", "readme", "license", "changelog"]` |
| `EXCLUDED_DIRECTORIES` | 排除的目录列表 (JSON 数组) | `[".git", "node_modules", "dist", "build", "venv", ".venv", "target"]` |

### Celery 配置

| 变量名 | 描述 | 默认值 |
| :--- | :--- | :--- |
| `CELERY_BROKER_URL` | Celery 代理 URL | `"redis://redis:6379/0"` |

## 🤝 贡献

欢迎各种形式的贡献！无论是报告 bug、提交功能请求还是贡献代码。

1.  Fork 项目
2.  创建您的功能分支 (`git checkout -b feature/AmazingFeature`)
3.  提交您的更改 (`git commit -m 'Add some AmazingFeature'`)
4.  推送到分支 (`git push origin feature/AmazingFeature`)
5.  提交 Pull Request

## 📄 许可证

本项目采用 MIT 许可证。详情请见 [LICENSE](LICENSE) 文件。

