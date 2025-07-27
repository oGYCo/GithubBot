### **项目：GitHub 仓库问答机器人 架构**

-----

### **第一部分：核心分析服务 (RepoInsight-Service)**

这是一个独立的 FastAPI 应用，是整个项目的大脑，负责所有的计算和数据处理

#### **项目根目录结构**

```
repoinsight_service/
├── .env                  # 【配置】存放环境变量和密钥 (数据库密码, API Keys)
├── .gitignore            # 【Git】Git 忽略文件配置
├── architecture.md       # 【架构】项目的整体架构介绍
├── README.md             # 【文档】项目说明文档
├── docker-compose.yml    # 【部署】Docker 编排文件，用于一键启动所有服务
├── requirements.txt      # 【依赖】Python 依赖包列表
├── pyproject.toml        # 【配置】现代 Python 项目配置文件
│
├── scripts/              # 【脚本】存放一次性或辅助脚本 (如数据迁移)
│   └── __init__.py
│
├── src/                  # 【核心】存放所有应用源代码
│   ├── __init__.py       # 将 src 声明为可导入的根包
│   ├── main.py           # 【入口】FastAPI 应用主入口
│   │
│   ├── api/              # 【接口层】负责处理所有 HTTP 请求和响应
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── api.py    # 【路由】聚合 v1 版本的所有 API 路由器
│   │       └── endpoints/
│   │           ├── __init__.py
│   │           └── repositories.py # 【端点】定义 /repositories/ 相关的所有 API 端点
│   │
│   ├── core/             # 【配置层】负责应用的核心配置和启动事件
│   │   └── config.py     # 【配置】加载和管理所有配置
│   │
│   ├── db/               # 【数据层-关系型】负责与关系型数据库 (PostgreSQL/SQLite) 交互
│   │   ├── models.py     # 【模型】定义数据库表结构 (SQLAlchemy ORM)
│   │   └── session.py    # 【会话】创建和管理数据库会话
│   │
│   ├── schemas/          # 【数据校验层】负责定义 API 的数据结构
│   │   └── repository.py # 【模型】定义仓库分析相关的请求和响应体模型 (Pydantic)
│   │
│   ├── services/         # 【业务逻辑层】负责实现所有核心功能
|   |   ├── embedding_manager.py # 【新】Embedding 模型管理器
│   │   ├── ingestion_service.py # 【服务】数据注入服务
|   |   ├── llm_manager.py       # 【新】LLM 管理器
│   │   ├── query_service.py     # 【服务】问答查询服务
│   │   └── vector_store.py      # 【服务】向量数据库客户端
|   |   └── task_queue.py        #  基于redis的，添加query任务到消息队列中和通过session_id查询任务进行状态，以及取消任务、查询任务信息的函数
│   │
│   ├── utils/            # 【工具层】负责提供通用的辅助函数
│   │   ├── file_parser.py     # 【工具】文件过滤和专门解析
│   │   └── git_helper.py      # 【工具】Git 仓库克隆
│   │
│   └── worker/           # 【后台任务层】负责处理耗时的异步任务
│       ├── celery_app.py # 【配置】Celery 应用实例的配置
│       └── tasks.py      # 【任务】定义具体的后台任务
│
└── tests/                # 【测试】存放所有测试代码
    ├── __init__.py
    ├── test_api/
    │   ├── __init__.py
    │   └── test_repositories.py
    └── test_services/
        ├── __init__.py
        └── test_ingestion.py
```

