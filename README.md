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

# Установка зависимостей
pip install -r api/requirements.txt

# Создайте файл .env в корне проекта и добавьте свои ключи Tinkoff:
TINKOFF_TERMINAL_KEY=ваш_ключ

TINKOFF_SECRET_KEY=ваш_секретный_ключ

WEBHOOK_URL=http://localhost:8000/api/payment/webhook

# Запустите сервер
uvicorn api.main:app --reload --port 8000

# Откройте в браузере: http://127.0.0.1:8000

