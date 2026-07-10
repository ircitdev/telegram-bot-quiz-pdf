"""
Модуль для отправки conversion-сообщений (AI-разбор, drip-цепочка, зеркало)
"""
import logging
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import get_user_data, update_stage
from topic_logger import log_user_answer

logger = logging.getLogger(__name__)


async def send_ai_analysis(bot: Bot, user_id: int):
    """
    Отправляет персонализированный AI-разбор с CTA на диагностику

    Args:
        bot: Экземпляр бота
        user_id: ID пользователя
    """
    try:
        logger.info(f"Sending AI analysis to user {user_id}")

        # Загружаем данные пользователя
        user_data = await get_user_data(user_id)
        if not user_data:
            logger.error(f"User data not found for {user_id}")
            return

        # Генерируем персонализированный разбор через OpenAI
        from openai_assistant import generate_conversion_analysis
        analysis = await generate_conversion_analysis(user_data)

        if not analysis:
            logger.error(f"Failed to generate analysis for user {user_id}")
            # Fallback на шаблонное сообщение
            analysis = _get_fallback_analysis(user_data)

        # Формируем кнопку CTA
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="📅 Записаться на диагностику",
                url="https://personalstrategy.romandusenko.ru/form/"
            )
        ]])

        # Отправляем сообщение
        await bot.send_message(
            chat_id=user_id,
            text=analysis,
            parse_mode="HTML",
            reply_markup=kb
        )

        # Обновляем статус воронки
        await update_stage(user_id, 'ai_insight_delivered')

        # Логируем в топик админа
        await log_user_answer(
            bot, user_id,
            "📊 AI-разбор отправлен",
            "Персонализированный анализ стратегии доставлен пользователю"
        )

        logger.info(f"Successfully sent AI analysis to user {user_id}")

    except Exception as e:
        logger.error(f"Failed to send AI analysis to user {user_id}: {e}", exc_info=True)


def _get_fallback_analysis(user_data: dict) -> str:
    """Fallback-сообщение если OpenAI недоступен"""
    return (
        f"<b>Анализ вашей стратегии</b>\n\n"
        f"Я проанализировал ваши ответы. Вы описали себя как "
        f"<i>{user_data.get('role_outer', 'человек')}</i> снаружи, "
        f"но внутри ощущаете себя <i>{user_data.get('role_inner', 'по-другому')}</i>.\n\n"
        f"Этот разрыв между внешней ролью и внутренним ощущением — "
        f"ключевой сигнал. На диагностике мы разберём, что это значит "
        f"и как построить стратегию, которая учитывает обе стороны.\n\n"
        f"45 минут. Онлайн. Без записи."
    )


async def send_drip_day1(bot: Bot, user_id: int):
    """
    День 1: Провокационный вопрос на основе ответов пользователя

    Args:
        bot: Экземпляр бота
        user_id: ID пользователя
    """
    try:
        logger.info(f"Sending drip day 1 to user {user_id}")

        user_data = await get_user_data(user_id)
        if not user_data:
            logger.error(f"User data not found for {user_id}")
            return

        # Генерируем провокационный вопрос через OpenAI
        from openai_assistant import generate_drip_question
        question = await generate_drip_question(user_data)

        if not question:
            # Fallback на шаблонный вопрос
            question = (
                f"Ты написал, что снаружи ты — {user_data.get('role_outer', '...')}, "
                f"а внутри ощущаешь себя {user_data.get('role_inner', '...')}. "
                f"Сколько ещё можно носить эту маску?"
            )

        text = (
            f"Один вопрос по твоим ответам:\n\n"
            f"<i>{question}</i>\n\n"
            f"Можешь ответить прямо здесь — я передам Роману."
        )

        await bot.send_message(
            chat_id=user_id,
            text=text,
            parse_mode="HTML"
        )

        # Обновляем статус
        await update_stage(user_id, 'drip_1_done')

        logger.info(f"Successfully sent drip day 1 to user {user_id}")

    except Exception as e:
        logger.error(f"Failed to send drip day 1 to user {user_id}: {e}", exc_info=True)


async def send_drip_day3(bot: Bot, user_id: int):
    """
    День 3: История клиента с похожим cost_of_delay (social proof)

    Args:
        bot: Экземпляр бота
        user_id: ID пользователя
    """
    try:
        logger.info(f"Sending drip day 3 to user {user_id}")

        user_data = await get_user_data(user_id)
        if not user_data:
            logger.error(f"User data not found for {user_id}")
            return

        cost = user_data.get('cost_of_delay', 'Смысл')

        # Истории клиентов (заглушки — нужно заменить реальными)
        stories = {
            'Здоровье': (
                "<b>История Алексея (36 лет, IT-директор)</b>\n\n"
                "«Я откладывал себя 5 лет. Платил здоровьем — панические атаки начались прямо на совещании. "
                "Диагностика показала: я управляю компанией, но не управляю собой.\n\n"
                "Мы нашли точку опоры. Через 2 месяца — впервые за годы чувствую, что живу, а не выживаю.»"
            ),
            'Отношения': (
                "<b>История Марины (42 года, владелец бизнеса)</b>\n\n"
                "«Муж сказал: 'Ты здесь, но тебя нет'. Я платила отношениями за успех. "
                "На диагностике Роман спросил: 'А если бизнес исчезнет завтра — кто ты?'\n\n"
                "Этот вопрос развернул всё. Сейчас я — владелец бизнеса, а не заложник.»"
            ),
            'Смысл': (
                "<b>История Дмитрия (39 лет, предприниматель)</b>\n\n"
                "«Результаты есть, радости нет. Я платил смыслом. "
                "Думал, это кризис. Роман показал: это навигационная ошибка — карта устарела.\n\n"
                "Диагностика заняла 45 минут. Через 3 месяца запустил проект, который горит изнутри.»"
            ),
            'Свобода': (
                "<b>История Екатерины (44 года, топ-менеджер)</b>\n\n"
                "«Я построила карьеру, но потеряла себя. Платила свободой — каждый день по чужому сценарию. "
                "На диагностике услышала: 'Свобода — это не уйти. Это перестать убегать.'\n\n"
                "Сейчас я на той же должности, но живу по своей карте.»"
            )
        }

        story = stories.get(cost, stories['Смысл'])

        text = f"{story}\n\n━━━━━━━━━━━━━━━\n\nДиагностика заняла 45 минут. Без записи разговора. Только ты и карта."

        await bot.send_message(
            chat_id=user_id,
            text=text,
            parse_mode="HTML"
        )

        # Обновляем статус
        await update_stage(user_id, 'drip_3_done')

        logger.info(f"Successfully sent drip day 3 to user {user_id}")

    except Exception as e:
        logger.error(f"Failed to send drip day 3 to user {user_id}: {e}", exc_info=True)


