#!/usr/bin/env python3
"""Скрипт для тестирования подключения к Google Sheets"""

import os
import sys
from utils import load_env
from gsheets import GoogleSheetsManager

def test_connection():
    """Тестирует подключение к Google Sheets"""
    print("Тестирование подключения к Google Sheets...")
    
    # Загружаем переменные окружения
    load_env()
    
    # Получаем настройки
    credentials_path = os.getenv("CREDENTIALS_PATH", "credentials.json")
    if not os.path.isabs(credentials_path):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        credentials_path = os.path.join(script_dir, credentials_path)
    
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    sheet_name = os.getenv("GOOGLE_SHEET_NAME", "Sheet1")
    
    print(f"Credentials path: {credentials_path}")
    print(f"Sheet ID: {sheet_id}")
    print(f"Sheet name: {sheet_name}")
    
    # Проверяем наличие файлов
    if not os.path.exists(credentials_path):
        print(f"ОШИБКА: Файл credentials не найден: {credentials_path}")
        return False
    
    if not sheet_id:
        print("ОШИБКА: GOOGLE_SHEET_ID не установлен в .env")
        return False
    
    try:
        # Пытаемся подключиться
        print("\nПодключаемся к Google Sheets...")
        manager = GoogleSheetsManager(credentials_path, sheet_id, sheet_name)
        print("УСПЕХ: Подключение успешно!")
        
        # Тестируем получение категорий
        print("\nТестируем получение категорий...")
        
        print("  Получаем категории расходов...")
        expenses = manager.get_categories("Расходы", use_cache=False)
        print(f"  Найдено категорий расходов: {len(expenses)}")
        if expenses:
            print(f"  Первые 3: {expenses[:3]}")
        
        print("  Получаем категории доходов...")
        incomes = manager.get_categories("Доходы", use_cache=False)
        print(f"  Найдено категорий доходов: {len(incomes)}")
        if incomes:
            print(f"  Первые 3: {incomes[:3]}")
        
        if not expenses and not incomes:
            print("ПРЕДУПРЕЖДЕНИЕ: Категории не найдены. Проверьте лист 'Категории'")
            return False
        
        print("\nУСПЕХ: Все тесты прошли успешно!")
        return True
        
    except Exception as e:
        print(f"\nОШИБКА: {e}")
        print(f"Тип ошибки: {type(e).__name__}")
        return False

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
