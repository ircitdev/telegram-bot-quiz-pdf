"""
Модуль для логирования действий пользователей в супергруппу с топиками
"""
import os
import logging
from aiogram import Bot
from aiogram.types import FSInputFile
from dotenv import load_dotenv
import aiosqlite

load_dotenv()

LOG_GROUP_ID = int(os.getenv('LOG_GROUP_ID', '-1003535325557'))
DB_PATH = "navigator.db"  # Используем ту же БД что и в database.py

# Кэш для хранения topic_id пользователей (чтобы не создавать дубли)
user_topics_cache = {}


async def get_or_create_user_topic(bot: Bot, user_id: int, full_name: str, username: str = None) -> int:
    """
    Получает существующий или создает новый топик для пользователя

    Args:
        bot: Экземпляр бота
        user_id: ID пользователя в Telegram
        full_name: Полное имя пользователя
        username: Username пользователя (может быть None)

    Returns:
        message_thread_id топика
    """
    # Проверяем кэш
    if user_id in user_topics_cache:
        logging.info(f"Found cached topic for user {user_id}: {user_topics_cache[user_id]}")
        return user_topics_cache[user_id]

    # Проверяем базу данных
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT topic_id FROM users WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                topic_id = row[0]
                user_topics_cache[user_id] = topic_id
                logging.info(f"Found topic in DB for user {user_id}: {topic_id}")
                return topic_id

    # Топик не найден - создаем новый
    topic_name = full_name if full_name else f"User {user_id}"
    if username:
        topic_name = f"{topic_name} (@{username})"

    try:
        # Создаем топик в супергруппе
        result = await bot.create_forum_topic(
            chat_id=LOG_GROUP_ID,
            name=topic_name
        )
        topic_id = result.message_thread_id

        # Сохраняем в кэш
        user_topics_cache[user_id] = topic_id

        # Сохраняем в БД
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE users SET topic_id = ? WHERE user_id = ?",
                (topic_id, user_id)
            )
            await db.commit()

        logging.info(f"Created new topic for user {user_id}: {topic_id} (name: {topic_name})")
        return topic_id

    except Exception as e:
        logging.error(f"Failed to create topic for user {user_id}: {e}")
        # Возвращаем None чтобы сообщения отправлялись в общий чат
        return None


async def log_user_start(bot: Bot, user_id: int, full_name: str, username: str = None, referral_source: str = None):
    """
    Логирует начало работы пользователя с ботом

    Args:
        bot: Экземпляр бота
        user_id: ID пользователя
        full_name: Полное имя
        username: Username (опционально)
        referral_source: Источник перехода из параметра ?from= (опционально)
    """
    try:
        topic_id = await get_or_create_user_topic(bot, user_id, full_name, username)

        if not topic_id:
            logging.warning(f"No topic_id for user {user_id}, skipping log")
            return

        # Формируем сообщение
        user_link = f"<a href='tg://user?id={user_id}'>{full_name}</a>"
        message = f"🚀 <b>Новый пользователь начал навигацию</b>\n\n"
        message += f"👤 Пользователь: {user_link}\n"
        message += f"🆔 ID: <code>{user_id}</code>\n"

        if username:
            message += f"📱 Username: @{username}\n"

        if referral_source:
            message += f"📊 Источник: <code>{referral_source}</code>\n"

        # Отправляем в топик
        await bot.send_message(
            chat_id=LOG_GROUP_ID,
            message_thread_id=topic_id,
            text=message,
            parse_mode="HTML"
        )
        logging.info(f"Logged user start for {user_id} to topic {topic_id}")

    except Exception as e:
        logging.error(f"Failed to log user start: {e}")


async def log_user_answer(bot: Bot, user_id: int, question_title: str, answer: str):
    """
    Логирует ответ пользователя на вопрос

    Args:
        bot: Экземпляр бота
        user_id: ID пользователя
        question_title: Название/описание вопроса
        answer: Ответ пользователя
    """
    try:
        # Получаем topic_id из кэша или БД
        topic_id = user_topics_cache.get(user_id)

        if not topic_id:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                    "SELECT topic_id FROM users WHERE user_id = ?",
                    (user_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row and row[0]:
                        topic_id = row[0]
                        user_topics_cache[user_id] = topic_id

        if not topic_id:
            logging.warning(f"No topic_id for user {user_id}, skipping answer log")
            return

        # Формируем сообщение
        message = f"💬 <b>{question_title}</b>\n\n"
        message += f"<i>{answer}</i>"

        # Отправляем в топик
        await bot.send_message(
            chat_id=LOG_GROUP_ID,
            message_thread_id=topic_id,
            text=message,
            parse_mode="HTML"
        )
        logging.info(f"Logged answer for user {user_id} to topic {topic_id}")

    except Exception as e:
        logging.error(f"Failed to log user answer: {e}")


async def log_user_pdf(bot: Bot, user_id: int, pdf_path: str):
    """
    Логирует отправку PDF пользователю

    Args:
        bot: Экземпляр бота
        user_id: ID пользователя
        pdf_path: Путь к PDF файлу
    """
    try:
        # Получаем topic_id
        topic_id = user_topics_cache.get(user_id)

        if not topic_id:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute(
                    "SELECT topic_id FROM users WHERE user_id = ?",
                    (user_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row and row[0]:
                        topic_id = row[0]
                        user_topics_cache[user_id] = topic_id

        if not topic_id:
            logging.warning(f"No topic_id for user {user_id}, skipping PDF log")
            return

        # Отправляем PDF в топик
        doc = FSInputFile(pdf_path)
        await bot.send_document(
            chat_id=LOG_GROUP_ID,
            message_thread_id=topic_id,
            document=doc,
            caption="📄 <b>Персональная стратегия сгенерирована</b>",
            parse_mode="HTML"
        )
        logging.info(f"Logged PDF for user {user_id} to topic {topic_id}")

    except Exception as e:
        logging.error(f"Failed to log PDF: {e}")
