from fpdf import FPDF
import os
import datetime
import logging
import re
from dotenv import load_dotenv
from openai_assistant import generate_personal_strategy

load_dotenv()

# Получаем абсолютный путь к директории со скриптом
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(SCRIPT_DIR, "assets")

# Абсолютные пути к ресурсам
FONT_PATH = os.path.join(ASSETS_DIR, "Roboto-Light.ttf")
FONT_BOLD = os.path.join(ASSETS_DIR, "Roboto-Bold.ttf")
FONT_ITALIC = os.path.join(ASSETS_DIR, "Roboto-Italic.ttf")
YACHT_IMAGE = os.path.join(ASSETS_DIR, "yacht.jpg")
PHOTO_IMAGE = os.path.join(ASSETS_DIR, "photo.png")

# Глобальная переменная для имени шрифта
FONT_NAME = 'Roboto'

def clean_markdown(text: str) -> str:
    """Убирает markdown разметку из текста"""
    # Убираем жирный шрифт ** и __
    text = re.sub(r'\*\*([^\*]+)\*\*', r'\1', text)
    text = re.sub(r'__([^_]+)__', r'\1', text)
    # Убираем курсив * и _
    text = re.sub(r'\*([^\*]+)\*', r'\1', text)
    text = re.sub(r'_([^_]+)_', r'\1', text)
    # Убираем заголовки ##
    text = re.sub(r'#+\s*', '', text)
    return text

