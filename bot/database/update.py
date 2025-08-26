# 文件路径: /root/my_new_bot/database/upgrade_db.py
import sqlite3
import os

DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, 'main.db')

def upgrade_database():
    """为现有数据库安全地添加新功能 (V4)"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # --- 检查/升级旧表 ---
    try: c.execute("ALTER TABLE commands ADD COLUMN command_type TEXT NOT NULL DEFAULT 'script'")
    except: pass
    try: c.execute("ALTER TABLE commands ADD COLUMN reply_text TEXT")
    except: pass
    try: c.execute("ALTER TABLE users ADD COLUMN referred_by INTEGER")
    except: pass

    # --- [新增] 创建签到记录表 ---
    c.execute('''CREATE TABLE IF NOT EXISTS checkin_logs (
        user_id INTEGER PRIMARY KEY,
        last_checkin_date TEXT NOT NULL
    )''')
    print("-> `checkin_logs` 表已创建或已存在。")

    # --- [新增] 创建指令使用日志表 ---
    c.execute('''CREATE TABLE IF NOT EXISTS command_logs (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        command_name TEXT NOT NULL,
        timestamp TEXT NOT NULL
    )''')
    print("-> `command_logs` 表已创建或已存在。")

    # --- 更新 settings 表 ---
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    print("-> `settings` 表已创建或已存在。")

    default_settings = {
        'welcome_message': '注册成功，欢迎使用本机器人！',
        'force_join_enabled': '0',
        'force_join_chat_id': '',
        'force_join_invite_link': '',
        'referral_reward_points': '1',
        'checkin_enabled': '1', # [新增] 签到功能开关
        'checkin_reward_min': '1', # [新增] 签到最小奖励
        'checkin_reward_max': '5'  # [新增] 签到最大奖励
    }

    for key, value in default_settings.items():
        try:
            c.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (key, value))
            print(f"-> 默认设置 '{key}' 已插入。")
        except sqlite3.IntegrityError:
            print(f"-> 设置 '{key}' 已存在，跳过。")
    
    conn.commit()
    conn.close()
    print("\n数据库升级成功！")

if __name__ == '__main__':
    upgrade_database()