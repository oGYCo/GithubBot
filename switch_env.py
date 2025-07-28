#!/usr/bin/env python3
"""
Environment switcher for GithubBot development

Usage:
  python switch_env.py docker   # Switch to Docker environment
  python switch_env.py local    # Switch to local development environment
"""

import sys
import shutil
import os
from pathlib import Path

def switch_environment(env_type: str):
    """Switch between Docker and local development environments"""
    project_root = Path(__file__).parent
    env_file = project_root / ".env"
    
    if env_type == "docker":
        # For Docker environment, use the current .env (already configured for Docker)
        print("✅ Switched to Docker environment")
        print("   - ChromaDB: chromadb:8000 (internal Docker network)")
        print("   - Redis: redis:6379 (internal Docker network)")
        print("   - PostgreSQL: postgres:5432 (internal Docker network)")
        print("\n🐳 Run: docker-compose up -d")
        
    elif env_type == "local":
        # For local development, copy .env.local to .env
        env_local = project_root / ".env.local"
        
        if not env_local.exists():
            print("❌ Error: .env.local file not found!")
            return False
            
        shutil.copy2(env_local, env_file)
        print("✅ Switched to local development environment")
        print("   - ChromaDB: localhost:8001 (connects to Docker ChromaDB)")
        print("   - Redis: localhost:6380 (connects to Docker Redis)")
        print("   - PostgreSQL: localhost:5432 (connects to Docker PostgreSQL)")
        print("\n🚀 Run local worker: celery -A src.worker.celery_app worker --loglevel=info")
        print("🚀 Run local API: uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload")
        
    else:
        print("❌ Error: Invalid environment type. Use 'docker' or 'local'")
        return False
        
    return True

def main():
    if len(sys.argv) != 2:
        print("Usage: python switch_env.py [docker|local]")
        sys.exit(1)
        
    env_type = sys.argv[1].lower()
    
    if switch_environment(env_type):
        print("\n📝 Environment configuration updated successfully!")
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()