async def send_drip_day7(bot: Bot, user_id: int):
    """
    День 7: Прямое предложение + scarcity

    Args:
        bot: Экземпляр бота
        user_id: ID пользователя
    """
    try:
        logger.info(f"Sending drip day 7 to user {user_id}")

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="📅 Записаться на диагностику",
                url="https://personalstrategy.romandusenko.ru/form/"
            )],
            [InlineKeyboardButton(
                text="✅ Я уже записался",
                callback_data="diagnostic_booked"
            )]
        ])

        text = (
            "Неделя прошла с момента твоей стратегии.\n\n"
            "Вопрос остался?\n\n"
            "В феврале осталось 3 слота на личную диагностику.\n"
            "45 минут. Онлайн. Без записи разговора.\n\n"
            "<b>Это не коучинг. Это навигация.</b>"
        )

        await bot.send_message(
            chat_id=user_id,
            text=text,
            parse_mode="HTML",
            reply_markup=kb
        )

        # Обновляем статус
        await update_stage(user_id, 'drip_7_done')

        logger.info(f"Successfully sent drip day 7 to user {user_id}")

    except Exception as e:
        logger.error(f"Failed to send drip day 7 to user {user_id}: {e}", exc_info=True)


async def send_mirror_reflection(bot: Bot, user_id: int):
    """
    День 7: "Зеркало" — цитирует собственные ответы пользователя

    Args:
        bot: Экземпляр бота
        user_id: ID пользователя
    """
    try:
        logger.info(f"Sending mirror reflection to user {user_id}")

        user_data = await get_user_data(user_id)
        if not user_data:
            logger.error(f"User data not found for {user_id}")
            return

        cost = user_data.get('cost_of_delay', 'временем')
        final_question = user_data.get('final_question', 'свой вопрос')

        text = (
            "Неделю назад ты написал:\n\n"
            f"<i>«Платишь {cost.lower()}»</i>\n"
            f"<i>«Главный вопрос: {final_question}»</i>\n\n"
            "Что изменилось за эту неделю?\n"
            "Напиши одно слово."
        )

        await bot.send_message(
            chat_id=user_id,
            text=text,
            parse_mode="HTML"
        )

        # Ответ пользователя автоматически попадёт в топик через relay_from_user_to_topic()

        logger.info(f"Successfully sent mirror reflection to user {user_id}")

    except Exception as e:
        logger.error(f"Failed to send mirror reflection to user {user_id}: {e}", exc_info=True)


async def send_reactivation_message(bot: Bot, user_id: int):
    """
    Отправляет сообщение реактивации брошенной сессии

    Args:
        bot: Экземпляр бота
        user_id: ID пользователя
    """
    try:
        logger.info(f"Sending reactivation message to user {user_id}")

        user_data = await get_user_data(user_id)
        if not user_data:
            logger.error(f"User data not found for {user_id}")
            return

        last_question = _detect_last_completed_step(user_data)

        text = (
            f"Ты остановился на {last_question}.\n\n"
            "Часто это само по себе сигнал — значит, вопрос задел.\n\n"
            "Продолжить навигацию?"
        )

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, продолжу", callback_data="resume_form")],
            [InlineKeyboardButton(text="❌ Не сейчас", callback_data="dismiss_reactivation")]
        ])

        await bot.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=kb
        )

        logger.info(f"Successfully sent reactivation message to user {user_id}")

    except Exception as e:
        logger.error(f"Failed to send reactivation message to user {user_id}: {e}", exc_info=True)


def _detect_last_completed_step(user_data: dict) -> str:
    """Определяет, на каком вопросе остановился пользователь"""
    if user_data.get('first_step'):
        return "вопросе 9 из 10"
    elif user_data.get('stop_action'):
        return "вопросе 8 из 10"
    elif user_data.get('anchor_word'):
        return "вопросе 7 из 10"
    elif user_data.get('family_presence'):
        return "вопросе 6 из 10"
    elif user_data.get('cost_of_delay'):
        return "вопросе 5 из 10"
    elif user_data.get('gap'):
        return "вопросе 4 из 10"
    elif user_data.get('role_inner'):
        return "вопросе 3 из 10"
    elif user_data.get('role_outer'):
        return "вопросе 2 из 10"
    elif user_data.get('course'):
        return "вопросе 1 из 10"
    else:
        return "самом начале пути"
