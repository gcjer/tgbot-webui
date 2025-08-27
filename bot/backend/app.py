from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
import telebot
from functools import wraps
import subprocess
from datetime import datetime, date

# --- 配置 (请修改为你自己的) ---
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = '123'
DATABASE_PATH = '/root/bot/database/main.db'
BOT_TOKEN = '666'
SECRET_KEY = '123'
BOT_SUPERVISOR_PROGRAM_NAME = 'bot' # Supervisor中机器人的进程名

app = Flask(__name__)
app.secret_key = SECRET_KEY

# --- 数据库 & 登录 ---
def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'): return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == ADMIN_USERNAME and request.form['password'] == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else: flash('用户名或密码错误', 'danger')
    return render_template('login.html')
@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

# --- 页面路由 ---
@app.route('/')
@login_required
def dashboard():
    conn = get_db_connection(); today_str = date.today().strftime('%Y-%m-%d')
    stats = {
        'total_users': conn.execute('SELECT COUNT(*) FROM users').fetchone()[0],
        'today_new_users': conn.execute("SELECT COUNT(*) FROM users WHERE join_date LIKE ?", (today_str + '%',)).fetchone()[0],
        'today_commands_used': conn.execute("SELECT COUNT(*) FROM command_logs WHERE timestamp LIKE ?", (today_str + '%',)).fetchone()[0],
        'today_checkins': conn.execute("SELECT COUNT(*) FROM checkin_logs WHERE last_checkin_date = ?", (today_str,)).fetchone()[0]
    }
    leaderboards = {
        'points': conn.execute("SELECT join_name, points FROM users WHERE join_name IS NOT NULL ORDER BY points DESC LIMIT 10").fetchall(),
        'referrals': conn.execute("SELECT u.join_name, COUNT(r.user_id) as referral_count FROM users u JOIN users r ON u.user_id = r.referred_by WHERE u.join_name IS NOT NULL GROUP BY u.user_id ORDER BY referral_count DESC LIMIT 10").fetchall()
    }
    bot_status = "UNKNOWN"
    try:
        result = subprocess.run(['supervisorctl', 'status', BOT_SUPERVISOR_PROGRAM_NAME], capture_output=True, text=True)
        if "RUNNING" in result.stdout: bot_status = "RUNNING"
        elif "STOPPED" in result.stdout: bot_status = "STOPPED"
        else: bot_status = "ERROR"
    except Exception: bot_status = "UNAVAILABLE"
    conn.close()
    return render_template('dashboard.html', stats=stats, leaderboards=leaderboards, bot_status=bot_status)

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    conn = get_db_connection()
    if request.method == 'POST':
        form = request.form
        settings_to_save = {
            'welcome_message': form['welcome_message'],
            'referral_reward_points': form['referral_reward_points'],
            'force_join_enabled': '1' if 'force_join_enabled' in form else '0',
            'force_join_chat_id': form['force_join_chat_id'].strip(),
            'force_join_invite_link': form['force_join_invite_link'].strip(),
            'checkin_enabled': '1' if 'checkin_enabled' in form else '0',
            'checkin_reward_min': form['checkin_reward_min'],
            'checkin_reward_max': form['checkin_reward_max'],
            'recharge_usdt_address': form['recharge_usdt_address'].strip(),
            'recharge_usdt_rate': form['recharge_usdt_rate']
        }
        for key, value in settings_to_save.items():
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        conn.commit()
        flash('设置已成功保存! 部分设置需要重启机器人后生效。', 'success')
    settings_data = conn.execute("SELECT * FROM settings").fetchall()
    settings_dict = {row['key']: row['value'] for row in settings_data}
    conn.close()
    return render_template('settings.html', settings=settings_dict)

@app.route('/users')
@login_required
def list_users():
    conn = get_db_connection(); users = conn.execute('SELECT * FROM users ORDER BY join_date DESC').fetchall(); conn.close()
    return render_template('users.html', users=users)
