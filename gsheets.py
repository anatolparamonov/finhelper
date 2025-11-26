"""Модуль для работы с Google Sheets"""
import os
import re
import time
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from typing import List, Optional
from utils import format_number


def retry_on_error(max_retries=3, delay=1):
    """Декоратор для повторных попыток при ошибках API"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            import logging
            logger = logging.getLogger(__name__)
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        logger.error(f"Все попытки исчерпаны для {func.__name__}: {e}")
                        raise
                    
                    logger.warning(f"Попытка {attempt + 1} не удалась для {func.__name__}: {e}")
                    if "500" in str(e) or "Internal error" in str(e):
                        wait_time = delay * (2 ** attempt)  # Экспоненциальная задержка
                        logger.info(f"Ждем {wait_time} секунд перед повторной попыткой...")
                        time.sleep(wait_time)
                    else:
                        raise  # Не повторяем для других типов ошибок
            return None
        return wrapper
    return decorator


class GoogleSheetsManager:
    """Класс для управления Google Sheets"""
    
    def __init__(self, credentials_path: str, sheet_id: str, sheet_name: str = "Sheet1"):
        """
        Инициализация менеджера Google Sheets
        
        Args:
            credentials_path: Путь к файлу credentials.json
            sheet_id: ID Google таблицы
            sheet_name: Название листа (по умолчанию "Sheet1")
        """
        self.credentials_path = credentials_path
        self.sheet_id = sheet_id
        self.sheet_name = sheet_name
        self.client = None
        self.sheet = None
        self._categories_cache = {}  # Кэш категорий для ускорения работы
        self._connect()
    
    @retry_on_error(max_retries=3, delay=2)
    def _connect(self):
        """Подключение к Google Sheets"""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            logger.info(f"Начало подключения к Google Sheets")
            logger.info(f"Путь к credentials: {self.credentials_path}")
            logger.info(f"Sheet ID: {self.sheet_id}")
            logger.info(f"Sheet name: {self.sheet_name}")
            
            # Проверяем существование файла credentials
            if not os.path.exists(self.credentials_path):
                raise FileNotFoundError(f"Файл credentials не найден: {self.credentials_path}")
            
            scope = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive"
            ]
            logger.info("Загружаем credentials...")
            creds = Credentials.from_service_account_file(
                self.credentials_path,
                scopes=scope
            )
            
            logger.info("Авторизуемся в gspread...")
            self.client = gspread.authorize(creds)
            
            logger.info("Открываем таблицу по ID...")
            spreadsheet = self.client.open_by_key(self.sheet_id)
            logger.info(f"Таблица открыта: {spreadsheet.title}")
            
            logger.info(f"Получаем лист: {self.sheet_name}")
            self.sheet = spreadsheet.worksheet(self.sheet_name)
            logger.info(f"Лист получен: {self.sheet.title}")
            
        except Exception as e:
            logger.error(f"Ошибка подключения к Google Sheets: {e}")
            logger.error(f"Тип ошибки: {type(e).__name__}")
            raise
    
    def get_categories(self, category_type: str, use_cache: bool = True) -> List[str]:
        """
        Получает список категорий из листа "Категории"
        
        Args:
            category_type: "Расходы" или "Доходы"
            use_cache: Использовать кэш (по умолчанию True)
        
        Returns:
            Список категорий
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Проверяем кэш
        if use_cache and category_type in self._categories_cache:
            logger.info(f"Категории типа '{category_type}' получены из кэша")
            return self._categories_cache[category_type]
        
        try:
            logger.info(f"Получение категорий типа: {category_type}")
            categories_sheet = self.client.open_by_key(self.sheet_id).worksheet("Категории")
            logger.info("Лист 'Категории' открыт")
            
            # Определяем столбец по типу
            # Расходы - столбец B (индекс 2), Доходы - столбец A (индекс 1)
            if category_type == "Расходы":
                column_index = 2  # Столбец B
            elif category_type == "Доходы":
                column_index = 1  # Столбец A
            else:
                logger.warning(f"Неизвестный тип категории: {category_type}")
                return []
            
            logger.info(f"Чтение столбца {column_index} для типа {category_type}")
            # Получаем все значения из столбца (игнорируя заголовок)
            values = categories_sheet.col_values(column_index)
            logger.info(f"Получено значений из столбца: {len(values)}")
            # Убираем заголовок и пустые значения
            categories = [v.strip() for v in values[1:] if v.strip()]
            logger.info(f"Обработано категорий: {len(categories)} - {categories[:5]}")
            
            # Сохраняем в кэш
            if use_cache:
                self._categories_cache[category_type] = categories
            
            return categories
        except Exception as e:
            logger.error(f"Ошибка при получении категорий: {e}", exc_info=True)
            return []
    
    def clear_categories_cache(self):
        """Очищает кэш категорий (полезно при обновлении категорий в таблице)"""
        self._categories_cache.clear()
    
    def add_record(
        self,
        fact_type: str,
        amount: int,
        category: str,
        description: str,
        username: str,
        is_plan: bool = False
    ):
        """
        Добавляет запись в таблицу
        
        Args:
            fact_type: "расход" или "доход"
            amount: Сумма в рублях
            category: Категория
            description: Описание
            username: Имя пользователя Telegram
            is_plan: True если это запланированная запись
        """
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            logger.info(f"Начало записи: {fact_type}, {amount}, {category}, {description}, {username}, is_plan={is_plan}")
            # Получаем текущую дату и время
            now = datetime.now()
            date_str = now.strftime("%d.%m.%Y")
            time_str = now.strftime("%H:%M:%S")
            logger.info(f"Дата и время: {date_str} {time_str}")
            
            # Определяем значение для столбца Факт/План
            fact_plan_value = fact_type  # Записываем "расход" или "доход" (и для факта, и для плана)
            
            # Подготавливаем данные для записи
            # Структура: Дата (A), Время (B), Факт (C), Сумма (D), Категория (E), Описание (F), Пользователь (G), План (H)
            if is_plan:
                # Для плана: столбец C пустой, столбец H содержит "расход" или "доход"
                fact_value = ""
                plan_value = fact_type
            else:
                # Для факта: столбец C содержит "расход" или "доход", столбец H пустой
                fact_value = fact_plan_value
                plan_value = ""
            
            # Подготавливаем массив данных для одной строки
            row_data = [
                date_str,
                time_str,
                fact_value,
                format_number(amount),
                category,
                description,
                username,
                plan_value
            ]
            
            # Используем append_row для добавления строки (быстрее чем множественные update)
            self.sheet.append_row(row_data)
            logger.info("Данные записаны через append_row")
            
            # Получаем номер только что добавленной строки
            # append_row добавляет строку в конец, поэтому используем количество строк в столбце A
            # Это быстрее, чем get_all_values(), так как читает только один столбец
            row_num = len(self.sheet.col_values(1))
            
            logger.info(f"Данные записаны в строку {row_num}")
            
            # Применяем цвет к ячейке суммы (только для фактических записей)
            if not is_plan:
                cell_range = f"D{row_num}"
                # Зеленый для дохода, красный для расхода
                if fact_type == "доход":
                    color = {"red": 0.0, "green": 1.0, "blue": 0.0}
                else:
                    color = {"red": 1.0, "green": 0.0, "blue": 0.0}
                
                self.sheet.format(cell_range, {
                    "backgroundColor": color
                })
                logger.info(f"Применено форматирование цвета для ячейки {cell_range}")
            
            logger.info(f"Запись успешно завершена")
            return True
        except Exception as e:
            logger.error(f"Ошибка при добавлении записи: {e}", exc_info=True)
            return False

