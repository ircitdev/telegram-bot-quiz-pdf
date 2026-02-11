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
                    role_outer TEXT,
                    role_inner TEXT,
                    nav_score TEXT,
                    family_presence TEXT,
                    anchor_word TEXT,
                    cost_of_delay TEXT,
                    final_question TEXT,
                    created_at TIMESTAMP,
                    topic_id INTEGER,
                    referral_source TEXT
                )
            """)
            await db.commit()
            logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

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
        'role_outer', 'role_inner', 'nav_score', 'family_presence',
        'anchor_word', 'cost_of_delay', 'final_question', 'username', 'full_name',
        'topic_id', 'referral_source'
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
