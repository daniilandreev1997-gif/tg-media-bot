# TG Media Bot v1

Telegram-бот для скачивания медиа по ссылкам и отправки обратно в Telegram.

## Возможности

- Поддержка источников: Instagram, TikTok, YouTube, Яндекс Музыка, VK
- Репост постов VK по ссылке формата `vk.com/wall...` (текст + ссылка)
- Режимы запуска: `polling` и `webhook`
- Публичный доступ (без белого списка)
- Ограничения v1: до 60 минут и до 500 МБ
- Для приватных ссылок: бот может запросить логин/пароль или токен
- Учетные данные сохраняются в SQLite на 7 дней

## Быстрый старт

```bash
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e .[dev]
copy deploy/.env.example .env
python -m app.main
```

## Основные команды

- `/start` — инструкция и список поддерживаемых сервисов
- `/help` — примеры ссылок, лимиты и поведение для приватных ссылок
- `/mode` — текущий режим запуска (`polling`/`webhook`), доступно только админам

## Структура

- `app/` — код бота, сервисов и хранения
- `storage/migrations/` — SQL-миграции схемы SQLite
- `deploy/` — env-шаблон, systemd unit и заметки по webhook
- `tests/` — unit/integration тесты