#### **各文件职责详解**

  * **`docker-compose.yml`**: **【部署核心】** 负责编排和一键启动项目的所有服务组件（FastAPI应用、ChromaDB、Redis、Celery Worker），是实现完整部署的关键。

  * **`src/main.py`**: **【应用入口】** 创建 FastAPI 应用实例，是整个 Web 服务的起点。它会加载 `src/api/v1/api.py` 中定义的路由，让所有 API 接口生效。

  * **`src/api/v1/endpoints/repositories.py`**: **【API网关】** 定义所有对外暴露的 HTTP 接口（如 `/analyze`, `/status`, `/query`）。它负责接收外部请求，使用 `schemas` 验证数据，然后将处理任务分发给相应的 `services` 或 `worker`。
      - /analyze 端点：接收包含 embedding_config 的请求，并将其传递给后台任务。
      - /query 端点：接收包含 generation_mode 和 llm_config 的请求，并将其传递给 query_service.

  * **`src/core/config.py`**: **【配置中心】** 安全地从 `.env` 文件中读取所有配置信息（API密钥、数据库地址、ChromaDB地址等），供应用全局使用。

  * **`src/db/models.py`**: **【数据结构蓝图 (关系型)】** 定义了 `AnalysisSession` 等数据表，描述了任务状态等信息如何存储在 PostgreSQL 或 SQLite 中。

  * **`src/schemas/repository.py`**: 【架构核心变更】职责：定义 API 的数据结构，这是实现灵活配置的关键。构建内容:

      - EmbeddingConfig 模型：包含 provider (e.g., "openai", "huggingface"), model_name, api_key (可选) 等字段。

      - LLMConfig 模型：与 EmbeddingConfig 类似，定义 LLM 的配置。

      - RepoAnalyzeRequest 模型：请求体中包含 repo_url 和一个 embedding_config 对象。

      - QueryRequest 模型：请求体中包含 session_id, question, 一个**generation_mode**字段 (值为 "service" 或 "plugin")，以及一个可选的 llm_config 对象（当 generation_mode 为 "service" 时使用）。

      - QueryResponse 模型：响应体中包含一个可选的 answer 字段和一个可选的 retrieved_context 字段。

  * **`src/services/embedding_manager.py`**:
      - 职责：Embedding 模型工厂。根据传入的 EmbeddingConfig，动态地实例化并返回一个 LangChain 的 Embedding 模型对象。
      - 构建内容：一个 get_embedding_model(config: EmbeddingConfig) 函数，内部使用 if/elif 或字典映射来处理不同的 provider（如 "openai", "azure", "huggingface" 等），并加载相应的模型。

  * **`src/services/llm_manager.py`**:
      - 职责：LLM 工厂。与 embedding_manager 类似，根据传入的 LLMConfig，动态地实例化并返回一个 LangChain 的 LLM 或 ChatModel 对象。
      

  * **`src/services/ingestion_service.py`**: **【数据处理流水线】** 负责从“克隆仓库”到“存入数据库”的完整数据注入流程。它编排 `utils` 和 `vector_store` 模块来完成这项复杂任务。
      - 关系：它在执行时，会从任务参数中接收 EmbeddingConfig，然后调用 embedding_manager.get_embedding_model() 来获取正确的模型实例，用这个实例来进行向量化。

  * **`src/services/query_service.py`**: **【问答引擎】** 负责处理用户的提问。它实现了混合检索、重排序等高级 RAG 策略，并最终调用 LLM 生成答案。
      - 接收到 QueryRequest 后，首先执行混合检索和重排序，得到最终的上下文 retrieved_context。
      - 检查请求中的 generation_mode 字段：
            - 如果为 "plugin"，则直接将 retrieved_context 放入 QueryResponse 并返回。工作到此结束
            - 如果为 "service"，则继续下一步：调用 llm_manager.get_llm() 获取 LLM 实例，构建 Prompt，生成答案，然后将 answer 和 retrieved_context 一起放入 QueryResponse 并返回。

  * **`src/services/vector_store.py`**: **【向量数据库适配器】** 封装了所有与 ChromaDB 的直接交互，提供如“创建集合”、“添加文档”、“查询向量”等标准接口，使上层服务无需关心 ChromaDB 的具体实现细节。

  * **`src/utils/` 目录**: **【工具箱】** 提供了专一、可复用的功能函数，如 `git_helper.py` 只负责克隆，`file_parser.py` 只负责解析文件，这让 `services` 层的代码更整洁。

  * **`src/worker/tasks.py`**: **【后台工人】** 定义了耗时的后台任务（如 `process_repository_task`）。当需要处理一个大仓库时，API会把这个任务“扔”给它，然后立即返回，不阻塞主流程。

  * **`tests/` 目录**: **【质量保证】** 存放所有的单元测试和集成测试，确保代码质量和功能正确性。

#### **文件之间的关系 (数据流)**

一个典型的“分析并提问”流程如下：

