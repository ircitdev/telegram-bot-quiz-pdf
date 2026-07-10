import asyncio
import os
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

from database import (init_db, add_user, update_user_field, get_user_data,
                       get_user_id_by_topic, is_admin, get_admins, add_admin,
                       remove_admin, get_users_with_pdf)
from states import Form, AdminBroadcast, AdminAdd
from pdf_gen import create_pdf
from openai_assistant import validate_answer
from topic_logger import log_user_start, log_user_answer, log_user_pdf

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
CHANNEL_URL = os.getenv("CHANNEL_URL")
LOG_GROUP_ID = int(os.getenv("LOG_GROUP_ID", "-1003535325557"))

# Проверка обязательных переменных окружения
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in environment variables. Please create .env file.")
if not CHANNEL_ID:
    raise ValueError("CHANNEL_ID not found in environment variables. Please create .env file.")
if not CHANNEL_URL:
    raise ValueError("CHANNEL_URL not found in environment variables. Please create .env file.")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def check_subscription(user_id: int) -> bool:
    try:
        logging.info(f"Checking subscription for user {user_id} in channel {CHANNEL_ID}")
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        is_subscribed = member.status in ['creator', 'administrator', 'member']
        logging.info(f"User {user_id} subscription status: {member.status}, is_subscribed: {is_subscribed}")
        return is_subscribed
    except Exception as e:
        logging.error(f"Error checking subscription for user {user_id} in channel {CHANNEL_ID}: {e}")
        return False

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Anon"
    full_name = message.from_user.full_name

    # Парсинг UTM-меток из deep link: /start tgads_var1
    utm_source = None
    utm_campaign = None
    referral_source = None

    if message.text and len(message.text.split()) > 1:
        utm_param = message.text.split()[1]  # "tgads_var1"
        referral_source = utm_param  # Сохраняем для обратной совместимости

        # Парсинг формата: SOURCE_CAMPAIGN
        if '_' in utm_param:
            parts = utm_param.split('_', 1)
            utm_source = parts[0]      # "tgads"
            utm_campaign = parts[1]    # "var1"
        else:
            utm_source = utm_param     # Fallback: весь параметр = source

        logging.info(f"User {user_id} came from: utm_source={utm_source}, utm_campaign={utm_campaign}")

    try:
        # Получаем данные пользователя (если уже существует)
        from datetime import datetime
        user_data = await get_user_data(user_id)

        if not user_data:
            # Новый пользователь
            await add_user(user_id, username, full_name)

            # Сохраняем UTM-метки для новых пользователей
            if utm_source:
                await update_user_field(user_id, 'utm_source', utm_source)
                await update_user_field(user_id, 'utm_campaign', utm_campaign or '')
            if referral_source:
                await update_user_field(user_id, 'referral_source', referral_source)

            # Устанавливаем начальный статус воронки
            await update_user_field(user_id, 'current_stage', 'started')
            await update_user_field(user_id, 'last_interaction_date', datetime.now().isoformat())

            # Логируем начало работы в супергруппу
            await log_user_start(bot, user_id, full_name, username, referral_source)
        else:
            # Повторный запуск — обновляем только timestamp
            await update_user_field(user_id, 'last_interaction_date', datetime.now().isoformat())
            logging.info(f"Existing user {user_id} restarted bot")

    except Exception as e:
        logging.error(f"Failed to add user {user_id}: {e}")
        await message.answer("Произошла техническая ошибка. Попробуйте позже.")
        return

    # Позволяем всем пользователям начать навигацию
    # Проверка подписки будет перед скачиванием PDF
    await show_welcome(message)

async def show_subscription_gate(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Подписаться на канал", url=CHANNEL_URL)],
        [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_sub")]
    ])
    await message.answer(
        "⚓️ <b>Внимание, капитан!</b>\n\n"
        "Чтобы взойти на борт и начать навигацию, пропускной режим требует подписки на канал навигатора.",
        parse_mode="HTML",
        reply_markup=kb
    )

async def show_welcome(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧭 Принять управление", callback_data="start_contract")]
    ])

    if os.path.exists("assets/bort.jpg"):
        photo = FSInputFile("assets/bort.jpg")
        await message.answer_photo(
            photo,
            caption="<b>Добро пожаловать на борт.</b>\n\n"
                    "Это не лекция, это навигация. Я буду твоим бортовым журналом.\n"
                    "Мы соберем твою стратегию здесь, шаг за шагом.\n"
                    "В конце ты получишь PDF-файл с твоими ответами.\n\n"
                    "Условие одно: <b>честность</b>.",
            parse_mode="HTML",
            reply_markup=kb
        )
    else:
        await message.answer(
            "<b>Добро пожаловать на борт.</b>\n\n"
            "Это не лекция, это навигация. Я буду твоим бортовым журналом.\n"
            "Мы соберем твою стратегию здесь, шаг за шагом.\n"
            "В конце ты получишь PDF-файл с твоими ответами.\n\n"
            "Условие одно: <b>честность</b>.",
            parse_mode="HTML", reply_markup=kb
        )

@dp.callback_query(F.data == "check_sub")
async def callback_check_sub(callback: types.CallbackQuery):
    is_subscribed = await check_subscription(callback.from_user.id)
    if is_subscribed:
        await callback.message.delete()
        # Отправляем приветственное сообщение напрямую
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🧭 Принять управление", callback_data="start_contract")]
        ])

        if os.path.exists("assets/bort.jpg"):
            photo = FSInputFile("assets/bort.jpg")
            await bot.send_photo(
                callback.message.chat.id,
                photo,
                caption="<b>Добро пожаловать на борт.</b>\n\n"
                        "Это не лекция, это навигация. Я буду твоим бортовым журналом.\n"
                        "Мы соберем твою стратегию здесь, шаг за шагом.\n"
                        "В конце ты получишь PDF-файл с твоими ответами.\n\n"
                        "Условие одно: <b>честность</b>.",
                parse_mode="HTML",
                reply_markup=kb
            )
        else:
            await bot.send_message(
                callback.message.chat.id,
                "<b>Добро пожаловать на борт.</b>\n\n"
                "Это не лекция, это навигация. Я буду твоим бортовым журналом.\n"
                "Мы соберем твою стратегию здесь, шаг за шагом.\n"
                "В конце ты получишь PDF-файл с твоими ответами.\n\n"
                "Условие одно: <b>честность</b>.",
                parse_mode="HTML",
                reply_markup=kb
            )
    else:
        await callback.answer("Система всё еще не видит подписку. Попробуйте снова.", show_alert=True)

