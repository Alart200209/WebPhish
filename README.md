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

## Модерация отзывов

Отзыв с формы на сайте не попадает в журнал сразу - он уходит в очередь модерации.
Администратор проверяет его на странице `/admin.html` и одобряет, снимает или удаляет.

Логин и пароль администратора лежат в файле **`admin.env`** в корне проекта.

```
ADMIN_EMAIL=admin@phishdet.ru
ADMIN_PASSWORD=admin12345
```

Поменяйте значения и перезапустите сервер - при старте учётная запись администратора
обновится сама. Администратор ровно один - тот, что указан в этом файле. Сам файл
`admin.env` в git не попадает. Переменные окружения `ADMIN_EMAIL` и `ADMIN_PASSWORD`
работают как запасной вариант, если этого файла нет.

Ручки модерации (нужен токен администратора)

- `GET /api/admin/reviews?status_filter=pending|published|all`
- `PATCH /api/admin/reviews/{id}` с телом `{"is_published": true|false}`
- `DELETE /api/admin/reviews/{id}`

В журнале на лендинге видно не больше трёх отзывов за раз. Кнопка «далее» справа
листает остальные.

