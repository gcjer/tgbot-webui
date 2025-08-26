import telebot
import sqlite3
import time
import subprocess
import random
from telebot import types
from datetime import datetime, date


# --- 配置 (请修改为你自己的) ---
API_TOKEN = '123'
ADMIN_IDS = [123]
DB_PATH = '/root/bot/database/main.db'

# --- 全局设置变量 ---
SETTINGS = {
    'welcome_message': "注册成功，欢迎使用！(默认)",
    'force_join_enabled': False,
    'force_join_chat_id': None,
    'force_join_invite_link': None,
    'referral_reward_points': 1.0,
    'checkin_enabled': True,
    'checkin_reward_min': 1.0,
    'checkin_reward_max': 5.0
}
BOT_USERNAME = "YourBotUsername"

# --- 数据库连接 & Markdown转义 ---
def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def escape_markdown_v2(text):
    if text is None: return ""
    text = str(text)
    special_characters = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_characters: text = text.replace(char, f'\\{char}')
    return text

# --- 加载设置和指令 ---
def load_settings_and_commands():
    global SETTINGS
    try:
        conn = get_db_connection()
        settings_from_db = conn.execute("SELECT key, value FROM settings").fetchall()
        for row in settings_from_db:
            key, value = row['key'], row['value']
            if key in ['force_join_enabled', 'checkin_enabled']:
                SETTINGS[key] = (value == '1')
            elif key in ['referral_reward_points', 'checkin_reward_min', 'checkin_reward_max']:
                SETTINGS[key] = float(value)
            else:
                SETTINGS[key] = value
        
        commands = [row['name'] for row in conn.execute("SELECT name FROM commands").fetchall()]
        conn.close()
        print(f"Loaded settings: {SETTINGS}")
        print(f"Loaded commands for handler registration: {commands}")
        return commands
    except Exception as e:
        print(f"Fatal Error: Could not load settings/commands from DB: {e}")
        return []

# --- 辅助函数 ---
def is_user_in_channel(user_id):
    if not SETTINGS['force_join_enabled'] or not SETTINGS['force_join_chat_id']:
        return True
    try:
        member = bot.get_chat_member(SETTINGS['force_join_chat_id'], user_id)
        return member.status in ['creator', 'administrator', 'member']
    except:
        return False

def send_join_request_message(message):
    markup = types.InlineKeyboardMarkup()
    invite_link = SETTINGS['force_join_invite_link']
    chat_id = SETTINGS['force_join_chat_id']
    if invite_link:
        markup.add(types.InlineKeyboardButton("✅ 点击加入", url=invite_link))
    elif chat_id and chat_id.startswith('@'):
        markup.add(types.InlineKeyboardButton("✅ 点击加入", url=f"https://t.me/{chat_id[1:]}"))
    bot.reply_to(message, "请先加入我们的官方频道/群组后再进行操作。", reply_markup=markup)

