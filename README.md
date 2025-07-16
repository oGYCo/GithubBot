<div align="center">
  <pre style="line-height:1.2; font-family:'Courier New', monospace; text-align:center; display:inline-block; margin-top:20px; background:#0d1117;">
<span style="color:#3382FF;">██████╗  ██╗████████╗██╗  ██╗██╗   ██╗██████╗ ██████╗  ██████╗ ████████╗</span>
<span style="color:#3E87FF;">██╔════╝ ██║╚══██╔══╝██║  ██║██║   ██║██╔══██╗██╔══██╗██╔═══██╗╚══██╔══╝</span>
<span style="color:#498DFF;">██║  ███╗██║   ██║   ███████║██║   ██║██████╔╝██████╔╝██║   ██║   ██║   </span>
<span style="color:#5493FF;">██║   ██║██║   ██║   ██╔══██║██║   ██║██╔══██╗██╔══██╗██║   ██║   ██║   </span>
<span style="color:#5F99FF;">██████╔╝ ██║   ██║   ██║  ██║╚██████╔╝██████╔╝██████╔╝╚██████╔╝   ██║   </span>
<span style="color:#699FFF;">╚═════╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═════╝  ╚═════╝    ╚═╝   </span>
  </pre>
  <p><strong>An open-source, LLM-based intelligent analysis bot for GitHub repositories</strong></p>
  <p>Chat with your codebase, gain deep insights, and automate code understanding</p>

  <p>
    <a href="https://github.com/oGYCo/GithubBot/blob/main/LICENSE"><img src="https://img.shields.io/github/license/oGYCo/GithubBot" alt="License"></a>
    <a href="https://python.org"><img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python" alt="Python Version"></a>
    <a href="https://fastapi.tiangolo.com/"><img src="https://img.shields.io/badge/FastAPI-0.116.1-blueviolet?logo=fastapi" alt="FastAPI"></a>
    <a href="https://www.langchain.com/"><img src="https://img.shields.io/badge/LangChain-0.3.26-green?logo=langchain" alt="LangChain"></a>
    <a href="https://www.docker.com/"><img src="https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white" alt="Docker"></a>
  </p>
</div>

---
**Note: This project is currently under active development and is not yet ready for production use.**

**GithubBot** is a powerful AI framework designed to revolutionize how developers interact with codebases. It automatically "learns" an entire GitHub repository—including all its code and documentation—and answers any questions about it in natural language through an intelligent chatbot, from "What does this function do?" to "How do I implement a new feature?".

## 🚀 Core Features

- **🤖 Intelligent Code Q&A**: Provides precise, context-aware code explanations and suggestions based on Retrieval-Augmented Generation (RAG).
- **⚡️ Fully Automated Processing**: Simply provide a GitHub repository URL to automatically clone, parse, chunk, vectorize, and index the code.
- **🔌 Highly Extensible**: Easily swap or extend LLMs, embedding models, and vector databases. Supports various models like OpenAI, Azure, Cohere, and HuggingFace.
- **🔍 Hybrid Search**: Combines vector search with BM25 keyword search to ensure optimal context retrieval for various types of queries.
- **⚙️ Asynchronous Task Handling**: Uses Celery and Redis to manage time-consuming repository indexing tasks, ensuring API responsiveness and stability.
- **🐳 One-Click Deployment**: Comes with a complete Docker Compose setup, allowing you to launch all services (API, Worker, databases, etc.) with a single command.

## 🏗️ Architecture Overview

GithubBot uses a modern microservices architecture to ensure system scalability and maintainability. The core process is divided into two stages: **"Data Ingestion"** and **"Query Answering"**.

