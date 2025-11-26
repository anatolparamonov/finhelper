# Пошаговое руководство по развертыванию бота на сервере

## Подготовка

### 1. Загрузите файлы на сервер

Есть несколько способов:

#### Вариант A: Через Git (рекомендуется)
```bash
# На сервере
git clone https://github.com/ваш-username/FinHelper.git
cd FinHelper
```

#### Вариант B: Через SCP (если нет Git)
```bash
# На вашем компьютере
scp -r FinHelper user@your-server-ip:/path/to/destination/
```

#### Вариант C: Через SFTP
Используйте FileZilla, WinSCP или другой SFTP-клиент для загрузки папки проекта.

### 2. Установите Python и зависимости

```bash
# Обновите систему (Ubuntu/Debian)
sudo apt update && sudo apt upgrade -y

# Установите Python 3 и pip (если еще не установлены)
sudo apt install python3 python3-pip python3-venv -y

# Перейдите в папку проекта
cd /path/to/FinHelper

# Создайте виртуальное окружение
python3 -m venv venv

# Активируйте виртуальное окружение
source venv/bin/activate

# Установите зависимости
pip install -r requirements.txt
```

### 3. Настройте файлы конфигурации

#### Создайте файл `.env`:
```bash
nano .env
```

Добавьте:
```env
TELEGRAM_BOT_TOKEN=ваш_токен_бота
GOOGLE_SHEET_ID=ваш_id_таблицы
GOOGLE_CREDENTIALS_PATH=credentials.json
SHEET_NAME=Sheet1
ADMIN_USER_IDS=ваш_telegram_user_id
```

