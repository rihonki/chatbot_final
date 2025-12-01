#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
用户管理系统主程序
提供用户注册、登录、下线和状态查询功能
"""
import os
import sys
import json
import time
from database import get_db, close_db

def clear_screen():
    """清屏函数"""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_menu():
    """打印菜单"""
    print("="*40)
    print("      用户管理系统")
    print("="*40)
    print("1. 用户注册")
    print("2. 用户登录")
    print("3. 用户下线")
    print("4. 查询用户状态")
    print("5. 退出系统")
    print("="*40)

def get_input(prompt, allow_empty=False):
    """获取用户输入，支持非空验证"""
    while True:
        value = input(prompt).strip()
        if value or allow_empty:
            return value
        print("输入不能为空，请重新输入！")

def register_user(db):
    """用户注册功能"""
    clear_screen()
    print("用户注册")
    print("-"*30)
    
    username = get_input("请输入用户名: ")
    password = get_input("请输入密码: ")
    
    print("正在注册...")
    time.sleep(0.5)
    
    success, message = db.register_user(username, password)
    if success:
        print(f"✓ {message}")
    else:
        print(f"✗ {message}")
    
    input("按回车键继续...")

def login_user(db):
    """用户登录功能"""
    clear_screen()
    print("用户登录")
    print("-"*30)
    
    username = get_input("请输入用户名: ")
    password = get_input("请输入密码: ")
    
    print("正在登录...")
    time.sleep(0.5)
    
    success, message = db.login_user(username, password)
    if success:
        print(f"✓ {message}")
    else:
        print(f"✗ {message}")
    
    input("按回车键继续...")

def logout_user(db):
    """用户下线功能"""
    clear_screen()
    print("用户下线")
    print("-"*30)
    
    username = get_input("请输入要下线的用户名: ")
    
    print("正在处理...")
    time.sleep(0.5)
    
    success, message = db.logout_user(username)
    if success:
        print(f"✓ {message}")
    else:
        print(f"✗ {message}")
    
    input("按回车键继续...")

def query_user_status(db):
    """查询用户状态功能"""
    clear_screen()
    print("查询用户状态")
    print("-"*30)
    
    username = get_input("请输入要查询的用户名: ")
    
    print("正在查询...")
    time.sleep(0.5)
    
    status_code, status_text = db.get_user_status(username)
    if status_code is not None:
        print(f"✓ 用户 {username} 当前状态: {status_text}")
    else:
        print(f"✗ {status_text}")
    
    input("按回车键继续...")

def main():
    """主函数"""
    db = get_db()
    
    try:
        while True:
            clear_screen()
            print_menu()
            
            choice = get_input("请选择操作 (1-5): ")
            
            if choice == '1':
                register_user(db)
            elif choice == '2':
                login_user(db)
            elif choice == '3':
                logout_user(db)
            elif choice == '4':
                query_user_status(db)
            elif choice == '5':
                print("感谢使用，再见！")
                break
            else:
                print("无效的选择，请重新输入！")
                time.sleep(1)
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"程序运行出错: {str(e)}")
    finally:
        close_db()

if __name__ == "__main__":
    main()