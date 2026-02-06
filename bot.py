import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

from database import init_db, add_user, update_user_field, get_user_data
from states import Form
from pdf_gen import create_pdf
from openai_assistant import validate_answer
from topic_logger import log_user_start, log_user_answer, log_user_pdf

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
CHANNEL_URL = os.getenv("CHANNEL_URL")

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

    # Извлекаем параметр источника из deep link (/start SOURCE)
    referral_source = None
    if message.text and len(message.text.split()) > 1:
        referral_source = message.text.split()[1]
        logging.info(f"User {user_id} came from source: {referral_source}")

    try:
        await add_user(user_id, username, full_name)

        # Сохраняем источник перехода если есть
        if referral_source:
            await update_user_field(user_id, 'referral_source', referral_source)

        # Логируем начало работы в супергруппу
        await log_user_start(bot, user_id, full_name, username, referral_source)

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

@dp.callback_query(F.data == "start_contract")
async def step_role_outer(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(Form.role_outer)
    await callback.message.answer(
        "🌊 <b>Отходим от берега.</b>\n\n"
        "Напиши ОДНИМ словом: <b>Кем тебя видят другие?</b>\n"
        "(Твоя социальная роль, функция, маска).",
        parse_mode="HTML"
    )

@dp.message(Form.role_outer)
async def process_role_outer(message: types.Message, state: FSMContext):
    # Валидация ответа через ChatGPT
    validation = validate_answer(
        question="Кем тебя видят другие? (Твоя социальная роль, функция)",
        answer=message.text,
        context="Ответ должен быть одним словом, описывающим социальную роль"
    )

    if not validation.get('is_valid', True):
        # Ответ невалидный - просим переформулировать
        feedback = validation.get('feedback', 'Пожалуйста, ответь более конкретно.')
        await message.answer(
            f"⚠️ {feedback}\n\n"
            "Попробуй ещё раз: <b>Кем тебя видят другие?</b> (Одним словом)",
            parse_mode="HTML"
        )
        return

    # Ответ валидный - сохраняем и продолжаем
    await update_user_field(message.from_user.id, "role_outer", message.text)

    # Логируем ответ в супергруппу
    await log_user_answer(bot, message.from_user.id, "1. Внешняя роль (как видят)", message.text)

    await state.set_state(Form.role_inner)
    await message.answer(
        "Принято.\n\n"
        "А теперь честно: <b>Кем ты ощущаешь себя изнутри</b>, когда никто не видит?\n"
        "(Тоже одним словом).",
        parse_mode="HTML"
    )

@dp.message(Form.role_inner)
async def process_role_inner(message: types.Message, state: FSMContext):
    # Валидация ответа через ChatGPT
    validation = validate_answer(
        question="Кем ты ощущаешь себя изнутри, когда никто не видит?",
        answer=message.text,
        context="Ответ должен быть одним словом, описывающим внутреннее ощущение"
    )

    if not validation.get('is_valid', True):
        # Ответ невалидный - просим переформулировать
        feedback = validation.get('feedback', 'Пожалуйста, ответь более искренне.')
        await message.answer(
            f"⚠️ {feedback}\n\n"
            "Попробуй ещё раз: <b>Кем ты ощущаешь себя изнутри?</b> (Одним словом)",
            parse_mode="HTML"
        )
        return

    # Ответ валидный - сохраняем и продолжаем
    await update_user_field(message.from_user.id, "role_inner", message.text)

    # Логируем ответ в супергруппу
    await log_user_answer(bot, message.from_user.id, "2. Внутреннее ощущение", message.text)

    await state.set_state(Form.quiz)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да", callback_data="quiz_1_yes"),
         InlineKeyboardButton(text="Нет", callback_data="quiz_1_no")]
    ])

    await state.update_data(quiz_score=0)
    await message.answer(
        "🔄 <b>Повороты. Проверим навигацию.</b>\n\n"
        "Вопрос 1/3: Результаты есть, а радости нет?",
        parse_mode="HTML", reply_markup=kb
    )

