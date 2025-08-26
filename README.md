## 全部内容均由AI(Gemini)编写

## ✨ 核心功能

*   **强大的 Web 管理后台**:
    *   基于 Flask，提供直观的图形化界面。
    *   **增强型仪表盘**: 实时查看机器人状态、今日新增用户、指令使用次数、签到人数等核心指标。
    *   **用户排行榜**: 内置积分榜和邀请榜，激励用户参与。

*   **数据库驱动的动态指令**:
    *   无需修改代码，在后台即可添加、编辑、禁用或删除指令。
    *   支持**两种指令类型**：
        1.  **脚本执行型**: 调用服务器上的 Python 脚本并返回结果。
        2.  **文本回复型**: 直接回复后台预设的文本内容（支持 MarkdownV2）。

*   **完善的用户管理系统**:
    *   完整的用户注册与信息管理。
    *   强大的积分系统，可在后台手动修改用户积分。

*   **高阶运营功能**:
    *   **强制加入频道/群组**: 用户必须先加入指定频道才能使用机器人。
    *   **邀请奖励系统**: 用户可通过专属链接邀请新用户，成功后自动获得积分奖励。
    *   **每日签到功能**: 用户可通过 `/checkin` 指令每日签到，获取随机积分，提升用户黏性。

*   **后台全功能可配置**:
    *   所有核心功能（欢迎语、强制加入、邀请奖励、签到奖励等）均可在“机器人设置”页面进行配置，无需改动代码。

*   **生产环境就绪**:
    *   提供 Supervisor 配置文件，确保机器人和后台服务能够稳定、持久地在后台运行。

## 🛠️ 技术栈

*   **机器人**: Python 3, pyTelegramBotAPI
*   **Web 后台**: Flask
*   **数据库**: SQLite3 (轻量、无需配置)
*   **进程管理**: Supervisor

## 📂 项目结构

```
/bot/
|
|-- backend/                # Flask 后台应用
|   |-- app.py              # 后台核心逻辑
|   `-- templates/          # HTML 模板文件
|
|-- bot/                    # Telegram 机器人
|   `-- tg_bot.py           # 机器人核心逻辑
|
|-- database/               # 数据库相关
|   |-- main.db             # 数据库文件 (初始化后生成)
|   `-- init_db.py          # 数据库初始化脚本
|
|-- scripts/                # 存放指令调用的脚本
|   `-- hello.py            # 一个示例脚本
|
|-- supervisor_configs/     # Supervisor 配置文件
|   |-- bot.conf
|   `-- backend.conf
|
|-- requirements.txt        # Python 依赖包
`-- README.md               # 本文档
```

## 🚀 部署指南

本指南以 CentOS 为例。

### 1. 准备环境
确保你的服务器已安装 `python3`, `pip`, `git`, 和 `supervisor`。
```bash
sudo yum install epel-release -y
sudo yum install python3-pip git supervisor -y
```

### 2. 克隆项目
将本项目克隆到你的服务器。
```bash
git clone https://github.com/gcjer/tgbot-webui.git
cd /root/bot
```

### 3. 安装依赖
```bash
pip3 install -r requirements.txt
```

### 4. 初始化数据库
此操作将创建 `database/main.db` 文件及所有数据表。
```bash
python3 database/init_db.py
```
> **注意**: 此脚本仅在首次部署时运行。如果数据库已存在，脚本将安全退出以防覆盖数据。

### 5. 修改配置 (重要！)
你需要修改以下两个文件中的配置信息：

*   **机器人配置 (`bot/tg_bot.py`)**:
    *   `API_TOKEN`: 填入你从 @BotFather 获取的机器人TOKEN。
    *   `ADMIN_IDS`: 填入你的 Telegram User ID。

*   **后台配置 (`backend/app.py`)**:
    *   `ADMIN_USERNAME`: 设置你的后台登录用户名。
    *   `ADMIN_PASSWORD`: **务必修改为一个强密码！**
    *   `BOT_TOKEN`: 再次填入你的机器人TOKEN。

### 6. 配置 Supervisor
将配置文件链接到 Supervisor 的配置目录中，使其能够管理我们的服务。
```bash
sudo ln -s /root/bot/supervisor_configs/bot.conf /etc/supervisor/conf.d/bot.conf
sudo ln -s /root/bot/supervisor_configs/backend.conf /etc/supervisor/conf.d/backend.conf
```

### 7. 启动服务
使用 `supervisorctl` 来加载配置并启动机器人和后台。
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start bot backend
```

### 8. 验证
*   **检查服务状态**: `sudo supervisorctl status`。你应该能看到 `bot` 和 `backend` 都处于 `RUNNING` 状态。
*   **访问后台**: 在浏览器中打开 `http://你的服务器IP:5001`，使用你设置的用户名和密码登录。
*   **与机器人交互**: 找到你的机器人，发送 `/start` 指令。

## ⚙️ 管理与使用

### 后台管理
登录后台后，你可以：
*   在 **仪表盘** 查看机器人核心数据和排行榜。
*   在 **用户管理** 页面查看所有用户并修改他们的积分。
*   在 **指令管理** 页面添加、编辑或删除指令。
*   在 **机器人设置** 页面配置欢迎语、强制加入、邀请和签到等功能。
*   在 **广播消息** 页面向所有用户群发消息。

> **重要**: 当你在后台 **添加新指令** 或 **修改机器人设置** 后，需要返回 **仪表盘** 点击 **“重启机器人”** 按钮来使新配置生效。

### 机器人指令
*   `/start`: 注册并开始使用机器人。
*   `/me`: 查看你的个人信息、积分和专属邀请链接。
*   `/checkin`: 每日签到以获取随机积分奖励。
*   以及所有你在后台动态添加的指令。

### 如何添加一个新指令
1.  在 `scripts/` 目录下创建一个新的 Python 脚本 (例如 `my_script.py`)。
2.  登录后台，进入“指令管理”页面，点击“添加新指令”。
3.  选择指令类型为“执行脚本”。
4.  **指令名**: 填 `myscript` (无需 `/`)。
5.  **脚本绝对路径**: 填 `/root/bot/scripts/my_script.py`。
6.  填写其他信息（如消耗积分、参数提示）后，点击“确认添加”。
7.  返回“仪表盘”页面，点击“重启机器人”。几秒后，新指令 `/myscript` 就可以使用了！

## 📄 许可证
本项目采用 [MIT License](https://opensource.org/licenses/MIT) 授权。