<div align="center" style="font-family: sans-serif; background-color: #0d1117; padding: 16px; border-radius: 8px;">
<table style="width: 100%; border-collapse: collapse; background-color: #0d1117;">
<thead>
<tr>
<th style="width: 50%; text-align: center; padding-bottom: 16px; font-size: 18px;">📥 Data Ingestion Flow</th>
<th style="width: 50%; text-align: center; padding-bottom: 16px; font-size: 18px;">💬 Query Answering Flow</th>
</tr>
</thead>
<tbody>
<tr>
<td style="vertical-align: top; padding-right: 12px; border-right: 1px solid #30363d;">
<!-- Ingestion Flow Table -->
<table style="width: 100%; border-spacing: 0 8px; border-collapse: separate;">
<tr><td align="center"><div style="border: 1px solid #21262d; border-radius: 6px; padding: 8px 12px; width: 95%; text-align: center; background-color: #161b22;">1. User submits repo URL via API</div></td></tr>
<tr><td align="center" style="color: #8b949e; line-height: 1;">↓</td></tr>
<tr><td align="center"><div style="border: 1px solid #21262d; border-radius: 6px; padding: 8px 12px; width: 95%; text-align: center; background-color: #161b22;">2. API service creates a <strong>Celery</strong> async task</div></td></tr>
<tr><td align="center" style="color: #8b949e; line-height: 1;">↓</td></tr>
<tr><td align="center"><div style="border: 1px solid #21262d; border-radius: 6px; padding: 8px 12px; width: 95%; text-align: center; background-color: #161b22;">3. Task enters <strong>Redis</strong> message queue</div></td></tr>
<tr><td align="center" style="color: #8b949e; line-height: 1;">↓</td></tr>
<tr><td align="center"><div style="border: 1px solid #21262d; border-radius: 6px; padding: 8px 12px; width: 95%; text-align: center; background-color: #161b22;">4. <strong>Celery Worker</strong> executes `ingestion_service`</div></td></tr>
<tr><td align="center" style="color: #8b949e; line-height: 1;">↓</td></tr>
<tr><td align="center"><div style="border: 2px solid #388bfd; border-radius: 6px; padding: 12px; width: 95%; text-align: left; background-color: #161b22;">
<div style="text-align: center; font-weight: bold; margin-bottom: 8px;">Processing Steps:</div>
• Git Helper: Clone repository<br>
• File Parser: Parse & chunk files<br>
• Embedding Manager: Generate vectors
</div></td></tr>
<tr><td align="center" style="color: #8b949e; line-height: 1;">↓</td></tr>
<tr><td align="center"><div style="border: 1px solid #21262d; border-radius: 6px; padding: 8px 12px; width: 95%; text-align: center; background-color: #161b22;">5. Store in <strong>ChromaDB</strong> (vectors) & <strong>PostgreSQL</strong> (metadata)</div></td></tr>
</table>
</td>
<td style="vertical-align: top; padding-left: 12px;">
<!-- Query Flow Table -->
<table style="width: 100%; border-spacing: 0 8px; border-collapse: separate;">
<tr><td align="center"><div style="border: 1px solid #21262d; border-radius: 6px; padding: 8px 12px; width: 95%; text-align: center; background-color: #161b22;">1. User asks a question via API</div></td></tr>
<tr><td align="center" style="color: #8b949e; line-height: 1;">↓</td></tr>
<tr><td align="center"><div style="border: 1px solid #21262d; border-radius: 6px; padding: 8px 12px; width: 95%; text-align: center; background-color: #161b22;">2. API service calls `query_service`</div></td></tr>
<tr><td align="center" style="color: #8b949e; line-height: 1;">↓</td></tr>
<tr><td align="center"><div style="border: 2px solid #388bfd; border-radius: 6px; padding: 12px; width: 95%; text-align: left; background-color: #161b22;">
<div style="text-align: center; font-weight: bold; margin-bottom: 8px;">Hybrid Search:</div>
• Vector search from <strong>ChromaDB</strong><br>
• Keyword search with <strong>BM25</strong>
</div></td></tr>
<tr><td align="center" style="color: #8b949e; line-height: 1;">↓</td></tr>
<tr><td align="center"><div style="border: 1px solid #21262d; border-radius: 6px; padding: 8px 12px; width: 95%; text-align: center; background-color: #161b22;">3. Fuse and rerank retrieved results</div></td></tr>
<tr><td align="center" style="color: #8b949e; line-height: 1;">↓</td></tr>
<tr><td align="center"><div style="border: 1px solid #21262d; border-radius: 6px; padding: 8px 12px; width: 95%; text-align: center; background-color: #161b22;">4. <strong>LLM Manager</strong> builds prompt & calls LLM</div></td></tr>
<tr><td align="center" style="color: #8b949e; line-height: 1;">↓</td></tr>
<tr><td align="center"><div style="border: 1px solid #21262d; border-radius: 6px; padding: 8px 12px; width: 95%; text-align: center; background-color: #161b22;">5. Return final answer via API</div></td></tr>
</table>
</td>
</tr>
</tbody>
</table>
</div>

