
#### `database/init_db.py` (数据库初始化脚本)

```python
import sqlite3
import os

DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, 'main.db')

def initialize_database():
    """创建数据库和所有需要的表"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 创建用户表
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        join_date TEXT,
        join_name TEXT,
        points REAL DEFAULT 0
    )''')

    # 创建指令表
    c.execute('''CREATE TABLE IF NOT EXISTS commands (
        name TEXT PRIMARY KEY,
        cost REAL NOT NULL DEFAULT 1,
        script_path TEXT NOT NULL,
        description TEXT,
        placeholder TEXT,
        is_enabled INTEGER NOT NULL DEFAULT 1
    )''')

    # 检查是否已存在示例指令
    c.execute("SELECT 1 FROM commands WHERE name = 'hello'")
    if c.fetchone() is None:
        # 插入一个示例指令
        c.execute("""
            INSERT INTO commands (name, cost, script_path, description, placeholder, is_enabled)
            VALUES ('hello', 0, '/root/my_new_bot/scripts/hello.py', '一个简单的问候指令', '你的名字')
        """)
        print("示例指令 '/hello' 已添加。")

    conn.commit()
    conn.close()
    print("数据库初始化成功！")

if __name__ == '__main__':
    initialize_database()