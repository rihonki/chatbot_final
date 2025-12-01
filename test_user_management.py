#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
用户管理功能测试脚本
"""
import os
import sys
import json
from database import get_db, close_db

def test_user_management():
    """测试用户管理功能"""
    print("=== 开始测试用户管理功能 ===")
    
    try:
        # 获取数据库实例
        db = get_db()
        
        # 测试用户注册
        print("\n1. 测试用户注册")
        test_username = "testuser123"
        test_password = "Test@123456"
        
        success, message = db.register_user(test_username, test_password)
        print(f"  注册结果: {'成功' if success else '失败'} - {message}")
        
        # 测试重复注册
        print("  测试重复注册:")
        success, message = db.register_user(test_username, test_password)
        print(f"    注册结果: {'成功' if success else '失败'} - {message}")
        
        # 测试用户登录
        print("\n2. 测试用户登录")
        # 错误密码测试
        success, message = db.login_user(test_username, "wrongpassword")
        print(f"  错误密码测试: {'成功' if success else '失败'} - {message}")
        
        # 正确密码测试
        success, message = db.login_user(test_username, test_password)
        print(f"  正确密码测试: {'成功' if success else '失败'} - {message}")
        
        # 测试用户状态查询
        print("\n3. 测试用户状态查询")
        status_code, status_text = db.get_user_status(test_username)
        print(f"  {test_username} 的状态: {status_text}")
        
        # 查询不存在的用户
        status_code, status_text = db.get_user_status("nonexistentuser")
        print(f"  不存在用户的状态查询: {status_text}")
        
        # 测试用户下线
        print("\n4. 测试用户下线")
        success, message = db.logout_user(test_username)
        print(f"  下线结果: {'成功' if success else '失败'} - {message}")
        
        # 测试重复下线
        success, message = db.logout_user(test_username)
        print(f"  重复下线测试: {'成功' if success else '失败'} - {message}")
        
        # 再次查询用户状态
        status_code, status_text = db.get_user_status(test_username)
        print(f"  下线后状态: {status_text}")
        
        print("\n=== 测试完成 ===")
        
    except Exception as e:
        print(f"测试过程中发生错误: {str(e)}")
    finally:
        # 关闭数据库连接
        close_db()

def main():
    """主函数"""
    test_user_management()

if __name__ == "__main__":
    main()