def log_command_usage(user_id, command_name):
    try:
        conn = get_db_connection()
        conn.execute("INSERT INTO command_logs (user_id, command_name, timestamp) VALUES (?, ?, ?)",
                     (user_id, command_name, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error logging command usage: {e}")

# --- 初始化 ---
bot = telebot.TeleBot(API_TOKEN)
ALL_CONFIGURED_COMMANDS = load_settings_and_commands()
try:
    BOT_USERNAME = bot.get_me().username
except Exception as e:
    print(f"Warning: Could not get bot username. Using default. Error: {e}")

# --- 启动通知 ---
def send_startup_message():
    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(admin_id, f"*机器人已启动！*", parse_mode='MarkdownV2')
        except:
            pass

# --- 静态指令处理器 ---
@bot.message_handler(commands=['start', 'me', 'checkin'])
def handle_static_commands(message):
    user_id = message.from_user.id
    conn = get_db_connection()
    command = message.text.split()[0]
    
    if not is_user_in_channel(user_id):
        send_join_request_message(message)
        conn.close()
        return
    
    # 记录指令使用
    log_command_usage(user_id, command[1:])
    
    if command == '/start':
        is_new_user = not conn.execute('SELECT 1 FROM users WHERE user_id = ?', (user_id,)).fetchone()
        if is_new_user:
            join_name = message.from_user.username or "无用户名"
            referred_by_id = None
            parts = message.text.split()
            if len(parts) > 1:
                try:
                    potential_referrer_id = int(parts[1])
                    if potential_referrer_id != user_id: referred_by_id = potential_referrer_id
                except: pass
            conn.execute('INSERT INTO users (user_id, join_date, join_name, referred_by) VALUES (?, ?, ?, ?)', (user_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), join_name, referred_by_id))
            conn.commit()
            if referred_by_id:
                reward = SETTINGS['referral_reward_points']
                if conn.execute("SELECT 1 FROM users WHERE user_id = ?", (referred_by_id,)).fetchone():
                    conn.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (reward, referred_by_id)); conn.commit()
                    try: bot.send_message(referred_by_id, f"🎉 恭喜！您邀请的用户已成功注册，您获得了 `{reward}` 积分！", parse_mode='MarkdownV2')
                    except Exception as e: print(f"Failed to send referral notification: {e}")
        bot.reply_to(message, SETTINGS['welcome_message'], parse_mode='MarkdownV2', disable_web_page_preview=True)
    
    elif command == '/me':
        user = conn.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()
        if user:
            my_referral_link = f"`https://t.me/{BOT_USERNAME}?start={user_id}`"
            response = (f"🆔 *User ID*: `{escape_markdown_v2(user_id)}`\n" f"👤 *Username*: @{escape_markdown_v2(user['join_name'])}\n" f"💰 *Points*: `{escape_markdown_v2(user['points'])}`\n\n" f"🔗 *您的专属邀请链接*:\n{my_referral_link}")
        else: response = "您尚未注册，请先使用 `/start`。"
        bot.reply_to(message, response, parse_mode='MarkdownV2', disable_web_page_preview=True)
    
    elif command == '/checkin':
        if not SETTINGS['checkin_enabled']:
            bot.reply_to(message, "签到功能当前未开放。")
            conn.close()
            return

        today_str = date.today().strftime('%Y-%m-%d')
        last_checkin = conn.execute("SELECT last_checkin_date FROM checkin_logs WHERE user_id = ?", (user_id,)).fetchone()
        
        if last_checkin and last_checkin['last_checkin_date'] == today_str:
            bot.reply_to(message, "您今天已经签到过了，请明天再来吧！")
        else:
            min_reward = SETTINGS['checkin_reward_min']
            max_reward = SETTINGS['checkin_reward_max']
            reward = round(random.uniform(min_reward, max_reward), 2)
            
            conn.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (reward, user_id))
            conn.execute("INSERT OR REPLACE INTO checkin_logs (user_id, last_checkin_date) VALUES (?, ?)", (user_id, today_str))
            conn.commit()
            bot.reply_to(message, f"✅ 签到成功！\n🎁 您获得了 `{escape_markdown_v2(reward)}` 积分奖励！", parse_mode='MarkdownV2')

    conn.close()

# --- 动态指令处理器 ---
@bot.message_handler(commands=ALL_CONFIGURED_COMMANDS)
def generic_command_handler(message):
    user_id = message.from_user.id
    if not is_user_in_channel(user_id):
        send_join_request_message(message)
        return

    command_name = message.text.split()[0][1:]
    log_command_usage(user_id, command_name)

    args = message.text.split()[1:]
    conn = get_db_connection()
    command_info = conn.execute("SELECT * FROM commands WHERE name = ?", (command_name,)).fetchone()
    if not command_info or not command_info['is_enabled']: conn.close(); return
    user = conn.execute("SELECT points FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if not user: bot.reply_to(message, "您尚未注册。"); conn.close(); return
    if user['points'] < command_info['cost']: bot.reply_to(message, f"积分不足。需要: `{escape_markdown_v2(command_info['cost'])}`", parse_mode='MarkdownV2'); conn.close(); return

    command_type = command_info['command_type']
    if command_type == 'reply':
        conn.execute("UPDATE users SET points = points - ? WHERE user_id = ?", (command_info['cost'], user_id)); conn.commit()
        bot.reply_to(message, command_info['reply_text'] or "...", parse_mode='MarkdownV2', disable_web_page_preview=True)
        conn.close()
        return
    elif command_type == 'script':
        num_expected_args = len(command_info['placeholder'].split()) if command_info['placeholder'] else 0
        if len(args) < num_expected_args: bot.reply_to(message, f"参数错误！\n用法: `/{escape_markdown_v2(command_name)} {escape_markdown_v2(command_info['placeholder'])}`", parse_mode='MarkdownV2'); conn.close(); return
        conn.execute("UPDATE users SET points = points - ? WHERE user_id = ?", (command_info['cost'], user_id)); conn.commit()
        processing_message = bot.reply_to(message, "`正在处理...`", parse_mode='MarkdownV2')
        try:
            result = subprocess.run(['python3', command_info['script_path']] + args, capture_output=True, text=True, timeout=60)
            output = result.stdout.strip()
            if result.stderr or not output:
                response_text = "查询无结果或脚本出错，积分已退还。"
                conn.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (command_info['cost'], user_id)); conn.commit()
            else: response_text = output
            bot.edit_message_text(f"```\n{escape_markdown_v2(response_text)}\n```", chat_id=user_id, message_id=processing_message.message_id, parse_mode='MarkdownV2')
        except Exception as e:
            print(f"Handler error for '{command_name}': {e}")
            bot.edit_message_text("机器人发生内部错误，积分已退还。", chat_id=user_id, message_id=processing_message.message_id)
            conn.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (command_info['cost'], user_id)); conn.commit()
        finally: conn.close()

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