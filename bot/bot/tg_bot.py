import telebot
import sqlite3
import time
import subprocess
import random
import requests
import threading
from telebot import types
from datetime import datetime, date, timedelta

API_TOKEN = '666'
ADMIN_IDS = [666]
DB_PATH = '/root/bot/database/main.db'

# --- 全局设置变量 (从数据库加载) ---
SETTINGS = {
    'welcome_message': "注册成功，欢迎使用！(默认)",
    'force_join_enabled': False,
    'force_join_chat_id': None,
    'force_join_invite_link': None,
    'referral_reward_points': 1.0,
    'checkin_enabled': True,
    'checkin_reward_min': 1.0,
    'checkin_reward_max': 5.0,
    'recharge_usdt_address': None,
    'recharge_usdt_rate': 1.0
}
BOT_USERNAME = "YourBotUsername" # 默认值, 会在启动时尝试获取
ACTIVE_ORDERS = {} # 结构: {user_id: {'order_id': str, 'stop_event': threading.Event}}

# --- 支付监控配置 ---
TRONSCAN_API_URL = "https://apilist.tronscan.org/api/transaction"
USDT_CONTRACT_ADDRESS = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
ORDER_VALID_MINUTES = 10

# --- 数据库 & 工具函数 ---
def get_db_connection():
    """建立并返回数据库连接"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def escape_markdown_v2(text):
    """转义Markdown V2特殊字符"""
    if text is None: return ""
    text = str(text)
    special_characters = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_characters:
        text = text.replace(char, f'\\{char}')
    return text

def load_settings_and_commands():
    """从数据库加载设置和动态指令"""
    global SETTINGS
    try:
        conn = get_db_connection()
        settings_from_db = conn.execute("SELECT key, value FROM settings").fetchall()
        for row in settings_from_db:
            key, value = row['key'], row['value']
            if key in ['force_join_enabled', 'checkin_enabled']:
                SETTINGS[key] = (value == '1')
            elif key in ['referral_reward_points', 'checkin_reward_min', 'checkin_reward_max', 'recharge_usdt_rate']:
                SETTINGS[key] = float(value) if value else 0.0
            else:
                SETTINGS[key] = value
        
        commands = [row['name'] for row in conn.execute("SELECT name FROM commands WHERE is_enabled = 1").fetchall()]
        conn.close()
        print(f"Loaded settings: {SETTINGS}")
        return commands
    except Exception as e:
        print(f"致命错误: 无法从数据库加载配置: {e}")
        return []

# --- 支付监控核心功能 ---
def monitor_usdt_payment(user_id, order_id, amount_expected, points_to_add, stop_event):
    """在后台线程中监控USDT支付状态"""
    end_time = datetime.now() + timedelta(minutes=ORDER_VALID_MINUTES)
    print(f"开始监控订单 {order_id}，用户 {user_id}，金额 {amount_expected} USDT。")
    
    while datetime.now() < end_time:
        if stop_event.is_set():
            print(f"订单 {order_id} 的监控被手动停止。")
            return
        
        try:
            params = {
                'sort': '-timestamp', 'count': 'true', 'limit': '50',
                'to': SETTINGS['recharge_usdt_address'],
                'token': USDT_CONTRACT_ADDRESS
            }
            response = requests.get(TRONSCAN_API_URL, params=params, timeout=10)
            
            if response.status_code == 200:
                for tx in response.json().get('data', []):
                    tx_time = datetime.fromtimestamp(tx.get('timestamp') / 1000)
                    if tx_time > (datetime.now() - timedelta(minutes=ORDER_VALID_MINUTES)):
                        tx_amount = int(tx.get('amount', 0)) / 1_000_000
                        if abs(tx_amount - amount_expected) < 0.00001: # 精度匹配
                            conn = get_db_connection()
                            order_status = conn.execute("SELECT status FROM payment_orders WHERE order_id = ?", (order_id,)).fetchone()
                            if order_status and order_status['status'] == 'pending':
                                conn.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (points_to_add, user_id))
                                conn.execute("UPDATE payment_orders SET status = 'completed' WHERE order_id = ?", (order_id,))
                                conn.commit()
                                conn.close()
                                bot.send_message(user_id, f"✅ 充值成功！`{points_to_add}` 积分已到账。", parse_mode='MarkdownV2')
                                print(f"订单 {order_id} 完成。")
                                if user_id in ACTIVE_ORDERS:
                                    del ACTIVE_ORDERS[user_id]
                                return
                            else: # 如果订单状态不是pending，说明可能已被取消或处理
                                conn.close()
                                return
        except requests.exceptions.RequestException as e:
            print(f"检查TronScan API时网络错误: {e}")
        except Exception as e:
            print(f"检查支付时发生未知错误: {e}")
        
        stop_event.wait(20) # 等待20秒进行下一次查询

    # 循环结束，订单超时
    if user_id in ACTIVE_ORDERS:
        conn = get_db_connection()
        conn.execute("UPDATE payment_orders SET status = 'expired' WHERE order_id = ? AND status = 'pending'", (order_id,))
        conn.commit()
        conn.close()
        bot.send_message(user_id, "⌛️ 您的充值订单已超时，自动取消。")
        print(f"订单 {order_id} 超时。")
        del ACTIVE_ORDERS[user_id]

# --- 辅助函数 ---
def is_user_in_channel(user_id):
    """检查用户是否在强制加入的频道"""
    if not SETTINGS['force_join_enabled'] or not SETTINGS['force_join_chat_id']:
        return True
    try:
        member = bot.get_chat_member(SETTINGS['force_join_chat_id'], user_id)
        return member.status in ['creator', 'administrator', 'member']
    except Exception as e:
        print(f"检查用户是否在频道时出错: {e}")
        return False

def send_join_request_message(message):
    """发送要求用户加入频道的提示消息"""
    markup = types.InlineKeyboardMarkup()
    invite_link = SETTINGS['force_join_invite_link']
    chat_id = SETTINGS['force_join_chat_id']
    
    if invite_link:
        url = invite_link
    elif chat_id and chat_id.startswith('@'):
        url = f"https://t.me/{chat_id[1:]}"
    else: # 如果没有有效链接，则不发送按钮
        bot.reply_to(message, "请先加入我们的官方频道/群组后再进行操作。")
        return
        
    markup.add(types.InlineKeyboardButton("✅ 点击加入", url=url))
    bot.reply_to(message, "请先加入我们的官方频道/群组后再进行操作。", reply_markup=markup)

def log_command_usage(user_id, command_name):
    """记录用户指令使用情况"""
    try:
        conn = get_db_connection()
        conn.execute("INSERT INTO command_logs (user_id, command_name, timestamp) VALUES (?, ?, ?)", 
                     (user_id, command_name, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"记录指令使用日志时出错: {e}")

# --- Bot 初始化 ---
bot = telebot.TeleBot(API_TOKEN)
ALL_CONFIGURED_COMMANDS = load_settings_and_commands()
try:
    BOT_USERNAME = bot.get_me().username
except Exception as e:
    print(f"警告: 无法获取机器人用户名，将使用默认值。错误: {e}")

def send_startup_message():
    """向所有管理员发送机器人启动通知"""
    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(admin_id, f"✅ *机器人已成功启动并准备就绪\\!*", parse_mode='MarkdownV2')
        except Exception as e:
            print(f"向管理员 {admin_id} 发送启动通知失败: {e}")

# --- 静态指令处理器 ---
@bot.message_handler(commands=['start', 'me', 'qd', 'cz'])
def handle_static_commands(message):
    user_id = message.from_user.id
    command_parts = message.text.split()
    command = command_parts[0].lower()
    
    conn = get_db_connection()

    # 检查是否已注册 (除 /start 外)
    user = conn.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()
    if not user and command != '/start':
        bot.reply_to(message, "您尚未注册，请先使用 `/start` 开始。")
        conn.close()
        return
        
    # 检查是否加入频道
    if not is_user_in_channel(user_id):
        send_join_request_message(message)
        conn.close()
        return
    
    # 记录指令使用 (除 /start 外)
    if command != '/start':
        log_command_usage(user_id, command[1:])
    
    # --- /start 指令 ---
    if command == '/start':
        if not user: # 新用户
            join_name = message.from_user.username or "无用户名"
            referred_by_id = None
            if len(command_parts) > 1:
                try:
                    potential_referrer_id = int(command_parts[1])
                    if potential_referrer_id != user_id:
                        referred_by_id = potential_referrer_id
                except ValueError:
                    pass
            
            conn.execute('INSERT INTO users (user_id, join_date, join_name, referred_by) VALUES (?, ?, ?, ?)',
                         (user_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), join_name, referred_by_id))
            conn.commit()
            
            # 处理邀请奖励
            if referred_by_id and conn.execute("SELECT 1 FROM users WHERE user_id = ?", (referred_by_id,)).fetchone():
                reward = SETTINGS['referral_reward_points']
                conn.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (reward, referred_by_id))
                conn.commit()
                try:
                    bot.send_message(referred_by_id, f"🎉 您邀请的用户 `{escape_markdown_v2(join_name)}` 已注册，您获得了 `{escape_markdown_v2(reward)}` 积分！", parse_mode='MarkdownV2')
                except Exception as e:
                    print(f"发送邀请奖励通知失败: {e}")
        
        bot.reply_to(message, SETTINGS['welcome_message'], parse_mode='MarkdownV2', disable_web_page_preview=True)
    
    # --- /me 指令 ---
    elif command == '/me':
        response = (f"🆔 ID: `{escape_markdown_v2(user['user_id'])}`\n"
                    f"👤 用户名: @{escape_markdown_v2(user['join_name'])}\n"
                    f"💰 积分: `{escape_markdown_v2(user['points'])}`\n\n"
                    f"🔗 *您的专属邀请链接*:\n`https://t.me/{BOT_USERNAME}?start={user_id}`")
        bot.reply_to(message, response, parse_mode='MarkdownV2', disable_web_page_preview=True)
    
    # --- /checkin 指令 ---
    elif command == '/qd':
        if not SETTINGS['checkin_enabled']:
            bot.reply_to(message, "签到功能当前未开放。")
        else:
            today_str = date.today().strftime('%Y-%m-%d')
            last_checkin = conn.execute("SELECT last_checkin_date FROM checkin_logs WHERE user_id = ?", (user_id,)).fetchone()
            if last_checkin and last_checkin['last_checkin_date'] == today_str:
                bot.reply_to(message, "您今天已经签到过了，请明天再来吧！")
            else:
                reward = round(random.uniform(SETTINGS['checkin_reward_min'], SETTINGS['checkin_reward_max']), 2)
                conn.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (reward, user_id))
                conn.execute("INSERT OR REPLACE INTO checkin_logs (user_id, last_checkin_date) VALUES (?, ?)", (user_id, today_str))
                conn.commit()
                bot.reply_to(message, f"✅ 签到成功！🎁 您获得了 `{escape_markdown_v2(reward)}` 积分奖励！", parse_mode='MarkdownV2')
    
    # --- /recharge 指令 ---
    elif command == '/cz':
        if not SETTINGS.get('recharge_usdt_address'):
            bot.reply_to(message, "抱歉，当前未开启充值功能。")
        elif user_id in ACTIVE_ORDERS:
            bot.reply_to(message, "您当前有未完成的订单，请先处理或等待其超时。")
        else:
            try:
                points_to_recharge = float(command_parts[1])
                if points_to_recharge <= 0: raise ValueError
            except (IndexError, ValueError):
                bot.reply_to(message, "参数错误！\n格式: `/cz [积分数量]`\n例如: `/cz 100`")
                conn.close()
                return
            
            usdt_rate = SETTINGS.get('recharge_usdt_rate', 1.0)
            base_usdt_amount = points_to_recharge / usdt_rate
            # 增加一个随机微小量以区分不同订单
            final_usdt_amount = round(base_usdt_amount + random.randint(100, 999) / 100000.0, 5)
            order_id = f"ORDER-{user_id}-{int(time.time())}"
            
            conn.execute("INSERT INTO payment_orders (order_id, user_id, amount_expected, points_to_add, created_at, status) VALUES (?, ?, ?, ?, ?, ?)",
                         (order_id, user_id, final_usdt_amount, points_to_recharge, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'pending'))
            conn.commit()
            
            stop_event = threading.Event()
            ACTIVE_ORDERS[user_id] = {'order_id': order_id, 'stop_event': stop_event}
            
            threading.Thread(target=monitor_usdt_payment, args=(user_id, order_id, final_usdt_amount, points_to_recharge, stop_event)).start()
            
            markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("❌ 取消订单", callback_data=f"cancel_{order_id}"))
            
            response_text = (
                f"💰 *充值订单已创建*\n\n"
                f"请在 *{ORDER_VALID_MINUTES}分钟内* 向以下地址转账精确数量的USDT \\(TRC20\\)\n\n"
                f"⚠️ *金额必须完全一致，否则无法到账\\!*\n"
                f"数量: `{final_usdt_amount}`\n"
                f"地址: `{escape_markdown_v2(SETTINGS['recharge_usdt_address'])}`"
            )
            bot.reply_to(message, response_text, parse_mode='MarkdownV2', reply_markup=markup)

    conn.close()

# --- Callback Query 处理器 (处理取消订单按钮) ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('cancel_'))
def handle_cancel_order(call):
    user_id = call.from_user.id
    order_id_to_cancel = call.data.split('_')[1]

    try:
        if user_id in ACTIVE_ORDERS and ACTIVE_ORDERS[user_id]['order_id'] == order_id_to_cancel:
            # 停止监控线程
            ACTIVE_ORDERS[user_id]['stop_event'].set()
            
            # 更新数据库
            conn = get_db_connection()
            conn.execute("UPDATE payment_orders SET status = 'cancelled' WHERE order_id = ? AND user_id = ? AND status = 'pending'",
                         (order_id_to_cancel, user_id))
            conn.commit()
            conn.close()
            
            # 从活动订单列表中移除
            del ACTIVE_ORDERS[user_id]
            
            bot.edit_message_text("订单已成功取消。", call.message.chat.id, call.message.message_id)
            bot.answer_callback_query(call.id, "订单已取消！")
        else:
            bot.edit_message_text("此订单已失效或不存在。", call.message.chat.id, call.message.message_id)
            bot.answer_callback_query(call.id, "此订单已失效或不存在。", show_alert=True)
    except Exception as e:
        print(f"处理取消订单回调时出错: {e}")
        bot.answer_callback_query(call.id, "处理时发生错误。", show_alert=True)

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
    
    # 指令不存在或已禁用 (理论上不会触发，因为ALL_CONFIGURED_COMMANDS已筛选)
    if not command_info or not command_info['is_enabled']:
        conn.close()
        return

    user = conn.execute("SELECT points FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if not user:
        bot.reply_to(message, "未检测到您的注册信息，请先注册！")
        conn.close()
        return

    # 检查积分是否足够
    if user['points'] < command_info['cost']:
        bot.reply_to(message, f"积分不足。需要: `{escape_markdown_v2(command_info['cost'])}`", parse_mode='MarkdownV2')
        conn.close()
        return

    # 根据指令类型处理
    command_type = command_info['command_type']
    
    # 1. 纯文本回复类型
    if command_type == 'reply':
        conn.execute("UPDATE users SET points = points - ? WHERE user_id = ?", (command_info['cost'], user_id))
        conn.commit()
        bot.reply_to(message, command_info['reply_text'] or "...", parse_mode='MarkdownV2', disable_web_page_preview=True)
        conn.close()
        return
        
    # 2. 外部脚本执行类型
    elif command_type == 'script':
        # 检查参数数量
        num_expected_args = len(command_info['placeholder'].split()) if command_info['placeholder'] else 0
        if len(args) < num_expected_args:
            usage_text = f"参数错误！\n用法: `/{escape_markdown_v2(command_name)} {escape_markdown_v2(command_info['placeholder'])}`"
            bot.reply_to(message, usage_text, parse_mode='MarkdownV2')
            conn.close()
            return
        
        # 扣除积分
        conn.execute("UPDATE users SET points = points - ? WHERE user_id = ?", (command_info['cost'], user_id))
        conn.commit()
        
        processing_message = bot.reply_to(message, "`正在处理，请稍候...`", parse_mode='MarkdownV2')
        
        try:
            # 执行脚本
            result = subprocess.run(
                ['python3', command_info['script_path']] + args,
                capture_output=True, text=True, timeout=60, check=False
            )
            output = result.stdout.strip()
            
            # 如果脚本出错或无输出，则退还积分
            if result.returncode != 0 or not output:
                error_info = result.stderr.strip()
                print(f"脚本执行错误: {command_name}, stderr: {error_info}")
                response_text = "查询无结果或脚本出错，积分已退还。"
                conn.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (command_info['cost'], user_id))
                conn.commit()
            else:
                response_text = output
            
            # 编辑消息，显示结果
            bot.edit_message_text(
                f"```\n{escape_markdown_v2(response_text)}\n```",
                chat_id=processing_message.chat.id,
                message_id=processing_message.message_id,
                parse_mode='MarkdownV2'
            )
        except subprocess.TimeoutExpired:
            print(f"脚本 '{command_name}' 执行超时。")
            bot.edit_message_text("处理超时，积分已退还。", chat_id=processing_message.chat.id, message_id=processing_message.message_id)
            conn.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (command_info['cost'], user_id))
            conn.commit()
        except Exception as e:
            print(f"处理动态指令 '{command_name}' 时发生未知错误: {e}")
            bot.edit_message_text("机器人发生内部错误，积分已退还。", chat_id=processing_message.chat.id, message_id=processing_message.message_id)
            conn.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (command_info['cost'], user_id))
            conn.commit()
        finally:
            conn.close()

# --- 主程序入口 ---
if __name__ == "__main__":
    send_startup_message()
    while True:
        try:
            print("机器人正在运行...")
            bot.polling(none_stop=True, interval=0, timeout=30)
        except Exception as e:
            print(f"轮询时发生严重错误: {e}")
            print("将在15秒后重启轮询...")
            time.sleep(15)
