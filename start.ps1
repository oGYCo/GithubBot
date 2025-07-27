# GitHub Bot 项目启动脚本 (PowerShell)
# 使用方法: 右键点击 -> 使用 PowerShell 运行

# 设置错误处理
$ErrorActionPreference = "Stop"

# 设置控制台编码为 UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "🚀 启动 GitHub Bot 项目..." -ForegroundColor Green
Write-Host ""

try {
    # 检查 Docker 是否安装
    Write-Host "🔍 检查 Docker 安装状态..." -ForegroundColor Yellow
    $null = docker --version
    Write-Host "✅ Docker 已安装" -ForegroundColor Green
}
catch {
    Write-Host "❌ Docker 未安装，请先安装 Docker Desktop" -ForegroundColor Red
    Write-Host "下载地址: https://www.docker.com/products/docker-desktop" -ForegroundColor Cyan
    Read-Host "按任意键退出"
    exit 1
}

# 检查 Docker Compose（优先用新版）
$composeCmd = ""
try {
    $null = docker compose version
    $composeCmd = "docker compose"
    Write-Host "✅ 使用 Docker Compose (新版)" -ForegroundColor Green
}
catch {
    try {
        $null = docker-compose --version
        $composeCmd = "docker-compose"
        Write-Host "✅ 使用 Docker Compose (传统版)" -ForegroundColor Green
    }
    catch {
        Write-Host "❌ 未检测到 Docker Compose，请先安装 Docker Compose" -ForegroundColor Red
        Read-Host "按任意键退出"
        exit 1
    }
}

# 检查 .env 文件
if (-not (Test-Path ".env")) {
    Write-Host "⚠️  .env 文件不存在，正在从 .env.example 复制..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "📝 请编辑 .env 文件，填入您的 API 密钥" -ForegroundColor Cyan
    Write-Host "   至少需要设置一个 LLM API 密钥（如 OPENAI_API_KEY）" -ForegroundColor Cyan
    
    $editEnv = Read-Host "是否现在编辑 .env 文件？ (y/N)"
    if ($editEnv -eq "y" -or $editEnv -eq "Y") {
        notepad .env
        Write-Host "请保存并关闭记事本后继续..." -ForegroundColor Yellow
        Read-Host "按任意键继续"
    }
}

# 构建并启动服务
Write-Host "🐳 构建和启动 Docker 容器..." -ForegroundColor Yellow
try {
    Invoke-Expression "$composeCmd up --build -d"
    Write-Host "✅ Docker 容器启动成功" -ForegroundColor Green
}
catch {
    Write-Host "❌ Docker 容器启动失败" -ForegroundColor Red
    Write-Host "错误信息: $($_.Exception.Message)" -ForegroundColor Red
    Read-Host "按任意键退出"
    exit 1
}

# 等待服务启动
Write-Host "⏳ 等待服务启动..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# 检查服务状态
Write-Host "📊 检查服务状态..." -ForegroundColor Yellow
Invoke-Expression "$composeCmd ps"

# 显示访问信息
Write-Host ""
Write-Host "✅ GitHub Bot 启动完成！" -ForegroundColor Green
Write-Host ""
Write-Host "🌐 访问地址：" -ForegroundColor Cyan
Write-Host "   - API 文档: http://localhost:8000/docs" -ForegroundColor White
Write-Host "   - API 根路径: http://localhost:8000" -ForegroundColor White
Write-Host "   - Flower 监控: http://localhost:5555" -ForegroundColor White
Write-Host ""
Write-Host "📋 常用命令：" -ForegroundColor Cyan
Write-Host "   - 查看日志: $composeCmd logs -f" -ForegroundColor White
Write-Host "   - 停止服务: $composeCmd down" -ForegroundColor White
Write-Host "   - 重启服务: $composeCmd restart" -ForegroundColor White
Write-Host ""
Write-Host "🔧 如果遇到问题，请检查：" -ForegroundColor Cyan
Write-Host "   1. .env 文件中的 API 密钥是否正确" -ForegroundColor White
Write-Host "   2. 端口 8000、5555 是否被占用" -ForegroundColor White
Write-Host "   3. Docker Desktop 是否正常运行" -ForegroundColor White
Write-Host "   4. WSL2 是否已启用（Docker Desktop 需要）" -ForegroundColor White
Write-Host "   5. 防火墙是否阻止了 Docker 网络" -ForegroundColor White
Write-Host ""

# 询问是否打开浏览器
$openBrowser = Read-Host "是否打开浏览器查看 API 文档？ (y/N)"
if ($openBrowser -eq "y" -or $openBrowser -eq "Y") {
    Start-Process "http://localhost:8000/docs"
}

Read-Host "按任意键退出"