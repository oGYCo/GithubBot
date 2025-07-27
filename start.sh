#!/bin/bash

# 项目启动脚本

set -e

echo "🚀 启动 GitHub Bot 项目..."


# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装，请先安装 Docker"
    exit 1
fi

# 检查 Docker Compose（优先用新版）
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    echo "❌ 未检测到 Docker Compose，请先安装 Docker Compose"
    exit 1
fi

# 检查 .env 文件
if [ ! -f .env ]; then
    echo "⚠️  .env 文件不存在，正在从 .env.example 复制..."
    cp .env.example .env
    echo "📝 请编辑 .env 文件，填入您的 API 密钥"
    echo "   至少需要设置一个 LLM API 密钥（如 OPENAI_API_KEY）"
    read -p "是否现在编辑 .env 文件？ (y/N): " edit_env
    if [[ $edit_env =~ ^[Yy]$ ]]; then
        ${EDITOR:-nano} .env
    fi
fi

# 构建并启动服务
echo "🐳 构建和启动 Docker 容器..."
$COMPOSE_CMD up --build -d

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 10

# 检查服务状态
echo "📊 检查服务状态..."
$COMPOSE_CMD ps

# 显示访问信息
echo ""
echo "✅ GitHub Bot 启动完成！"
echo ""
echo "🌐 访问地址："
echo "   - API 文档: http://localhost:8000/docs"
echo "   - API 根路径: http://localhost:8000"
echo "   - Flower 监控: http://localhost:5555"
echo ""
echo "📋 常用命令："
echo "   - 查看日志: $COMPOSE_CMD logs -f"
echo "   - 停止服务: $COMPOSE_CMD down"
echo "   - 重启服务: $COMPOSE_CMD restart"
echo ""
echo "🔧 如果遇到问题，请检查："
echo "   1. .env 文件中的 API 密钥是否正确"
echo "   2. 端口 8000、5555 是否被占用"
echo "   3. Docker 服务是否正常运行"