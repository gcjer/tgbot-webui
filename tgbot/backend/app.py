from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
import telebot
from functools import wraps
import subprocess
import os

# --- 配置 (请修改为你自己的) ---
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'a_very_strong_password_123'
DATABASE_PATH = '/root/my_new_bot/database/main.db'
BOT_TOKEN = 'YOUR_TELEGRAM_API_TOKEN'
SECRET_KEY = 'a_very_secret_key_for_flask_sessions'
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
        else:
            flash('用户名或密码错误', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

# --- 页面 ---
@app.route('/')
@login_required
def dashboard():
    conn = get_db_connection()
    user_count = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    command_count = conn.execute('SELECT COUNT(*) FROM commands WHERE is_enabled = 1').fetchone()[0]
    conn.close()
    return render_template('dashboard.html', user_count=user_count, command_count=command_count)

@app.route('/users')
@login_required
def list_users():
    conn = get_db_connection()
    users = conn.execute('SELECT * FROM users ORDER BY join_date DESC').fetchall()
    conn.close()
    return render_template('users.html', users=users)

@app.route('/commands')
@login_required
def list_commands():
    conn = get_db_connection()
    commands = conn.execute('SELECT * FROM commands ORDER BY name').fetchall()
    conn.close()
    return render_template('commands.html', commands=commands)

@app.route('/broadcast', methods=['GET', 'POST'])
@login_required
def broadcast():
    if request.method == 'POST':
        message = request.form['message']
        if not message:
            flash('消息内容不能为空!', 'warning')
            return redirect(url_for('broadcast'))
        try:
            bot = telebot.TeleBot(BOT_TOKEN)
            conn = get_db_connection()
            users = conn.execute('SELECT user_id FROM users').fetchall()
            conn.close()
            success, fail = 0, 0
            for user in users:
                try:
                    bot.send_message(user['user_id'], message, parse_mode='MarkdownV2')
                    success += 1
                except Exception: fail += 1
            flash(f'广播完成！成功: {success}, 失败: {fail}', 'info')
        except Exception as e: flash(f'广播时发生错误: {e}', 'danger')
        return redirect(url_for('broadcast'))
    return render_template('broadcast.html')

# --- 操作 ---
@app.route('/update_points', methods=['POST'])
@login_required
def update_points():
    try:
        conn = get_db_connection()
        conn.execute('UPDATE users SET points = ? WHERE user_id = ?', 
                     (float(request.form['points']), int(request.form['user_id'])))
        conn.commit()
        conn.close()
        flash(f'用户积分已更新!', 'success')
    except Exception as e: flash(f'更新失败: {e}', 'danger')
    return redirect(url_for('list_users'))

@app.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    flash(f'用户已删除!', 'success')
    return redirect(url_for('list_users'))

@app.route('/add_command', methods=['POST'])
@login_required
def add_command():
    try:
        conn = get_db_connection()
        conn.execute('INSERT INTO commands (name, cost, script_path, description, placeholder) VALUES (?, ?, ?, ?, ?)',
                     (request.form['name'].lower().strip(), float(request.form['cost']),
                      request.form['script_path'].strip(), request.form['description'], request.form['placeholder']))
        conn.commit()
        conn.close()
        flash(f"指令 `/{request.form['name']}` 添加成功! 请重启机器人使新指令生效。", 'success')
    except Exception as e: flash(f'添加失败: {e}', 'danger')
    return redirect(url_for('list_commands'))

@app.route('/update_command', methods=['POST'])
@login_required
def update_command():
    try:
        conn = get_db_connection()
        conn.execute('UPDATE commands SET cost=?, script_path=?, description=?, placeholder=?, is_enabled=? WHERE name=?',
                     (float(request.form['cost']), request.form['script_path'], request.form['description'],
                      request.form['placeholder'], 1 if 'is_enabled' in request.form else 0, request.form['original_name']))
        conn.commit()
        conn.close()
        flash(f"指令 `/{request.form['original_name']}` 更新成功!", 'success')
    except Exception as e: flash(f'更新失败: {e}', 'danger')
    return redirect(url_for('list_commands'))

@app.route('/delete_command/<name>', methods=['POST'])
@login_required
def delete_command(name):
    conn = get_db_connection()
    conn.execute('DELETE FROM commands WHERE name = ?', (name,))
    conn.commit()
    conn.close()
    flash(f'指令 `/{name}` 已删除!', 'success')
    return redirect(url_for('list_commands'))

@app.route('/restart_bot', methods=['POST'])
@login_required
def restart_bot():
    try:
        result = subprocess.run(['supervisorctl', 'restart', BOT_SUPERVISOR_PROGRAM_NAME], capture_output=True, text=True, check=True)
        flash(f'机器人 (`{BOT_SUPERVISOR_PROGRAM_NAME}`) 重启命令已发送!', 'info')
    except Exception as e:
        flash(f'重启失败: 请确保 Supervisor 已正确配置。错误: {e}', 'danger')
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)