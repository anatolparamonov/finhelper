"""Telegram бот для учета финансов"""
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes
)
import random
from datetime import time
from gsheets import GoogleSheetsManager
from utils import load_env, format_number, parse_number
from reminder_settings import get_morning_time, get_evening_time, set_morning_time, set_evening_time

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Отключаем логирование HTTP запросов от httpx и telegram
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)

# Отключаем предупреждения PTBUserWarning
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="telegram")

async def safe_answer_callback_query(query):
    """Безопасный ответ на callback запрос с обработкой ошибок"""
    try:
        await query.answer()
    except Exception as e:
        logger.warning(f"Не удалось ответить на callback запрос: {e}")
        # Игнорируем ошибку, так как это не критично для работы бота


# Фразы для утренних напоминаний
MORNING_PHRASES = [
    "Доброе утро! ☀️ Запишем расходы?",
    "Привет! 🌅 Готовы вести учет финансов?", 
    "С добрым утром! 💰 Начнем записывать траты?",
    "Утро доброе! 📝 Время фиксировать расходы!",
    "Привет! ☕ Запишем что потратили?",
    "Доброе утро! 🌞 Ведем учет трат сегодня?",
    "С утром! 💸 Начинаем записывать расходы?",
    "Привет! 🌄 Готовы к учету финансов?"
]

# Фразы для вечерних напоминаний  
EVENING_PHRASES = [
    "Добрый вечер! 🌙 Запишем сколько за сегодня потратили?",
    "Вечер добрый! 🌆 Подведем итоги дня по тратам?",
    "Привет! 🌃 Время записать расходы за день!",
    "Добрый вечер! ✨ Зафиксируем траты за сегодня?",
    "Вечерочек! 🌇 Запишем что потратили сегодня?",
    "Привет! 🌉 Подсчитаем расходы за день?",
    "Добрый вечер! 🌠 Время учета трат за сегодня!",
    "Вечер! 🌌 Запишем дневные расходы?"
]


