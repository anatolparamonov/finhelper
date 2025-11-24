"""Утилиты для работы с окружением и форматированием"""
import os
from dotenv import load_dotenv


def load_env():
    """Загружает переменные окружения из .env файла"""
    load_dotenv()


def format_number(number: int) -> str:
    """
    Форматирует число с пробелами для разделения тысяч
    Пример: 10000 -> "10 000", 1000000 -> "1 000 000"
    """
    return f"{number:,}".replace(",", " ")


def parse_number(text: str) -> int:
    """
    Парсит число из текста, убирая пробелы
    Пример: "10 000" -> 10000
    """
    return int(text.replace(" ", "").replace(",", ""))


