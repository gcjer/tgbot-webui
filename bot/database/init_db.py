import sqlite3
import os
from datetime import datetime

# 获取当前脚本所在目录作为数据库目录
DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, 'main.db')

def initialize_database():
    """
    (最终版)
    创建一个全新的、包含所有功能的数据库。
    此脚本应在首次部署时运行。
    """
    if os.path.exists(DB_PATH):
        print(f"警告：数据库文件 '{DB_PATH}' 已存在。为防止数据丢失，初始化已中止。")
        print("如果您确定要重新创建，请先手动删除旧的数据库文件。")
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    print("正在创建数据库表...")

    # 1. 创建用户表 (包含邀请人字段)
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        join_date TEXT,
        join_name TEXT,
        points REAL DEFAULT 0,
        referred_by INTEGER
    )''')
    print("-> `users` 表已创建。")

    # 2. 创建指令表 (包含指令类型和回复文本字段)
    c.execute('''CREATE TABLE IF NOT EXISTS commands (
        name TEXT PRIMARY KEY,
        cost REAL NOT NULL DEFAULT 1,
        command_type TEXT NOT NULL DEFAULT 'script',
        script_path TEXT,
        placeholder TEXT,
        reply_text TEXT,
        is_enabled INTEGER NOT NULL DEFAULT 1
    )''')
    print("-> `commands` 表已创建。")

    # 3. 创建设置表
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
    print("-> `settings` 表已创建。")

    # 4. 创建签到记录表
    c.execute('''CREATE TABLE IF NOT EXISTS checkin_logs (
        user_id INTEGER PRIMARY KEY,
        last_checkin_date TEXT NOT NULL
    )''')
    print("-> `checkin_logs` 表已创建。")

    # 5. 创建指令使用日志表
    c.execute('''CREATE TABLE IF NOT EXISTS command_logs (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        command_name TEXT NOT NULL,
        timestamp TEXT NOT NULL
    )''')
    print("-> `command_logs` 表已创建。")

    print("\n正在插入默认数据...")

    # 插入一个示例指令
    c.execute("""
        INSERT INTO commands (name, cost, command_type, script_path, placeholder, reply_text, is_enabled)
        VALUES ('hello', 0, 'script', '/root/my_new_bot/scripts/hello.py', '你的名字', NULL, 1)
    """)
    print("-> 示例指令 '/hello' 已添加。")

    # 插入所有默认设置
    default_settings = {
        'welcome_message': '注册成功，欢迎使用本机器人！发送 /me 查看个人信息和邀请链接。',
        'force_join_enabled': '0',
        'force_join_chat_id': '',
        'force_join_invite_link': '',
        'referral_reward_points': '1',
        'checkin_enabled': '1',
        'checkin_reward_min': '1',
        'checkin_reward_max': '5'
    }
    for key, value in default_settings.items():
        c.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (key, value))
    
    print(f"-> {len(default_settings)} 条默认设置已插入。")

    conn.commit()
    conn.close()
    print("\n数据库初始化成功！")
    print(f"数据库文件已创建于: {DB_PATH}")

if __name__ == '__main__':
    initialize_database()