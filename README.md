# Navigator Bot - AI-Powered Telegram Bot для Стратегических Сессий

Интеллектуальный Telegram-бот для проведения интерактивных психологических сессий с генерацией персонализированных PDF-отчетов и AI-аналитикой.

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![aiogram](https://img.shields.io/badge/aiogram-3.x-blue.svg)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-green.svg)

## 🎯 Основные возможности

### ✨ Для пользователей:
- 📝 Интерактивный пошаговый опрос из 7 этапов
- 🤖 AI-валидация ответов через ChatGPT (снисходительная)
- 📄 Персонализированный PDF-отчет с AI-рекомендациями
- 🎨 Красивый дизайн PDF с фото и призывом к действию
- 📊 Диагностика состояния через психологический тест
- 🔒 Проверка подписки на канал перед получением PDF

### 🛠 Для администратора:
- 📍 Логирование всех действий в супергруппу с отдельными топиками для каждого пользователя
- 📊 Отслеживание источников переходов (UTM-tracking через deep links)
- 💬 Все ответы пользователя в одном месте (топик)
- 📥 Автоматическая отправка PDF в топик
- 🌐 Web-дашборд с облаком слов в реальном времени

## 🚀 Технологии

- **Python 3.10+**
- **aiogram 3.x** - асинхронный фреймворк для Telegram Bot API
- **OpenAI GPT-4o-mini** - AI-генерация персонализированных рекомендаций
- **fpdf2** - генерация PDF с поддержкой кириллицы
- **aiosqlite** - асинхронная работа с SQLite
- **FastAPI** - web-дашборд для аналитики
- **Jinja2** - шаблонизация для web

## 📋 Требования

- Python 3.10 или выше
- Telegram Bot Token (получить у [@BotFather](https://t.me/BotFather))
- OpenAI API Key (получить на [platform.openai.com](https://platform.openai.com))
- Telegram Channel (бот должен быть администратором)
- Telegram Supergroup с включенными Topics (для логирования)

## ⚙️ Установка

### 1. Клонирование репозитория

```bash
git clone https://github.com/ircitdev/telegram-bot-quiz-pdf.git
cd telegram-bot-quiz-pdf/navigator_bot
```

### 2. Создание виртуального окружения

```bash
# Linux/Mac
python3 -m venv .venv
source .venv/bin/activate

# Windows
python -m venv .venv
.venv\Scripts\activate
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Настройка окружения

Создайте файл `.env` в корне проекта:

```env
# Токен бота от @BotFather
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# ID канала (с @ для публичных, числовой для приватных)
CHANNEL_ID=@DusenkoRoman
CHANNEL_URL=https://t.me/DusenkoRoman

# Путь к шрифту с поддержкой кириллицы
FONT_PATH=assets/Roboto-Light.ttf

# OpenAI API ключ
OPENAI_API_KEY=sk-proj-...

# ID супергруппы для логирования (должны быть включены Topics)
LOG_GROUP_ID=-1003535325557
```

### 5. Подготовка ресурсов

Создайте папку `assets` и добавьте необходимые файлы:

```bash
mkdir -p assets
```

**Необходимые файлы в `assets/`:**
- `yacht.jpg` - изображение для приветствия
- `photo.png` - фото Романа Дусенко для CTA-страницы
- `Roboto-Light.ttf` - основной шрифт
- `Roboto-Bold.ttf` - жирный шрифт
- `Roboto-Italic.ttf` - курсивный шрифт

Шрифты Roboto можно скачать с [Google Fonts](https://fonts.google.com/specimen/Roboto).

## 🎮 Настройка Telegram Bot

### 1. Создание бота

1. Найдите [@BotFather](https://t.me/BotFather) в Telegram
2. Отправьте команду `/newbot`
3. Следуйте инструкциям и получите токен
4. Сохраните токен в `.env` как `BOT_TOKEN`

### 2. Настройка канала

1. Создайте публичный Telegram-канал
2. Добавьте бота в канал как **администратора** (обязательно!)
3. Укажите username канала в `.env` как `CHANNEL_ID` (формат: `@channel_name`)

### 3. Настройка супергруппы для логирования

1. Создайте супергруппу в Telegram
2. **Включите Topics** (Настройки → Темы → Включить)
3. Добавьте бота как **администратора** с правами:
   - Управление темами
   - Отправка сообщений
4. Получите ID группы (можно использовать [@getmyid_bot](https://t.me/getmyid_bot))
5. Укажите ID в `.env` как `LOG_GROUP_ID` (формат: `-1003535325557`)

## 🏃 Запуск

### Запуск только бота:

```bash
python bot.py
```

### Запуск с web-дашбордом:

```bash
python run.py
```

Сервисы будут доступны на:
- **Telegram Bot**: автоматически
- **Web Dashboard**: http://localhost:8000

## 📂 Структура проекта

```
navigator_bot/
├── bot.py                  # Основная логика бота с FSM
├── database.py             # Работа с SQLite БД
├── states.py               # FSM состояния для aiogram
├── pdf_gen.py              # Генерация PDF с AI-контентом
├── openai_assistant.py     # Интеграция с OpenAI API
├── topic_logger.py         # Логирование в супергруппу
├── web.py                  # Web-дашборд для аналитики
├── run.py                  # Точка входа (бот + web)
├── requirements.txt        # Python зависимости
├── .env                    # Конфигурация (не в git!)
├── .gitignore              # Git ignore правила
├── README.md               # Документация
└── assets/                 # Ресурсы
    ├── yacht.jpg           # Изображение для приветствия
    ├── photo.png           # Фото для CTA
    ├── Roboto-Light.ttf    # Шрифты
    ├── Roboto-Bold.ttf
    └── Roboto-Italic.ttf
```

## 🎯 Использование

### Для пользователей

1. **Старт**: Пользователь запускает бота командой `/start`
2. **Прохождение**: Отвечает на 7 вопросов:
   - Внешняя роль (как видят другие)
   - Внутреннее ощущение
   - Психологический тест (3 вопроса)
   - Присутствие с семьей
   - Слово-якорь (после паузы)
   - Цена откладывания
   - Главный вопрос стратегии
3. **Проверка подписки**: При попытке скачать PDF проверяется подписка на канал
4. **Получение PDF**: Генерируется персональный отчет с AI-рекомендациями

### Для администратора

**Отслеживание источников:**
```
https://t.me/YourBot?start=instagram
https://t.me/YourBot?start=facebook_campaign_1
https://t.me/YourBot?start=email_newsletter
```

Источник автоматически логируется в топик пользователя.

**В супергруппе:**
- Для каждого пользователя создается отдельный топик "Имя Фамилия (@username)"
- Все ответы логируются в реальном времени
- PDF автоматически отправляется в топик
- Источник перехода отображается в первом сообщении

**Web-дашборд:**
- Откройте http://localhost:8000
- Облако слов обновляется каждые 5 секунд
- Отображает внутренние ощущения пользователей

## 🤖 AI-функции

### Валидация ответов (ChatGPT)

Бот использует **снисходительную валидацию** через OpenAI:
- ✅ Принимает любые осмысленные ответы
- ✅ Короткие вопросы "как...?", "что...?" всегда валидны
- ✅ Даже односложные ответы принимаются
- ❌ Отклоняет только явный троллинг или бессмыслицу

### Персонализированные рекомендации (ChatGPT)

AI генерирует уникальное заключение по структуре:
1. **Диагноз Навигатора** - анализ разрыва между ролями
2. **Штормовое предупреждение** - о цене откладывания
3. **Точка тишины** - как использовать слово-якорь
4. **Ориентир** - метафора для главного вопроса

### PDF с Call-to-Action

**Первая страница:**
- Бортовой журнал с 6 секциями ответов
- AI-сгенерированная "Лоция Навигатора"
- Чистое форматирование (без markdown символов)

**Вторая страница:**
- Фото Романа Дусенко
- Призыв к консультации
- Кнопка "Записаться на консультацию"
- Ссылка: https://personalstrategy.romandusenko.ru/form/

## 🔧 Решение проблем

### ❌ "BOT_TOKEN not found"
**Решение:** Убедитесь, что файл `.env` существует и содержит корректный токен.

### ❌ "Font file not found"
**Решение:**
1. Скачайте шрифты Roboto
2. Поместите в папку `assets/`
3. Проверьте пути в `.env`

### ❌ "Система не видит подписку"
**Решение:**
1. Бот должен быть **администратором** канала
2. `CHANNEL_ID` должен быть с `@` для публичных каналов
3. Пользователь должен быть подписан

### ❌ "Failed to create topic"
**Решение:**
1. Бот должен быть администратором супергруппы
2. Topics должны быть **включены** в настройках группы
3. У бота должны быть права на управление темами

### ❌ "OpenAI API Error"
**Решение:**
1. Проверьте `OPENAI_API_KEY` в `.env`
2. Убедитесь, что у вас есть кредиты на OpenAI
3. Проверьте интернет-соединение

## 🔒 Безопасность

- ✅ **SQL-инъекции**: Белый список полей в `update_user_field()`
- ✅ **XSS**: Экранирование HTML в логах
- ✅ **Секреты**: Все токены в `.env` (не в git)
- ✅ **Валидация**: AI-проверка всех пользовательских вводов
- ✅ **Логирование**: Детальные логи всех операций
- ✅ **Error Handling**: Graceful degradation при ошибках API

## 📊 База данных

**Таблица `users`:**
```sql
CREATE TABLE users (
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
    topic_id INTEGER,           -- ID топика в супергруппе
    referral_source TEXT        -- Источник перехода
);
```

## 🎨 Кастомизация

### Изменение вопросов

Редактируйте обработчики в `bot.py`:
- `step_role_outer()` - вопрос о внешней роли
- `process_role_inner()` - внутреннее ощущение
- и т.д.

### Изменение дизайна PDF

Редактируйте `pdf_gen.py`:
- Цвета: `pdf.set_text_color(R, G, B)`
- Шрифты: `pdf.set_font(name, style, size)`
- Отступы: `pdf.set_margins(left, top, right)`

### Изменение AI-промпта

Редактируйте `SYSTEM_PROMPT` в `openai_assistant.py`:
- Структура ответа (4 блока)
- Тон и стиль
- Длина ответа

## 📈 Аналитика

### Метрики в супергруппе:
- Количество пользователей (топиков)
- Источники переходов
- Полные ответы каждого пользователя
- Сгенерированные PDF

### Web-дашборд:
- Облако слов из внутренних ощущений
- Автообновление каждые 5 секунд
- Последние 50 ответов

## 🤝 Вклад в проект

1. Fork репозитория
2. Создайте feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit изменения (`git commit -m 'Add some AmazingFeature'`)
4. Push в branch (`git push origin feature/AmazingFeature`)
5. Откройте Pull Request

## 📝 Лицензия

Проект разработан для **Романа Дусенко** ([@DusenkoRoman](https://t.me/DusenkoRoman))

Психолог, стратег и навигатор личных стратегий

Telegram: [@DusenkoRoman](https://t.me/DusenkoRoman)

## 🆘 Поддержка

По вопросам и предложениям:
- Telegram: [@DusenkoRoman](https://t.me/DusenkoRoman)
- GitHub Issues: [telegram-bot-quiz-pdf/issues](https://github.com/ircitdev/telegram-bot-quiz-pdf/issues)

---

Made with ❤️ using Python, aiogram, and OpenAI GPT-4
