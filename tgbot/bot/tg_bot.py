import telebot
import sqlite3
import time
import subprocess
from telebot import types
from datetime import datetime
import os

# --- 配置 (请修改为你自己的) ---
API_TOKEN = 'YOUR_TELEGRAM_API_TOKEN'
ADMIN_IDS = [123456789] # 你的管理员 Telegram ID
DB_PATH = '/root/my_new_bot/database/main.db'

# --- 数据库连接 ---
def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# --- MarkdownV2 转义函数 ---
def escape_markdown_v2(text):
    if text is None: return ""
    text = str(text)
    special_characters = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_characters: text = text.replace(char, f'\\{char}')
    return text

# --- 加载指令 ---
def load_all_commands_from_db():
    try:
        conn = get_db_connection()
        commands = [row['name'] for row in conn.execute("SELECT name FROM commands").fetchall()]
        conn.close()
        print(f"Loaded commands for handler registration: {commands}")
        return commands
    except Exception as e:
        print(f"Fatal Error: Could not load commands from DB: {e}")
        return []

# --- 初始化 ---
bot = telebot.TeleBot(API_TOKEN)
ALL_CONFIGURED_COMMANDS = load_all_commands_from_db()

# --- 启动通知 ---
def send_startup_message():
    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(admin_id, f"*机器人已启动！*\n配置指令数量: `{len(ALL_CONFIGURED_COMMANDS)}`个", parse_mode='MarkdownV2')
        except Exception as e:
            print(f"Failed to send startup message to {admin_id}: {e}")

# --- 静态指令处理器 ---
@bot.message_handler(commands=['start', 'me'])
def handle_static_commands(message):
    user_id = message.from_user.id
    conn = get_db_connection()
    command = message.text.split()[0]
    
    if command == '/start':
        join_name = message.from_user.username or "无用户名"
        if not conn.execute('SELECT 1 FROM users WHERE user_id = ?', (user_id,)).fetchone():
            conn.execute('INSERT INTO users (user_id, join_date, join_name, points) VALUES (?, ?, ?, ?)',
                         (user_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), join_name, 0))
            conn.commit()
        bot.reply_to(message, "注册成功，欢迎使用！", parse_mode='MarkdownV2')
    
    elif command == '/me':
        user = conn.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()
        if user:
            response = (f"🆔 *User ID*: `{escape_markdown_v2(user_id)}`\n"
                        f"👤 *Username*: @{escape_markdown_v2(user['join_name'])}\n"
                        f"📅 *Registration Date*: `{escape_markdown_v2(user['join_date'])}`\n"
                        f"💰 *Points*: `{escape_markdown_v2(user['points'])}`")
        else:
            response = "未找到您的个人信息，请先使用 `/start` 注册。"
        bot.reply_to(message, response, parse_mode='MarkdownV2')
    
    conn.close()

# --- 动态指令处理器 ---
@bot.message_handler(commands=ALL_CONFIGURED_COMMANDS)
def generic_command_handler(message):
    user_id = message.from_user.id
    command_name = message.text.split()[0][1:]
    args = message.text.split()[1:]
    conn = get_db_connection()
    
    command_info = conn.execute("SELECT * FROM commands WHERE name = ?", (command_name,)).fetchone()
    if not command_info or not command_info['is_enabled']:
        conn.close()
        return
    
    user = conn.execute("SELECT points FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if not user:
        bot.reply_to(message, "您尚未注册，请使用 `/start` 注册。")
        conn.close()
        return
    
    if user['points'] < command_info['cost']:
        bot.reply_to(message, f"积分不足。本次查询需要: `{escape_markdown_v2(command_info['cost'])}`", parse_mode='MarkdownV2')
        conn.close()
        return
        
    num_expected_args = len(command_info['placeholder'].split()) if command_info['placeholder'] else 0
    if len(args) < num_expected_args:
        bot.reply_to(message, f"参数错误！\n用法: `/{escape_markdown_v2(command_name)} {escape_markdown_v2(command_info['placeholder'])}`", parse_mode='MarkdownV2')
        conn.close()
        return

    conn.execute("UPDATE users SET points = points - ? WHERE user_id = ?", (command_info['cost'], user_id))
    conn.commit()
    processing_message = bot.reply_to(message, "`正在处理，请稍候...`", parse_mode='MarkdownV2')
    
    try:
        result = subprocess.run(['python3', command_info['script_path']] + args, capture_output=True, text=True, timeout=60)
        output = result.stdout.strip()
        
        if result.stderr or not output:
            response_text = "查询无结果或脚本出错，积分已退还。"
            conn.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (command_info['cost'], user_id))
            conn.commit()
        else:
            response_text = output
        
        bot.edit_message_text(f"```\n{escape_markdown_v2(response_text)}\n```", chat_id=user_id, message_id=processing_message.message_id, parse_mode='MarkdownV2')
    
    except Exception as e:
        print(f"Handler error for '{command_name}': {e}")
        bot.edit_message_text("机器人发生内部错误，积分已退还。", chat_id=user_id, message_id=processing_message.message_id)
        conn.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (command_info['cost'], user_id))
        conn.commit()
    finally:
        conn.close()

# --- 主循环 ---
if __name__ == "__main__":
    send_startup_message()
    while True:
        try:
            print("Bot is polling...")
            bot.polling(none_stop=True)
        except Exception as e:
            print(f"Polling error: {e}")
            time.sleep(15)