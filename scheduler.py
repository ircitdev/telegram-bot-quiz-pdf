"""
Модуль для управления отложенными сообщениями через APScheduler
"""
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from database import add_scheduled_message, mark_message_sent

logger = logging.getLogger(__name__)

# Инициализация scheduler с SQLite job store для персистентности
jobstores = {
    'default': SQLAlchemyJobStore(url='sqlite:///navigator_jobs.db')
}
executors = {
    'default': AsyncIOExecutor()
}
job_defaults = {
    'coalesce': False,
    'max_instances': 3
}

scheduler = AsyncIOScheduler(
    jobstores=jobstores,
    executors=executors,
    job_defaults=job_defaults,
    timezone='Europe/Moscow'
)


async def schedule_message(user_id: int, message_type: str, delay_hours: float, payload: str = None):
    """
    Планирует отправку сообщения через указанное время

    Args:
        user_id: ID пользователя
        message_type: Тип сообщения ('ai_analysis_30min', 'drip_day1', etc.)
        delay_hours: Задержка в часах (может быть дробной, например 0.5 = 30 мин)
        payload: Дополнительные данные (JSON string)
    """
    try:
        scheduled_at = datetime.now() + timedelta(hours=delay_hours)

        # Сохраняем в БД
        message_id = await add_scheduled_message(
            user_id=user_id,
            message_type=message_type,
            scheduled_at=scheduled_at,
            payload=payload,
            status='pending'
        )

        # Планируем задачу в APScheduler
        scheduler.add_job(
            execute_scheduled_message,
            'date',
            run_date=scheduled_at,
            args=[message_id, user_id, message_type],
            id=f"{message_type}_{user_id}_{message_id}",
            replace_existing=True
        )

        logger.info(
            f"Scheduled message: type={message_type}, user={user_id}, "
            f"run_at={scheduled_at.strftime('%Y-%m-%d %H:%M:%S')}"
        )

    except Exception as e:
        logger.error(f"Failed to schedule message for user {user_id}: {e}", exc_info=True)


async def cancel_scheduled_messages(user_id: int, message_type: str = None):
    """
    Отменяет запланированные сообщения для пользователя

    Args:
        user_id: ID пользователя
        message_type: Если указан — отменить только этот тип, иначе все
    """
    try:
        from database import cancel_user_messages

        # Отменяем в БД
        cancelled_count = await cancel_user_messages(user_id, message_type)

        # Отменяем задачи в APScheduler
        jobs = scheduler.get_jobs()
        cancelled_jobs = 0

        for job in jobs:
            job_id = job.id
            # Формат job_id: "{message_type}_{user_id}_{message_id}"
            parts = job_id.split('_')

            if len(parts) >= 3:
                job_user_id = int(parts[-2])
                job_message_type = '_'.join(parts[:-2])

                if job_user_id == user_id:
                    if message_type is None or job_message_type == message_type:
                        scheduler.remove_job(job_id)
                        cancelled_jobs += 1

        logger.info(
            f"Cancelled messages for user {user_id}: "
            f"DB={cancelled_count}, Scheduler={cancelled_jobs}"
        )

    except Exception as e:
        logger.error(f"Failed to cancel messages for user {user_id}: {e}", exc_info=True)


async def execute_scheduled_message(message_id: int, user_id: int, message_type: str):
    """
    Выполняет отправку запланированного сообщения

    Args:
        message_id: ID записи в scheduled_messages
        user_id: ID пользователя
        message_type: Тип сообщения
    """
    try:
        logger.info(f"Executing scheduled message: id={message_id}, type={message_type}, user={user_id}")

        # Динамический импорт для избежания циклических зависимостей
        from conversion_messages import (
            send_ai_analysis,
            send_drip_day1,
            send_drip_day3,
            send_drip_day7,
            send_mirror_reflection
        )
        from bot import bot

        # Маршрутизация по типу сообщения
        if message_type == 'ai_analysis_30min':
            await send_ai_analysis(bot, user_id)
        elif message_type == 'drip_day1':
            await send_drip_day1(bot, user_id)
        elif message_type == 'drip_day3':
            await send_drip_day3(bot, user_id)
        elif message_type == 'drip_day7':
            await send_drip_day7(bot, user_id)
        elif message_type == 'mirror_day7':
            await send_mirror_reflection(bot, user_id)
        else:
            logger.warning(f"Unknown message type: {message_type}")
            return

        # Помечаем как отправленное
        await mark_message_sent(message_id)
        logger.info(f"Successfully sent scheduled message: id={message_id}")

    except Exception as e:
        logger.error(
            f"Failed to execute scheduled message: id={message_id}, "
            f"type={message_type}, user={user_id}, error={e}",
            exc_info=True
        )
        # Помечаем как failed
        from database import mark_message_failed
        await mark_message_failed(message_id, str(e))


