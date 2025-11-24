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

# Отключаем предупреждения PTBUserWarning
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="telegram")

# Состояния для ConversationHandler
WAITING_FOR_AMOUNT, WAITING_FOR_CATEGORY, WAITING_FOR_DESCRIPTION, CONFIRMING = range(4)
# Состояния для команды /test
WAITING_FOR_TEST_TYPE, WAITING_FOR_TEST_INPUT = range(4, 6)

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
        "<code>+ 50000 зарплата</code> - доход"
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
        "<code>+ 50000 зарплата</code> - доход",
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
        
        if len(parts) < 3:
            await update.message.reply_text(
                "Неверный формат. Введите: <b>+/- сумма категория [описание]</b>\n\n"
                "Примеры:\n"
                "<code>+ 1000 продукты магазин</code> - доход\n"
                "<code>- 5000 транспорт</code> - расход",
                parse_mode='HTML'
            )
            return WAITING_FOR_TEST_INPUT
        
        # Парсим тип операции (первый символ: + или -)
        type_symbol = parts[0]
        if type_symbol == "+":
            fact_type = "доход"
        elif type_symbol == "-":
            fact_type = "расход"
        else:
            await update.message.reply_text(
                "Неверный формат. Первый символ должен быть <b>+</b> (доход) или <b>-</b> (расход).\n\n"
                "Пример: <code>+ 1000 продукты</code> или <code>- 5000 транспорт</code>",
                parse_mode='HTML'
            )
            return WAITING_FOR_TEST_INPUT
        
        logger.info(f"Определен тип операции: {fact_type} (символ: {type_symbol})")
        context.user_data['fact_type'] = fact_type
        
        # Парсим сумму (второе слово)
        try:
            logger.info(f"Парсинг суммы из '{parts[1]}'")
            amount = parse_number(parts[1])
            logger.info(f"Распарсенная сумма: {amount}")
            if amount <= 0:
                raise ValueError("Сумма должна быть положительной")
        except (ValueError, IndexError) as e:
            logger.error(f"Ошибка парсинга суммы для пользователя {user_id}: {e}")
            await update.message.reply_text(
                "Неверный формат суммы. Введите число в целых рублях.\n"
                "Пример: <code>+ 1000</code> или <code>- 10 000</code>",
                parse_mode='HTML'
            )
            return WAITING_FOR_TEST_INPUT
        
        # Ищем категорию по третьему слову
        try:
            category_word = parts[2]
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
        
        # Описание - все остальные слова (если есть, начиная с 4-го)
        description = " ".join(parts[3:]) if len(parts) > 3 else ""
        
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
    user_id = update.effective_user.id
    logger.info(f"expense_income_callback вызван для пользователя {user_id}, data: {query.data}")
    
    await query.answer()
    
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
        await query.answer()
        
        context.user_data['test_mode'] = True
        await query.edit_message_text(
            "Продолжаем быстрый ввод данных.\n\n"
            "Введите данные через пробел:\n"
            "<b>+/- сумма категория [описание]</b>\n\n"
            "Примеры:\n"
            "<code>+ 1000 продукты магазин</code> - доход\n"
            "<code>- 5000 транспорт</code> - расход",
            parse_mode='HTML'
        )
        return WAITING_FOR_TEST_INPUT
    
    async def test_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'В начало' после /test"""
        query = update.callback_query
        await query.answer()
        
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
    application.add_handler(CommandHandler("restart", restart_command))
    # ConversationHandler для основного потока ввода данных
    application.add_handler(conv_handler)
    # ConversationHandler для команды /test
    application.add_handler(test_conv_handler)
    
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
    
    # Запускаем бота
    logger.info("Бот запущен")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

