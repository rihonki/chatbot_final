import sqlite3
import json
import logging
import os
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path='chat_history.db'):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self._init_database()
    
    def _init_database(self):
        """初始化数据库，创建必要的表"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
            
            # 创建用户表
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                online_status INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
            ''')
            
            # 创建消息表
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT NOT NULL,
                message_type TEXT NOT NULL,  -- message, ai_message, movie_message, system_message
                content TEXT NOT NULL,
                additional_data TEXT,  -- 存储额外数据，如iframe_src等，使用JSON格式
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            ''')
            
            # 创建会话表（用于管理聊天会话）
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL UNIQUE,
                user_id INTEGER,
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            ''')
            
            self.conn.commit()
            logger.info("数据库初始化成功")
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            if self.conn:
                self.conn.rollback()
    
    def hash_password(self, password):
        """对密码进行哈希加密"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def user_exists(self, username):
        """检查用户是否存在"""
        try:
            self.cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            return self.cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"检查用户是否存在失败: {e}")
            return False
    
    def update_user_status(self, username, is_online):
        """更新用户在线状态"""
        try:
            self.cursor.execute("UPDATE users SET is_online = ? WHERE username = ?", 
                               (1 if is_online else 0, username))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"更新用户状态失败: {e}")
            self.conn.rollback()
            return False
    
    def register_user(self, username, password):
        """用户注册功能"""
        try:
            # 检查用户名是否已存在
            self.cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            if self.cursor.fetchone():
                return False, "用户名已存在"
            
            # 对密码进行哈希处理
            hashed_password = self.hash_password(password)
            
            # 插入新用户
            self.cursor.execute(
                "INSERT INTO users (username, password, online_status) VALUES (?, ?, 0)",
                (username, hashed_password)
            )
            self.conn.commit()
            return True, "注册成功"
        except sqlite3.IntegrityError:
            logger.error(f"注册失败：用户名已存在 - {username}")
            return False, "用户名已存在"
        except Exception as e:
            logger.error(f"注册用户失败: {e}")
            if self.conn:
                self.conn.rollback()
            return False, f"注册失败：{str(e)}"
    
    def login_user(self, username, password):
        """用户登录功能"""
        try:
            # 查询用户是否存在
            self.cursor.execute("SELECT id, password FROM users WHERE username = ?", (username,))
            result = self.cursor.fetchone()
            
            if not result:
                return False, "用户名或密码错误"
            
            user_id, stored_password = result
            
            # 验证密码
            if self.hash_password(password) != stored_password:
                return False, "用户名或密码错误"
            
            # 更新在线状态和最后登录时间
            self.cursor.execute(
                "UPDATE users SET online_status = 1, last_login = CURRENT_TIMESTAMP WHERE id = ?",
                (user_id,)
            )
            self.conn.commit()
            return True, "登录成功"
        except Exception as e:
            logger.error(f"用户登录失败: {e}")
            return False, f"登录失败：{str(e)}"
    
    def logout_user(self, username):
        """用户下线功能"""
        try:
            # 检查用户是否存在且在线
            self.cursor.execute("SELECT id, online_status FROM users WHERE username = ?", (username,))
            result = self.cursor.fetchone()
            
            if not result:
                return False, "用户不存在"
            
            user_id, online_status = result
            
            if online_status == 0:
                return False, "用户已经处于离线状态"
            
            # 更新为离线状态
            self.cursor.execute("UPDATE users SET online_status = 0 WHERE id = ?", (user_id,))
            self.conn.commit()
            return True, "下线成功"
        except Exception as e:
            logger.error(f"用户下线失败: {e}")
            if self.conn:
                self.conn.rollback()
            return False, f"下线失败：{str(e)}"
    
    def get_user_status(self, username):
        """查询用户在线状态"""
        try:
            self.cursor.execute("SELECT online_status FROM users WHERE username = ?", (username,))
            result = self.cursor.fetchone()
            
            if not result:
                return None, "用户不存在"
            
            return result[0], "在线" if result[0] == 1 else "离线"
        except Exception as e:
            logger.error(f"获取用户状态失败: {e}")
            return None, f"查询失败：{str(e)}"
    
    def get_user_id(self, username):
        """获取用户ID，如果不存在则创建"""
        try:
            self.cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            result = self.cursor.fetchone()
            
            if result:
                # 更新最后登录时间
                self.cursor.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (result[0],))
                self.conn.commit()
                return result[0]
            else:
                # 创建新用户（为保持兼容性，密码使用默认值）
                default_password = self.hash_password("default_password")
                self.cursor.execute("INSERT INTO users (username, password, online_status) VALUES (?, ?, 0)", 
                                   (username, default_password))
                self.conn.commit()
                return self.cursor.lastrowid
        except Exception as e:
            logger.error(f"获取用户ID失败: {e}")
            return None
    
    def save_message(self, username, message_type, content, additional_data=None):
        """保存消息到数据库"""
        try:
            user_id = self.get_user_id(username)
            additional_data_str = json.dumps(additional_data) if additional_data else None
            
            self.cursor.execute(
                "INSERT INTO messages (user_id, username, message_type, content, additional_data) VALUES (?, ?, ?, ?, ?)",
                (user_id, username, message_type, content, additional_data_str)
            )
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"保存消息失败: {e}")
            if self.conn:
                self.conn.rollback()
            return False
    
    def get_history_messages(self, limit=100, offset=0, search=None, username=None):
        """获取历史消息，支持搜索和用户名过滤"""
        try:
            # 构建基础查询
            query = '''
            SELECT username, message_type, content, additional_data, timestamp 
            FROM messages 
            WHERE 1=1
            '''
            params = []
            
            # 添加用户名过滤条件
            if username:
                query += ' AND username = ?'
                params.append(username)
            
            # 添加搜索条件
            if search:
                query += ' AND content LIKE ?'
                params.append(f'%{search}%')
            
            # 添加排序和分页
            query += ' ORDER BY timestamp DESC LIMIT ? OFFSET ?'
            params.extend([limit, offset])
            
            # 执行查询
            self.cursor.execute(query, params)
            
            messages = []
            for row in self.cursor.fetchall():
                message = {
                    'username': row[0],
                    'type': row[1],
                    'content': row[2],
                    'timestamp': row[4]
                }
                if row[3]:
                    try:
                        message['additional_data'] = json.loads(row[3])
                    except:
                        message['additional_data'] = {}
                messages.append(message)
            
            # 按时间正序返回
            messages.reverse()
            return messages
        except Exception as e:
            logger.error(f"获取历史消息失败: {e}")
            return []
    
    def get_user_messages(self, username, limit=50):
        """获取指定用户的消息"""
        try:
            self.cursor.execute('''
            SELECT message_type, content, additional_data, timestamp 
            FROM messages 
            WHERE username = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
            ''', (username, limit))
            
            messages = []
            for row in self.cursor.fetchall():
                message = {
                    'type': row[0],
                    'content': row[1],
                    'timestamp': row[3]
                }
                if row[2]:
                    try:
                        message['additional_data'] = json.loads(row[2])
                    except:
                        message['additional_data'] = {}
                messages.append(message)
            
            # 按时间正序返回
            messages.reverse()
            return messages
        except Exception as e:
            logger.error(f"获取用户消息失败: {e}")
            return []
    
    def save_session(self, session_id, user_id):
        """保存会话信息"""
        try:
            self.cursor.execute(
                "INSERT INTO sessions (session_id, user_id) VALUES (?, ?)",
                (session_id, user_id)
            )
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"保存会话失败: {e}")
            return False
    
    def end_session(self, session_id):
        """结束会话"""
        try:
            self.cursor.execute(
                "UPDATE sessions SET end_time = CURRENT_TIMESTAMP WHERE session_id = ?",
                (session_id,)
            )
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"结束会话失败: {e}")
            return False
    
    def update_user_status(self, username, status):
        """更新用户在线状态"""
        try:
            # 将布尔状态转换为整数
            status_int = 1 if status else 0
            
            # 更新用户状态
            self.cursor.execute(
                "UPDATE users SET online_status = ? WHERE username = ?",
                (status_int, username)
            )
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"更新用户状态失败: {e}")
            if self.conn:
                self.conn.rollback()
            return False
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            logger.info("数据库连接已关闭")

# 全局数据库管理器实例
db_manager = None

def get_db():
    """获取数据库管理器实例"""
    global db_manager
    if db_manager is None:
        db_manager = DatabaseManager()
    return db_manager

# 在应用关闭时关闭数据库连接
def close_db():
    global db_manager
    if db_manager:
        db_manager.close()