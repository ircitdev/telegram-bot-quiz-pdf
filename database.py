import aiosqlite
import datetime
import logging

DB_NAME = "navigator.db"
logger = logging.getLogger(__name__)

async def init_db():
    """Инициализация базы данных"""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    course TEXT,
                    role_outer TEXT,
                    role_inner TEXT,
                    gap TEXT,
                    cost_of_delay TEXT,
                    family_presence TEXT,
                    anchor_word TEXT,
                    stop_action TEXT,
                    first_step TEXT,
                    final_question TEXT,
                    created_at TIMESTAMP,
                    topic_id INTEGER,
                    referral_source TEXT
                )
            """)
            # Миграция: добавляем новые колонки если их нет (для уже существующей БД)
            for col in ("course", "gap", "stop_action", "first_step"):
                try:
                    await db.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT")
                    logger.info(f"Migration: added column '{col}' to users")
                except Exception:
                    pass  # Колонка уже существует

            # Миграция для фич конверсии
            conversion_fields = [
                ('nav_score', 'TEXT'),
                ('pdf_sent_at', 'TIMESTAMP'),
                ('conversion_status', 'TEXT DEFAULT "not_started"'),
                ('utm_source', 'TEXT'),
                ('utm_campaign', 'TEXT'),
                ('current_stage', 'TEXT DEFAULT "started"'),
                ('last_interaction_date', 'TIMESTAMP'),
                ('conversion_source', 'TEXT')
            ]

            for col_name, col_type in conversion_fields:
                try:
                    await db.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                    logger.info(f"Migration: added column '{col_name}' to users")
                except Exception:
                    pass  # Колонка уже существует

            # Создаём таблицу scheduled_messages
            await db.execute("""
                CREATE TABLE IF NOT EXISTS scheduled_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    message_type TEXT NOT NULL,
                    scheduled_at TIMESTAMP NOT NULL,
                    sent_at TIMESTAMP,
                    status TEXT DEFAULT 'pending',
                    payload TEXT,
                    error_message TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS admins (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    added_at TIMESTAMP
                )
            """)
            await db.commit()
            logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

async def is_admin(user_id: int) -> bool:
    """Проверяет является ли пользователь админом"""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone() is not None

async def get_admins() -> list:
    """Возвращает список всех админов"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM admins ORDER BY added_at") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def add_admin(user_id: int, username: str = None) -> bool:
    """Добавляет нового админа. Возвращает False если уже существует."""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "INSERT OR IGNORE INTO admins (user_id, username, added_at) VALUES (?, ?, ?)",
                (user_id, username, datetime.datetime.now())
            )
            await db.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to add admin {user_id}: {e}")
        return False

async def remove_admin(user_id: int) -> bool:
    """Удаляет админа"""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
            await db.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to remove admin {user_id}: {e}")
        return False

async def get_users_with_pdf() -> list:
    """Возвращает user_id всех пользователей прошедших весь опрос"""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT user_id FROM users WHERE final_question IS NOT NULL"
        ) as cursor:
            rows = await cursor.fetchall()
            return [r[0] for r in rows]

async def add_user(user_id: int, username: str, full_name: str):
    """Добавляет нового пользователя в БД"""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)) as cursor:
                if not await cursor.fetchone():
                    await db.execute("""
                        INSERT INTO users (user_id, username, full_name, created_at)
                        VALUES (?, ?, ?, ?)
                    """, (user_id, username, full_name, datetime.datetime.now()))
                    await db.commit()
                    logger.info(f"New user added: {user_id} (@{username})")
    except Exception as e:
        logger.error(f"Failed to add user {user_id}: {e}")
        raise

async def update_user_field(user_id: int, field: str, value: str):
    """
    Обновляет поле пользователя в БД.
    field - должно быть из списка разрешенных полей для безопасности.
    """
    # Белый список разрешенных полей для защиты от SQL-инъекций
    ALLOWED_FIELDS = {
        'course', 'role_outer', 'role_inner', 'gap',
        'cost_of_delay', 'family_presence', 'anchor_word',
        'stop_action', 'first_step', 'final_question',
        'username', 'full_name', 'topic_id', 'referral_source',
        'nav_score', 'pdf_sent_at', 'conversion_status',
        'utm_source', 'utm_campaign', 'current_stage',
        'last_interaction_date', 'conversion_source'
    }

    if field not in ALLOWED_FIELDS:
        raise ValueError(f"Invalid field name: {field}")

    async with aiosqlite.connect(DB_NAME) as db:
        # Теперь безопасно использовать field в запросе, т.к. проверили белый список
        query = f"UPDATE users SET {field} = ? WHERE user_id = ?"
        await db.execute(query, (value, user_id))
        await db.commit()