**Как узнать ваш Telegram User ID:**
- Напишите боту [@userinfobot](https://t.me/userinfobot)
- Скопируйте ваш ID

#### Загрузите `credentials.json`:
```bash
# Через SCP с вашего компьютера
scp credentials.json user@your-server-ip:/path/to/FinHelper/

# Или создайте файл напрямую на сервере
nano credentials.json
# Вставьте содержимое вашего credentials.json
```

### 4. Проверьте работу бота

```bash
# Убедитесь, что виртуальное окружение активировано
source venv/bin/activate

# Запустите бота вручную для проверки
python main.py
```

Если все работает, остановите бота (Ctrl+C) и переходите к следующему шагу.

## Настройка автозапуска

Выберите один из вариантов:

### Вариант 1: Systemd (рекомендуется для Linux)

#### Создайте файл сервиса:
```bash
sudo nano /etc/systemd/system/finhelper.service
```

Вставьте (замените пути на ваши):
```ini
[Unit]
Description=FinHelper Telegram Bot
After=network.target

[Service]
Type=simple
User=ваш_пользователь
WorkingDirectory=/path/to/FinHelper
Environment="PATH=/path/to/FinHelper/venv/bin"
ExecStart=/path/to/FinHelper/venv/bin/python /path/to/FinHelper/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Важно:** Замените:
- `ваш_пользователь` - имя пользователя на сервере (например, `ubuntu`, `root`)
- `/path/to/FinHelper` - полный путь к папке проекта (например, `/home/ubuntu/FinHelper`)

#### Активируйте сервис:
```bash
# Перезагрузите systemd
sudo systemctl daemon-reload

# Включите автозапуск
sudo systemctl enable finhelper.service

# Запустите бота
sudo systemctl start finhelper.service

# Проверьте статус
sudo systemctl status finhelper.service

# Просмотр логов
sudo journalctl -u finhelper.service -f
```

**Управление:**
```bash
# Остановить
sudo systemctl stop finhelper.service

# Перезапустить
sudo systemctl restart finhelper.service

# Просмотр логов
sudo journalctl -u finhelper.service -f
```

### Вариант 2: Supervisor

#### Установите Supervisor:
```bash
sudo apt install supervisor -y
```

#### Создайте конфигурационный файл:
```bash
sudo nano /etc/supervisor/conf.d/finhelper.conf
```

Вставьте (замените пути):
```ini
[program:finhelper]
command=/path/to/FinHelper/venv/bin/python /path/to/FinHelper/main.py
directory=/path/to/FinHelper
user=ваш_пользователь
autostart=true
autorestart=true
startretries=3
startsecs=10
stderr_logfile=/var/log/finhelper/error.log
stdout_logfile=/var/log/finhelper/output.log
environment=HOME="/home/ваш_пользователь",USER="ваш_пользователь"
```

#### Создайте папку для логов:
```bash
sudo mkdir -p /var/log/finhelper
sudo chown ваш_пользователь:ваш_пользователь /var/log/finhelper
```

#### Активируйте:
```bash
# Перезагрузите конфигурацию
sudo supervisorctl reread
sudo supervisorctl update

# Запустите
sudo supervisorctl start finhelper

# Проверьте статус
sudo supervisorctl status finhelper
```

### Вариант 3: PM2

#### Установите Node.js и PM2:
```bash
# Установите Node.js
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# Установите PM2
sudo npm install -g pm2
```

#### Создайте конфигурационный файл:
```bash
nano ecosystem.config.js
```

Вставьте (замените пути):
```javascript
module.exports = {
  apps: [{
    name: 'finhelper',
    script: 'main.py',
    interpreter: '/path/to/FinHelper/venv/bin/python',
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

#### Запустите:
```bash
# Создайте папку для логов
mkdir -p logs

# Запустите
pm2 start ecosystem.config.js

# Автозапуск при перезагрузке
pm2 startup
pm2 save

# Просмотр логов
pm2 logs finhelper
```

## Проверка работы

1. **Проверьте статус бота:**
   - Systemd: `sudo systemctl status finhelper.service`
   - Supervisor: `sudo supervisorctl status finhelper`
   - PM2: `pm2 status`

2. **Проверьте логи:**
   - Systemd: `sudo journalctl -u finhelper.service -f`
   - Supervisor: `tail -f /var/log/finhelper/output.log`
   - PM2: `pm2 logs finhelper`

3. **Протестируйте команду `/restart`:**
   - Отправьте `/restart` боту в Telegram
   - Бот должен перезапуститься автоматически через несколько секунд

## Обновление бота

Если вы используете Git:

```bash
cd /path/to/FinHelper
source venv/bin/activate
git pull
pip install -r requirements.txt  # Если добавились новые зависимости

# Перезапустите бота
sudo systemctl restart finhelper.service  # для systemd
# или
sudo supervisorctl restart finhelper  # для supervisor
# или
pm2 restart finhelper  # для PM2
```

## Устранение проблем

### Бот не запускается

1. Проверьте логи:
   ```bash
   sudo journalctl -u finhelper.service -n 50  # для systemd
   ```

2. Проверьте права доступа к файлам:
   ```bash
   ls -la /path/to/FinHelper/.env
   ls -la /path/to/FinHelper/credentials.json
   ```

3. Проверьте, что виртуальное окружение активировано в сервисе

4. Запустите бота вручную для проверки:
   ```bash
   cd /path/to/FinHelper
   source venv/bin/activate
   python main.py
   ```

### Бот не отвечает

1. Проверьте, что токен бота правильный в `.env`
2. Проверьте интернет-соединение сервера
3. Проверьте логи на наличие ошибок

### Команда `/restart` не работает

1. Убедитесь, что процесс-менеджер настроен правильно
2. Проверьте, что `Restart=always` (systemd) или `autorestart=true` (supervisor/pm2)
3. Проверьте логи после команды `/restart`

## Безопасность

1. **Ограничьте доступ к файлам:**
   ```bash
   chmod 600 .env
   chmod 600 credentials.json
   ```

2. **Используйте файрвол:**
   ```bash
   # Установите UFW (если еще не установлен)
   sudo apt install ufw
   
   # Разрешите SSH (важно!)
   sudo ufw allow 22/tcp
   
   # Включите файрвол
   sudo ufw enable
   ```

3. **Регулярно обновляйте систему:**
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

## Полезные команды

```bash
# Просмотр использования ресурсов
htop

# Просмотр сетевых подключений
netstat -tulpn

# Проверка места на диске
df -h

# Просмотр процессов Python
ps aux | grep python
```

