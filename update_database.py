#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
更新数据库结构，为users表添加password和online_status字段
"""
import sqlite3
import hashlib
import logging
import os

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def update_database_structure():
    """更新数据库结构"""
    try:
        # 连接数据库
        conn = sqlite3.connect('chat_history.db')
        cursor = conn.cursor()
        
        logger.info("开始更新数据库结构...")
        
        # 添加password字段
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN password TEXT NOT NULL DEFAULT 'default'")
            logger.info("添加password字段成功")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                logger.info("password字段已存在")
            else:
                logger.error(f"添加password字段失败: {e}")
        
        # 添加online_status字段
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN online_status INTEGER DEFAULT 0")
            logger.info("添加online_status字段成功")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                logger.info("online_status字段已存在")
            else:
                logger.error(f"添加online_status字段失败: {e}")
        
        # 更新现有记录的密码为哈希值
        cursor.execute("SELECT id FROM users")
        user_ids = cursor.fetchall()
        
        for user_id, in user_ids:
            # 使用默认密码的哈希值更新
            default_hash = hashlib.sha256("default_password".encode()).hexdigest()
            cursor.execute("UPDATE users SET password = ? WHERE id = ?", (default_hash, user_id))
        
        conn.commit()
        logger.info("数据库结构更新完成")
        print("数据库结构更新成功！")
        
    except Exception as e:
        logger.error(f"更新数据库结构失败: {e}")
        print(f"更新数据库结构失败: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

def main():
    """主函数"""
    update_database_structure()

if __name__ == "__main__":
    main()