# ==============================
# HELPERS
# ==============================

def _gap_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ Энергия",    callback_data="gap_energy"),
         InlineKeyboardButton(text="🕊 Свобода",    callback_data="gap_freedom")],
        [InlineKeyboardButton(text="🔮 Смысл",      callback_data="gap_meaning"),
         InlineKeyboardButton(text="❤️ Отношения",  callback_data="gap_relations")],
        [InlineKeyboardButton(text="🏃 Тело",       callback_data="gap_body"),
         InlineKeyboardButton(text="💰 Деньги",     callback_data="gap_money")],
        [InlineKeyboardButton(text="✏️ Другое...",  callback_data="gap_other")],
    ])

def _cost_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏥 Здоровье",   callback_data="cost_health"),
         InlineKeyboardButton(text="❤️ Отношения",  callback_data="cost_relations")],
        [InlineKeyboardButton(text="🔮 Смысл",      callback_data="cost_meaning"),
         InlineKeyboardButton(text="🕊 Свобода",    callback_data="cost_freedom")],
        [InlineKeyboardButton(text="💰 Деньги",     callback_data="cost_money"),
         InlineKeyboardButton(text="🏆 Репутация",  callback_data="cost_reputation")],
    ])

def _family_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 В телефоне",  callback_data="fam_phone"),
         InlineKeyboardButton(text="💼 В делах",    callback_data="fam_work")],
        [InlineKeyboardButton(text="🔭 В будущем",  callback_data="fam_future"),
         InlineKeyboardButton(text="😰 В тревоге",  callback_data="fam_worry")],
        [InlineKeyboardButton(text="✅ Я здесь",    callback_data="fam_here")],
    ])

def _anchor_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="😴 Сон",         callback_data="anc_sleep"),
         InlineKeyboardButton(text="🏃 Спорт",       callback_data="anc_sport")],
        [InlineKeyboardButton(text="🚶 Прогулка",    callback_data="anc_walk"),
         InlineKeyboardButton(text="🙏 Молитва",     callback_data="anc_prayer")],
        [InlineKeyboardButton(text="💬 Разговор",    callback_data="anc_talk"),
         InlineKeyboardButton(text="💧 Вода",        callback_data="anc_water")],
        [InlineKeyboardButton(text="✏️ Другое...",   callback_data="anc_other")],
    ])


# ==============================
# Q1 — КУРС
# ==============================

@dp.callback_query(F.data == "start_contract")
async def start_storm_test(callback: types.CallbackQuery, state: FSMContext):
    """Запуск теста 'Шторм' для определения nav_score"""
    await state.set_state(Form.storm_q1)

    # Инициализируем счётчик "Да" ответов в FSM data
    await state.update_data(storm_yes_count=0)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да", callback_data="storm_q1_yes")],
        [InlineKeyboardButton(text="❌ Нет", callback_data="storm_q1_no")]
    ])

    await callback.message.answer(
        "⛈ <b>Проверим навигацию. Тест «Шторм».</b>\n\n"
        "Честно ответь на 3 вопроса:\n\n"
        "<b>Вопрос 1 из 3:</b>\n"
        "Результаты есть, а радости нет?",
        parse_mode="HTML",
        reply_markup=kb
    )
    await callback.answer()


# ==============================
# ТЕСТ "ШТОРМ" (Определение nav_score)
# ==============================

@dp.callback_query(F.data.in_(["storm_q1_yes", "storm_q1_no"]))
async def storm_q1_answer(callback: types.CallbackQuery, state: FSMContext):
    """Обработка ответа на вопрос 1 теста Шторм"""
    data = await state.get_data()
    yes_count = data.get('storm_yes_count', 0)

    if callback.data == "storm_q1_yes":
        yes_count += 1

    await state.update_data(storm_yes_count=yes_count)
    await state.set_state(Form.storm_q2)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да", callback_data="storm_q2_yes")],
        [InlineKeyboardButton(text="❌ Нет", callback_data="storm_q2_no")]
    ])

    await callback.message.answer(
        "<b>Вопрос 2 из 3:</b>\n"
        "Живёшь по инерции?",
        parse_mode="HTML",
        reply_markup=kb
    )
    await callback.answer()


@dp.callback_query(F.data.in_(["storm_q2_yes", "storm_q2_no"]))
async def storm_q2_answer(callback: types.CallbackQuery, state: FSMContext):
    """Обработка ответа на вопрос 2 теста Шторм"""
    data = await state.get_data()
    yes_count = data.get('storm_yes_count', 0)

    if callback.data == "storm_q2_yes":
        yes_count += 1

    await state.update_data(storm_yes_count=yes_count)
    await state.set_state(Form.storm_q3)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да", callback_data="storm_q3_yes")],
        [InlineKeyboardButton(text="❌ Нет", callback_data="storm_q3_no")]
    ])

    await callback.message.answer(
        "<b>Вопрос 3 из 3:</b>\n"
        "Раздражают внешне успешные люди?",
        parse_mode="HTML",
        reply_markup=kb
    )
    await callback.answer()


@dp.callback_query(F.data.in_(["storm_q3_yes", "storm_q3_no"]))
async def storm_q3_answer(callback: types.CallbackQuery, state: FSMContext):
    """Обработка финального ответа теста Шторм и расчёт nav_score"""
    data = await state.get_data()
    yes_count = data.get('storm_yes_count', 0)

    if callback.data == "storm_q3_yes":
        yes_count += 1

    # Вычисляем nav_score
    if yes_count >= 2:
        nav_score = "Переход"
        feedback = (
            "⚠️ <b>Анализ завершён.</b>\n\n"
            "Похоже, твоя старая карта больше не соответствует местности.\n"
            "Это не кризис — это навигационная ошибка."
        )
    else:
        nav_score = "Курс устойчив"
        feedback = (
            "✅ <b>Анализ завершён.</b>\n\n"
            "Курс в целом устойчив, но есть внутренний вопрос."
        )

    # Сохраняем nav_score в БД
    user_id = callback.from_user.id
    await update_user_field(user_id, 'nav_score', nav_score)
    await update_user_field(user_id, 'current_stage', 'answering_1_5')

    logging.info(f"User {user_id} nav_score: {nav_score} (yes_count: {yes_count})")

    # Очищаем временные данные теста
    await state.update_data(storm_yes_count=0)

    # Переходим к первому вопросу анкеты
    await state.set_state(Form.course)
    await callback.message.answer(feedback, parse_mode="HTML")
    await callback.message.answer(
        "🌊 <b>Отходим от берега.</b>\n\n"
        "Первая точка навигации — твой курс.\n\n"
        "Напиши <b>3 слова</b>: куда ты движешься в ближайшие 6–12 месяцев?\n"
        "<i>(Например: масштаб свобода смысл)</i>",
        parse_mode="HTML"
    )
    await callback.answer()


