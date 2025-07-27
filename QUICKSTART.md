# GitHub Bot 快速启动指南

## 🚀 快速部署

### 1. 环境准备
```bash
# 确保安装了 Docker 和 Docker Compose
docker --version
docker-compose --version
```

### 2. 配置环境变量
```bash
# 复制环境配置文件
cp .env.example .env

# 编辑配置文件，填入你的 API 密钥
nano .env
```

**必需配置的 API 密钥：**
- `OPENAI_API_KEY`: OpenAI API 密钥（推荐）
- `AZURE_OPENAI_API_KEY`: Azure OpenAI 密钥（可选）
- `HUGGINGFACE_API_TOKEN`: HuggingFace Token（可选）

### 3. 一键启动
```bash
# 使用启动脚本
chmod +x start.sh
./start.sh
```

或者手动启动：
```bash
# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f api
```

### 4. 验证部署
```bash
# 检查健康状态
curl http://localhost:8000/health

# 访问 API 文档
open http://localhost:8000/docs
```

## 📝 使用示例

### 添加仓库
```bash
curl -X POST "http://localhost:8000/api/v1/repositories/" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://github.com/octocat/Hello-World",
    "name": "Hello-World",
    "description": "测试仓库"
  }'
```

### 查询代码
```bash
curl -X POST "http://localhost:8000/api/v1/repositories/1/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "如何创建新的类？",
    "max_results": 5
  }'
```

## 🔧 常见问题

### Q: 启动失败怎么办？
A: 检查端口占用和环境变量配置
```bash
# 检查端口占用
netstat -tlnp | grep :8000
netstat -tlnp | grep :5432

# 重新启动
docker-compose down
docker-compose up -d
```

### Q: 代理连接错误 (WSL2 环境)
A: 如果看到 "proxyconnect tcp: dial tcp 127.0.0.1:7890: connect: connection refused"
这是 WSL2 环境下的代理配置问题，有两种解决方案：

**方案 1：修复 Docker Desktop 代理设置（推荐）**
1. 打开 Docker Desktop
2. 进入 Settings → Resources → Proxies
3. 修改代理地址：
   - Web Server (HTTP): `http://10.255.255.254:7890`
   - Secure Web Server (HTTPS): `http://10.255.255.254:7890`
   - Bypass proxy: `localhost,127.0.0.1,::1,10.*,172.*,192.168.*`
4. 点击 "Apply & Restart"

**方案 2：使用无代理模式启动**
```bash
./start-no-proxy.sh
```

**方案 3：临时禁用 Docker Desktop 代理**
1. 进入 Docker Desktop Settings → Resources → Proxies
2. 取消勾选 "Manual proxy configuration"
3. 点击 "Apply & Restart"

### Q: 环境变量未设置警告
A: 如果看到 "variable is not set. Defaulting to a blank string"
```bash
# 检查 .env 文件配置
cat .env | grep -E "(DATABASE_URL|REDIS_URL)"

# 确保这两行没有被注释
DATABASE_URL="postgresql+psycopg2://user:password@postgres:5432/repoinsight"
REDIS_URL="redis://redis:6379/0"
```

### Q: 向量存储初始化失败？
A: 清理并重建数据卷
```bash
docker-compose down -v
docker-compose up -d
```

### Q: 如何监控任务队列？
A: 访问 Flower 监控界面
- URL: http://localhost:5555
- 查看任务执行状态和队列信息

## 📊 服务监控

| 服务 | 端口 | 监控 URL | 说明 |
|------|------|----------|------|
| API 服务 | 8000 | http://localhost:8000/health | 主要 API 接口 |
| API 文档 | 8000 | http://localhost:8000/docs | Swagger 文档 |
| Flower | 5555 | http://localhost:5555 | 任务队列监控 |
| PostgreSQL | 5432 | - | 数据库服务 |
| Redis | 6379 | - | 缓存和消息队列 |
| ChromaDB | 8001 | - | 向量数据库 (主机端口，容器内部8000) |

## 🔄 开发模式

如需开发调试：
```bash
# 停止容器化的 API 服务
docker-compose stop api worker

# 本地运行 API 服务
pip install -r requirements.txt
python -m src.main

# 本地运行 Worker
celery -A src.worker.celery_app worker --loglevel=info
```