## 🛠️ Tech Stack

- **Backend**: FastAPI, Python 3.10+
- **AI / RAG**: LangChain, OpenAI, Cohere, HuggingFace (extendable)
- **Database**: PostgreSQL (metadata), ChromaDB (vector storage)
- **Task Queue**: Celery, Redis
- **Containerization**: Docker, Docker Compose
- **Data Validation**: Pydantic

## 🚀 Quick Start

You can get GithubBot up and running in minutes with Docker.

### 1. Prerequisites

- **Docker**: [Install Docker](https://docs.docker.com/get-docker/)
- **Docker Compose**: Usually included with Docker Desktop.
- **Git**: To clone this project.

### 2. Clone the Project

```bash
git clone https://github.com/oGYCo/GithubBot.git
cd GithubBot
```

### 3. Configure Environment

The project uses a `.env` file to manage sensitive information and configurations. **Please note: The project includes a `.env.example` file. You need to create your own `.env` file from it.**

```bash
cp .env.example .env
```

Then, edit the `.env` file and add at least your OpenAI API key:

```dotenv
# .env

# --- LLM and Embedding Model API Keys ---
# At least one model key is required
OPENAI_API_KEY="sk-..."
# AZURE_OPENAI_API_KEY=
# ANTHROPIC_API_KEY=
# ... other API keys
```

### 4. Launch Services

Build and start all services with a single command using Docker Compose:

```bash
docker-compose up --build -d
```

This command will start the API service, Celery worker, PostgreSQL, Redis, and ChromaDB.

### 5. Check Status

Wait a moment for the services to initialize, then check if all containers are running correctly:

```bash
docker-compose ps
```

You should see the status of all services as `running` or `healthy`.

## 📖 API Usage Example

Once the services are running, the API will be available at `http://localhost:8000`. You can access the interactive API documentation (Swagger UI) at `http://localhost:8000/docs`.

### 1. Index a New Repository

Send a `POST` request to the following endpoint to start analyzing a repository. This is an asynchronous operation, and the API will immediately return a task ID.

- **URL**: `/api/v1/repositories/`
- **Method**: `POST`
- **Body**:

```json
{
  "repo_url": "https://github.com/tiangolo/fastapi"
}
```

**Example (using cURL):**

```bash
curl -X 'POST' \
  'http://localhost:8000/api/v1/repositories/' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "repo_url": "https://github.com/tiangolo/fastapi"
}'
```

### 2. Check Analysis Status

Use the `session_id` returned from the previous step to check the analysis progress.

- **URL**: `/api/v1/repositories/{session_id}/status`
- **Method**: `GET`

### 3. Chat with the Repository

Once the repository status changes to `COMPLETED`, you can start asking questions.

- **URL**: `/api/v1/repositories/{session_id}/query`
- **Method**: `POST`
- **Body**:

```json
{
  "query": "How to handle CORS in FastAPI?"
}
```

**Example (using cURL):**

```bash
curl -X 'POST' \
  'http://localhost:8000/api/v1/repositories/{your_session_id}/query' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "query": "How to handle CORS in FastAPI?"
}'
```

## ⚙️ Environment Configuration Details

You can customize almost every aspect of the application in the `.env` file.

| Variable Name | Description | Default Value |
| :--- | :--- | :--- |
| `API_PORT` | Port for the API service to listen on | `8000` |
| `POSTGRES_USER` | PostgreSQL username | `user` |
| `POSTGRES_PASSWORD` | PostgreSQL password | `password` |
| `REDIS_HOST` | Redis service address | `redis` |
| `OPENAI_API_KEY` | OpenAI API key | `""` |
| `CHUNK_SIZE` | Maximum size of text chunks | `1000` |
| `CHUNK_OVERLAP` | Overlap size between text chunks | `200` |
| `VECTOR_SEARCH_TOP_K` | Number of documents from vector search | `10` |
| `BM25_SEARCH_TOP_K` | Number of documents from BM25 search | `10` |
| `ALLOWED_FILE_EXTENSIONS` | List of allowed file extensions | (see `config.py`) |
| `EXCLUDED_DIRECTORIES` | List of directories to ignore | `.git,node_modules,...` |

## 🤝 Contributing

Contributions of all kinds are welcome! Whether it's reporting a bug, submitting a feature request, or contributing code.

1.  Fork the Project
2.  Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the Branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