# ==============================
# Q1 — КУРС (3 слова)
# ==============================

@dp.message(Form.course)
async def process_course(message: types.Message, state: FSMContext):
    validation = validate_answer(
        question="Куда ты движешься в ближайшие 6–12 месяцев? (3 слова)",
        answer=message.text,
        context="Ответ — 3 слова-ориентира"
    )
    if not validation.get('is_valid', True):
        await message.answer(
            f"⚠️ {validation.get('feedback', 'Попробуй ещё раз.')}\n\n"
            "Напиши <b>3 слова</b> — куда движешься?",
            parse_mode="HTML"
        )
        return

    await update_user_field(message.from_user.id, "course", message.text)
    await log_user_answer(bot, message.from_user.id, "1. Курс (3 слова)", message.text)

    await state.set_state(Form.role_outer)
    await message.answer(
        "Принято.\n\n"
        "Напиши ОДНИМ словом: <b>кем тебя видят другие?</b>\n"
        "<i>(Твоя роль, функция, маска в глазах окружающих)</i>",
        parse_mode="HTML"
    )


# ==============================
# Q2 — РОЛЬ
# ==============================

@dp.message(Form.role_outer)
async def process_role_outer(message: types.Message, state: FSMContext):
    validation = validate_answer(
        question="Кем тебя видят другие? (одно слово)",
        answer=message.text,
        context="Ответ должен быть одним словом — социальная роль"
    )
    if not validation.get('is_valid', True):
        await message.answer(
            f"⚠️ {validation.get('feedback', 'Попробуй ещё раз.')}\n\n"
            "Одним словом: <b>кем тебя видят другие?</b>",
            parse_mode="HTML"
        )
        return

    await update_user_field(message.from_user.id, "role_outer", message.text)
    await log_user_answer(bot, message.from_user.id, "2. Роль (как видят другие)", message.text)

    await state.set_state(Form.role_inner)
    await message.answer(
        "А теперь честно.\n\n"
        "Одним словом: <b>кем ты ощущаешь себя изнутри</b>, когда никто не видит?",
        parse_mode="HTML"
    )


# ==============================
# Q3 — ЯДРО
# ==============================

@dp.message(Form.role_inner)
async def process_role_inner(message: types.Message, state: FSMContext):
    validation = validate_answer(
        question="Кем ты ощущаешь себя изнутри? (одно слово)",
        answer=message.text,
        context="Ответ — одно слово, внутреннее ощущение"
    )
    if not validation.get('is_valid', True):
        await message.answer(
            f"⚠️ {validation.get('feedback', 'Попробуй ещё раз.')}\n\n"
            "Одним словом: <b>кем ты ощущаешь себя изнутри?</b>",
            parse_mode="HTML"
        )
        return

    await update_user_field(message.from_user.id, "role_inner", message.text)
    await log_user_answer(bot, message.from_user.id, "3. Ядро (внутреннее ощущение)", message.text)

    await state.set_state(Form.gap)
    await message.answer(
        "📍 <b>Разрыв.</b>\n\n"
        "Чего тебе больше всего не хватает прямо сейчас?",
        parse_mode="HTML",
        reply_markup=_gap_kb()
    )


# ==============================
# Q4 — РАЗРЫВ
# ==============================

GAP_MAP = {
    "gap_energy":    "Энергия",
    "gap_freedom":   "Свобода",
    "gap_meaning":   "Смысл",
    "gap_relations": "Отношения",
    "gap_body":      "Тело",
    "gap_money":     "Деньги",
}

