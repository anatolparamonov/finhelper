# Исправления ошибок бота

## Проблемы и решения

### 1. PTBUserWarning: CallbackQueryHandler не отслеживается

**Проблема:**
```
PTBUserWarning: If 'per_message=False', 'CallbackQueryHandler' will not be tracked for every message.
```

**Решение:**
Добавлен параметр `per_message=True` в оба ConversationHandler:
- `conv_handler` (основной обработчик)
- `test_conv_handler` (обработчик команды /test)

### 2. BadRequest: Query is too old

**Проблема:**
```
telegram.error.BadRequest: Query is too old and response timeout expired or query id is invalid
```

**Причина:**
После перезапуска бота старые callback запросы становятся недействительными, но бот пытается на них ответить.

**Решение:**
Создана функция `safe_answer_callback_query()` которая:
- Пытается ответить на callback запрос
- Если возникает ошибка, логирует предупреждение и продолжает работу
- Заменены все `await query.answer()` на `await safe_answer_callback_query(query)`

## Изменения в коде

### bot.py

1. **Добавлена функция безопасного ответа:**
```python
async def safe_answer_callback_query(query):
    """Безопасный ответ на callback запрос с обработкой ошибок"""
    try:
        await query.answer()
    except Exception as e:
        logger.warning(f"Не удалось ответить на callback запрос: {e}")
        # Игнорируем ошибку, так как это не критично для работы бота
```

2. **Добавлен параметр per_message=True в ConversationHandler:**
```python
conv_handler = ConversationHandler(
    # ... остальные параметры ...
    per_message=True  # Добавлено для корректной работы с CallbackQueryHandler
)

test_conv_handler = ConversationHandler(
    # ... остальные параметры ...
    per_message=True  # Добавлено для корректной работы с CallbackQueryHandler
)
```

3. **Заменены все вызовы query.answer():**
- Было: `await query.answer()`
- Стало: `await safe_answer_callback_query(query)`

## Результат

После этих исправлений:
- ✅ Убраны предупреждения PTBUserWarning
- ✅ Исправлена ошибка "Query is too old" при перезапуске
- ✅ Бот корректно обрабатывает старые callback запросы
- ✅ Команда /restart работает без ошибок

## Тестирование

Для проверки исправлений:

1. Запустите бота: `python main.py`
2. Нажмите несколько кнопок в боте
3. Выполните команду `/restart`
4. Проверьте, что в логах нет ошибок "Query is too old"
5. Убедитесь, что предупреждения PTBUserWarning больше не появляются
