@echo off
chcp 65001 >nul
title FinHelper Bot

echo Запуск FinHelper бота...
echo.

cd /d "D:\Docs\ZeroCoder\Vibe coding\FinHelper"
echo Рабочая директория: %CD%

echo Останавливаем существующие процессы Python...
taskkill /f /im python.exe >nul 2>&1
timeout /t 2 >nul

echo Проверяем наличие файлов...
if not exist "main.py" (
    echo ОШИБКА: Файл main.py не найден
    pause
    exit /b 1
)

if not exist ".env" (
    echo ОШИБКА: Файл .env не найден
    pause
    exit /b 1
)

if not exist "credentials.json" (
    echo ОШИБКА: Файл credentials.json не найден
    pause
    exit /b 1
)

echo Все файлы найдены.
echo.
echo Запускаем бота...
echo Для остановки нажмите Ctrl+C
echo ----------------------------------------
echo.

python main.py

echo.
echo Бот остановлен.
pause