@dp.callback_query(F.data.startswith("gap_"))
async def process_gap(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "gap_other":
        await state.set_state(Form.gap_other)
        await callback.message.edit_text(
            "📍 <b>Разрыв — другое.</b>\n\n"
            "Напиши одним словом — чего тебе больше всего не хватает?",
            parse_mode="HTML"
        )
        await callback.answer()
        return

    selected = GAP_MAP.get(callback.data, callback.data)
    await update_user_field(callback.from_user.id, "gap", selected)
    await log_user_answer(bot, callback.from_user.id, "4. Разрыв (чего не хватает)", selected)

    await callback.message.edit_text(f"Принято: {selected}")
    await state.set_state(Form.cost)
    await callback.message.answer(
        "💰 <b>Цена.</b>\n\n"
        "Если долго откладывать себя — приходится платить.\n"
        "<b>Чем платишь ты прямо сейчас?</b>",
        parse_mode="HTML",
        reply_markup=_cost_kb()
    )
    await callback.answer()

@dp.message(Form.gap_other)
async def process_gap_other(message: types.Message, state: FSMContext):
    await update_user_field(message.from_user.id, "gap", message.text)
    await log_user_answer(bot, message.from_user.id, "4. Разрыв (другое)", message.text)

    await state.set_state(Form.cost)
    await message.answer(
        "💰 <b>Цена.</b>\n\n"
        "Если долго откладывать себя — приходится платить.\n"
        "<b>Чем платишь ты прямо сейчас?</b>",
        parse_mode="HTML",
        reply_markup=_cost_kb()
    )


# ==============================
# Q5 — ЦЕНА
# ==============================

COST_MAP = {
    "cost_health":     "Здоровье",
    "cost_relations":  "Отношения",
    "cost_meaning":    "Смысл",
    "cost_freedom":    "Свобода",
    "cost_money":      "Деньги",
    "cost_reputation": "Репутация",
}

@dp.callback_query(F.data.startswith("cost_"))
async def process_cost(callback: types.CallbackQuery, state: FSMContext):
    selected = COST_MAP.get(callback.data, callback.data)
    await update_user_field(callback.from_user.id, "cost_of_delay", selected)
    await log_user_answer(bot, callback.from_user.id, "5. Цена откладывания", selected)

    await callback.message.edit_text(f"Принято: {selected}")
    await state.set_state(Form.family)
    await callback.message.answer(
        "🏠 <b>Семья — это зеркало.</b>\n\n"
        "Когда ты физически дома — где ты находишься ментально?",
        parse_mode="HTML",
        reply_markup=_family_kb()
    )
    await callback.answer()


# ==============================
# Q6 — СЕМЬЯ
# ==============================

FAMILY_MAP = {
    "fam_phone":  "в телефоне",
    "fam_work":   "в делах",
    "fam_future": "в будущем",
    "fam_worry":  "в тревоге",
    "fam_here":   "я здесь",
}

@dp.callback_query(F.data.startswith("fam_"))
async def process_family(callback: types.CallbackQuery, state: FSMContext):
    selected = FAMILY_MAP.get(callback.data, callback.data)
    await update_user_field(callback.from_user.id, "family_presence", selected)
    await log_user_answer(bot, callback.from_user.id, "6. Семья (где ментально)", selected)

    await callback.message.edit_text(f"Записано. Это между нами.")

    # Пауза с дыханием перед якорем
    await callback.message.answer(
        "⚓️ <b>Стоп машина.</b>\n\n"
        "В следующие несколько секунд ничего не пиши. Просто дыши.",
        parse_mode="HTML"
    )

    if os.path.exists("assets/vdoh.jpg"):
        photo = FSInputFile("assets/vdoh.jpg")
        msg = await callback.message.answer_photo(photo, caption="⏳ Тишина... (10 сек)")
    else:
        msg = await callback.message.answer("⏳ Тишина... (10 сек)")

    await asyncio.sleep(10)
    await msg.delete()

    await state.set_state(Form.anchor)
    await callback.message.answer(
        "Тишина закончилась.\n\n"
        "🔋 <b>Якорь восстановления.</b>\n\n"
        "Что тебя реально восстанавливает — когда ты это делаешь?",
        parse_mode="HTML",
        reply_markup=_anchor_kb()
    )
    await callback.answer()


# ==============================
# Q7 — ЯКОРЬ
# ==============================

ANCHOR_MAP = {
    "anc_sleep":  "сон",
    "anc_sport":  "спорт",
    "anc_walk":   "прогулка",
    "anc_prayer": "молитва",
    "anc_talk":   "разговор",
    "anc_water":  "вода",
}

@dp.callback_query(F.data.startswith("anc_"))
async def process_anchor(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "anc_other":
        await state.set_state(Form.anchor_other)
        await callback.message.edit_text(
            "🔋 <b>Якорь — другое.</b>\n\n"
            "Напиши одним словом — что тебя восстанавливает?",
            parse_mode="HTML"
        )
        await callback.answer()
        return

    selected = ANCHOR_MAP.get(callback.data, callback.data)
    await update_user_field(callback.from_user.id, "anchor_word", selected)
    await log_user_answer(bot, callback.from_user.id, "7. Якорь восстановления", selected)

    await callback.message.edit_text(f"Принято: {selected}")
    await state.set_state(Form.stop_action)
    await callback.message.answer(
        "🔄 <b>Повороты.</b>\n\n"
        "Одно действие, которое тебе важно <b>остановить</b> прямо сейчас.\n"
        "<i>(Не объяснение — одно конкретное действие)</i>",
        parse_mode="HTML"
    )
    await callback.answer()

@dp.message(Form.anchor_other)
async def process_anchor_other(message: types.Message, state: FSMContext):
    await update_user_field(message.from_user.id, "anchor_word", message.text)
    await log_user_answer(bot, message.from_user.id, "7. Якорь (другое)", message.text)

    await state.set_state(Form.stop_action)
    await message.answer(
        "🔄 <b>Повороты.</b>\n\n"
        "Одно действие, которое тебе важно <b>остановить</b> прямо сейчас.\n"
        "<i>(Не объяснение — одно конкретное действие)</i>",
        parse_mode="HTML"
    )


# ==============================
# Q8 — ПОВОРОТ (СТОП)
# ==============================

@dp.message(Form.stop_action)
async def process_stop_action(message: types.Message, state: FSMContext):
    validation = validate_answer(
        question="Одно действие, которое важно остановить прямо сейчас",
        answer=message.text,
        context="Ответ — одно конкретное действие или привычка"
    )
    if not validation.get('is_valid', True):
        await message.answer(
            f"⚠️ {validation.get('feedback', 'Попробуй ещё раз.')}\n\n"
            "Одно действие, которое важно <b>остановить</b>?",
            parse_mode="HTML"
        )
        return

    await update_user_field(message.from_user.id, "stop_action", message.text)
    await log_user_answer(bot, message.from_user.id, "8. Поворот (что остановить)", message.text)

    await state.set_state(Form.first_step)
    await message.answer(
        "👣 <b>Первый шаг.</b>\n\n"
        "Одно действие, которое ты готов делать <b>3 раза в неделю</b> — для себя.\n"
        "<i>(Конкретно и реалистично)</i>",
        parse_mode="HTML"
    )


# ==============================
# Q9 — ПЕРВЫЙ ШАГ
# ==============================

@dp.message(Form.first_step)
async def process_first_step(message: types.Message, state: FSMContext):
    validation = validate_answer(
        question="Одно действие, которое ты готов делать 3 раза в неделю — для себя",
        answer=message.text,
        context="Ответ — конкретное регулярное действие"
    )
    if not validation.get('is_valid', True):
        await message.answer(
            f"⚠️ {validation.get('feedback', 'Попробуй ещё раз.')}\n\n"
            "Одно действие <b>3 раза в неделю</b>?",
            parse_mode="HTML"
        )
        return

    await update_user_field(message.from_user.id, "first_step", message.text)
    await log_user_answer(bot, message.from_user.id, "9. Первый шаг (3х в неделю)", message.text)

    await state.set_state(Form.final)

    if os.path.exists("assets/bereg.jpg"):
        photo = FSInputFile("assets/bereg.jpg")
        await message.answer_photo(
            photo,
            caption="🏁 <b>Мы подходим к берегу.</b>\n\n"
                    "Последний вопрос.\n\n"
                    "<b>Какой главный вопрос ты забираешь с собой из этой навигации?</b>\n"
                    "<i>(Одна строка)</i>",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "🏁 <b>Мы подходим к берегу.</b>\n\n"
            "Последний вопрос.\n\n"
            "<b>Какой главный вопрос ты забираешь с собой из этой навигации?</b>\n"
            "<i>(Одна строка)</i>",
            parse_mode="HTML"
        )


# ==============================
# Q10 — ГЛАВНЫЙ ВОПРОС
# ==============================

@dp.message(Form.final)
async def process_final(message: types.Message, state: FSMContext):
    validation = validate_answer(
        question="Какой главный вопрос ты забираешь с собой?",
        answer=message.text,
        context="Личный вопрос о стратегии, смысле или жизни"
    )
    if not validation.get('is_valid', True):
        await message.answer(
            f"⚠️ {validation.get('feedback', 'Попробуй ещё раз.')}\n\n"
            "Попробуй ещё раз: <b>Какой главный вопрос ты забираешь?</b>",
            parse_mode="HTML"
        )
        return

    await update_user_field(message.from_user.id, "final_question", message.text)
    await log_user_answer(bot, message.from_user.id, "10. Главный вопрос стратегии", message.text)

    await state.clear()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Скачать стратегию", callback_data="download_pdf")]
    ])

    if os.path.exists("assets/prichal.jpg"):
        photo = FSInputFile("assets/prichal.jpg")
        await message.answer_photo(
            photo,
            caption="⚓️ <b>Швартовка завершена.</b>\n\n"
                    "Твой бортовой журнал заполнен и готов к выдаче.",
            parse_mode="HTML",
            reply_markup=kb
        )
    else:
        await message.answer(
            "⚓️ <b>Швартовка завершена.</b>\n\n"
            "Твой бортовой журнал заполнен и готов к выдаче.",
            parse_mode="HTML",
            reply_markup=kb
        )

