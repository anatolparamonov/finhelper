#!/bin/bash

# Скрипт для быстрого развертывания FinHelper бота на сервере
# Использование: ./deploy.sh

set -e

echo "🚀 Начало развертывания FinHelper бота..."

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 не установлен. Установите Python3 и повторите попытку."
    exit 1
fi

# Получаем путь к проекту
PROJECT_DIR=$(pwd)
echo "📁 Рабочая директория: $PROJECT_DIR"

# Создание виртуального окружения
if [ ! -d "venv" ]; then
    echo "📦 Создание виртуального окружения..."
    python3 -m venv venv
fi

# Активация виртуального окружения
echo "🔌 Активация виртуального окружения..."
source venv/bin/activate

# Установка зависимостей
echo "📥 Установка зависимостей..."
pip install --upgrade pip
pip install -r requirements.txt

# Проверка наличия .env
if [ ! -f ".env" ]; then
    echo "⚠️  Файл .env не найден!"
    echo "Создайте файл .env со следующим содержимым:"
    echo ""
    echo "TELEGRAM_BOT_TOKEN=ваш_токен"
    echo "GOOGLE_SHEET_ID=ваш_id_таблицы"
    echo "GOOGLE_CREDENTIALS_PATH=credentials.json"
    echo "SHEET_NAME=Sheet1"
    echo "ADMIN_USER_IDS=ваш_telegram_user_id"
    echo ""
    read -p "Создать файл .env сейчас? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        nano .env
    fi
fi

# Проверка наличия credentials.json
if [ ! -f "credentials.json" ]; then
    echo "⚠️  Файл credentials.json не найден!"
    echo "Загрузите файл credentials.json в папку проекта."
    exit 1
fi

# Установка прав доступа
echo "🔒 Установка прав доступа..."
chmod 600 .env 2>/dev/null || true
chmod 600 credentials.json 2>/dev/null || true

# Проверка работы бота
echo "🧪 Проверка работы бота..."
echo "Запустите бота вручную для проверки:"
echo "  source venv/bin/activate"
echo "  python main.py"
echo ""
echo "Если все работает, нажмите Ctrl+C и настройте автозапуск."
echo ""
read -p "Запустить бота сейчас для проверки? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python main.py
fi

echo ""
echo "✅ Развертывание завершено!"
echo ""
echo "📚 Следующие шаги:"
echo "1. Настройте автозапуск (см. DEPLOY_GUIDE.md)"
echo "2. Для systemd: sudo nano /etc/systemd/system/finhelper.service"
echo "3. Для supervisor: sudo nano /etc/supervisor/conf.d/finhelper.conf"
echo "4. Для PM2: pm2 start ecosystem.config.js"
echo ""
echo "📖 Подробные инструкции в файле DEPLOY_GUIDE.md"

