import asyncio
import logging
import os
import random
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, ChatMemberUpdatedFilter, IS_MEMBER, IS_NOT_MEMBER
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatMemberUpdated
from aiogram.utils.keyboard import InlineKeyboardBuilder
import sqlite3

# Конфигурация
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('chat_game.db')
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER,
            chat_id INTEGER,
            username TEXT,
            size REAL DEFAULT 0,
            last_up_time TIMESTAMP,
            PRIMARY KEY (user_id, chat_id)
        )
    ''')
    
    # Таблица настроек чата (приветствия/прощания)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_settings (
            chat_id INTEGER PRIMARY KEY,
            welcome_message TEXT DEFAULT '👋 Добро пожаловать, {username}! Рады видеть тебя в чате! 🎉\nНе забудь использовать /up чтобы начать расти! 📏',
            goodbye_message TEXT DEFAULT '😢 {username} покинул нас... Надеемся, ты ещё вернёшься! 👋'
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# Функции для работы с базой данных
def get_user_data(user_id, chat_id):
    conn = sqlite3.connect('chat_game.db')
    cursor = conn.cursor()
    cursor.execute('SELECT size, last_up_time FROM users WHERE user_id = ? AND chat_id = ?', 
                   (user_id, chat_id))
    result = cursor.fetchone()
    conn.close()
    return {'size': result[0], 'last_up_time': result[1]} if result else None

def update_user(user_id, chat_id, username, new_size):
    conn = sqlite3.connect('chat_game.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO users (user_id, chat_id, username, size, last_up_time)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id, chat_id) 
        DO UPDATE SET size = ?, last_up_time = ?, username = ?
    ''', (user_id, chat_id, username, new_size, datetime.now(), 
          new_size, datetime.now(), username))
    conn.commit()
    conn.close()

def get_top_users(chat_id, limit=10):
    conn = sqlite3.connect('chat_game.db')
    cursor = conn.cursor()
    cursor.execute('SELECT username, size FROM users WHERE chat_id = ? ORDER BY size DESC LIMIT ?', 
                   (chat_id, limit))
    top_users = cursor.fetchall()
    conn.close()
    return top_users

def get_chat_settings(chat_id):
    conn = sqlite3.connect('chat_game.db')
    cursor = conn.cursor()
    cursor.execute('SELECT welcome_message, goodbye_message FROM chat_settings WHERE chat_id = ?', 
                   (chat_id,))
    result = cursor.fetchone()
    conn.close()
    return result

def update_chat_settings(chat_id, welcome_message=None, goodbye_message=None):
    conn = sqlite3.connect('chat_game.db')
    cursor = conn.cursor()
    
    if welcome_message is not None:
        cursor.execute('''
            INSERT INTO chat_settings (chat_id, welcome_message) 
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET welcome_message = ?
        ''', (chat_id, welcome_message, welcome_message))
    
    if goodbye_message is not None:
        cursor.execute('''
            INSERT INTO chat_settings (chat_id, goodbye_message) 
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET goodbye_message = ?
        ''', (chat_id, goodbye_message, goodbye_message))
    
    conn.commit()
    conn.close()

# Проверка прав администратора
async def is_admin(chat_id, user_id):
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ['creator', 'administrator']
    except:
        return False

# Создание клавиатуры для добавления в чат
async def get_add_to_chat_keyboard():
    bot_info = await bot.get_me()
    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 Добавить бота в чат", url=f"https://t.me/{bot_info.username}?startgroup=true")
    return builder.as_markup()

# Обработчик входа нового участника
@dp.chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
async def on_user_join(event: ChatMemberUpdated):
    chat_id = event.chat.id
    user = event.new_chat_member.user
    username = user.username or user.first_name
    
    settings = get_chat_settings(chat_id)
    if settings and settings[0]:
        welcome_text = settings[0].replace('{username}', f'@{username}')
    else:
        welcome_text = f'👋 Добро пожаловать, @{username}! Рады видеть тебя в чате! 🎉\nНе забудь использовать /up чтобы начать расти! 📏'
    
    await bot.send_message(chat_id, welcome_text)

# Обработчик выхода участника
@dp.chat_member(ChatMemberUpdatedFilter(IS_MEMBER >> IS_NOT_MEMBER))
async def on_user_leave(event: ChatMemberUpdated):
    chat_id = event.chat.id
    user = event.old_chat_member.user
    username = user.username or user.first_name
    
    settings = get_chat_settings(chat_id)
    if settings and settings[1]:
        goodbye_text = settings[1].replace('{username}', f'@{username}')
    else:
        goodbye_text = f'😢 @{username} покинул нас... Надеемся, ты ещё вернёшься! 👋'
    
    await bot.send_message(chat_id, goodbye_text)

