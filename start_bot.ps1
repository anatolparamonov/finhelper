# Скрипт для запуска бота с проверкой дублирующихся процессов
# Использование: .\start_bot.ps1

Write-Host "Запуск FinHelper бота..." -ForegroundColor Green

# Переходим в директорию проекта
$projectDir = "D:\Docs\ZeroCoder\Vibe coding\FinHelper"
Set-Location $projectDir

Write-Host "Рабочая директория: $projectDir" -ForegroundColor Yellow

# Останавливаем все процессы Python
Write-Host "Останавливаем существующие процессы Python..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

# Проверяем, что процессы остановлены
$pythonProcesses = Get-Process python -ErrorAction SilentlyContinue
if ($pythonProcesses) {
    Write-Host "ПРЕДУПРЕЖДЕНИЕ: Найдены активные процессы Python:" -ForegroundColor Red
    $pythonProcesses | Format-Table Id, ProcessName, StartTime
    Write-Host "Принудительно останавливаем..." -ForegroundColor Red
    $pythonProcesses | Stop-Process -Force
    Start-Sleep -Seconds 3
}

# Проверяем наличие файлов
if (-not (Test-Path "main.py")) {
    Write-Host "ОШИБКА: Файл main.py не найден в $projectDir" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path ".env")) {
    Write-Host "ОШИБКА: Файл .env не найден в $projectDir" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path "credentials.json")) {
    Write-Host "ОШИБКА: Файл credentials.json не найден в $projectDir" -ForegroundColor Red
    exit 1
}

Write-Host "Все необходимые файлы найдены." -ForegroundColor Green

# Запускаем бота
Write-Host "Запускаем бота..." -ForegroundColor Green
Write-Host "Для остановки нажмите Ctrl+C" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Cyan

try {
    python main.py
} catch {
    Write-Host "ОШИБКА при запуске бота: $_" -ForegroundColor Red
    exit 1
}
