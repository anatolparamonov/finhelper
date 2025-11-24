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
from gsheets import GoogleSheetsManager
from utils import load_env, format_number, parse_number

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

# Состояния для ConversationHandler
WAITING_FOR_AMOUNT, WAITING_FOR_CATEGORY, WAITING_FOR_DESCRIPTION, CONFIRMING = range(4)

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
        "/help - Показать эту справку\n\n"
        "<b>Как использовать:</b>\n"
        "1. Нажмите СТАРТ\n"
        "2. Выберите Расходы или Доходы\n"
        "3. Введите сумму в целых рублях\n"
        "4. Выберите категорию\n"
        "5. Введите описание (или нажмите Enter для пропуска)\n"
        "6. Подтвердите или отмените запись"
    )
    await update.message.reply_text(help_text, parse_mode='HTML')


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
    return WAITING_FOR_AMOUNT


async def start_input_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатия кнопки СТАРТ"""
    query = update.callback_query
    await query.answer()
    
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
    await query.answer()
    
    fact_type = "расход" if query.data == "expense" else "доход"
    context.user_data['fact_type'] = fact_type
    
    await query.edit_message_text(
        f"Вы выбрали: <b>{fact_type}</b>\n\n"
        "Введите сумму в целых рублях (например: 10000 или 10 000):",
        parse_mode='HTML'
    )
    return WAITING_FOR_AMOUNT


async def amount_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ввода суммы"""
    try:
        amount = parse_number(update.message.text)
        if amount <= 0:
            await update.message.reply_text(
                "Сумма должна быть положительным числом. Попробуйте еще раз:"
            )
            return WAITING_FOR_AMOUNT
        
        context.user_data['amount'] = amount
        
        # Получаем категории
        category_type = "Расходы" if context.user_data['fact_type'] == "расход" else "Доходы"
        categories = sheets_manager.get_categories(category_type)
        
        if not categories:
            await update.message.reply_text(
                f"Категории для {category_type.lower()} не найдены в таблице. "
                "Обратитесь к администратору."
            )
            return ConversationHandler.END
        
        context.user_data['categories'] = categories
        context.user_data['category_type'] = category_type
        
        keyboard = get_category_keyboard(categories, context.user_data['fact_type'])
        await update.message.reply_text(
            f"Сумма: <b>{format_number(amount)} руб.</b>\n\n"
            "Выберите категорию:",
            parse_mode='HTML',
            reply_markup=keyboard
        )
        return WAITING_FOR_CATEGORY
    except ValueError:
        await update.message.reply_text(
            "Неверный формат числа. Введите сумму в целых рублях (например: 10000):"
        )
        return WAITING_FOR_AMOUNT


async def category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора категории"""
    query = update.callback_query
    await query.answer()
    
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
        await query.answer()
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
    await query.answer()
    
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
    await query.answer()
    
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
    await query.answer()
    
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
    await query.answer()
    
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


def main():
    """Основная функция запуска бота"""
    global sheets_manager, sheet_url
    
    # Загружаем переменные окружения
    load_env()
    
    # Получаем токен бота
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN не найден в .env файле")
    
    # Получаем настройки Google Sheets
    credentials_path = os.getenv("CREDENTIALS_PATH", "credentials.json")
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
    
    # Создаем ConversationHandler для основного потока ввода данных
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_input_callback, pattern="^start_input$"),
            CommandHandler("plan", plan_command)
        ],
        per_message=True,  # Отслеживать CallbackQuery для каждого сообщения
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
        fallbacks=[CommandHandler("cancel", cancel_conversation)]
    )
    
    # Регистрируем обработчики
    # Команды /start, /help, /report должны работать вне ConversationHandler
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("report", report_command))
    # ConversationHandler для основного потока ввода данных
    application.add_handler(conv_handler)
    
    # Добавляем обработчик ошибок
    async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик ошибок"""
        logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)
        
        if update and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "Произошла ошибка при обработке запроса. Попробуйте еще раз или используйте /start для начала работы."
                )
            except Exception:
                pass  # Игнорируем ошибки при отправке сообщения об ошибке
    
    application.add_error_handler(error_handler)
    
    # Запускаем бота
    logger.info("Бот запущен")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