# Команда /start
@dp.message(Command('start'))
async def start_command(message: types.Message):
    if message.chat.type in ['group', 'supergroup']:
        help_text = """
🎮 Игровой бот для чата!

Доступные команды:
📏 /up - Увеличить свой размер (от 0.1 до 5 см, раз в 1 минуту)
📊 /size - Посмотреть свой текущий размер
🏆 /top - Топ-10 самых больших размеров в чате

Для админов:
📝 /set_welcome - Изменить приветствие
📝 /set_goodbye - Изменить прощание

Удачи в росте! 📈
        """
        await message.reply(help_text)
    else:
        welcome_text = """
👋 Привет! Я игровой бот для чатов!

🎮 В личных сообщениях доступны команды:
📏 /up - Увеличить размер (раз в 1 минуту)
🏆 /top - Топ-10 игроков в ЛС

⚠️ Для игры с друзьями добавь меня в групповой чат!

Добавь меня в свой чат и начни игру! 🚀
        """
        keyboard = await get_add_to_chat_keyboard()
        await message.answer(welcome_text, reply_markup=keyboard)

# Команда /help
@dp.message(Command('help'))
async def help_command(message: types.Message):
    if message.chat.type in ['group', 'supergroup']:
        help_text = """
🎮 Доступные команды в чате:

📏 /up - Увеличить размер (0.1-5 см, раз в 1 минуту)
📊 /size - Посмотреть свой размер
🏆 /top - Топ-10 игроков чата

Админ-команды:
📝 /set_welcome [текст] - Установить приветствие
📝 /set_goodbye [текст] - Установить прощание
📝 /reset_welcome - Сбросить приветствие
📝 /reset_goodbye - Сбросить прощание

Используйте {username} в тексте для упоминания пользователя
        """
        await message.reply(help_text)
    else:
        help_text = """
🎮 В личных сообщениях работают команды:

📏 /up - Увеличить размер (0.1-5 см, раз в 1 минуту)
🏆 /top - Топ-10 игроков в ЛС

💡 Для полного функционала добавь бота в групповой чат!
        """
        keyboard = await get_add_to_chat_keyboard()
        await message.answer(help_text, reply_markup=keyboard)

# Команда /up (работает в чатах и ЛС)
@dp.message(Command('up'))
async def up_command(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    
    # Определяем chat_id: для ЛС используем 0, для чатов - реальный chat_id
    if message.chat.type in ['group', 'supergroup']:
        chat_id = message.chat.id
    else:
        # В ЛС используем специальный chat_id = 0 для общего рейтинга
        chat_id = 0
    
    user_data = get_user_data(user_id, chat_id)
    
    # Проверка на время последнего использования (1 минута)
    if user_data and user_data['last_up_time']:
        last_up = datetime.strptime(user_data['last_up_time'], '%Y-%m-%d %H:%M:%S.%f')
        time_diff = datetime.now() - last_up
        
        if time_diff < timedelta(minutes=1):
            remaining_time = timedelta(minutes=1) - time_diff
            seconds = remaining_time.seconds
            await message.reply(f"⏳ @{username}, подожди ещё {seconds} сек. перед следующей попыткой!")
            return
    
    # Генерация случайного увеличения
    increase = round(random.uniform(0.1, 5.0), 1)
    current_size = user_data['size'] if user_data else 0
    new_size = round(current_size + increase, 1)
    
    # Сохранение в БД
    update_user(user_id, chat_id, username, new_size)
    
    # Отправка результата
    response = f"📏 @{username}, твой размер увеличился на {increase} см!\n"
    response += f"Текущий размер: {new_size} см"
    
    if message.chat.type == 'private':
        response += "\n\n💡 Это твой размер в общем рейтинге ЛС. В чатах размер считается отдельно!"
    
    if increase >= 4.5:
        response += "\n🔥 Легендарное увеличение!"
    elif increase >= 3:
        response += "\n✨ Отличный результат!"
    
    await message.reply(response)

# Команда /size
@dp.message(Command('size', 'mysize'))
async def size_command(message: types.Message):
    if message.chat.type not in ['group', 'supergroup']:
        keyboard = await get_add_to_chat_keyboard()
        await message.reply("❌ Эта команда работает только в групповых чатах!\n\n💡 В ЛС используй команды:\n📏 /up - увеличить размер\n🏆 /top - посмотреть рейтинг", 
                          reply_markup=keyboard)
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    username = message.from_user.username or message.from_user.first_name
    
    user_data = get_user_data(user_id, chat_id)
    
    if user_data:
        response = f"📏 @{username}, твой текущий размер: {user_data['size']} см"
    else:
        response = f"📏 @{username}, ты ещё не использовал команду /up"
    
    await message.reply(response)

# Команда /top (работает в чатах и ЛС)
@dp.message(Command('top'))
async def top_command(message: types.Message):
    # Определяем chat_id: для ЛС используем 0, для чатов - реальный chat_id
    if message.chat.type in ['group', 'supergroup']:
        chat_id = message.chat.id
        chat_type = "чате"
    else:
        chat_id = 0
        chat_type = "общем рейтинге ЛС"
    
    top_users = get_top_users(chat_id)
    
    if not top_users:
        await message.reply(f"🏆 В {chat_type} пока нет участников с размерами!")
        return
    
    response = f"🏆 ТОП-10 САМЫХ БОЛЬШИХ РАЗМЕРОВ В {chat_type.upper()}:\n\n"
    medals = ['🥇', '🥈', '🥉'] + ['📏'] * 7
    
    for i, (username, size) in enumerate(top_users, 1):
        medal = medals[i-1] if i <= len(medals) else '📏'
        response += f"{medal} {i}. @{username}: {size} см\n"
    
    if message.chat.type == 'private':
        response += "\n💡 Это общий рейтинг игроков в ЛС. В каждом чате свой отдельный рейтинг!"
    
    await message.reply(response)

# Команда /set_welcome (только для админов в чатах)
@dp.message(Command('set_welcome'))
async def set_welcome(message: types.Message):
    if message.chat.type not in ['group', 'supergroup']:
        await message.reply("❌ Эта команда работает только в групповых чатах!")
        return
    
    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply("❌ Только администраторы могут изменять приветствие!")
        return
    
    # Получаем текст после команды
    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) < 2:
        await message.reply("📝 Использование: /set_welcome [текст]\n\nМожно использовать {username} для упоминания пользователя\nПример: /set_welcome Привет, {username}! Добро пожаловать!")
        return
    
    welcome_text = command_parts[1]
    update_chat_settings(message.chat.id, welcome_message=welcome_text)
    
    # Показываем превью
    preview = welcome_text.replace('{username}', f'@{message.from_user.username or message.from_user.first_name}')
    await message.reply(f"✅ Приветствие установлено!\n\nПревью:\n{preview}")