@dp.callback_query(F.data.startswith("quiz_"))
async def process_quiz(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    score = data.get("quiz_score", 0)
    
    if "yes" in callback.data:
        score += 1
    
    await state.update_data(quiz_score=score)
    
    if "quiz_1" in callback.data:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Да", callback_data="quiz_2_yes"), 
             InlineKeyboardButton(text="Нет", callback_data="quiz_2_no")]
        ])
        await callback.message.edit_text("Вопрос 2/3: Живешь по инерции?", reply_markup=kb)
        
    elif "quiz_2" in callback.data:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Да", callback_data="quiz_3_yes"), 
             InlineKeyboardButton(text="Нет", callback_data="quiz_3_no")]
        ])
        await callback.message.edit_text("Вопрос 3/3: Раздражают внешне успешные люди?", reply_markup=kb)
        
    elif "quiz_3" in callback.data:
        result = "Точка перехода" if score >= 2 else "Курс устойчив"
        await update_user_field(callback.from_user.id, "nav_score", result)

        # Логируем результат квиза в супергруппу
        await log_user_answer(bot, callback.from_user.id, "3. Состояние навигации (тест)", result)

        await state.set_state(Form.family)
        await callback.message.edit_text(
            f"📊 Анализ завершен.\nСтатус: <b>{result}</b>\n\n"
            "Движемся дальше...", parse_mode="HTML"
        )
        await asyncio.sleep(1)
        await callback.message.answer(
            "🏠 <b>Семья — это зеркало.</b>\n\n"
            "Когда ты физически дома, где ты находишься ментально?\n"
            "(В телефоне, в сделке, в будущем? Напиши честно).",
            parse_mode="HTML"
        )

@dp.message(Form.family)
async def process_family(message: types.Message, state: FSMContext):
    # Валидация ответа через ChatGPT
    validation = validate_answer(
        question="Когда ты физически дома, где ты находишься ментально?",
        answer=message.text,
        context="Ответ должен описывать ментальное состояние, место внимания (в телефоне, в работе, в мыслях о будущем и т.д.)"
    )

    if not validation.get('is_valid', True):
        # Ответ невалидный - просим переформулировать
        feedback = validation.get('feedback', 'Пожалуйста, ответь более подробно.')
        await message.answer(
            f"⚠️ {feedback}\n\n"
            "Попробуй ещё раз: <b>Где ты находишься ментально, когда физически дома?</b>",
            parse_mode="HTML"
        )
        return

    # Ответ валидный - сохраняем и продолжаем
    await update_user_field(message.from_user.id, "family_presence", message.text)

    # Логируем ответ в супергруппу
    await log_user_answer(bot, message.from_user.id, "4. Где я ментально, когда физически дома", message.text)

    await state.set_state(Form.anchor)
    await message.answer("Записано в журнал. Это останется только между нами.")
    await asyncio.sleep(1)

    await message.answer("⚓️ <b>Стоп машина. Якорная стоянка.</b>\n\n"
                         "В следующие несколько секунд ничего не пиши. Просто дыши.", parse_mode="HTML")

    # Отправляем изображение вдоха с таймером
    if os.path.exists("assets/vdoh.jpg"):
        photo = FSInputFile("assets/vdoh.jpg")
        msg = await message.answer_photo(photo, caption="⏳ Тишина... (10 сек)")
    else:
        msg = await message.answer("⏳ Тишина... (10 сек)")

    await asyncio.sleep(10)
    await msg.delete()

    await message.answer(
        "Тишина закончилась.\n\n"
        "<b>Напиши одно слово-состояние</b>, которое ты сейчас чувствуешь.",
        parse_mode="HTML"
    )