async def _send_pdf(message: types.Message, user_id: int):
    """Генерирует и отправляет PDF пользователю."""
    await message.answer("⏳ Формирую документ...")

    user_data = await get_user_data(user_id)
    if not user_data:
        await message.answer("Ошибка: данные не найдены.")
        return

    filename = f"Strategy_{user_id}.pdf"
    try:
        pdf_file = create_pdf(user_data, filename)
        if pdf_file:
            doc = FSInputFile(pdf_file)
            await message.answer_document(
                doc,
                caption="Ваша Личная Стратегия готова.\n\n"
                        "Навигация продолжается в канале @DusenkoRoman\n"
                        "Записаться на диагностику: personalstrategy.romandusenko.ru/form/"
            )
            await log_user_pdf(bot, user_id, pdf_file)
            os.remove(pdf_file)

            # ========== CONVERSION FUNNEL ==========
            from datetime import datetime
            from scheduler import schedule_message
            from database import update_stage, update_user_field

            # Сохраняем timestamp отправки PDF
            await update_user_field(user_id, 'pdf_sent_at', datetime.now().isoformat())
            await update_stage(user_id, 'pdf_delivered')

            # Планируем AI-разбор через 30 минут
            await schedule_message(
                user_id=user_id,
                message_type='ai_analysis_30min',
                delay_hours=0.5  # 30 минут
            )

            # Планируем drip-цепочку из 3 сообщений
            await schedule_message(user_id, 'drip_day1', delay_hours=24)      # +1 день
            await schedule_message(user_id, 'drip_day3', delay_hours=72)      # +3 дня
            await schedule_message(user_id, 'drip_day7', delay_hours=168)     # +7 дней

            # Планируем "Зеркало" через 7 дней
            await schedule_message(user_id, 'mirror_day7', delay_hours=168)   # +7 дней

            logging.info(f"Scheduled conversion funnel for user {user_id}")

        else:
            await message.answer("Ошибка генерации PDF (проблема со шрифтами).")
    except Exception as e:
        logging.error(f"PDF Error for user {user_id}: {e}", exc_info=True)
        await message.answer(f"Произошла техническая ошибка при создании файла.\nОшибка: {str(e)[:100]}")


@dp.callback_query(F.data == "download_pdf")
async def generate_and_send_pdf(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    is_subscribed = await check_subscription(user_id)

    if not is_subscribed:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Подписаться на канал", url=CHANNEL_URL)],
            [InlineKeyboardButton(text="✅ Я подписался, скачать PDF", callback_data="check_sub_and_download")]
        ])
        await callback.message.answer(
            "⚓️ <b>Навигация завершена!</b>\n\n"
            "Чтобы получить PDF, необходимо подписаться на канал Навигатора — там продолжение пути.",
            parse_mode="HTML",
            reply_markup=kb
        )
        await callback.answer()
        return

    await callback.answer()
    await _send_pdf(callback.message, user_id)

@dp.callback_query(F.data == "check_sub_and_download")
async def check_subscription_and_download(callback: types.CallbackQuery):
    """Проверяет подписку и скачивает PDF если пользователь подписался"""
    user_id = callback.from_user.id
    is_subscribed = await check_subscription(user_id)

    if not is_subscribed:
        await callback.answer(
            "❌ Система не видит подписку на канал.\n\nУбедитесь, что вы подписались, и попробуйте снова.",
            show_alert=True
        )
        return

    await callback.answer()
    await _send_pdf(callback.message, user_id)

# ==============================
# ADMIN COMMANDS
# ==============================

async def admin_guard(message: types.Message) -> bool:
    """Возвращает True если пользователь - админ, иначе отправляет отказ."""
    if not await is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав для этой команды.")
        return False
    return True


@dp.message(Command("firstadmin"))
async def cmd_firstadmin(message: types.Message):
    """Добавляет первого админа. Работает ТОЛЬКО когда список админов пуст."""
    admins = await get_admins()
    if admins:
        await message.answer("⛔ Команда недоступна: список админов уже настроен.")
        return
    user_id = message.from_user.id
    username = message.from_user.username or ""
    await add_admin(user_id, username)
    await message.answer(
        f"✅ <b>Вы добавлены как первый администратор.</b>\n\n"
        f"ID: <code>{user_id}</code>\n\n"
        f"Теперь вам доступны команды /admins, /help, /broadcast.\n"
        f"Для постоянной настройки добавьте в .env:\n"
        f"<code>ADMIN_IDS={user_id}</code>",
        parse_mode="HTML"
    )
    logging.info(f"First admin set: {user_id} (@{username})")


