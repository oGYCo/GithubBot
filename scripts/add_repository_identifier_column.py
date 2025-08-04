#!/usr/bin/env python3
"""
数据库迁移脚本：添加 repository_identifier 列到 analysis_sessions 表
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from src.db.session import engine
from src.utils.git_helper import GitHelper


def add_repository_identifier_column():
    """添加 repository_identifier 列到 analysis_sessions 表"""
    print("🚀 开始数据库迁移：添加 repository_identifier 列")
    
    with engine.connect() as conn:
        # 开始事务
        trans = conn.begin()
        
        try:
            # 检查列是否已经存在
            print("🔍 检查 repository_identifier 列是否已存在...")
            
            # PostgreSQL 检查列是否存在的查询
            check_column_query = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'analysis_sessions' 
                AND column_name = 'repository_identifier'
            """)
            
            result = conn.execute(check_column_query)
            existing_column = result.fetchone()
            
            if existing_column:
                print("✅ repository_identifier 列已存在，跳过创建")
            else:
                print("➕ 添加 repository_identifier 列...")
                
                # 添加新列
                add_column_query = text("""
                    ALTER TABLE analysis_sessions 
                    ADD COLUMN repository_identifier VARCHAR(128)
                """)
                conn.execute(add_column_query)
                
                # 创建索引
                create_index_query = text("""
                    CREATE INDEX IF NOT EXISTS ix_analysis_sessions_repository_identifier 
                    ON analysis_sessions (repository_identifier)
                """)
                conn.execute(create_index_query)
                
                print("✅ repository_identifier 列添加成功")
            
            # 更新现有记录的 repository_identifier 值
            print("🔄 更新现有记录的 repository_identifier 值...")
            
            # 获取所有没有 repository_identifier 值的记录
            select_query = text("""
                SELECT id, repository_url 
                FROM analysis_sessions 
                WHERE repository_identifier IS NULL 
                AND repository_url IS NOT NULL
            """)
            
            records = conn.execute(select_query).fetchall()
            
            if records:
                print(f"📋 找到 {len(records)} 条需要更新的记录")
                
                for record in records:
                    try:
                        # 为每个记录生成 repository_identifier
                        repo_identifier = GitHelper.generate_repository_identifier(record.repository_url)
                        
                        # 更新记录
                        update_query = text("""
                            UPDATE analysis_sessions 
                            SET repository_identifier = :repo_identifier 
                            WHERE id = :record_id
                        """)
                        
                        conn.execute(update_query, {
                            'repo_identifier': repo_identifier,
                            'record_id': record.id
                        })
                        
                        print(f"  📝 更新记录 ID {record.id}: {repo_identifier}")
                        
                    except Exception as e:
                        print(f"  ⚠️ 无法为记录 ID {record.id} 生成标识符: {e}")
                
                print("✅ 现有记录更新完成")
            else:
                print("ℹ️ 没有需要更新的记录")
            
            # 提交事务
            trans.commit()
            print("🎉 数据库迁移完成！")
            
        except Exception as e:
            # 回滚事务
            trans.rollback()
            print(f"❌ 数据库迁移失败: {e}")
            raise


if __name__ == "__main__":
    try:
        add_repository_identifier_column()
    except Exception as e:
        print(f"💥 迁移脚本执行失败: {e}")
        sys.exit(1)