# Команда /reset_welcome
@dp.message(Command('reset_welcome'))
async def reset_welcome(message: types.Message):
    if message.chat.type not in ['group', 'supergroup']:
        await message.reply("❌ Эта команда работает только в групповых чатах!")
        return
    
    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply("❌ Только администраторы могут сбрасывать приветствие!")
        return
    
    default_welcome = '👋 Добро пожаловать, {username}! Рады видеть тебя в чате! 🎉\nНе забудь использовать /up чтобы начать расти! 📏'
    update_chat_settings(message.chat.id, welcome_message=default_welcome)
    await message.reply(f"✅ Приветствие сброшено до стандартного:\n{default_welcome}")

# Команда /set_goodbye (только для админов)
@dp.message(Command('set_goodbye'))
async def set_goodbye(message: types.Message):
    if message.chat.type not in ['group', 'supergroup']:
        await message.reply("❌ Эта команда работает только в групповых чатах!")
        return
    
    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply("❌ Только администраторы могут изменять прощание!")
        return
    
    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) < 2:
        await message.reply("📝 Использование: /set_goodbye [текст]\n\nМожно использовать {username} для упоминания пользователя\nПример: /set_goodbye Пока, {username}! Возвращайся!")
        return
    
    goodbye_text = command_parts[1]
    update_chat_settings(message.chat.id, goodbye_message=goodbye_text)
    
    preview = goodbye_text.replace('{username}', f'@{message.from_user.username or message.from_user.first_name}')
    await message.reply(f"✅ Прощание установлено!\n\nПревью:\n{preview}")

# Команда /reset_goodbye
@dp.message(Command('reset_goodbye'))
async def reset_goodbye(message: types.Message):
    if message.chat.type not in ['group', 'supergroup']:
        await message.reply("❌ Эта команда работает только в групповых чатах!")
        return
    
    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply("❌ Только администраторы могут сбрасывать прощание!")
        return
    
    default_goodbye = '😢 {username} покинул нас... Надеемся, ты ещё вернёшься! 👋'
    update_chat_settings(message.chat.id, goodbye_message=default_goodbye)
    await message.reply(f"✅ Прощание сброшено до стандартного:\n{default_goodbye}")

# Обработка сообщений в ЛС
@dp.message(F.chat.type == "private")
async def handle_private_messages(message: types.Message):
    # Если это текстовая команда, которую мы не обработали
    if message.text and message.text.startswith('/'):
        await message.reply(
            "❌ В личных сообщениях работают только команды:\n\n"
            "📏 /up - Увеличить размер (раз в 1 минуту)\n"
            "🏆 /top - Посмотреть рейтинг\n\n"
            "Добавь бота в чат, чтобы использовать все функции! 👇",
            reply_markup=await get_add_to_chat_keyboard()
        )
    else:
        await message.answer(
            "👋 В личных сообщениях я поддерживаю команды:\n\n"
            "📏 /up - Увеличить размер (раз в 1 минуту)\n"
            "🏆 /top - Посмотреть рейтинг\n\n"
            "Добавь меня в чат для полного функционала! 🎮",
            reply_markup=await get_add_to_chat_keyboard()
        )

# Игнорирование неизвестных команд в чатах
@dp.message(F.text.startswith('/'))
async def handle_unknown_commands(message: types.Message):
    await message.reply("❓ Неизвестная команда. Используй /help для списка команд")

# Запуск бота
async def main():
    logger.info("Бот запущен...")
    logger.info("✓ База данных инициализирована")
    logger.info("✓ Интервал /up: 1 минута")
    logger.info("✓ В ЛС работают только команды /up и /top")
    logger.info("✓ Приветствия и прощания настраиваются админами")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