@dp.message(Command("dev"))
async def cmd_dev(message: types.Message):
    if not await admin_guard(message):
        return
    await message.answer(
        "💻 Разработка телеграм ботов любой сложности\n"
        "@uspeshnyy"
    )


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    if not await admin_guard(message):
        return
    help_text = (
        "🧭 <b>Навигатор Личной Стратегии — Admin Help</b>\n\n"
        "<b>Команды бота:</b>\n"
        "/broadcast — рассылка всем прошедшим опрос\n"
        "/admins — управление списком админов\n"
        "/leads — показать горячих лидов (сегментация)\n"
        "/export — выгрузить базу в CSV\n"
        "/dev — контакт разработчика\n"
        "/help — это сообщение\n\n"
        "<b>Как работает бот:</b>\n"
        "1️⃣ Пользователь проходит 7 вопросов\n"
        "2️⃣ Подписывается на @DusenkoRoman\n"
        "3️⃣ Получает персональный PDF\n\n"
        "<b>Deep links (UTM-трекинг):</b>\n"
        "<code>https://t.me/DusenkoQuizBot?start=tgads_var1</code>\n"
        "<code>https://t.me/DusenkoQuizBot?start=instagram_story</code>\n"
        "Формат: SOURCE_CAMPAIGN (сохраняется в utm_source + utm_campaign)\n\n"
        "<b>Автоматические отчёты:</b>\n"
        "• Ежедневный отчёт по воронке — каждый день в 10:00\n"
        "• Статистика: новые запуски, PDF, конверсии, сегментация\n\n"
        "<b>📚 Документация:</b>\n"
        "• <a href='https://uspeshnyy.notion.site/Navigator-Bot-AI-Powered-Telegram-Bot-2ffbf815097280dea14cd8d547999cf6'>Общая документация бота</a>\n"
        "• <a href='https://uspeshnyy.notion.site/Navigator-Bot-PDF-gen-prompt-2ffbf81509728024a0d6e02058419d63'>Алгоритм генерации PDF</a>\n"
        "• <a href='https://romandusenko.ru/quiz/?utm_campaign=from_help_in_bot'>Лендинг квиза</a>\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "Разработчик: @uspeshnyy"
    )
    await message.answer(help_text, parse_mode="HTML", disable_web_page_preview=True)


# --- /admins ---

@dp.message(Command("admins"))
async def cmd_admins(message: types.Message):
    if not await admin_guard(message):
        return
    await show_admins_list(message)


# ==============================
# КОМАНДЫ АНАЛИТИКИ (Фича #6)
# ==============================

@dp.message(Command("leads"))
async def cmd_leads(message: types.Message):
    """Показывает список горячих лидов с сегментацией"""
    # Проверка прав (только в админской группе или для админов)
    if message.chat.id != LOG_GROUP_ID and not await is_admin(message.from_user.id):
        return

    from admin_analytics import get_hot_leads

    leads = await get_hot_leads()

    if not leads:
        await message.answer("📊 Горячих лидов нет.")
        return

    # Группировка по сегментам
    transition_leads = [l for l in leads if l.get('nav_score') == 'Переход']
    stable_leads = [l for l in leads if l.get('nav_score') == 'Курс устойчив']

    text = "🔥 <b>Горячие лиды (Сегмент «Переход»):</b>\n\n"
    for i, lead in enumerate(transition_leads[:10], 1):
        username_display = f"@{lead['username']}" if lead.get('username') else f"ID {lead['user_id']}"
        source = f"{lead.get('utm_source', '')}_{lead.get('utm_campaign', '')}" if lead.get('utm_source') else "organic"
        text += (
            f"{i}. {username_display} "
            f"(Источник: <code>{source}</code>)\n"
            f"   Платит: <i>{lead.get('cost_of_delay', 'N/A')}</i>. "
            f"Этап: <i>{lead.get('current_stage', 'N/A')}</i>\n\n"
        )

    text += "\n🟢 <b>Лиды (Сегмент «Курс устойчив»):</b>\n\n"
    for i, lead in enumerate(stable_leads[:10], 1):
        username_display = f"@{lead['username']}" if lead.get('username') else f"ID {lead['user_id']}"
        source = f"{lead.get('utm_source', '')}_{lead.get('utm_campaign', '')}" if lead.get('utm_source') else "organic"
        text += (
            f"{i}. {username_display} "
            f"(Источник: <code>{source}</code>)\n"
            f"   Платит: <i>{lead.get('cost_of_delay', 'N/A')}</i>. "
            f"Этап: <i>{lead.get('current_stage', 'N/A')}</i>\n\n"
        )

    await message.answer(text, parse_mode="HTML")


@dp.message(Command("export"))
async def cmd_export(message: types.Message):
    """Экспорт базы лидов в CSV"""
    if message.chat.id != LOG_GROUP_ID and not await is_admin(message.from_user.id):
        return

    from admin_analytics import export_leads_csv
    from aiogram.types import BufferedInputFile

    await message.answer("⏳ Генерирую выгрузку...")

    csv_file = await export_leads_csv()
    filename = f"leads_export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"

    doc = BufferedInputFile(csv_file.read(), filename=filename)
    await message.answer_document(
        doc,
        caption="📄 <b>Выгрузка базы лидов</b>\n\nГотово к импорту в CRM.",
        parse_mode="HTML"
    )


async def show_admins_list(message: types.Message):
    admins = await get_admins()
    if not admins:
        text = "📋 <b>Список админов пуст.</b>"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить админа", callback_data="admin_add")]
        ])
    else:
        text = "📋 <b>Список админов:</b>\n\n"
        buttons = []
        for a in admins:
            label = f"@{a['username']}" if a.get('username') else f"ID {a['user_id']}"
            text += f"• {label} (<code>{a['user_id']}</code>)\n"
            buttons.append([
                InlineKeyboardButton(
                    text=f"❌ Удалить {label}",
                    callback_data=f"admin_del_{a['user_id']}"
                )
            ])
        buttons.append([InlineKeyboardButton(text="➕ Добавить", callback_data="admin_add")])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    await message.answer(text, parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data == "admin_add")