def create_pdf(user_data: dict, filename: str):
    global FONT_NAME
    pdf = FPDF()
    # Увеличенные отступы для аккуратности
    pdf.set_margins(left=20, top=20, right=20)
    pdf.set_auto_page_break(auto=True, margin=20)

    # Загружаем шрифт Roboto, который поддерживает кириллицу
    try:
        # Проверяем существование файлов перед загрузкой
        if not os.path.exists(FONT_PATH):
            raise FileNotFoundError(f"Font file not found: {FONT_PATH}")

        # Добавляем шрифт для основного текста
        pdf.add_font('Roboto', '', FONT_PATH)
        pdf.add_font('Roboto', 'B', FONT_BOLD)
        pdf.add_font('Roboto', 'I', FONT_ITALIC)
        FONT_NAME = 'Roboto'
    except Exception as e:
        logging.error(f"Font loading error: {e}")
        # Fallback на стандартный шрифт (не поддерживает кириллицу!)
        FONT_NAME = 'helvetica'

    pdf.add_page()

    # Вычисляем доступную ширину
    w = pdf.w - pdf.l_margin - pdf.r_margin

    # === ШАПКА ДОКУМЕНТА ===
    if os.path.exists(YACHT_IMAGE):
        # Уменьшенное изображение в углу
        pdf.image(YACHT_IMAGE, 20, 20, 30)
        pdf.set_y(55)

    # Заголовок документа
    pdf.set_font(FONT_NAME, "B", 18)
    pdf.set_text_color(0, 51, 102)  # Темно-синий
    pdf.cell(w, 10, 'ЛИЧНАЯ СТРАТЕГИЯ', ln=True)

    pdf.set_font(FONT_NAME, "", 14)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(w, 8, 'Бортовой журнал навигатора', ln=True)
    pdf.ln(8)

    # Информация о капитане
    pdf.set_text_color(0)
    pdf.set_font(FONT_NAME, "B", 12)
    pdf.cell(w, 7, f"Капитан: {user_data.get('full_name', 'Неизвестный')}", ln=True)
    pdf.set_font(FONT_NAME, "", 9)
    pdf.set_text_color(120)
    pdf.cell(w, 5, f"Дата навигации: {datetime.datetime.now().strftime('%d.%m.%Y')}", ln=True)
    pdf.ln(12)

    # Разделительная линия
    pdf.set_draw_color(200, 200, 200)
    pdf.line(20, pdf.get_y(), pdf.w - 20, pdf.get_y())
    pdf.ln(10)

    # === СЕКЦИИ С ОТВЕТАМИ ===
    sections = [
        ("1. КУРС", [
            ("Направление на 6–12 месяцев", user_data.get('course', '-'))
        ]),
        ("2. ЧЕЛОВЕК И РОЛЬ", [
            ("Роль (как видят другие)", user_data.get('role_outer', '-')),
            ("Ядро (внутреннее ощущение)", user_data.get('role_inner', '-'))
        ]),
        ("3. РАЗРЫВ И ЦЕНА", [
            ("Чего не хватает", user_data.get('gap', '-')),
            ("Цена откладывания", user_data.get('cost_of_delay', '-'))
        ]),
        ("4. ПРИСУТСТВИЕ И ЯКОРЬ", [
            ("Где я ментально с семьёй", user_data.get('family_presence', '-')),
            ("Якорь восстановления", user_data.get('anchor_word', '-'))
        ]),
        ("5. ПОВОРОТЫ", [
            ("Что остановить", user_data.get('stop_action', '-')),
            ("Первый шаг (3 раза в неделю)", user_data.get('first_step', '-'))
        ]),
        ("6. ГЛАВНЫЙ ВОПРОС СТРАТЕГИИ", [
            ("", user_data.get('final_question', '-'))
        ])
    ]

    for title, items in sections:
        pdf.set_text_color(0, 51, 102)
        pdf.set_font(FONT_NAME, "B", 11)
        pdf.cell(w, 7, title, ln=True)
        pdf.ln(2)

        pdf.set_text_color(40, 40, 40)
        pdf.set_font(FONT_NAME, "", 10)
        for label, value in items:
            if label:
                pdf.set_font(FONT_NAME, "I", 9)
                pdf.set_text_color(100)
                pdf.cell(w, 5, label + ":", ln=True)
            pdf.set_font(FONT_NAME, "", 10)
            pdf.set_text_color(40, 40, 40)
            pdf.multi_cell(w, 5, value)
            pdf.ln(1)

        pdf.ln(5)

    # === ЛОЦИЯ НАВИГАТОРА ===
    pdf.ln(5)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(20, pdf.get_y(), pdf.w - 20, pdf.get_y())
    pdf.ln(8)

    pdf.set_font(FONT_NAME, "B", 13)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(w, 8, "ЛОЦИЯ НАВИГАТОРА", ln=True)
    pdf.ln(3)

    # Генерация персонализированного текста
    try:
        personal_strategy = generate_personal_strategy(user_data)
        # ВАЖНО: Очищаем от markdown разметки
        personal_strategy = clean_markdown(personal_strategy)

        pdf.set_font(FONT_NAME, "", 10)
        pdf.set_text_color(40, 40, 40)

        # Разбиваем текст на параграфы
        paragraphs = personal_strategy.split('\n\n')
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if paragraph:
                # Проверяем, является ли параграф заголовком
                # (после очистки markdown заголовки это просто текст с цифрами)
                if re.match(r'^\d+\.\s+[А-ЯЁ]', paragraph):
                    # Это подзаголовок
                    pdf.ln(2)
                    pdf.set_font(FONT_NAME, "B", 10)
                    pdf.set_text_color(0, 51, 102)
                    pdf.multi_cell(w, 5, paragraph)
                    pdf.set_font(FONT_NAME, "", 10)
                    pdf.set_text_color(40, 40, 40)
                    pdf.ln(1)
                else:
                    # Обычный текст
                    pdf.multi_cell(w, 5, paragraph)
                    pdf.ln(2)
    except Exception as e:
        logging.error(f"Failed to generate personal strategy: {e}")
        pdf.set_font(FONT_NAME, "", 10)
        pdf.set_text_color(40, 40, 40)
        pdf.multi_cell(w, 5, "Твой бортовой журнал зафиксировал важные координаты. Это начало маршрута. Навигация продолжается.")

    pdf.set_text_color(0)
    pdf.ln(8)

    # === ПРИЗЫВ К ДЕЙСТВИЮ ===
    # Добавляем новую страницу для CTA
    pdf.add_page()

    # Разделительная линия
    pdf.set_draw_color(0, 51, 102)
    pdf.set_line_width(0.5)
    pdf.line(20, 30, pdf.w - 20, 30)
    pdf.ln(15)

    # Фото Романа Дусенко
    if os.path.exists(PHOTO_IMAGE):
        # Центрируем фото
        photo_width = 40
        photo_x = (pdf.w - photo_width) / 2
        pdf.image(PHOTO_IMAGE, photo_x, pdf.get_y(), photo_width)
        pdf.ln(45)

    # Заголовок CTA
    pdf.set_font(FONT_NAME, "B", 16)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(w, 10, "Готовы к глубокой навигации?", ln=True, align='C')
    pdf.ln(5)

    # Основной текст CTA
    pdf.set_font(FONT_NAME, "", 11)
    pdf.set_text_color(40, 40, 40)
    cta_text = """Этот бортовой журнал — только начало пути. Если вы чувствуете, что готовы к более глубокой работе со своей стратегией, я приглашаю вас на личную консультацию.

Мы проработаем ваши вопросы в формате индивидуальной сессии: найдем точки роста, распутаем сложные узлы и построим ясную карту движения вперед."""

    pdf.multi_cell(w, 6, cta_text, align='C')
    pdf.ln(8)

    # Кнопка записи (имитация)
    pdf.set_fill_color(0, 51, 102)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font(FONT_NAME, "B", 12)
    button_width = 140
    button_x = (pdf.w - button_width) / 2
    pdf.set_x(button_x)
    pdf.cell(button_width, 12, "ЗАПИСАТЬСЯ НА КОНСУЛЬТАЦИЮ", ln=True, align='C', fill=True)
    pdf.ln(3)

    # Ссылка под кнопкой
    pdf.set_text_color(100, 100, 100)
    pdf.set_font(FONT_NAME, "", 9)
    pdf.cell(w, 5, "https://personalstrategy.romandusenko.ru/form/", ln=True, align='C')
    pdf.ln(15)

    # Футер с контактами
    pdf.set_draw_color(200, 200, 200)
    pdf.line(20, pdf.get_y(), pdf.w - 20, pdf.get_y())
    pdf.ln(8)

    pdf.set_font(FONT_NAME, "B", 10)
    pdf.set_text_color(0)
    pdf.cell(w, 5, "Роман Дусенко", ln=True, align='C')
    pdf.set_font(FONT_NAME, "", 9)
    pdf.set_text_color(100)
    pdf.cell(w, 5, "Психолог, стратег и навигатор личных стратегий", ln=True, align='C')
    pdf.ln(2)
    pdf.set_font(FONT_NAME, "I", 8)
    pdf.cell(w, 4, "Telegram: @DusenkoRoman", ln=True, align='C')

    pdf.output(filename)
    return filename
