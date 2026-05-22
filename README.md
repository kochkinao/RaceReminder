# RaceDay Bot 🏁

Telegram-бот для отслеживания гоночного календаря с данными **RaceDay.watch**.

Объединяет архитектурные решения из **TrainingSchedule** (Database-класс, CallbackData,
Throttling/Subscription middlewares) с парсером RaceDay API и функциональностью уведомлений.

Требует **Python 3.14+**

---

## Структура

```
raceday_final/
├── main.py                 # Точка входа. Middlewares и роутеры — здесь, нигде больше.
├── config.py               # Все константы из .env
├── database.py             # class Database — единственный способ работы с БД
├── scheduler.py            # APScheduler: уведомления (каждый час) + дайджест (пн)
├── pyproject.toml
│
├── states/
│   ├── __init__.py
│   └── user.py             # OnboardingStates, ProfileStates, SearchStates
│
├── middlewares/
│   ├── __init__.py
│   ├── db.py               # Инжектирует db в data['db'] каждого хендлера
│   ├── throttling.py       # 1 сообщение/сек на пользователя
│   └── subscription.py     # Гейт подписки на канал (если CHANNEL_ID задан)
│
├── handlers/
│   ├── __init__.py         # from . import start, profile, ...
│   ├── start.py            # /start, /menu, онбординг, check_sub
│   ├── profile.py          # /profile, все настройки
│   ├── subscriptions.py    # /subscriptions, браузер серий/классов
│   ├── digest.py           # /today, /week, /history, избранное, напоминания
│   └── search.py           # /search, /kb
│
└── utils/
    ├── __init__.py         # Реэкспорт всего публичного API
    ├── api.py              # gRPC-Web клиент + кэш через db
    ├── formatters.py       # session_card, build_digest, notification_text
    ├── images.py           # Pillow баннеры (градиент по классу авто)
    ├── kb.py               # Все InlineKeyboard + CallbackData-классы
    └── knowledge_base.py   # Описания 11 серий, format_card
```

---

## Что взято откуда

| Решение | Источник |
|---------|----------|
| `class Database` с методами | TrainingSchedule |
| `CallbackData` (`SubToggleCD`, `FavCD` …) | TrainingSchedule |
| `ThrottlingMiddleware` | TrainingSchedule |
| `SubscriptionMiddleware` (канал) | TrainingSchedule |
| `DatabaseMiddleware` (инжекция `db`) | новое |
| `PRAGMA foreign_keys = ON` | TrainingSchedule |
| `states/` как отдельный пакет | TrainingSchedule |
| gRPC-Web парсер + кэш | RaceDay |
| `match` statement в парсерах | RaceDay / Python 3.14 |
| `type` aliases (`type Row = ...`) | Python 3.14 |
| Все keyboard-функции в `utils/kb.py` | новое |
| `dp.include_routers()` без цикл. импортов | новое |
| `pyproject.toml` вместо `requirements.txt` | новое |

---

## Быстрый старт

```bash
# Python 3.14 + uv
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.14
cd raceday_final
uv sync

cp .env.example .env
# Вставить BOT_TOKEN в .env

uv run python main.py
```

### pip

```bash
python3.14 -m venv venv && source venv/bin/activate
pip install aiogram==3.28.2 aiosqlite==0.22.1 apscheduler==3.11.2 \
            aiohttp==3.13.5 pillow==12.1.1 python-dotenv==1.0.1 \
            pytz==2026.2
python main.py
```

---

## Деплой (systemd)

```ini
[Unit]
Description=RaceDay Telegram Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/raceday_final
ExecStart=/home/ubuntu/raceday_final/venv/bin/python main.py
Restart=always
RestartSec=10
EnvironmentFile=/home/ubuntu/raceday_final/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now raceday-bot
sudo journalctl -u raceday-bot -f
```

---

## Переменные окружения

| Переменная | Обязательна | Описание |
|------------|-------------|----------|
| `BOT_TOKEN` | ✅ | Токен от @BotFather |
| `DATABASE_PATH` | — | Путь к SQLite (default: `data/raceday.db`) |
| `API_BASE_URL` | — | Базовый URL API (default: `https://api.raceday.watch`) |
| `API_FALLBACK_STALE_SECONDS` | — | Максимальный возраст stale L2 cache для fallback (default: `604800`) |
| `LOG_LEVEL` | — | `INFO` / `DEBUG` / `WARNING` |
| `CHANNEL_ID` | — | ID канала для гейта (напр. `@mychannel`) |
| `CHANNEL_LINK` | — | Ссылка на канал для кнопки |

При недоступности `raceday.watch` бот умеет использовать `stale` данные из SQLite-кэша
как fallback source, если они не старше `API_FALLBACK_STALE_SECONDS`.
