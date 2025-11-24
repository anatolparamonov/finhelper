# Развертывание бота на сервере

## Автоматический перезапуск бота

Команда `/restart` завершает процесс бота (`os._exit(0)`). Для автоматического перезапуска на сервере нужен процесс-менеджер.

## Варианты настройки

### 1. Systemd (Linux)

Создайте файл `/etc/systemd/system/finhelper.service`:

```ini
[Unit]
Description=FinHelper Telegram Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/FinHelper
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python /path/to/FinHelper/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Команды для управления:**
```bash
# Загрузить сервис
sudo systemctl daemon-reload

# Включить автозапуск
sudo systemctl enable finhelper.service

# Запустить сервис
sudo systemctl start finhelper.service

# Проверить статус
sudo systemctl status finhelper.service

# Просмотр логов
sudo journalctl -u finhelper.service -f
```

**Как работает:**
- При команде `/restart` процесс завершается
- Systemd автоматически перезапускает сервис через 10 секунд (RestartSec=10)
- `Restart=always` гарантирует перезапуск при любом завершении

### 2. Supervisor

Создайте файл `/etc/supervisor/conf.d/finhelper.conf`:

```ini
[program:finhelper]
command=/path/to/venv/bin/python /path/to/FinHelper/main.py
directory=/path/to/FinHelper
user=your_user
autostart=true
autorestart=true
startretries=3
startsecs=10
stderr_logfile=/var/log/finhelper/error.log
stdout_logfile=/var/log/finhelper/output.log
environment=HOME="/home/your_user",USER="your_user"
```

**Команды для управления:**
```bash
# Перезагрузить конфигурацию
sudo supervisorctl reread
sudo supervisorctl update

# Управление
sudo supervisorctl start finhelper
sudo supervisorctl stop finhelper
sudo supervisorctl restart finhelper
sudo supervisorctl status finhelper
```

**Как работает:**
- При команде `/restart` процесс завершается
- Supervisor автоматически перезапускает программу
- `autorestart=true` включает автоматический перезапуск

### 3. Docker

Создайте `docker-compose.yml`:

```yaml
version: '3.8'

services:
  finhelper:
    build: .
    container_name: finhelper
    restart: always
    volumes:
      - ./credentials.json:/app/credentials.json:ro
      - ./.env:/app/.env:ro
    environment:
      - PYTHONUNBUFFERED=1
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

**Обновите Dockerfile:**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

**Команды для управления:**
```bash
# Запустить
docker-compose up -d

# Просмотр логов
docker-compose logs -f

# Перезапуск
docker-compose restart
```

**Как работает:**
- При команде `/restart` контейнер завершается
- Docker автоматически перезапускает контейнер (`restart: always`)
- Контейнер перезапускается через несколько секунд

### 4. PM2 (Node.js процесс-менеджер, но работает с Python)

Установите PM2:
```bash
npm install -g pm2
```

Создайте `ecosystem.config.js`:

```javascript
module.exports = {
  apps: [{
    name: 'finhelper',
    script: 'main.py',
    interpreter: '/path/to/venv/bin/python',
    cwd: '/path/to/FinHelper',
    autorestart: true,
    watch: false,
    max_memory_restart: '1G',
    env: {
      NODE_ENV: 'production'
    },
    error_file: './logs/err.log',
    out_file: './logs/out.log',
    log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
  }]
};
```

**Команды для управления:**
```bash
# Запустить
pm2 start ecosystem.config.js

# Автозапуск при перезагрузке системы
pm2 startup
pm2 save

# Управление
pm2 restart finhelper
pm2 stop finhelper
pm2 logs finhelper
```

## Проверка работы команды /restart

После настройки одного из вариантов:

1. Запустите бота через процесс-менеджер
2. Отправьте команду `/restart` в Telegram
3. Проверьте логи - бот должен перезапуститься автоматически

## Важно

- Убедитесь, что файлы `.env` и `credentials.json` доступны боту
- Проверьте права доступа к файлам
- Настройте логирование для диагностики
- Для production используйте `ADMIN_USER_IDS` в `.env` для безопасности