@dp.message(Form.anchor)
async def process_anchor(message: types.Message, state: FSMContext):
    # Валидация ответа через ChatGPT
    validation = validate_answer(
        question="Напиши одно слово-состояние, которое ты сейчас чувствуешь",
        answer=message.text,
        context="Ответ должен быть одним словом, описывающим эмоциональное состояние"
    )

    if not validation.get('is_valid', True):
        # Ответ невалидный - просим переформулировать
        feedback = validation.get('feedback', 'Пожалуйста, напиши одно слово.')
        await message.answer(
            f"⚠️ {feedback}\n\n"
            "Попробуй ещё раз: <b>Одно слово-состояние</b>, которое ты сейчас чувствуешь.",
            parse_mode="HTML"
        )
        return

    # Ответ валидный - сохраняем и продолжаем
    await update_user_field(message.from_user.id, "anchor_word", message.text)

    # Логируем ответ в супергруппу
    await log_user_answer(bot, message.from_user.id, "5. Слово-состояние (якорь)", message.text)

    await state.set_state(Form.cost)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Здоровье", callback_data="cost_health")],
        [InlineKeyboardButton(text="Отношения", callback_data="cost_relations")],
        [InlineKeyboardButton(text="Смысл", callback_data="cost_meaning")],
        [InlineKeyboardButton(text="Свобода", callback_data="cost_freedom")]
    ])
    
    await message.answer(
        "💰 <b>Цена вопроса.</b>\n\n"
        "Если долго откладывать себя, приходится платить.\n"
        "<b>Чем платишь ты прямо сейчас?</b>",
        parse_mode="HTML", reply_markup=kb
    )

@dp.callback_query(F.data.startswith("cost_"))
async def process_cost(callback: types.CallbackQuery, state: FSMContext):
    cost_map = {
        "cost_health": "Здоровье",
        "cost_relations": "Отношения",
        "cost_meaning": "Смысл",
        "cost_freedom": "Свобода"
    }
    selected_cost = cost_map.get(callback.data, "Другое")
    await update_user_field(callback.from_user.id, "cost_of_delay", selected_cost)

    # Логируем ответ в супергруппу
    await log_user_answer(bot, callback.from_user.id, "6. Цена откладывания", selected_cost)

    await state.set_state(Form.final)
    await callback.message.edit_text(f"Принято: {selected_cost}")

    # Отправляем сообщение с изображением берега
    if os.path.exists("assets/bereg.jpg"):
        photo = FSInputFile("assets/bereg.jpg")
        await callback.message.answer_photo(
            photo,
            caption="🏁 Мы подходим к берегу.\n\n"
                    "<b>Какой ГЛАВНЫЙ вопрос ты забираешь с собой из этого путешествия?</b>",
            parse_mode="HTML"
        )
    else:
        await callback.message.answer(
            "🏁 Мы подходим к берегу.\n\n"
            "<b>Какой ГЛАВНЫЙ вопрос ты забираешь с собой из этого путешествия?</b>",
            parse_mode="HTML"
        )

@dp.message(Form.final)
async def process_final(message: types.Message, state: FSMContext):
    # Валидация ответа через ChatGPT
    validation = validate_answer(
        question="Какой ГЛАВНЫЙ вопрос ты забираешь с собой?",
        answer=message.text,
        context="Ответ должен быть вопросом, касающимся личной стратегии, жизненных целей или внутренних противоречий"
    )

    if not validation.get('is_valid', True):
        # Ответ невалидный - просим переформулировать
        feedback = validation.get('feedback', 'Пожалуйста, сформулируй это как вопрос.')
        await message.answer(
            f"⚠️ {feedback}\n\n"
            "Попробуй ещё раз: <b>Какой ГЛАВНЫЙ вопрос ты забираешь с собой?</b>",
            parse_mode="HTML"
        )
        return

    # Ответ валидный - сохраняем и завершаем
    await update_user_field(message.from_user.id, "final_question", message.text)

    # Логируем ответ в супергруппу
    await log_user_answer(bot, message.from_user.id, "7. Главный вопрос стратегии", message.text)

    await state.clear()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Скачать стратегию", callback_data="download_pdf")]
    ])

    # Отправляем сообщение с изображением причала
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