async def cb_admin_add(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав.", show_alert=True)
        return
    await state.set_state(AdminAdd.waiting_user_id)
    await callback.message.answer(
        "Введите <b>Telegram ID</b> нового админа (только цифры).\n"
        "Узнать ID можно через @userinfobot",
        parse_mode="HTML"
    )
    await callback.answer()

@dp.message(AdminAdd.waiting_user_id)
async def process_admin_add(message: types.Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("⚠️ Введите числовой Telegram ID.")
        return
    new_id = int(message.text.strip())
    await add_admin(new_id)
    await state.clear()
    await message.answer(f"✅ Пользователь <code>{new_id}</code> добавлен как админ.", parse_mode="HTML")

@dp.callback_query(F.data.startswith("admin_del_"))
async def cb_admin_del(callback: types.CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав.", show_alert=True)
        return
    target_id = int(callback.data.split("admin_del_")[1])
    if target_id == callback.from_user.id:
        await callback.answer("⚠️ Нельзя удалить самого себя.", show_alert=True)
        return
    await remove_admin(target_id)
    await callback.answer(f"Админ {target_id} удалён.")
    # Обновляем список
    await callback.message.delete()
    await show_admins_list(callback.message)


# --- /broadcast ---

@dp.message(Command("broadcast"))
async def cmd_broadcast(message: types.Message, state: FSMContext):
    if not await admin_guard(message):
        return
    users = await get_users_with_pdf()
    await state.set_state(AdminBroadcast.waiting_message)
    await state.update_data(recipients_count=len(users))
    await message.answer(
        f"📢 <b>Массовая рассылка</b>\n\n"
        f"Получателей: <b>{len(users)}</b> (прошли весь опрос)\n\n"
        f"Отправьте сообщение для рассылки.\n"
        f"Поддерживается: текст, фото, документ, видео.\n\n"
        f"Для отмены: /cancel",
        parse_mode="HTML"
    )

@dp.message(Command("cancel"), AdminBroadcast.waiting_message)
@dp.message(Command("cancel"), AdminBroadcast.waiting_confirm)
@dp.message(Command("cancel"), AdminAdd.waiting_user_id)
async def cmd_cancel_admin(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Отменено.")

@dp.message(AdminBroadcast.waiting_message)
async def broadcast_preview(message: types.Message, state: FSMContext):
    data = await state.get_data()
    count = data.get("recipients_count", 0)

    # Сохраняем данные сообщения для рассылки
    msg_data = {"type": None}
    if message.text:
        msg_data = {"type": "text", "text": message.text}
    elif message.photo:
        msg_data = {"type": "photo", "file_id": message.photo[-1].file_id, "caption": message.caption}
    elif message.document:
        msg_data = {"type": "document", "file_id": message.document.file_id, "caption": message.caption}
    elif message.video:
        msg_data = {"type": "video", "file_id": message.video.file_id, "caption": message.caption}
    else:
        await message.answer("⚠️ Неподдерживаемый тип. Отправьте текст, фото, документ или видео.")
        return

    await state.update_data(msg_data=msg_data)
    await state.set_state(AdminBroadcast.waiting_confirm)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"✅ Разослать {count} пользователям", callback_data="broadcast_confirm"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast_cancel")
        ]
    ])
    await message.answer(
        f"👆 Сообщение выше будет разослано <b>{count}</b> пользователям.\n"
        f"Подтверждаете?",
        parse_mode="HTML",
        reply_markup=kb
    )

@dp.callback_query(F.data == "broadcast_cancel")
async def cb_broadcast_cancel(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Рассылка отменена.")

@dp.callback_query(F.data == "broadcast_confirm")
async def cb_broadcast_confirm(callback: types.CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет прав.", show_alert=True)
        return

    data = await state.get_data()
    msg_data = data.get("msg_data", {})
    await state.clear()

    users = await get_users_with_pdf()
    await callback.message.edit_text(f"⏳ Рассылка запущена... ({len(users)} получателей)")
    await callback.answer()

    sent, failed = 0, 0
    for user_id in users:
        try:
            t = msg_data.get("type")
            if t == "text":
                await bot.send_message(user_id, msg_data["text"])
            elif t == "photo":
                await bot.send_photo(user_id, msg_data["file_id"], caption=msg_data.get("caption"))
            elif t == "document":
                await bot.send_document(user_id, msg_data["file_id"], caption=msg_data.get("caption"))
            elif t == "video":
                await bot.send_video(user_id, msg_data["file_id"], caption=msg_data.get("caption"))
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # Не превышаем лимиты Telegram

    await callback.message.answer(
        f"✅ <b>Рассылка завершена</b>\n\n"
        f"Доставлено: {sent}\n"
        f"Ошибок: {failed}",
        parse_mode="HTML"
    )


LOG_GROUP_ID = int(os.getenv("LOG_GROUP_ID", "-1003535325557"))


@dp.message(F.chat.type == "private")
async def relay_from_user_to_topic(message: types.Message, state: FSMContext):
    """
    Пересылает сообщения от пользователя в его топик в супергруппе.
    Срабатывает только если нет активного FSM-состояния (вне процесса заполнения формы).
    Создаёт двусторонний чат: админ пишет в топик → пользователь получает в боте,
    пользователь отвечает боту → сообщение попадает в топик.
    """
    # Не пересылаем если пользователь в середине заполнения формы
    current_state = await state.get_state()
    if current_state is not None:
        return

    user_id = message.from_user.id
    full_name = message.from_user.full_name

    # Получаем topic_id пользователя из БД
    user_data = await get_user_data(user_id)
    if not user_data or not user_data.get("topic_id"):
        return  # Нет топика — не пересылаем

    topic_id = user_data["topic_id"]
    prefix = f"💬 <b>{full_name}:</b>\n"

    try:
        if message.text:
            await bot.send_message(
                chat_id=LOG_GROUP_ID,
                message_thread_id=topic_id,
                text=prefix + message.text,
                parse_mode="HTML"
            )
        elif message.photo:
            await bot.send_photo(
                chat_id=LOG_GROUP_ID,
                photo=message.photo[-1].file_id,
                caption=prefix + (message.caption or ""),
                message_thread_id=topic_id,
                parse_mode="HTML"
            )
        elif message.document:
            await bot.send_document(
                chat_id=LOG_GROUP_ID,
                document=message.document.file_id,
                caption=prefix + (message.caption or ""),
                message_thread_id=topic_id,
                parse_mode="HTML"
            )
        elif message.video:
            await bot.send_video(
                chat_id=LOG_GROUP_ID,
                video=message.video.file_id,
                caption=prefix + (message.caption or ""),
                message_thread_id=topic_id,
                parse_mode="HTML"
            )
        elif message.voice:
            await bot.send_voice(
                chat_id=LOG_GROUP_ID,
                voice=message.voice.file_id,
                message_thread_id=topic_id
            )
            await bot.send_message(
                chat_id=LOG_GROUP_ID,
                message_thread_id=topic_id,
                text=prefix.strip(),
                parse_mode="HTML"
            )
        elif message.sticker:
            await bot.send_sticker(
                chat_id=LOG_GROUP_ID,
                sticker=message.sticker.file_id,
                message_thread_id=topic_id
            )
        else:
            return  # Неподдерживаемый тип

        logging.info(f"Relay user→topic: user {user_id} → topic {topic_id}")

    except Exception as e:
        logging.error(f"Relay user→topic failed for {user_id}: {e}")


@dp.message(F.chat.id == LOG_GROUP_ID)
async def relay_from_group_to_user(message: types.Message):
    """
    Пересылает сообщения из топика супергруппы пользователю в личный чат.
    Срабатывает когда админ пишет в топик конкретного пользователя.
    """
    # Игнорируем сообщения без топика (общий чат группы)
    if not message.message_thread_id:
        return

    # Игнорируем сообщения от самого бота
    if message.from_user and message.from_user.is_bot:
        return

    topic_id = message.message_thread_id
    user_id = await get_user_id_by_topic(topic_id)

    if not user_id:
        logging.warning(f"Relay: no user found for topic_id={topic_id}")
        return

    try:
        # Пересылаем с учетом типа контента
        if message.text:
            await bot.send_message(user_id, message.text)

        elif message.photo:
            await bot.send_photo(
                user_id,
                message.photo[-1].file_id,
                caption=message.caption
            )
        elif message.document:
            await bot.send_document(
                user_id,
                message.document.file_id,
                caption=message.caption
            )
        elif message.video:
            await bot.send_video(
                user_id,
                message.video.file_id,
                caption=message.caption
            )
        elif message.voice:
            await bot.send_voice(user_id, message.voice.file_id)

        elif message.sticker:
            await bot.send_sticker(user_id, message.sticker.file_id)

        elif message.audio:
            await bot.send_audio(
                user_id,
                message.audio.file_id,
                caption=message.caption
            )
        else:
            logging.info(f"Relay: unsupported message type from topic {topic_id}")
            return

        logging.info(f"Relay: message from topic {topic_id} forwarded to user {user_id}")

    except Exception as e:
        logging.error(f"Relay: failed to forward message to user {user_id}: {e}")


# ================================
# CONVERSION CALLBACKS
# ================================

@dp.callback_query(F.data == "diagnostic_booked")
async def cb_diagnostic_booked(callback: types.CallbackQuery):
    """Обработчик кнопки 'Я уже записался'"""
    user_id = callback.from_user.id

    try:
        from database import update_stage, update_user_field, get_user_data
        from scheduler import cancel_scheduled_messages

        # Обновляем статус в БД
        await update_stage(user_id, 'diagnostic_booked')

        # Сохраняем источник конверсии
        user_data = await get_user_data(user_id)
        if user_data:
            current_stage = user_data.get('current_stage', 'manual')
            await update_user_field(user_id, 'conversion_source', current_stage)

            # Отменяем все будущие scheduled сообщения
            await cancel_scheduled_messages(user_id)

            # Уведомляем пользователя
            await callback.message.answer(
                "🎉 <b>Отлично!</b>\n\n"
                "Все запланированные сообщения отменены.\n"
                "До встречи на диагностике!",
                parse_mode="HTML"
            )

            # Уведомляем в админскую группу
            utm_info = ""
            if user_data.get('utm_source'):
                utm_info = f"\nИсточник: {user_data['utm_source']}_{user_data.get('utm_campaign', '')}"

            await bot.send_message(
                LOG_GROUP_ID,
                f"🎯 <b>КОНВЕРСИЯ!</b>\n\n"
                f"Пользователь <b>{user_data['full_name']}</b> "
                f"(@{user_data.get('username', 'unknown')}) записался на диагностику.{utm_info}\n"
                f"Конверсия через: <code>{current_stage}</code>",
                parse_mode="HTML"
            )

            logging.info(f"User {user_id} converted! Source: {current_stage}")

        await callback.answer()

    except Exception as e:
        logging.error(f"Failed to handle diagnostic_booked for user {user_id}: {e}", exc_info=True)
        await callback.answer("Произошла ошибка. Попробуйте позже.", show_alert=True)


@dp.callback_query(F.data == "resume_form")
async def cb_resume_form(callback: types.CallbackQuery, state: FSMContext):
    """Возобновляет FSM с того места, где пользователь остановился"""
    user_id = callback.from_user.id

    try:
        from database import get_user_data

        user_data = await get_user_data(user_id)
        if not user_data:
            await callback.message.answer("Ошибка: данные не найдены.")
            await callback.answer()
            return

        # Определяем следующее состояние
        next_state = _get_next_state(user_data)

        if next_state:
            await state.set_state(next_state)
            await callback.message.answer("Продолжаем навигацию. Вот следующий вопрос:")

            # TODO: Нужно вызвать соответствующий обработчик для next_state
            # Пока просто подтверждаем
            await callback.message.answer(
                "Перезапустите бота командой /start для продолжения опроса."
            )
        else:
            await callback.message.answer("Не удалось определить следующий вопрос.")

        await callback.answer()

    except Exception as e:
        logging.error(f"Failed to resume form for user {user_id}: {e}", exc_info=True)
        await callback.answer("Произошла ошибка.", show_alert=True)


@dp.callback_query(F.data == "dismiss_reactivation")
async def cb_dismiss_reactivation(callback: types.CallbackQuery):
    """Отклоняет реактивацию"""
    await callback.message.edit_text("Хорошо. Когда будешь готов — я здесь.")
    await callback.answer()


def _get_next_state(user_data: dict):
    """Определяет следующее FSM-состояние на основе заполненных полей"""
    from states import Form

    if not user_data.get('course'):
        return Form.course
    elif not user_data.get('role_outer'):
        return Form.role_outer
    elif not user_data.get('role_inner'):
        return Form.role_inner
    elif not user_data.get('gap'):
        return Form.gap
    elif not user_data.get('cost_of_delay'):
        return Form.cost
    elif not user_data.get('family_presence'):
        return Form.family
    elif not user_data.get('anchor_word'):
        return Form.anchor
    elif not user_data.get('stop_action'):
        return Form.stop_action
    elif not user_data.get('first_step'):
        return Form.first_step
    elif not user_data.get('final_question'):
        return Form.final
    else:
        return None  # Всё заполнено


async def main():
    """Главная функция запуска бота"""
    logging.info("Starting Navigator Bot...")
    await init_db()
    logging.info("Database initialized")

    # Добавляем начальных админов из .env (ADMIN_IDS=123,456)
    admin_ids_str = os.getenv("ADMIN_IDS", "")
    if admin_ids_str:
        for uid_str in admin_ids_str.split(","):
            uid_str = uid_str.strip()
            if uid_str.isdigit():
                await add_admin(int(uid_str))
                logging.info(f"Initial admin ensured: {uid_str}")

    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
