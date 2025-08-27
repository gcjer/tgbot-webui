import sqlite3
import os

DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, 'main.db')

def upgrade_database():
    """为现有数据库安全地添加所有新功能"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    def add_column(table, column, definition):
        try:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            print(f"-> `{table}` 表已成功添加 '{column}' 字段。")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"-> `{table}` 表的 '{column}' 字段已存在，跳过。")
            else:
                raise e

    print("--- 检查/升级旧表 ---")
    add_column('commands', 'command_type', "TEXT NOT NULL DEFAULT 'script'")
    add_column('commands', 'reply_text', "TEXT")
    add_column('users', 'referred_by', "INTEGER")

    print("\n--- 正在创建/更新新表 ---")
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS checkin_logs (user_id INTEGER PRIMARY KEY, last_checkin_date TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS command_logs (log_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, command_name TEXT NOT NULL, timestamp TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS payment_orders (
        order_id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        amount_expected REAL NOT NULL,
        points_to_add REAL NOT NULL,
        created_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending' -- pending, completed, expired, cancelled
    )''')
    print("-> 所有表已创建或已存在。")

    print("\n--- 正在插入/更新默认设置 ---")
    default_settings = {
        'welcome_message': '注册成功，欢迎使用本机器人！',
        'force_join_enabled': '0',
        'force_join_chat_id': '',
        'force_join_invite_link': '',
        'referral_reward_points': '1',
        'checkin_enabled': '1',
        'checkin_reward_min': '1',
        'checkin_reward_max': '5',
        'recharge_usdt_address': '',
        'recharge_usdt_rate': '1'
    }
    for key, value in default_settings.items():
        try:
            c.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (key, value))
            print(f"-> 默认设置 '{key}' 已插入。")
        except sqlite3.IntegrityError:
            pass # 如果已存在，则静默跳过

    conn.commit()
    conn.close()
    print("\n数据库升级成功！")

if __name__ == '__main__':
    upgrade_database()
