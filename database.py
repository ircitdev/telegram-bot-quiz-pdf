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
        'username', 'full_name', 'topic_id', 'referral_source'
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
