# 启动指南

本项目提供了多种启动方式，适用于不同的操作系统环境。

## 🚀 快速启动

### Windows 用户

#### 方式一：批处理文件（推荐）
1. 双击 `start.bat` 文件
2. 或在命令提示符中运行：
   ```cmd
   start.bat
   ```

#### 方式二：PowerShell 脚本
1. 右键点击 `start.ps1` → "使用 PowerShell 运行"
2. 或在 PowerShell 中运行：
   ```powershell
   .\start.ps1
   ```

**注意**：如果遇到执行策略限制，请在 PowerShell 中运行：
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Linux/macOS 用户

#### 使用 Bash 脚本
```bash
chmod +x start.sh
./start.sh
```

### 手动启动（所有平台）

如果自动脚本无法运行，可以手动执行以下步骤：

1. **检查环境**
   ```bash
   docker --version
   docker-compose --version
   ```

2. **配置环境变量**
   ```bash
   cp .env.example .env
   # 编辑 .env 文件，添加 API 密钥
   ```

3. **启动服务**
   ```bash
   docker-compose up --build -d
   ```

4. **检查状态**
   ```bash
   docker-compose ps
   ```

## 🔧 常见问题

### Windows 特有问题

1. **Docker Desktop 未启动**
   - 确保 Docker Desktop 正在运行
   - 检查系统托盘中的 Docker 图标

2. **WSL2 未启用**
   - Docker Desktop 需要 WSL2 支持
   - 参考 [WSL2 安装指南](https://docs.microsoft.com/en-us/windows/wsl/install)

3. **端口占用**
   - 检查端口 8000、5555、5432、6379 是否被占用
   - 使用 `netstat -ano | findstr :8000` 检查端口状态

4. **防火墙阻止**
   - 确保 Windows 防火墙允许 Docker 网络访问

### 通用问题

1. **API 密钥未设置**
   - 确保 `.env` 文件中至少设置了一个 LLM API 密钥
   - 推荐设置 `OPENAI_API_KEY`

2. **内存不足**
   - 确保系统有足够的内存运行所有容器
   - 推荐至少 4GB 可用内存

3. **网络连接问题**
   - 确保能够访问 Docker Hub
   - 如在中国大陆，可能需要配置 Docker 镜像加速器

## 📊 验证部署

启动成功后，访问以下地址验证服务状态：

- **API 文档**: http://localhost:8000/docs
- **API 根路径**: http://localhost:8000
- **任务监控**: http://localhost:5555

## 🛑 停止服务

```bash
docker-compose down
```

## 🔄 重启服务

```bash
docker-compose restart
```

## 📝 查看日志

```bash
# 查看所有服务日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f api
docker-compose logs -f worker
```