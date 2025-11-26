#!/usr/bin/env python3
"""Скрипт для запуска бота с проверкой дублирующихся процессов"""

import os
import sys
import time
import subprocess
import psutil

def kill_python_processes():
    """Останавливает все процессы Python кроме текущего"""
    current_pid = os.getpid()
    killed = 0
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['name'] == 'python.exe' and proc.info['pid'] != current_pid:
                # Проверяем, что это не системный процесс
                cmdline = proc.info.get('cmdline', [])
                if cmdline and any('main.py' in arg or 'bot.py' in arg for arg in cmdline):
                    print(f"Останавливаем процесс Python PID {proc.info['pid']}")
                    proc.kill()
                    killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    if killed > 0:
        print(f"Остановлено {killed} процессов Python")
        time.sleep(2)
    else:
        print("Дублирующиеся процессы Python не найдены")

def check_files():
    """Проверяет наличие необходимых файлов"""
    required_files = ['main.py', '.env', 'credentials.json']
    missing_files = []
    
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print(f"ОШИБКА: Не найдены файлы: {', '.join(missing_files)}")
        return False
    
    print("Все необходимые файлы найдены")
    return True

def main():
    """Основная функция"""
    print("=" * 50)
    print("Запуск FinHelper бота")
    print("=" * 50)
    
    # Переходим в директорию скрипта
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    print(f"Рабочая директория: {script_dir}")
    
    # Останавливаем дублирующиеся процессы
    print("\nОстанавливаем дублирующиеся процессы...")
    kill_python_processes()
    
    # Проверяем файлы
    print("\nПроверяем наличие файлов...")
    if not check_files():
        input("\nНажмите Enter для выхода...")
        sys.exit(1)
    
    # Запускаем бота
    print("\nЗапускаем бота...")
    print("Для остановки нажмите Ctrl+C")
    print("-" * 40)
    
    try:
        # Импортируем и запускаем main из bot.py
        from bot import main as bot_main
        bot_main()
    except KeyboardInterrupt:
        print("\n\nБот остановлен пользователем")
    except Exception as e:
        print(f"\nОШИБКА при запуске бота: {e}")
        input("\nНажмите Enter для выхода...")
        sys.exit(1)

if __name__ == "__main__":
    main()
