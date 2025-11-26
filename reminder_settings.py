"""Модуль для сохранения настроек напоминаний"""
import json
import os
from typing import Dict, Any

SETTINGS_FILE = "reminder_settings.json"

def load_reminder_settings() -> Dict[str, Any]:
    """Загружает настройки напоминаний из файла"""
    default_settings = {
        "morning_time": "08:00",
        "evening_time": "22:20"
    }
    
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                # Проверяем, что все необходимые ключи присутствуют
                for key in default_settings:
                    if key not in settings:
                        settings[key] = default_settings[key]
                return settings
    except Exception as e:
        print(f"Ошибка загрузки настроек: {e}")
    
    return default_settings

def save_reminder_settings(settings: Dict[str, Any]) -> bool:
    """Сохраняет настройки напоминаний в файл"""
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Ошибка сохранения настроек: {e}")
        return False

def get_morning_time() -> str:
    """Получает время утреннего напоминания"""
    # Сначала проверяем переменную окружения, потом файл настроек
    env_time = os.getenv("MORNING_REMINDER_TIME")
    if env_time:
        return env_time
    
    settings = load_reminder_settings()
    return settings.get("morning_time", "08:00")

def get_evening_time() -> str:
    """Получает время вечернего напоминания"""
    # Сначала проверяем переменную окружения, потом файл настроек
    env_time = os.getenv("EVENING_REMINDER_TIME")
    if env_time:
        return env_time
    
    settings = load_reminder_settings()
    return settings.get("evening_time", "22:20")

def set_morning_time(time_str: str) -> bool:
    """Устанавливает время утреннего напоминания"""
    settings = load_reminder_settings()
    settings["morning_time"] = time_str
    
    # Также устанавливаем в переменную окружения для текущей сессии
    os.environ["MORNING_REMINDER_TIME"] = time_str
    
    return save_reminder_settings(settings)

def set_evening_time(time_str: str) -> bool:
    """Устанавливает время вечернего напоминания"""
    settings = load_reminder_settings()
    settings["evening_time"] = time_str
    
    # Также устанавливаем в переменную окружения для текущей сессии
    os.environ["EVENING_REMINDER_TIME"] = time_str
    
    return save_reminder_settings(settings)