async def check_and_reactivate_abandoned():
    """Проверяет брошенные сессии каждый час и отправляет реактивационные сообщения"""
    try:
        from database import get_abandoned_sessions, check_message_sent, add_scheduled_message
        from conversion_messages import send_reactivation_message
        from bot import bot
        from datetime import datetime

        logger.info("Checking abandoned sessions...")

        sessions = await get_abandoned_sessions(hours_ago=2)

        for session in sessions:
            user_id = session['user_id']

            # Проверяем, не отправляли ли уже реактивацию
            already_sent = await check_message_sent(user_id, 'reactivation')
            if already_sent:
                continue

            # Отправляем реактивационное сообщение
            await send_reactivation_message(bot, user_id)

            # Помечаем в scheduled_messages как отправленное
            await add_scheduled_message(
                user_id, 'reactivation',
                datetime.now(),
                status='sent'
            )

            logger.info(f"Sent reactivation message to user {user_id}")

    except Exception as e:
        logger.error(f"Failed to check abandoned sessions: {e}", exc_info=True)


async def send_daily_report():
    """Отправляет ежедневный отчёт по воронке в админскую группу в 10:00"""
    try:
        from admin_analytics import get_funnel_stats_24h
        from bot import bot
        import os

        LOG_GROUP_ID = int(os.getenv("LOG_GROUP_ID", "-1003535325557"))

        logger.info("Generating daily report...")

        stats = await get_funnel_stats_24h()

        conversion_rate = 0
        if stats['pdf_delivered'] > 0:
            conversion_rate = (stats['conversions'] / stats['pdf_delivered']) * 100

        report = (
            "📊 <b>Отчет по воронке за 24 часа:</b>\n\n"
            f"• Новых запусков: <b>{stats['new_starts']}</b>\n"
            f"• С рекламы: <b>{stats['from_ads']}</b>\n"
            f"• Дошли до PDF: <b>{stats['pdf_delivered']}</b> "
            f"(Конверсия: {conversion_rate:.1f}%)\n\n"
            f"<b>Сегментация:</b>\n"
            f"• Сегмент «Переход»: <b>{stats['segment_transition']}</b>\n"
            f"• Сегмент «Курс устойчив»: <b>{stats['segment_stable']}</b>\n\n"
            f"• Ответили на «Зеркало»: <b>{stats['mirror_replies']}</b>\n"
            f"• 🎯 Записались на диагностику: <b>{stats['conversions']}</b>"
        )

        await bot.send_message(
            LOG_GROUP_ID,
            report,
            parse_mode="HTML"
        )

        logger.info("Daily report sent successfully")

    except Exception as e:
        logger.error(f"Failed to send daily report: {e}", exc_info=True)


def start_scheduler():
    """Запускает scheduler"""
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started successfully")

        # Добавляем периодическую задачу для реактивации брошенных сессий
        from apscheduler.triggers.interval import IntervalTrigger
        from apscheduler.triggers.cron import CronTrigger

        scheduler.add_job(
            check_and_reactivate_abandoned,
            trigger=IntervalTrigger(hours=1),
            id='reactivation_checker',
            replace_existing=True
        )
        logger.info("Reactivation checker scheduled (every 1 hour)")

        # Добавляем ежедневный отчёт в 10:00 по московскому времени
        scheduler.add_job(
            send_daily_report,
            trigger=CronTrigger(hour=10, minute=0),
            id='daily_report',
            replace_existing=True
        )
        logger.info("Daily report scheduled (every day at 10:00 MSK)")


def shutdown_scheduler():
    """Останавливает scheduler"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler shut down")