1.  **启动分析**:

      * **LangBot 插件** 向 `src/api/v1/endpoints/repositories.py` 的 `/analyze` 端点发送一个 HTTP POST 请求。
      * `/analyze` 端点验证请求数据后，立即调用 `src/worker/tasks.py` 中的 `process_repository_task.delay()`，将任务放入 **Redis** 消息队列，然后向插件返回一个“任务已开始”的响应。
      * **Celery Worker** 从 Redis 中获取任务，并开始执行 `process_repository_task`。
      * 该任务的核心是调用 `src/services/ingestion_service.py`。
      * `ingestion_service` 依次调用 `utils.git_helper` 克隆代码，`utils.file_parser` 解析文件，然后调用 `src/services/vector_store.py` 将处理好的数据块存入 **ChromaDB**。
      * 任务完成后，会更新 **PostgreSQL** 中对应任务的状态。

2.  **进行提问**:

      * **LangBot 插件** 向 `src/api/v1/endpoints/repositories.py` 的 `/query` 端点发送一个 HTTP POST 请求，包含问题和会话ID。
      * `/query` 端点直接调用 `src/services/query_service.py`。
      * `query_service` 从 **PostgreSQL** 验证会话状态，然后执行混合检索：一部分通过 `src/services/vector_store.py` 查询 **ChromaDB**，另一部分在内存中进行 BM25 关键词检索。
      * 在融合和重排序结果后，`query_service` 调用 **OpenAI LLM** 生成答案。
      * 最终，答案通过 API 层层返回给 LangBot 插件和用户。

-----

### **第二部分：轻量级 LangBot 插件 (RepoInsight-LangBot-Plugin)**

#### **插件目录结构**

```
langbot/plugins/repoinsight_plugin/
├── __init__.py           # 插件主文件，定义指令和消息处理
├── api_client.py         # 封装所有对 RepoInsight-Service 的 API 调用
├── config.py             # 【新】插件侧的配置文件
└── session_manager.py    # 管理微信用户 ID 和分析任务 session_id 的映射
```

#### **各文件职责详解**

  * **`__init__.py`**: **【插件入口】** 负责处理用户交互，定义 `!set_repo` 等指令，并调用 `api_client`。插件主逻辑，现在需要根据配置决定如何行动。
      - 处理 !set_repo:
            - 从 config.py 读取默认的 EmbeddingConfig。
            - 允许用户通过指令参数覆盖默认配置，例如 !set_repo <url> --model=openai/text-embedding-3-large。
            - 调用 api_client.start_analysis()，将最终的 EmbeddingConfig 发送给后端。
      - 处理普通消息 (提问):
            - 从 config.py 读取默认的 GENERATION_MODE。
            - 如果模式是 "service": 调用 api_client.post_question()，将 generation_mode 设为 "service"，并可能传递插件侧的 LLM 配置。然后直接将返回的 answer 显示给用户。
            - 如果模式是 "plugin": 调用 api_client.post_question()，将 generation_mode 设为 "plugin"。API 只会返回 retrieved_context。插件随后将这些上下文和用户问题组合成一个 Prompt，调用 LangBot 框架自身提供的 LLM 接口来生成最终答案，再显示给用户

  * **`api_client.py`**: **【通信桥梁】** 一个纯粹的 HTTP 客户端，使用 `httpx` 等库与 `RepoInsight-Service` 的 API 端点进行通信。需要更新其函数签名，以接受和发送包含 embedding_config, llm_config, generation_mode 等参数的复杂请求体。

  * **`session_manager.py`**: **【用户状态管理】** 在内存或 Redis 中维护 `wechat_user_id` 到 `session_id` 的映射，帮助插件保持用户的会话状态。

  * **`config.py`**:
      - 职责：提供插件侧的默认配置。
      - 构建内容：定义插件默认使用的 Embedding 模型配置、默认的 LLM 配置（如果需要独立配置），以及最重要的——默认的 GENERATION_MODE (值为 "service" 或 "plugin")。


### 改变

Embedding 阶段：插件决定使用哪个模型进行向量化。
Query 阶段：插件决定在哪里完成最后一步的“生成”工作——是在算力更强的后端服务上完成，还是利用 LangBot 平台自身可能已经优化过或更经济的 LLM 服务来完成。