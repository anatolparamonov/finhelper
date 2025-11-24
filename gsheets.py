"""Модуль для работы с Google Sheets"""
import os
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from typing import List, Optional
from utils import format_number


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
        self._connect()
    
    def _connect(self):
        """Подключение к Google Sheets"""
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_file(
            self.credentials_path,
            scopes=scope
        )
        self.client = gspread.authorize(creds)
        self.sheet = self.client.open_by_key(self.sheet_id).worksheet(self.sheet_name)
    
    def get_categories(self, category_type: str) -> List[str]:
        """
        Получает список категорий из листа "Категории"
        
        Args:
            category_type: "Расходы" или "Доходы"
        
        Returns:
            Список категорий
        """
        try:
            categories_sheet = self.client.open_by_key(self.sheet_id).worksheet("Категории")
            
            # Определяем столбец по типу
            # Расходы - столбец B (индекс 2), Доходы - столбец A (индекс 1)
            if category_type == "Расходы":
                column_index = 2  # Столбец B
            elif category_type == "Доходы":
                column_index = 1  # Столбец A
            else:
                return []
            
            # Получаем все значения из столбца (игнорируя заголовок)
            values = categories_sheet.col_values(column_index)
            # Убираем заголовок и пустые значения
            categories = [v.strip() for v in values[1:] if v.strip()]
            return categories
        except Exception as e:
            print(f"Ошибка при получении категорий: {e}")
            return []
    
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
        try:
            # Получаем текущую дату и время
            now = datetime.now()
            date_str = now.strftime("%d.%m.%Y")
            time_str = now.strftime("%H:%M:%S")
            
            # Определяем значение для столбца Факт/План
            # По требованию: для плана в столбец "План" записывается "расход" или "доход"
            # Для факта в столбец "Факт" записывается "расход" или "доход"
            # В текущей структуре таблицы столбец называется "Факт", но для плана записываем тип операции
            fact_plan_value = fact_type  # Записываем "расход" или "доход" (и для факта, и для плана)
            
            # Находим первую пустую строку
            all_values = self.sheet.get_all_values()
            next_row = len(all_values) + 1
            
            # Записываем данные
            # Структура: Дата, Время, Факт, Сумма, Категория, Описание, Пользователь, План
            self.sheet.update(f"A{next_row}", date_str)
            self.sheet.update(f"B{next_row}", time_str)
            
            if is_plan:
                # Для плана: в столбец C ничего не записываем (или пусто), в столбец H записываем "расход" или "доход"
                self.sheet.update(f"C{next_row}", "")  # Столбец Факт пустой для плана
                self.sheet.update(f"H{next_row}", fact_type)  # Столбец План - "расход" или "доход"
            else:
                # Для факта: в столбец C записываем "расход" или "доход", столбец H пустой
                self.sheet.update(f"C{next_row}", fact_plan_value)  # Столбец Факт
                self.sheet.update(f"H{next_row}", "")  # Столбец План пустой для факта
            
            self.sheet.update(f"D{next_row}", format_number(amount))
            self.sheet.update(f"E{next_row}", category)
            self.sheet.update(f"F{next_row}", description)
            self.sheet.update(f"G{next_row}", username)
            
            # Применяем цвет к ячейке суммы (только для фактических записей)
            if not is_plan:
                cell_range = f"D{next_row}"
                # Зеленый для дохода, красный для расхода
                if fact_type == "доход":
                    # Зеленый цвет: RGB(0, 255, 0) -> (0.0, 1.0, 0.0)
                    color = {"red": 0.0, "green": 1.0, "blue": 0.0}
                else:
                    # Красный цвет: RGB(255, 0, 0) -> (1.0, 0.0, 0.0)
                    color = {"red": 1.0, "green": 0.0, "blue": 0.0}
                
                self.sheet.format(cell_range, {
                    "backgroundColor": color
                })
            
            return True
        except Exception as e:
            print(f"Ошибка при добавлении записи: {e}")
            return False