async def get_user_data(user_id: int):
    """Получает данные пользователя из БД"""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(row)
                return None
    except Exception as e:
        logger.error(f"Failed to get user data for {user_id}: {e}")
        return None

async def get_user_id_by_topic(topic_id: int) -> int | None:
    """Находит user_id пользователя по topic_id супергруппы"""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute(
                "SELECT user_id FROM users WHERE topic_id = ?", (topic_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None
    except Exception as e:
        logger.error(f"Failed to get user by topic {topic_id}: {e}")
        return None

async def get_all_inner_roles(limit=50):
    """Получает список внутренних ролей для Word Cloud"""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT role_inner FROM users WHERE role_inner IS NOT NULL ORDER BY created_at DESC LIMIT ?", (limit,)) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows if row[0]]
    except Exception as e:
        logger.error(f"Failed to get inner roles: {e}")
        return []


# ========================
# Функции для воронки конверсии
# ========================

async def update_stage(user_id: int, new_stage: str):
    """Обновляет current_stage и last_interaction_date"""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "UPDATE users SET current_stage = ?, last_interaction_date = ? WHERE user_id = ?",
                (new_stage, datetime.datetime.now(), user_id)
            )
            await db.commit()
            logger.info(f"User {user_id} moved to stage: {new_stage}")
    except Exception as e:
        logger.error(f"Failed to update stage for user {user_id}: {e}")


# ========================
# Функции для scheduled_messages
# ========================

async def add_scheduled_message(
    user_id: int,
    message_type: str,
    scheduled_at: datetime.datetime,
    payload: str = None,
    status: str = 'pending'
) -> int:
    """Добавляет запланированное сообщение. Возвращает message_id."""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("""
                INSERT INTO scheduled_messages (user_id, message_type, scheduled_at, payload, status)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, message_type, scheduled_at, payload, status))
            await db.commit()
            return cursor.lastrowid
    except Exception as e:
        logger.error(f"Failed to add scheduled message: {e}")
        raise


async def mark_message_sent(message_id: int):
    """Помечает сообщение как отправленное"""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                UPDATE scheduled_messages
                SET status = 'sent', sent_at = ?
                WHERE id = ?
            """, (datetime.datetime.now(), message_id))
            await db.commit()
    except Exception as e:
        logger.error(f"Failed to mark message {message_id} as sent: {e}")


async def mark_message_failed(message_id: int, error_message: str):
    """Помечает сообщение как неудачное"""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                UPDATE scheduled_messages
                SET status = 'failed', error_message = ?
                WHERE id = ?
            """, (error_message, message_id))
            await db.commit()
    except Exception as e:
        logger.error(f"Failed to mark message {message_id} as failed: {e}")


async def get_pending_messages() -> list:
    """Получает список pending сообщений"""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM scheduled_messages
                WHERE status = 'pending'
                ORDER BY scheduled_at
            """) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Failed to get pending messages: {e}")
        return []


async def check_message_sent(user_id: int, message_type: str) -> bool:
    """Проверяет, было ли уже отправлено сообщение данного типа пользователю"""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("""
                SELECT 1 FROM scheduled_messages
                WHERE user_id = ? AND message_type = ? AND status = 'sent'
            """, (user_id, message_type)) as cursor:
                return await cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Failed to check if message sent: {e}")
        return False


async def cancel_user_messages(user_id: int, message_type: str = None) -> int:
    """
    Отменяет запланированные сообщения для пользователя.
    Возвращает количество отменённых сообщений.
    """
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            if message_type:
                cursor = await db.execute("""
                    UPDATE scheduled_messages
                    SET status = 'cancelled'
                    WHERE user_id = ? AND message_type = ? AND status = 'pending'
                """, (user_id, message_type))
            else:
                cursor = await db.execute("""
                    UPDATE scheduled_messages
                    SET status = 'cancelled'
                    WHERE user_id = ? AND status = 'pending'
                """, (user_id,))
            await db.commit()
            return cursor.rowcount
    except Exception as e:
        logger.error(f"Failed to cancel messages for user {user_id}: {e}")
        return 0


# ========================
# Функции для реактивации брошенных сессий
# ========================

async def get_abandoned_sessions(hours_ago: int = 2) -> list:
    """Возвращает user_id пользователей, бросивших бота 2+ часа назад"""
    from datetime import timedelta
    cutoff = datetime.datetime.now() - timedelta(hours=hours_ago)

    try:
        async with aiosqlite.connect(DB_NAME) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT user_id, full_name, created_at
                FROM users
                WHERE created_at < ?
                  AND final_question IS NULL
                  AND role_inner IS NOT NULL
            """, (cutoff,)) as cursor:
                rows = await cursor.fetchall()
                return [{"user_id": r[0], "full_name": r[1]} for r in rows]
    except Exception as e:
        logger.error(f"Failed to get abandoned sessions: {e}")
        return []
