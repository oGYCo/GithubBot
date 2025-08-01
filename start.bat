@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo 🚀 启动 GitHub Bot 项目...
echo.

REM 检查 Docker 是否安装
docker --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker 未安装，请先安装 Docker Desktop
    pause
    exit /b 1
)

REM 检查 Docker Compose（优先用新版）
docker compose version >nul 2>&1
if errorlevel 1 (
    docker-compose --version >nul 2>&1
    if errorlevel 1 (
        echo ❌ 未检测到 Docker Compose，请先安装 Docker Compose
        pause
        exit /b 1
    ) else (
        set "COMPOSE_CMD=docker-compose"
    )
) else (
    set "COMPOSE_CMD=docker compose"
)

REM 检查 .env 文件
if not exist ".env" (
    echo ⚠️  .env 文件不存在，正在从 .env.example 复制...
    copy ".env.example" ".env" >nul
    echo 📝 请编辑 .env 文件，填入您的 API 密钥
    echo    至少需要设置一个 LLM API 密钥（如 OPENAI_API_KEY）
    set /p "edit_env=是否现在编辑 .env 文件？ (y/N): "
    if /i "!edit_env!"=="y" (
        notepad .env
    )
)

REM 创建 Docker 网络（如果不存在）
echo 🌐 检查并创建 Docker 网络...
docker network ls --filter name=github_bot_network --format "{{.Name}}" | findstr /x "github_bot_network" >nul 2>&1
if errorlevel 1 (
    docker network create github_bot_network >nul 2>&1
    if errorlevel 1 (
        echo ⚠️  创建网络时出现警告，继续执行...
    ) else (
        echo ✅ Docker 网络 github_bot_network 创建成功
    )
) else (
    echo ✅ Docker 网络 github_bot_network 已存在
)
echo.

REM 构建并启动服务
echo 🐳 构建和启动 Docker 容器...
%COMPOSE_CMD% up --build -d
if errorlevel 1 (
    echo ❌ Docker 容器启动失败
    pause
    exit /b 1
)

REM 等待服务启动
echo ⏳ 等待服务启动...
timeout /t 10 /nobreak >nul

REM 检查服务状态
echo 📊 检查服务状态...
%COMPOSE_CMD% ps

REM 显示访问信息
echo.
echo ✅ GitHub Bot 启动完成！
echo.
echo 🌐 访问地址：
echo    - API 文档: http://localhost:8000/docs
echo    - API 根路径: http://localhost:8000
echo    - Flower 监控: http://localhost:5555
echo.
echo 📋 常用命令：
echo    - 查看日志: %COMPOSE_CMD% logs -f
echo    - 停止服务: %COMPOSE_CMD% down
echo    - 重启服务: %COMPOSE_CMD% restart
echo.
echo 🔧 如果遇到问题，请检查：
echo    1. .env 文件中的 API 密钥是否正确
echo    2. 端口 8000、5555 是否被占用
echo    3. Docker Desktop 是否正常运行
echo    4. WSL2 是否已启用（Docker Desktop 需要）
echo.
pause