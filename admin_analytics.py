"""
Модуль аналитики для администраторов в Telegram
"""
import aiosqlite
from datetime import datetime, timedelta
from database import DB_NAME
import csv
import io
import logging

logger = logging.getLogger(__name__)


async def get_funnel_stats_24h() -> dict:
    """Статистика воронки за последние 24 часа"""
    cutoff = datetime.now() - timedelta(hours=24)

    async with aiosqlite.connect(DB_NAME) as db:
        stats = {}

        # Новых запусков
        async with db.execute(
            "SELECT COUNT(*) FROM users WHERE created_at > ?", (cutoff,)
        ) as cursor:
            stats['new_starts'] = (await cursor.fetchone())[0]

        # С рекламы (есть utm_source)
        async with db.execute(
            "SELECT COUNT(*) FROM users WHERE created_at > ? AND utm_source IS NOT NULL", (cutoff,)
        ) as cursor:
            stats['from_ads'] = (await cursor.fetchone())[0]

        # Дошли до PDF
        async with db.execute(
            "SELECT COUNT(*) FROM users WHERE created_at > ? AND current_stage >= 'pdf_delivered'", (cutoff,)
        ) as cursor:
            stats['pdf_delivered'] = (await cursor.fetchone())[0]

        # Сегменты
        async with db.execute(
            "SELECT COUNT(*) FROM users WHERE created_at > ? AND nav_score = 'Переход'", (cutoff,)
        ) as cursor:
            stats['segment_transition'] = (await cursor.fetchone())[0]

        async with db.execute(
            "SELECT COUNT(*) FROM users WHERE created_at > ? AND nav_score = 'Курс устойчив'", (cutoff,)
        ) as cursor:
            stats['segment_stable'] = (await cursor.fetchone())[0]

        # Ответили на зеркало
        async with db.execute(
            "SELECT COUNT(*) FROM users WHERE created_at > ? AND current_stage = 'mirror_replied'", (cutoff,)
        ) as cursor:
            stats['mirror_replies'] = (await cursor.fetchone())[0]

        # Конверсии
        async with db.execute(
            "SELECT COUNT(*) FROM users WHERE created_at > ? AND current_stage = 'diagnostic_booked'", (cutoff,)
        ) as cursor:
            stats['conversions'] = (await cursor.fetchone())[0]

        return stats


async def get_hot_leads() -> list:
    """Горячие лиды (получили PDF, но не записались)"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT user_id, username, full_name, utm_source, utm_campaign,
                   cost_of_delay, current_stage, nav_score
            FROM users
            WHERE current_stage >= 'pdf_delivered'
              AND current_stage < 'diagnostic_booked'
            ORDER BY
                CASE nav_score
                    WHEN 'Переход' THEN 1
                    ELSE 2
                END,
                last_interaction_date DESC
            LIMIT 50
        """) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def export_leads_csv() -> io.BytesIO:
    """Экспорт всех лидов в CSV"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT user_id, username, full_name, utm_source, utm_campaign,
                   current_stage, nav_score, cost_of_delay,
                   created_at, last_interaction_date
            FROM users
            ORDER BY created_at DESC
        """) as cursor:
            rows = await cursor.fetchall()

            # Генерируем CSV
            output = io.BytesIO()
            output_text = io.StringIO()
            writer = csv.DictWriter(
                output_text,
                fieldnames=['user_id', 'username', 'full_name', 'utm_source',
                           'utm_campaign', 'current_stage', 'nav_score',
                           'cost_of_delay', 'created_at', 'last_interaction_date']
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(dict(row))

            output.write(output_text.getvalue().encode('utf-8'))
            output.seek(0)
            return output
