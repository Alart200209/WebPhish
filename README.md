# PhishDet

Веб-приложение для определения фишинговых ссылок с использованием машинного обучения и интеграцией с Tinkoff Касса.

## Как запустить на новом компьютере

1. Клонируйте репозиторий:
   ```bash
   git clone <ссылка_на_твой_репозиторий>
   cd WebPhish
   
# Windows

python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate

# Установка зависимостей сервера (в api/requirements.txt лежит лишнее — numpy, torch и т.п., они для запуска сайта не нужны)
pip install -r requirements-server.txt

# (Необязательно) Скопируйте .env.example в .env и укажите свои ключи Tinkoff:
#   cp .env.example .env        # macOS / Linux
#   copy .env.example .env      # Windows
# Без .env всё работает на локальной SQLite-базе (файл phishdet.db создастся сам)
# и тестовых ключах оплаты.

# Запустите сервер
uvicorn api.main:app --reload --port 8000

# Откройте в браузере: http://127.0.0.1:8000