@app.route('/commands')
@login_required
def list_commands():
    conn = get_db_connection(); commands = conn.execute('SELECT * FROM commands ORDER BY name').fetchall(); conn.close()
    return render_template('commands.html', commands=commands)
@app.route('/broadcast', methods=['GET', 'POST'])
@login_required
def broadcast():
    if request.method == 'POST':
        message = request.form.get('message', '')
        if not message: flash('消息内容不能为空!', 'warning'); return redirect(url_for('broadcast'))
        try:
            bot = telebot.TeleBot(BOT_TOKEN); conn = get_db_connection(); users = conn.execute('SELECT user_id FROM users').fetchall(); conn.close()
            success, fail = 0, 0
            for user in users:
                try: bot.send_message(user['user_id'], message, parse_mode='MarkdownV2'); success += 1
                except: fail += 1
            flash(f'广播完成！成功: {success}, 失败: {fail}', 'info')
        except Exception as e: flash(f'广播时发生错误: {e}', 'danger')
        return redirect(url_for('broadcast'))
    return render_template('broadcast.html')

# --- 操作路由 ---
@app.route('/update_points', methods=['POST'])
@login_required
def update_points():
    try:
        conn = get_db_connection(); conn.execute('UPDATE users SET points = ? WHERE user_id = ?', (float(request.form['points']), int(request.form['user_id']))); conn.commit(); conn.close()
        flash('用户积分已更新!', 'success')
    except Exception as e: flash(f'更新失败: {e}', 'danger')
    return redirect(url_for('list_users'))
@app.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    conn = get_db_connection(); conn.execute('DELETE FROM users WHERE user_id = ?', (user_id,)); conn.commit(); conn.close()
    flash('用户已删除!', 'success')
    return redirect(url_for('list_users'))
@app.route('/add_command', methods=['POST'])
@login_required
def add_command():
    try:
        conn = get_db_connection(); form = request.form
        conn.execute('INSERT INTO commands (name, cost, command_type, script_path, placeholder, reply_text) VALUES (?, ?, ?, ?, ?, ?)', (form['name'].lower().strip(), float(form['cost']), form['command_type'], form.get('script_path', '').strip(), form.get('placeholder', ''), form.get('reply_text', ''))); conn.commit(); conn.close()
        flash(f"指令 `/{form['name']}` 添加成功! 请重启机器人使新指令生效。", 'success')
    except Exception as e: flash(f'添加失败: {e}', 'danger')
    return redirect(url_for('list_commands'))
@app.route('/update_command', methods=['POST'])
@login_required
def update_command():
    try:
        conn = get_db_connection(); form = request.form
        conn.execute('UPDATE commands SET cost=?, script_path=?, placeholder=?, reply_text=?, is_enabled=? WHERE name=?',(float(form['cost']), form.get('script_path', ''), form.get('placeholder', ''),form.get('reply_text', ''), 1 if 'is_enabled' in form else 0, form['original_name'])); conn.commit(); conn.close()
        flash(f"指令 `/{form['original_name']}` 更新成功!", 'success')
    except Exception as e: flash(f'更新失败: {e}', 'danger')
    return redirect(url_for('list_commands'))
@app.route('/delete_command/<name>', methods=['POST'])
@login_required
def delete_command(name):
    conn = get_db_connection(); conn.execute('DELETE FROM commands WHERE name = ?', (name,)); conn.commit(); conn.close()
    flash(f'指令 `/{name}` 已删除!', 'success')
    return redirect(url_for('list_commands'))
@app.route('/restart_bot', methods=['POST'])
@login_required
def restart_bot():
    try:
        subprocess.run(['supervisorctl', 'restart', BOT_SUPERVISOR_PROGRAM_NAME], capture_output=True, text=True, check=True)
        flash(f'机器人 (`{BOT_SUPERVISOR_PROGRAM_NAME}`) 重启命令已发送!', 'info')
    except Exception as e:
        flash(f'重启失败: {e}', 'danger')
    return redirect(url_for('dashboard'))
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)