async def send_morning_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Отправляет утреннее напоминание"""
    try:
        # Получаем случайную фразу
        phrase = random.choice(MORNING_PHRASES)
        
        # Получаем список всех пользователей (можно расширить логику)
        # Пока отправляем админу, но можно добавить базу пользователей
        admin_ids = os.getenv("ADMIN_USER_IDS", "").split(",")
        
        for admin_id in admin_ids:
            if admin_id.strip():
                try:
                    user_id = int(admin_id.strip())
                    keyboard = [[InlineKeyboardButton("СТАРТ", callback_data="start_input")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=phrase,
                        reply_markup=reply_markup
                    )
                    logger.info(f"Утреннее напоминание отправлено пользователю {user_id}")
                except Exception as e:
                    logger.error(f"Ошибка отправки утреннего напоминания пользователю {admin_id}: {e}")
                    
    except Exception as e:
        logger.error(f"Ошибка в send_morning_reminder: {e}")


async def send_evening_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Отправляет вечернее напоминание"""
    try:
        # Получаем случайную фразу
        phrase = random.choice(EVENING_PHRASES)
        
        # Получаем список всех пользователей
        admin_ids = os.getenv("ADMIN_USER_IDS", "").split(",")
        
        for admin_id in admin_ids:
            if admin_id.strip():
                try:
                    user_id = int(admin_id.strip())
                    keyboard = [[InlineKeyboardButton("СТАРТ", callback_data="start_input")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=phrase,
                        reply_markup=reply_markup
                    )
                    logger.info(f"Вечернее напоминание отправлено пользователю {user_id}")
                except Exception as e:
                    logger.error(f"Ошибка отправки вечернего напоминания пользователю {admin_id}: {e}")
                    
    except Exception as e:
        logger.error(f"Ошибка в send_evening_reminder: {e}")


async def restart_reminder_jobs(context: ContextTypes.DEFAULT_TYPE):
    """Перезапускает задачи напоминаний с текущими настройками времени"""
    job_queue = context.application.job_queue
    
    # Удаляем старые задачи
    current_jobs = job_queue.jobs()
    for job in current_jobs:
        if job.name in ["morning_reminder", "evening_reminder"]:
            job.schedule_removal()
    
    # Получаем настройки времени
    morning_time_str = get_morning_time()
    evening_time_str = get_evening_time()
    
    try:
        # Парсим время утреннего напоминания
        morning_hour, morning_minute = map(int, morning_time_str.split(':'))
        morning_time_obj = time(hour=morning_hour, minute=morning_minute)
        
        # Парсим время вечернего напоминания  
        evening_hour, evening_minute = map(int, evening_time_str.split(':'))
        evening_time_obj = time(hour=evening_hour, minute=evening_minute)
        
        # Создаем новые задачи
        job_queue.run_daily(
            send_morning_reminder,
            time=morning_time_obj,
            name="morning_reminder"
        )
        
        job_queue.run_daily(
            send_evening_reminder,
            time=evening_time_obj,
            name="evening_reminder"
        )
        
        logger.info(f"Напоминания перезапущены: утром {morning_time_str}, вечером {evening_time_str}")
        
    except Exception as e:
        logger.error(f"Ошибка при перезапуске напоминаний: {e}")


def parse_time_string(time_str: str) -> tuple:
    """Парсит строку времени в формате ЧЧ:ММ"""
    try:
        parts = time_str.strip().split(':')
        if len(parts) != 2:
            raise ValueError("Неверный формат времени")
        
        hour = int(parts[0])
        minute = int(parts[1])
        
        if not (0 <= hour <= 23):
            raise ValueError("Час должен быть от 0 до 23")
        if not (0 <= minute <= 59):
            raise ValueError("Минуты должны быть от 0 до 59")
            
        return hour, minute
    except Exception:
        raise ValueError("Неверный формат времени. Используйте ЧЧ:ММ")


async def time_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ввода времени для напоминаний"""
    user_id = update.effective_user.id
    
    # Проверяем права доступа
    admin_ids_str = os.getenv("ADMIN_USER_IDS", "")
    admin_ids = [int(id.strip()) for id in admin_ids_str.split(",") if id.strip()]
    
    if user_id not in admin_ids:
        await update.message.reply_text("❌ У вас нет прав для управления напоминаниями.")
        return ConversationHandler.END
    
    reminder_type = context.user_data.get('setting_reminder_type')
    if not reminder_type:
        await update.message.reply_text("❌ Ошибка: тип напоминания не определен.")
        return ConversationHandler.END
    
    time_str = update.message.text.strip()
    
    try:
        # Парсим введенное время
        hour, minute = parse_time_string(time_str)
        formatted_time = f"{hour:02d}:{minute:02d}"
        
        # Сохраняем настройки
        if reminder_type == 'morning':
            set_morning_time(formatted_time)
            reminder_name = "утреннего"
            emoji = "🌅"
        else:
            set_evening_time(formatted_time)
            reminder_name = "вечернего"
            emoji = "🌙"
        
        # Перезапускаем задачи с новым временем
        await restart_reminder_jobs(context)
        
        # Очищаем данные пользователя
        context.user_data.clear()
        
        # Отправляем подтверждение
        keyboard = [[InlineKeyboardButton("📅 Вернуться к настройкам", callback_data="back_to_reminders")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ {emoji} Время {reminder_name} напоминания изменено на <b>{formatted_time}</b>\n\n"
            f"Напоминания перезапущены с новыми настройками!",
            parse_mode='HTML',
            reply_markup=reply_markup
        )
        
        return ConversationHandler.END
        
    except ValueError as e:
        await update.message.reply_text(
            f"❌ {str(e)}\n\n"
            f"Введите время в формате <b>ЧЧ:ММ</b>\n"
            f"Например: <code>08:30</code> или <code>22:15</code>",
            parse_mode='HTML'
        )
        # Остаемся в том же состоянии для повторного ввода
        if reminder_type == 'morning':
            return WAITING_FOR_MORNING_TIME
        else:
            return WAITING_FOR_EVENING_TIME


async def back_to_reminders_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат к меню настроек напоминаний"""
    query = update.callback_query
    await safe_answer_callback_query(query)
    
    user_id = update.effective_user.id
    
    # Проверяем права доступа (только админы)
    admin_ids_str = os.getenv("ADMIN_USER_IDS", "")
    admin_ids = [int(id.strip()) for id in admin_ids_str.split(",") if id.strip()]
    
    if user_id not in admin_ids:
        await query.edit_message_text("❌ У вас нет прав для управления напоминаниями.")
        return
    
    # Получаем текущие настройки времени
    morning_time = get_morning_time()
    evening_time = get_evening_time()
    
    # Получаем информацию о текущих задачах
    job_queue = context.application.job_queue
    morning_jobs = job_queue.get_jobs_by_name("morning_reminder")
    evening_jobs = job_queue.get_jobs_by_name("evening_reminder")
    
    status_text = "📅 <b>Управление напоминаниями:</b>\n\n"
    
    if morning_jobs:
        status_text += f"🌅 Утреннее напоминание: ✅ Активно ({morning_time})\n"
    else:
        status_text += f"🌅 Утреннее напоминание: ❌ Отключено ({morning_time})\n"
        
    if evening_jobs:
        status_text += f"🌙 Вечернее напоминание: ✅ Активно ({evening_time})\n"
    else:
        status_text += f"🌙 Вечернее напоминание: ❌ Отключено ({evening_time})\n"
    
    status_text += "\n<b>Напоминания отправляются всем пользователям из ADMIN_USER_IDS</b>"
    
    keyboard = [
        [
            InlineKeyboardButton("⏰ Время утреннего", callback_data="set_morning_time"),
            InlineKeyboardButton("🌙 Время вечернего", callback_data="set_evening_time")
        ],
        [InlineKeyboardButton("🔄 Перезапустить напоминания", callback_data="restart_reminders")],
        [
            InlineKeyboardButton("🧪 Тест утреннего", callback_data="test_morning"),
            InlineKeyboardButton("🧪 Тест вечернего", callback_data="test_evening")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        status_text,
        parse_mode='HTML',
        reply_markup=reply_markup
    )

# Состояния для ConversationHandler
WAITING_FOR_AMOUNT, WAITING_FOR_CATEGORY, WAITING_FOR_DESCRIPTION, CONFIRMING = range(4)
# Состояния для команды /test
WAITING_FOR_TEST_TYPE, WAITING_FOR_TEST_INPUT = range(4, 6)
# Состояния для настройки напоминаний
WAITING_FOR_MORNING_TIME, WAITING_FOR_EVENING_TIME = range(6, 8)

# Глобальные переменные
sheets_manager: GoogleSheetsManager = None
sheet_url: str = None


def get_main_keyboard():
    """Клавиатура с кнопками Расходы/Доходы"""
    keyboard = [
        [InlineKeyboardButton("Расходы", callback_data="expense")],
        [InlineKeyboardButton("Доходы", callback_data="income")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_confirmation_keyboard():
    """Клавиатура для подтверждения"""
    keyboard = [
        [InlineKeyboardButton("Подтверждаю", callback_data="confirm")],
        [InlineKeyboardButton("Отмена", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_plan_continue_keyboard():
    """Клавиатура после ввода плана"""
    keyboard = [
        [InlineKeyboardButton("Продолжить ввод плана", callback_data="continue_plan")],
        [InlineKeyboardButton("Вернуться к факту", callback_data="back_to_fact")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_category_keyboard(categories: list, fact_type: str):
    """
    Создает клавиатуру с категориями
    Использует индексы вместо полных названий для callback_data (лимит 64 байта)
    """
    buttons = []
    # Используем короткие префиксы: "cat" вместо "category", "exp" вместо "расход", "inc" вместо "доход"
    prefix = "exp" if fact_type == "расход" else "inc"
    for idx, category in enumerate(categories):
        # Используем индекс вместо полного названия категории
        buttons.append([InlineKeyboardButton(
            category,
            callback_data=f"cat_{prefix}_{idx}"
        )])
    return InlineKeyboardMarkup(buttons)


def get_skip_description_keyboard():
    """Клавиатура для пропуска описания"""
    keyboard = [
        [InlineKeyboardButton("Пропустить описание", callback_data="skip_description")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_test_continue_keyboard():
    """Клавиатура после ввода данных через /test"""
    keyboard = [
        [InlineKeyboardButton("Продолжить ввод", callback_data="test_continue")],
        [InlineKeyboardButton("В начало", callback_data="test_start")]
    ]
    return InlineKeyboardMarkup(keyboard)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    keyboard = [[InlineKeyboardButton("СТАРТ", callback_data="start_input")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Добро пожаловать в FinHelper!\n\n"
        "Нажмите кнопку СТАРТ для начала работы.",
        reply_markup=reply_markup
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = (
        "📋 <b>Доступные команды:</b>\n\n"
        "/start - Начать работу с ботом\n"
        "/report - Получить ссылку на таблицу\n"
        "/plan - Ввести запланированные расходы/доходы\n"
        "/test - Быстрый ввод данных одной строкой\n"
        "/reminders - Управление напоминаниями\n"
        "/restart - Перезапустить бота (только для администраторов)\n"
        "/help - Показать эту справку\n\n"
        "<b>Обычный ввод:</b>\n"
        "1. Нажмите СТАРТ\n"
        "2. Выберите Расходы или Доходы\n"
        "3. Введите сумму в целых рублях\n"
        "4. Выберите категорию\n"
        "5. Введите описание (или нажмите Enter для пропуска)\n"
        "6. Подтвердите или отмените запись\n\n"
        "<b>Быстрый ввод (/test):</b>\n"
        "Введите: <code>+/- сумма категория [описание]</code>\n\n"
        "Примеры:\n"
        "<code>+ 1000 продукты магазин</code> - доход\n"
        "<code>- 5000 транспорт</code> - расход\n"
        "<code>+ 50000 зарплата</code> - доход\n\n"
        "<b>Напоминания:</b>\n"
        "🌅 Утром в 8:00 - напоминание записать расходы\n"
        "🌙 Вечером в 22:20 - напоминание подвести итоги дня"
    )
    await update.message.reply_text(help_text, parse_mode='HTML')


async def reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /reminders - управление напоминаниями"""
    user_id = update.effective_user.id
    
    # Проверяем права доступа (только админы)
    admin_ids_str = os.getenv("ADMIN_USER_IDS", "")
    admin_ids = [int(id.strip()) for id in admin_ids_str.split(",") if id.strip()]
    
    if user_id not in admin_ids:
        await update.message.reply_text(
            "❌ У вас нет прав для управления напоминаниями."
        )
        return
    
    # Получаем текущие настройки времени
    morning_time = get_morning_time()
    evening_time = get_evening_time()
    
    # Получаем информацию о текущих задачах
    job_queue = context.application.job_queue
    morning_jobs = job_queue.get_jobs_by_name("morning_reminder")
    evening_jobs = job_queue.get_jobs_by_name("evening_reminder")
    
    status_text = "📅 <b>Управление напоминаниями:</b>\n\n"
    
    if morning_jobs:
        status_text += f"🌅 Утреннее напоминание: ✅ Активно ({morning_time})\n"
    else:
        status_text += f"🌅 Утреннее напоминание: ❌ Отключено ({morning_time})\n"
        
    if evening_jobs:
        status_text += f"🌙 Вечернее напоминание: ✅ Активно ({evening_time})\n"
    else:
        status_text += f"🌙 Вечернее напоминание: ❌ Отключено ({evening_time})\n"
    
    status_text += "\n<b>Напоминания отправляются всем пользователям из ADMIN_USER_IDS</b>"
    
    keyboard = [
        [
            InlineKeyboardButton("⏰ Время утреннего", callback_data="set_morning_time"),
            InlineKeyboardButton("🌙 Время вечернего", callback_data="set_evening_time")
        ],
        [InlineKeyboardButton("🔄 Перезапустить напоминания", callback_data="restart_reminders")],
        [
            InlineKeyboardButton("🧪 Тест утреннего", callback_data="test_morning"),
            InlineKeyboardButton("🧪 Тест вечернего", callback_data="test_evening")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        status_text,
        parse_mode='HTML',
        reply_markup=reply_markup
    )


async def reminders_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок управления напоминаниями"""
    query = update.callback_query
    await safe_answer_callback_query(query)
    
    user_id = update.effective_user.id
    
    # Проверяем права доступа
    admin_ids_str = os.getenv("ADMIN_USER_IDS", "")
    admin_ids = [int(id.strip()) for id in admin_ids_str.split(",") if id.strip()]
    
    if user_id not in admin_ids:
        await query.edit_message_text("❌ У вас нет прав для управления напоминаниями.")
        return
    
    if query.data == "set_morning_time":
        # Настройка времени утреннего напоминания
        current_time = get_morning_time()
        await query.edit_message_text(
            f"⏰ <b>Настройка утреннего напоминания</b>\n\n"
            f"Текущее время: <code>{current_time}</code>\n\n"
            f"Введите новое время в формате <b>ЧЧ:ММ</b>\n"
            f"Например: <code>07:30</code> или <code>09:15</code>",
            parse_mode='HTML'
        )
        context.user_data['setting_reminder_type'] = 'morning'
        return WAITING_FOR_MORNING_TIME
        
    elif query.data == "set_evening_time":
        # Настройка времени вечернего напоминания
        current_time = get_evening_time()
        await query.edit_message_text(
            f"🌙 <b>Настройка вечернего напоминания</b>\n\n"
            f"Текущее время: <code>{current_time}</code>\n\n"
            f"Введите новое время в формате <b>ЧЧ:ММ</b>\n"
            f"Например: <code>21:00</code> или <code>23:30</code>",
            parse_mode='HTML'
        )
        context.user_data['setting_reminder_type'] = 'evening'
        return WAITING_FOR_EVENING_TIME
        
    elif query.data == "restart_reminders":
        # Перезапускаем напоминания с текущими настройками времени
        await restart_reminder_jobs(context)
        await query.edit_message_text("✅ Напоминания перезапущены с текущими настройками времени!")
        
    elif query.data == "test_morning":
        # Тестируем утреннее напоминание
        await send_morning_reminder(context)
        await query.edit_message_text("✅ Тестовое утреннее напоминание отправлено!")
        
    elif query.data == "test_evening":
        # Тестируем вечернее напоминание
        await send_evening_reminder(context)
        await query.edit_message_text("✅ Тестовое вечернее напоминание отправлено!")


async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /report"""
    # Очищаем состояние разговора
    context.user_data.clear()
    context.user_data['is_plan'] = False
    
    if sheet_url:
        await update.message.reply_text(
            f"📊 Ссылка на таблицу:\n{sheet_url}\n\n"
            "Возвращаемся к началу ввода данных.\n\n"
            "Выберите тип операции:",
            reply_markup=get_main_keyboard()
        )
    else:
        await update.message.reply_text(
            "Ссылка на таблицу не настроена. Обратитесь к администратору.\n\n"
            "Выберите тип операции:",
            reply_markup=get_main_keyboard()
        )


async def plan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /plan"""
    context.user_data['is_plan'] = True
    await update.message.reply_text(
        "Введите запланированные расходы или доходы.\n"
        "Выберите тип:",
        reply_markup=get_main_keyboard()
    )
    return WAITING_FOR_AMOUNT


def find_closest_category(search_word: str, categories: list) -> str:
    """
    Находит наиболее близкую категорию по второму слову
    Использует проверку вхождения подстроки (без учета регистра)
    """
    if not search_word or not categories:
        return None
    
    search_word_lower = search_word.lower()
    
    # Сначала ищем точное совпадение (без учета регистра)
    for category in categories:
        if search_word_lower == category.lower():
            return category
    
    # Затем ищем вхождение подстроки (категория содержит поисковое слово или наоборот)
    for category in categories:
        category_lower = category.lower()
        if search_word_lower in category_lower or category_lower in search_word_lower:
            return category
    
    # Если ничего не найдено, возвращаем None (не первую категорию)
    return None


async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /test - быстрый ввод данных"""
    user_id = update.effective_user.id
    logger.info(f"Команда /test от пользователя {user_id}")
    
    context.user_data.clear()
    context.user_data['is_plan'] = False
    context.user_data['test_mode'] = True
    
    logger.info(f"test_mode установлен для пользователя {user_id}")
    
    await update.message.reply_text(
        "Быстрый ввод данных.\n\n"
        "Введите данные через пробел:\n"
        "<b>+/- сумма категория [описание]</b>\n\n"
        "Примеры:\n"
        "<code>+ 1000 продукты магазин</code> - доход\n"
        "<code>- 5000 транспорт</code> - расход\n"
        "<code>+50000 зарплата</code> - доход (без пробела между знаком и суммой тоже можно)",
        parse_mode='HTML'
    )
    logger.info(f"Сообщение отправлено пользователю {user_id}, возвращаем WAITING_FOR_TEST_INPUT")
    return WAITING_FOR_TEST_INPUT


async def test_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ввода данных для /test"""
    user_id = update.effective_user.id
    logger.info(f"test_input_handler вызван для пользователя {user_id}")
    
    # Проверяем, что мы в правильном состоянии
    if not context.user_data.get('test_mode', False):
        logger.warning(f"test_input_handler вызван, но test_mode не установлен для пользователя {user_id}")
        try:
            await update.message.reply_text(
                "Ошибка: режим быстрого ввода не активен. Используйте /test для начала."
            )
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
        return ConversationHandler.END
    
    try:
        text = update.message.text.strip()
        logger.info(f"Получен текст от пользователя {user_id}: '{text}'")
        parts = text.split()
        logger.info(f"Разделено на части: {parts}")
        
        if len(parts) < 2:
            await update.message.reply_text(
                "Неверный формат. Введите: <b>+/- сумма категория [описание]</b>\n\n"
                "Примеры:\n"
                "<code>+ 1000 продукты магазин</code> - доход\n"
                "<code>- 5000 транспорт</code> - расход",
                parse_mode='HTML'
            )
            return WAITING_FOR_TEST_INPUT
        
        # Парсим тип операции и сумму
        symbol = None
        amount_text = None
        category_index = None
        
        first_token = parts[0]
        if first_token in ("+", "-"):
            symbol = first_token
            if len(parts) < 3:
                await update.message.reply_text(
                    "Неверный формат. После знака укажите сумму и категорию.\n\n"
                    "Пример: <code>+ 1000 продукты</code>",
                    parse_mode='HTML'
                )
                return WAITING_FOR_TEST_INPUT
            amount_text = parts[1]
            category_index = 2
        else:
            # Возможно, знак и сумма в одном токене (+1000)
            if first_token.startswith("+") or first_token.startswith("-"):
                symbol = first_token[0]
                amount_text = first_token[1:]
                category_index = 1
                if not amount_text:
                    await update.message.reply_text(
                        "После знака необходимо указать число.\n\n"
                        "Пример: <code>+1000 продукты</code>",
                        parse_mode='HTML'
                    )
                    return WAITING_FOR_TEST_INPUT
            else:
                await update.message.reply_text(
                    "Первый символ должен быть <b>+</b> (доход) или <b>-</b> (расход).\n\n"
                    "Пример: <code>+ 1000 продукты</code> или <code>-5000 транспорт</code>",
                    parse_mode='HTML'
                )
                return WAITING_FOR_TEST_INPUT
        
        fact_type = "доход" if symbol == "+" else "расход"
        logger.info(f"Определен тип операции: {fact_type} (символ: {symbol})")
        context.user_data['fact_type'] = fact_type
        
        # Парсим сумму
        try:
            logger.info(f"Парсинг суммы из '{amount_text}'")
            amount = parse_number(amount_text)
            logger.info(f"Распарсенная сумма: {amount}")
            if amount <= 0:
                raise ValueError("Сумма должна быть положительной")
        except (ValueError, IndexError) as e:
            logger.error(f"Ошибка парсинга суммы для пользователя {user_id}: {e}")
            await update.message.reply_text(
                "Неверный формат суммы. Введите число в целых рублях.\n"
                "Пример: <code>+ 1000</code> или <code>-10 000</code>",
                parse_mode='HTML'
            )
            return WAITING_FOR_TEST_INPUT
        
        # Ищем категорию по следующему слову
        try:
            if len(parts) <= category_index:
                await update.message.reply_text(
                    "Укажите категорию после суммы.\n\n"
                    "Пример: <code>+ 1000 продукты</code>",
                    parse_mode='HTML'
                )
                return WAITING_FOR_TEST_INPUT
            
            category_word = parts[category_index]
            logger.info(f"Поиск категории по слову '{category_word}'")
            category_type = "Расходы" if fact_type == "расход" else "Доходы"
            logger.info(f"Тип операции: {fact_type}, тип категории: {category_type}")
            categories = sheets_manager.get_categories(category_type)
            logger.info(f"Получено категорий: {len(categories)} - {categories[:5]}")
            
            if not categories:
                await update.message.reply_text(
                    f"Категории для {category_type.lower()} не найдены в таблице."
                )
                return WAITING_FOR_TEST_INPUT
            
            category = find_closest_category(category_word, categories)
            logger.info(f"Найденная категория для '{category_word}': {category}")
            
            if not category:
                logger.warning(f"Категория '{category_word}' не найдена для пользователя {user_id}. Доступные: {categories}")
                category_list = ', '.join(categories[:10]) if len(categories) > 10 else ', '.join(categories)
                await update.message.reply_text(
                    f"❌ Категория '<b>{category_word}</b>' не найдена.\n\n"
                    f"Доступные категории:\n{category_list}\n\n"
                    f"Попробуйте ввести еще раз с правильной категорией.",
                    parse_mode='HTML'
                )
                logger.info(f"Отправлено сообщение об ошибке пользователю {user_id}")
                return WAITING_FOR_TEST_INPUT
        except Exception as e:
            logger.error(f"Ошибка при поиске категории для пользователя {user_id}: {e}", exc_info=True)
            await update.message.reply_text(
                "Ошибка при поиске категории. Попробуйте еще раз."
            )
            return WAITING_FOR_TEST_INPUT
        
        # Описание - все остальные слова (если есть) после категории
        description_parts = parts[category_index + 1 :] if len(parts) > category_index + 1 else []
        description = " ".join(description_parts)
        
        # Сохраняем данные
        context.user_data['amount'] = amount
        context.user_data['category'] = category
        context.user_data['description'] = description
        
        # Записываем в таблицу
        try:
            username = update.effective_user.username or update.effective_user.first_name or "Неизвестный"
            fact_type = context.user_data.get('fact_type', 'расход')
            
            logger.info(f"Начало записи данных через /test для пользователя {user_id}: {fact_type}, {amount}, {category}, {description}, {username}")
            
            success = sheets_manager.add_record(
                fact_type=fact_type,
                amount=amount,
                category=category,
                description=description,
                username=username,
                is_plan=False
            )
            
            logger.info(f"Результат записи в таблицу для пользователя {user_id}: {success}")
            
            if success:
                logger.info(f"Данные успешно записаны для пользователя {user_id}, отправка подтверждения")
                try:
                    await update.message.reply_text(
                        f"✅ Данные успешно записаны в таблицу!\n\n"
                        f"Тип: <b>{fact_type}</b>\n"
                        f"Сумма: <b>{format_number(amount)} руб.</b>\n"
                        f"Категория: <b>{category}</b>\n"
                        f"{'Описание: ' + description if description else ''}\n\n"
                        "Выберите следующее действие:",
                        parse_mode='HTML',
                        reply_markup=get_test_continue_keyboard()
                    )
                    logger.info(f"Подтверждение отправлено пользователю {user_id}")
                except Exception as e:
                    logger.error(f"Ошибка при отправке подтверждения пользователю {user_id}: {e}", exc_info=True)
                
                # Сохраняем test_mode для продолжения
                test_mode = context.user_data.get('test_mode', False)
                context.user_data.clear()
                context.user_data['test_mode'] = test_mode
                logger.info(f"test_mode сохранен для пользователя {user_id}: {test_mode}")
                return WAITING_FOR_TEST_INPUT
            else:
                logger.error(f"Запись в таблицу не удалась для пользователя {user_id}")
                await update.message.reply_text(
                    "❌ Ошибка при записи данных. Попробуйте еще раз."
                )
                return WAITING_FOR_TEST_INPUT
        except Exception as e:
            logger.error(f"Ошибка при записи в таблицу для пользователя {user_id}: {e}", exc_info=True)
            try:
                await update.message.reply_text(
                    f"❌ Произошла ошибка при записи данных: {str(e)}\n"
                    "Попробуйте еще раз."
                )
            except Exception as send_error:
                logger.error(f"Не удалось отправить сообщение об ошибке пользователю {user_id}: {send_error}")
            return WAITING_FOR_TEST_INPUT
        
    except Exception as e:
        logger.error(f"Критическая ошибка в test_input_handler для пользователя {user_id}: {e}", exc_info=True)
        try:
            await update.message.reply_text(
                "❌ Произошла ошибка. Попробуйте еще раз.\n"
                "Формат: <b>сумма категория [описание]</b>",
                parse_mode='HTML'
            )
        except Exception as send_error:
            logger.error(f"Не удалось отправить сообщение об ошибке пользователю {user_id}: {send_error}")
        return WAITING_FOR_TEST_INPUT


async def start_input_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатия кнопки СТАРТ"""
    query = update.callback_query
    await safe_answer_callback_query(query)
    
    context.user_data.clear()
    context.user_data['is_plan'] = False
    
    await query.edit_message_text(
        "Выберите тип операции:",
        reply_markup=get_main_keyboard()
    )
    return WAITING_FOR_AMOUNT


async def expense_income_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора Расходы/Доходы"""
    query = update.callback_query
    user_id = update.effective_user.id
    logger.info(f"expense_income_callback вызван для пользователя {user_id}, data: {query.data}")
    
    await safe_answer_callback_query(query)
    
    fact_type = "расход" if query.data == "expense" else "доход"
    context.user_data['fact_type'] = fact_type
    logger.info(f"Установлен fact_type: {fact_type} для пользователя {user_id}")
    
    # Проверяем, находимся ли мы в режиме /test
    test_mode = context.user_data.get('test_mode', False)
    logger.info(f"test_mode для пользователя {user_id}: {test_mode}")
    
    if test_mode:
        # Режим быстрого ввода /test
        await query.edit_message_text(
            f"Вы выбрали: <b>{fact_type}</b>\n\n"
            "Введите данные через пробел:\n"
            "<b>сумма категория [описание]</b>\n\n"
            "Пример: <code>1000 продукты магазин</code>\n"
            "или: <code>50000 зарплата</code>",
            parse_mode='HTML'
        )
        return WAITING_FOR_TEST_INPUT
    else:
        # Обычный режим
        await query.edit_message_text(
            f"Вы выбрали: <b>{fact_type}</b>\n\n"
            "Введите сумму в целых рублях (например: 10000 или 10 000):",
            parse_mode='HTML'
        )
        logger.info(f"Переходим в состояние WAITING_FOR_AMOUNT для пользователя {user_id}")
        return WAITING_FOR_AMOUNT


async def amount_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ввода суммы"""
    user_id = update.effective_user.id
    logger.info(f"🔥 amount_handler ВЫЗВАН для пользователя {user_id}, текст: '{update.message.text}'")
    
    try:
        amount = parse_number(update.message.text)
        logger.info(f"Распарсенная сумма: {amount}")
        
        if amount <= 0:
            logger.warning(f"Пользователь {user_id} ввел неположительную сумму: {amount}")
            await update.message.reply_text(
                "Сумма должна быть положительным числом. Попробуйте еще раз:"
            )
            return WAITING_FOR_AMOUNT
        
        context.user_data['amount'] = amount
        logger.info(f"Сумма {amount} сохранена для пользователя {user_id}")
        
        # Получаем категории
        fact_type = context.user_data.get('fact_type')
        logger.info(f"fact_type для пользователя {user_id}: {fact_type}")
        
        category_type = "Расходы" if fact_type == "расход" else "Доходы"
        logger.info(f"Запрашиваем категории типа: {category_type}")
        
        categories = sheets_manager.get_categories(category_type)
        logger.info(f"Получено категорий: {len(categories) if categories else 0}")
        
        if categories:
            logger.info(f"Категории: {categories}")
        
        if not categories:
            logger.error(f"Категории для {category_type} не найдены!")
            await update.message.reply_text(
                f"Категории для {category_type.lower()} не найдены в таблице. "
                "Обратитесь к администратору."
            )
            return ConversationHandler.END
        
        context.user_data['categories'] = categories
        context.user_data['category_type'] = category_type
        
        logger.info(f"Создаем клавиатуру с категориями для пользователя {user_id}")
        keyboard = get_category_keyboard(categories, fact_type)
        
        await update.message.reply_text(
            f"Сумма: <b>{format_number(amount)} руб.</b>\n\n"
            "Выберите категорию:",
            parse_mode='HTML',
            reply_markup=keyboard
        )
        logger.info(f"Сообщение с категориями отправлено пользователю {user_id}")
        return WAITING_FOR_CATEGORY
        
    except ValueError as e:
        logger.error(f"Ошибка парсинга суммы для пользователя {user_id}: {e}")
        await update.message.reply_text(
            "Неверный формат числа. Введите сумму в целых рублях (например: 10000):"
        )
        return WAITING_FOR_AMOUNT
    except Exception as e:
        logger.error(f"Неожиданная ошибка в amount_handler для пользователя {user_id}: {e}")
        await update.message.reply_text(
            "Произошла ошибка. Попробуйте еще раз или обратитесь к администратору."
        )
        return WAITING_FOR_AMOUNT


async def category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора категории"""
    query = update.callback_query
    await safe_answer_callback_query(query)
    
    # Извлекаем индекс категории из callback_data: cat_{exp/inc}_{index}
    parts = query.data.split('_')
    if len(parts) >= 3:
        try:
            category_index = int(parts[2])
            categories = context.user_data.get('categories', [])
            
            if 0 <= category_index < len(categories):
                category = categories[category_index]
                context.user_data['category'] = category
                
                await query.edit_message_text(
                    f"Категория: <b>{category}</b>\n\n"
                    "Введите описание или нажмите кнопку для пропуска:",
                    parse_mode='HTML',
                    reply_markup=get_skip_description_keyboard()
                )
                return WAITING_FOR_DESCRIPTION
            else:
                await query.edit_message_text("Ошибка: категория не найдена. Попробуйте еще раз.")
                return ConversationHandler.END
        except (ValueError, IndexError):
            await query.edit_message_text("Ошибка при выборе категории. Попробуйте еще раз.")
            return ConversationHandler.END
    else:
        await query.edit_message_text("Ошибка при выборе категории. Попробуйте еще раз.")
        return ConversationHandler.END


async def description_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ввода описания"""
    if update.callback_query and update.callback_query.data == "skip_description":
        # Пропуск описания по кнопке
        query = update.callback_query
        await safe_answer_callback_query(query)
        description = ""
        message_to_edit = query
    else:
        # Ввод описания текстом
        description = update.message.text.strip()
        message_to_edit = None
    
    context.user_data['description'] = description if description else ""
    
    # Формируем сообщение для подтверждения
    fact_type = context.user_data.get('fact_type', '')
    amount = context.user_data.get('amount', 0)
    category = context.user_data.get('category', '')
    description_text = context.user_data.get('description', '')
    is_plan = context.user_data.get('is_plan', False)
    
    plan_text = " (запланировано)" if is_plan else ""
    
    confirmation_text = (
        f"Вы ввели данные{plan_text}:\n\n"
        f"Тип: <b>{fact_type}</b>\n"
        f"Сумма: <b>{format_number(amount)} руб.</b>\n"
        f"Категория: <b>{category}</b>\n"
    )
    
    if description_text:
        confirmation_text += f"Описание: <b>{description_text}</b>\n"
    
    confirmation_text += "\nВерно?"
    
    if message_to_edit:
        # Редактируем сообщение с кнопкой
        await message_to_edit.edit_message_text(
            confirmation_text,
            parse_mode='HTML',
            reply_markup=get_confirmation_keyboard()
        )
    else:
        # Отправляем новое сообщение
        await update.message.reply_text(
            confirmation_text,
            parse_mode='HTML',
            reply_markup=get_confirmation_keyboard()
        )
    return CONFIRMING


async def confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик подтверждения"""
    query = update.callback_query
    await safe_answer_callback_query(query)
    
    fact_type = context.user_data.get('fact_type')
    amount = context.user_data.get('amount')
    category = context.user_data.get('category')
    description = context.user_data.get('description', '')
    is_plan = context.user_data.get('is_plan', False)
    username = update.effective_user.username or update.effective_user.first_name or "Неизвестный"
    
    # Записываем в таблицу
    success = sheets_manager.add_record(
        fact_type=fact_type,
        amount=amount,
        category=category,
        description=description,
        username=username,
        is_plan=is_plan
    )
    
    if success:
        plan_text = "запланированные " if is_plan else ""
        await query.edit_message_text(
            f"✅ Данные {plan_text}{fact_type}а успешно записаны в таблицу!\n\n"
            f"Сумма: {format_number(amount)} руб.\n"
            f"Категория: {category}\n"
            f"{'Описание: ' + description if description else ''}\n\n"
            "Выберите следующее действие:",
            reply_markup=get_main_keyboard() if not is_plan else get_plan_continue_keyboard()
        )
        
        # Очищаем данные для следующего ввода, но сохраняем is_plan для плана
        if is_plan:
            # Сохраняем флаг is_plan перед очисткой
            plan_flag = context.user_data.get('is_plan', False)
            context.user_data.clear()
            context.user_data['is_plan'] = plan_flag
            return WAITING_FOR_AMOUNT
        else:
            context.user_data.clear()
            context.user_data['is_plan'] = False
            return WAITING_FOR_AMOUNT
    else:
        await query.edit_message_text(
            "❌ Ошибка при записи данных. Попробуйте еще раз.",
            reply_markup=get_main_keyboard()
        )
        return ConversationHandler.END


async def cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик отмены"""
    query = update.callback_query
    await safe_answer_callback_query(query)
    
    context.user_data.clear()
    context.user_data['is_plan'] = False
    
    await query.edit_message_text(
        "Отменено. Возвращаемся к началу ввода данных.\n\n"
        "Выберите тип операции:",
        reply_markup=get_main_keyboard()
    )
    return WAITING_FOR_AMOUNT


async def continue_plan_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик продолжения ввода плана"""
    query = update.callback_query
    await safe_answer_callback_query(query)
    
    # Очищаем данные, но сохраняем режим плана
    context.user_data.clear()
    context.user_data['is_plan'] = True
    
    await query.edit_message_text(
        "Продолжаем ввод запланированных данных.\n"
        "Выберите тип:",
        reply_markup=get_main_keyboard()
    )
    return WAITING_FOR_AMOUNT


async def back_to_fact_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик возврата к факту"""
    query = update.callback_query
    await safe_answer_callback_query(query)
    
    context.user_data.clear()
    context.user_data['is_plan'] = False
    
    await query.edit_message_text(
        "Возвращаемся к вводу фактических данных.\n"
        "Выберите тип:",
        reply_markup=get_main_keyboard()
    )
    return WAITING_FOR_AMOUNT


async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик отмены разговора"""
    context.user_data.clear()
    await update.message.reply_text(
        "Операция отменена. Используйте /start для начала работы."
    )
    return ConversationHandler.END


# Глобальная переменная для хранения application (для перезапуска)
application_instance = None


async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /restart - перезапуск бота"""
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name or "Неизвестный"
    logger.info(f"Команда /restart от пользователя {user_id} ({username})")
    
    # Получаем список администраторов из .env
    admin_ids_str = os.getenv("ADMIN_USER_IDS", "")
    logger.info(f"ADMIN_USER_IDS из .env: '{admin_ids_str}'")
    
    try:
        admin_ids = [int(uid.strip()) for uid in admin_ids_str.split(",") if uid.strip()] if admin_ids_str else []
        logger.info(f"Распарсенные admin_ids: {admin_ids}")
    except ValueError as e:
        logger.error(f"Ошибка парсинга ADMIN_USER_IDS: {e}")
        admin_ids = []
    
    # Если список администраторов пуст, разрешаем всем (для разработки)
    # В продакшене лучше всегда указывать ADMIN_USER_IDS
    if admin_ids and user_id not in admin_ids:
        logger.warning(f"Пользователь {user_id} ({username}) попытался использовать /restart, но не в списке администраторов")
        await update.message.reply_text(
            "❌ У вас нет прав для выполнения этой команды."
        )
        return
    
    logger.info(f"Пользователь {user_id} ({username}) имеет права на перезапуск")
    
    try:
        await update.message.reply_text(
            "🔄 Перезапуск бота...\n"
            "Пожалуйста, подождите несколько секунд."
        )
        logger.info(f"Сообщение о перезапуске отправлено пользователю {user_id}")
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения о перезапуске: {e}")
    
    # Останавливаем бота
    global application_instance
    if application_instance:
        logger.info(f"Перезапуск бота по запросу пользователя {user_id} ({username})")
        # Останавливаем polling и завершаем процесс
        # Внешний процесс (systemd/supervisor/docker) должен перезапустить бота
        import sys
        import os as os_module
        logger.info("Завершение процесса для перезапуска...")
        os_module._exit(0)  # Принудительное завершение процесса
    else:
        logger.error("application_instance не инициализирован")
        await update.message.reply_text(
            "❌ Ошибка: не удалось перезапустить бота. application_instance не инициализирован."
        )


def main():
    """Основная функция запуска бота"""
    global sheets_manager, sheet_url, application_instance
    
    # Загружаем переменные окружения
    load_env()
    
    # Получаем токен бота
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN не найден в .env файле")
    
    # Получаем настройки Google Sheets
    credentials_path = os.getenv("CREDENTIALS_PATH", "credentials.json")
    # Если путь относительный, делаем его абсолютным относительно папки скрипта
    if not os.path.isabs(credentials_path):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        credentials_path = os.path.join(script_dir, credentials_path)
    
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    sheet_name = os.getenv("GOOGLE_SHEET_NAME", "Sheet1")
    sheet_url = os.getenv("GOOGLE_SHEET_URL", "")
    
    if not sheet_id:
        raise ValueError("GOOGLE_SHEET_ID не найден в .env файле")
    
    # Инициализируем менеджер Google Sheets
    try:
        sheets_manager = GoogleSheetsManager(credentials_path, sheet_id, sheet_name)
        logger.info("Подключение к Google Sheets успешно")
    except Exception as e:
        logger.error(f"Ошибка подключения к Google Sheets: {e}")
        raise
    
    # Создаем приложение
    application = Application.builder().token(bot_token).build()
    application_instance = application  # Сохраняем для возможности перезапуска
    
    # Создаем ConversationHandler для основного потока ввода данных
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_input_callback, pattern="^start_input$")
        ],
        states={
            WAITING_FOR_AMOUNT: [
                CallbackQueryHandler(expense_income_callback, pattern="^(expense|income)$"),
                CallbackQueryHandler(continue_plan_callback, pattern="^continue_plan$"),
                CallbackQueryHandler(back_to_fact_callback, pattern="^back_to_fact$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, amount_handler)
            ],
            WAITING_FOR_CATEGORY: [
                CallbackQueryHandler(category_callback, pattern="^cat_")
            ],
            WAITING_FOR_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, description_handler),
                CallbackQueryHandler(description_handler, pattern="^skip_description$")
            ],
            CONFIRMING: [
                CallbackQueryHandler(confirm_callback, pattern="^confirm$"),
                CallbackQueryHandler(cancel_callback, pattern="^cancel$"),
                CallbackQueryHandler(continue_plan_callback, pattern="^continue_plan$"),
                CallbackQueryHandler(back_to_fact_callback, pattern="^back_to_fact$")
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            CommandHandler("plan", plan_command),  # Команда /plan работает в любом состоянии
            CommandHandler("restart", restart_command)  # Команда /restart работает в любом состоянии
        ]
    )
    
    # Обработчики для кнопок после ввода данных через /test
    async def test_continue_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Продолжить ввод' после /test"""
        query = update.callback_query
        await safe_answer_callback_query(query)
        
        context.user_data['test_mode'] = True
        await query.edit_message_text(
            "Продолжаем быстрый ввод данных.\n\n"
            "Введите: <b>+/- сумма категория [описание]</b>\n"
            "Примеры: <code>+ 1000 продукты</code>, <code>-5000 транспорт</code>",
            parse_mode='HTML'
        )
        return WAITING_FOR_TEST_INPUT
    
    async def test_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'В начало' после /test"""
        query = update.callback_query
        await safe_answer_callback_query(query)
        
        context.user_data.clear()
        keyboard = [[InlineKeyboardButton("СТАРТ", callback_data="start_input")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "Возвращаемся в начало.\n\n"
            "Нажмите кнопку СТАРТ для начала работы.",
            reply_markup=reply_markup
        )
        return ConversationHandler.END
    
    # Создаем ConversationHandler для команды /test
    # Используем test_type_callback как альтернативный обработчик, но основной обработчик expense_income_callback
    # будет проверять test_mode и переключаться в правильное состояние
    test_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("test", test_command)
        ],
        states={
            WAITING_FOR_TEST_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, test_input_handler),
                CallbackQueryHandler(test_continue_callback, pattern="^test_continue$"),
                CallbackQueryHandler(test_start_callback, pattern="^test_start$")
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            CommandHandler("restart", restart_command)  # Команда /restart работает в любом состоянии
        ]
    )
    
    # Регистрируем обработчики
    # Команды /start, /help, /report, /plan, /restart должны работать вне ConversationHandler
    # /plan также в fallbacks ConversationHandler для работы во время разговора
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("report", report_command))
    application.add_handler(CommandHandler("plan", plan_command))
    application.add_handler(CommandHandler("reminders", reminders_command))
    application.add_handler(CommandHandler("restart", restart_command))
    
    # ConversationHandler для настройки времени напоминаний
    reminders_conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(reminders_callback, pattern="^(set_morning_time|set_evening_time)$")
        ],
        states={
            WAITING_FOR_MORNING_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, time_input_handler)
            ],
            WAITING_FOR_EVENING_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, time_input_handler)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            CommandHandler("reminders", reminders_command)
        ]
    )
    
    # Обработчики кнопок управления напоминаниями
    application.add_handler(reminders_conv_handler)
    application.add_handler(CallbackQueryHandler(reminders_callback, pattern="^(restart_reminders|test_morning|test_evening)$"))
    application.add_handler(CallbackQueryHandler(back_to_reminders_callback, pattern="^back_to_reminders$"))
    # ConversationHandler для команды /test (должен быть ПЕРЕД основным)
    application.add_handler(test_conv_handler)
    # ConversationHandler для основного потока ввода данных
    application.add_handler(conv_handler)
    
    # Добавляем обработчик ошибок
    async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик ошибок"""
        logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)
        
        if update:
            try:
                if update.effective_message:
                    await update.effective_message.reply_text(
                        "❌ Произошла ошибка при обработке запроса.\n\n"
                        "Попробуйте еще раз или используйте /start для начала работы."
                    )
                elif update.callback_query:
                    await update.callback_query.answer("Произошла ошибка. Попробуйте еще раз.")
                    await update.callback_query.message.reply_text(
                        "❌ Произошла ошибка. Попробуйте еще раз или используйте /start."
                    )
            except Exception as e:
                logger.error(f"Не удалось отправить сообщение об ошибке: {e}")
    
    application.add_error_handler(error_handler)
    
    # Настраиваем ежедневные напоминания
    job_queue = application.job_queue
    
    # Получаем настройки времени
    morning_time_str = get_morning_time()
    evening_time_str = get_evening_time()
    
    try:
        # Парсим время утреннего напоминания
        morning_hour, morning_minute = map(int, morning_time_str.split(':'))
        morning_time_obj = time(hour=morning_hour, minute=morning_minute)
        
        job_queue.run_daily(
            send_morning_reminder,
            time=morning_time_obj,
            name="morning_reminder"
        )
        logger.info(f"Настроено утреннее напоминание на {morning_time_str}")
        
        # Парсим время вечернего напоминания
        evening_hour, evening_minute = map(int, evening_time_str.split(':'))
        evening_time_obj = time(hour=evening_hour, minute=evening_minute)
        
        job_queue.run_daily(
            send_evening_reminder, 
            time=evening_time_obj,
            name="evening_reminder"
        )
        logger.info(f"Настроено вечернее напоминание на {evening_time_str}")
        
    except Exception as e:
        logger.error(f"Ошибка настройки напоминаний: {e}")
        # Используем время по умолчанию при ошибке
        job_queue.run_daily(
            send_morning_reminder,
            time=time(hour=8, minute=0),
            name="morning_reminder"
        )
        job_queue.run_daily(
            send_evening_reminder, 
            time=time(hour=22, minute=20),
            name="evening_reminder"
        )
        logger.info("Использованы настройки времени по умолчанию")
    
    # Запускаем бота
    logger.info("Бот запущен")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