@dp.callback_query(F.data == "download_pdf")
async def generate_and_send_pdf(callback: types.CallbackQuery):
    user_id = callback.from_user.id

    # Проверяем подписку перед генерацией PDF
    is_subscribed = await check_subscription(user_id)

    if not is_subscribed:
        # Показываем сообщение о необходимости подписки
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Подписаться на канал", url=CHANNEL_URL)],
            [InlineKeyboardButton(text="✅ Я подписался, скачать PDF", callback_data="check_sub_and_download")]
        ])
        await callback.message.answer(
            "⚓️ <b>Навигация завершена!</b>\n\n"
            "Твоя персональная стратегия готова к выгрузке.\n\n"
            "Чтобы получить PDF-файл с твоим бортовым журналом, "
            "необходимо подписаться на канал Навигатора — там продолжение пути.",
            parse_mode="HTML",
            reply_markup=kb
        )
        await callback.answer()
        return

    # Если подписка есть - генерируем PDF
    await callback.message.answer("⏳ Формирую документ...")

    user_data = await get_user_data(user_id)
    if not user_data:
        await callback.message.answer("Ошибка: Данные не найдены.")
        return

    filename = f"Strategy_{user_id}.pdf"

    try:
        pdf_file = create_pdf(user_data, filename)
        if pdf_file:
            doc = FSInputFile(pdf_file)
            await callback.message.answer_document(
                doc,
                caption="Ваша Личная Стратегия готова.\n\n"
                        "Навигация продолжается в канале @DusenkoRoman\n"
                        "Записаться на диагностику personalstrategy.romandusenko.ru/form/"
            )

            # Логируем PDF в супергруппу (до удаления файла!)
            await log_user_pdf(bot, user_id, pdf_file)

            os.remove(pdf_file)
        else:
             await callback.message.answer("Ошибка генерации PDF (возможно, проблема со шрифтами).")
    except Exception as e:
        logging.error(f"PDF Error for user {user_id}: {e}", exc_info=True)
        await callback.message.answer(f"Произошла техническая ошибка при создании файла.\nОшибка: {str(e)[:100]}")

@dp.callback_query(F.data == "check_sub_and_download")
async def check_subscription_and_download(callback: types.CallbackQuery):
    """Проверяет подписку и скачивает PDF если пользователь подписался"""
    user_id = callback.from_user.id
    is_subscribed = await check_subscription(user_id)

    if is_subscribed:
        # Подписка подтверждена - генерируем PDF
        await callback.message.answer("⏳ Формирую документ...")

        user_data = await get_user_data(user_id)
        if not user_data:
            await callback.message.answer("Ошибка: Данные не найдены.")
            return

        filename = f"Strategy_{user_id}.pdf"

        try:
            pdf_file = create_pdf(user_data, filename)
            if pdf_file:
                doc = FSInputFile(pdf_file)
                await callback.message.answer_document(
                    doc,
                    caption="Ваша Личная Стратегия готова.\n\n"
                            "Навигация продолжается в канале @DusenkoRoman\n"
                            "Записаться на диагностику personalstrategy.romandusenko.ru/form/"
                )

                # Логируем PDF в супергруппу (до удаления файла!)
                await log_user_pdf(bot, user_id, pdf_file)

                os.remove(pdf_file)
            else:
                await callback.message.answer("Ошибка генерации PDF (возможно, проблема со шрифтами).")
        except Exception as e:
            logging.error(f"PDF Error for user {user_id}: {e}", exc_info=True)
            await callback.message.answer(f"Произошла техническая ошибка при создании файла.\nОшибка: {str(e)[:100]}")

        await callback.answer()
    else:
        # Подписка все еще не найдена
        await callback.answer(
            "❌ Система не видит подписку на канал.\n\n"
            "Убедитесь, что вы подписались, и попробуйте снова.",
            show_alert=True
        )

async def main():
    """Главная функция запуска бота"""
    logging.info("Starting Navigator Bot...")
    await init_db()
    logging.info("Database initialized")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
