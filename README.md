# RaceReminder Bot

**Documentation:** [Русский](#русский) · [English](#english)

---

## Русский

RaceReminder — Telegram-бот для гоночного календаря [RaceDay.watch](https://raceday.watch/). Он помогает подписываться на гоночные серии и классы, смотреть расписание на сегодня и неделю, получать напоминания о стартах, сохранять интересные уикенды и не пропускать этапы СМП РСКГ.

### Возможности

- Подписки на гоночные серии из RaceDay.watch.
- Подписки на классы автомобилей: GT3, Endurance, Single-Seaters и другие.
- Отдельная интеграция календаря **СМП РСКГ** с сайта `rskg.smpracing.ru`.
- Экраны `Сегодня`, `Неделя`, `История`, `Избранное`, `Не интересно`.
- Поиск серий, классов и статей базы знаний.
- Встроенная база знаний по сериям, классам и гоночным терминам.
- Уведомления за `3 дня`, `1 день`, `1 час` и в момент старта.
- Отдельные настройки уведомлений для квалификаций, практик и тестов.
- Персональные напоминания по конкретным сессиям.
- Live timing в карточках и уведомлениях, если он доступен в RaceDay.watch.
- Фильтр трансляций по языкам.
- Тихие часы, чтобы не получать уведомления ночью.
- Еженедельный дайджест по понедельникам.
- Админ-панель со статистикой, логами, кэшем, рассылками и backup базы.
- PM2-деплой с автообновлением при новых commit в `main`.
- Docker Compose для изолированного запуска.

### Языки интерфейса

Бот адаптирован под два языка интерфейса:

- `ru` — русский, язык по умолчанию;
- `en` — английский.

При первом запуске пользователь выбирает язык. Позже язык можно изменить в профиле. Локализованы основные пользовательские экраны, inline-кнопки, onboarding, профиль, подписки, поиск, база знаний, дайджесты, карточки сессий, уведомления, СМП РСКГ и избранное.

Важно: названия серий, трасс, сессий и трансляций приходят из внешних API и сохраняются в исходном виде. Админские служебные экраны ориентированы на владельца бота и могут оставаться на русском.

### Как работает пользовательский сценарий

1. Пользователь отправляет `/start`.
2. Бот предлагает выбрать язык интерфейса.
3. Пользователь выбирает часовой пояс.
4. Бот автоматически подписывает нового пользователя на базовый набор популярных серий:
   - Formula 1;
   - FIA World Endurance Championship / WEC;
   - IMSA.
5. Пользователь может добавить или удалить подписки в разделе `Подписки` / `Subscriptions`.
6. Экраны `Сегодня` и `Неделя` строятся только по подпискам пользователя.
7. Бот периодически проверяет календарь и отправляет уведомления с учётом:
   - часового пояса;
   - тихих часов;
   - глобальных настроек уведомлений;
   - настроек квалификаций и практик;
   - списка `Не интересно`;
   - уже отправленных уведомлений.
8. Из карточки сессии или уведомления можно добавить уикенд в `Избранное` или заглушить его через `Не интересно`.

### Основные команды

#### Пользовательские

- `/start` — запуск и первичная настройка.
- `/menu` — главное меню.
- `/today` — ближайшие гонки на сегодня по подпискам.
- `/week` — гоночная неделя по подпискам.
- `/history` — недавняя история по подпискам.
- `/favorites` — избранные гоночные уикенды.
- `/subscriptions` — управление подписками.
- `/profile` — профиль, язык, часовой пояс и уведомления.
- `/rscg` — календарь СМП РСКГ.
- `/help` — справка по работе бота.

#### Админские

- `/admin` — админ-панель.
- `/restart` — подтянуть изменения из GitHub и перезапустить PM2-процесс, если задан `ADMIN_RESTART_COMMAND`.
- `/admin_user CHAT_ID` — карточка пользователя.
- `/admin_broadcast ...` — массовая рассылка всем активным пользователям.
- `/admin_send CHAT_ID ...` — отправка сообщения одному пользователю.

### Архитектура

```text
Telegram
   │
   ▼
aiogram Dispatcher
   │
   ├── middlewares/
   │   ├── DatabaseMiddleware      # БД, cache и runtime state в handlers
   │   ├── MetricsMiddleware       # счётчики и метрики runtime
   │   ├── ThrottlingMiddleware    # антиспам: 1 msg/sec на пользователя
   │   └── SubscriptionMiddleware  # optional gate на Telegram-канал
   │
   ├── handlers/
   │   ├── start.py                # onboarding, /start, /menu, /help
   │   ├── profile.py              # язык, timezone, уведомления, дайджест
   │   ├── subscriptions.py        # подписки на серии/классы/РСКГ
   │   ├── digest.py               # today/week/history/favorites/ignored
   │   ├── search.py               # поиск и база знаний
   │   ├── session_details.py      # карточки сессий и персональные reminders
   │   ├── rscg.py                 # СМП РСКГ
   │   └── admin.py                # админка, рассылки, backups, restart
   │
   ├── scheduler.py                # фоновые jobs
   ├── database.py                 # SQLite WAL слой
   └── utils/
       ├── api.py                  # RaceDay.watch gRPC-Web клиент
       ├── rscg.py                 # парсер календаря СМП РСКГ
       ├── formatters.py           # карточки, дайджесты, уведомления
       ├── i18n.py                 # ru/en тексты интерфейса
       ├── kb.py                   # inline keyboards
       ├── knowledge_base.py       # база знаний
       ├── events.py               # сборка сессий в гоночные уикенды
       ├── delivery.py             # отправка и retry queue
       ├── cache.py                # L1 memory cache
       ├── metrics.py              # runtime метрики
       └── backups.py              # zip-backup базы админу
```

### Источники данных

#### RaceDay.watch

Основной API:

```env
API_BASE_URL=https://raceday.watch/api
```

Клиент находится в `utils/api.py`. Он получает:

- список серий;
- список классов;
- календарь сессий;
- трансляции;
- live timing.

RaceDay.watch API используется через reverse-engineered gRPC-Web запросы. Чтобы снизить нагрузку, бот использует два уровня кэша:

- L1 — память процесса (`MemoryCache`);
- L2 — SQLite таблица API cache.

Если API временно недоступен, бот может использовать stale cache в пределах `API_FALLBACK_STALE_SECONDS`.

#### СМП РСКГ

Календарь РСКГ парсится отдельно из frontend-данных сайта:

```text
https://rskg.smpracing.ru/calendar
```

Парсер находится в `utils/rscg.py`. Он умеет извлекать `stages` из Next.js flight chunks и сохранять данные в cache.

### База данных

Используется SQLite в режиме WAL. Для одного процесса этого достаточно: бот работает через polling и имеет один persistent connection через `aiosqlite`.

Основные таблицы:

- `users` — профиль пользователя, язык интерфейса, timezone, языки трансляций, quiet hours, digest и глобальные флаги уведомлений.
- `subscriptions` — подписки на `series`, `vehicle_class` и `rscg`.
- `sent_notifications` — дедупликация отправленных уведомлений.
- `pending_deliveries` — retry queue для временно неотправленных сообщений.
- `api_cache` — L2 cache внешнего API.
- `event_favorites` — избранные гоночные уикенды.
- `ignored_events` — уикенды, по которым пользователь отключил уведомления до конца события.
- `session_reminders` — персональные напоминания по конкретным сессиям.

### Что такое гоночный уикенд

RaceDay.watch не отдаёт явный `event_id`. Поэтому бот сам группирует сессии в уикенды по:

- серии;
- трассе / локации;
- близости дат.

Эта логика находится в `utils/events.py`. Именно event-level ключи используются для `Избранного` и `Не интересно`.

### Scheduler jobs

`APScheduler` запускается внутри процесса бота.

Основные jobs:

- `cache_warmup` — прогревает RaceDay.watch cache.
- `notifications` — отправляет уведомления о сессиях.
- `weekly_digest` — отправляет недельный дайджест.
- `session_reminders` — отправляет персональные напоминания.
- `retry_delivery` — повторяет временно неудачные доставки.
- `rscg_notifications` — уведомляет о ближайших этапах СМП РСКГ.
- `db_cleanup` — чистит старые технические записи.
- `admin_backup` — отправляет zip-backup SQLite базы администраторам.

### Уведомления

Глобальные offsets:

```python
3days = 3 дня до старта
1day  = 1 день до старта
1hour = 1 час до старта
start = момент старта
```

Бот не отправляет дубликаты: каждое уведомление имеет dedupe key и сохраняется в БД. Если Telegram временно отвечает rate limit или сетевой ошибкой, сообщение попадает в retry queue.

### Конфигурация

Создайте `.env` на основе `.env.example`:

```env
BOT_TOKEN=your_bot_token_here
DATABASE_PATH=data/raceday.db
API_BASE_URL=https://raceday.watch/api
LOG_LEVEL=INFO
API_FALLBACK_STALE_SECONDS=604800
LIVE_TIMING_CACHE_TTL=60
ADMIN_RESTART_COMMAND=
DEPLOY_WATCH_INTERVAL=60
CHANNEL_ID=
CHANNEL_LINK=
ADMIN_IDS=123456789,987654321
```

Переменные:

- `BOT_TOKEN` — токен Telegram Bot API. Обязателен.
- `ADMIN_IDS` — Telegram user IDs администраторов через запятую.
- `DATABASE_PATH` — путь к SQLite базе.
- `API_BASE_URL` — endpoint RaceDay.watch API.
- `LOG_LEVEL` — уровень логирования.
- `API_FALLBACK_STALE_SECONDS` — сколько секунд можно использовать stale cache при сбое API.
- `LIVE_TIMING_CACHE_TTL` — TTL live timing cache в секундах.
- `ADMIN_RESTART_COMMAND` — shell-команда для `/restart`.
- `DEPLOY_WATCH_INTERVAL` — интервал проверки GitHub в секундах.
- `CHANNEL_ID` и `CHANNEL_LINK` — optional Telegram channel gate.

Никогда не коммитьте `.env`, SQLite базы, WAL-файлы, backup-архивы и логи.

### Локальный запуск

Рекомендуемый вариант:

```bash
uv venv --python 3.14 --seed .venv
uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env
# заполните BOT_TOKEN и ADMIN_IDS
.venv/bin/python main.py
```

Альтернатива с уже установленным Python 3.14:

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

### Docker Compose

```bash
cp .env.example .env
# заполните BOT_TOKEN и ADMIN_IDS
docker compose up --build
```

Runtime-файлы монтируются с хоста:

- `./data` → SQLite база, WAL и backup-архивы;
- `./logs` → PM2/приложенческие логи, если включены.

### PM2 deploy

На сервере:

```bash
git clone https://github.com/kochkinao/RaceReminder.git /home/hermes/RaceReminder
cd /home/hermes/RaceReminder
uv venv --python 3.14 --seed .venv
uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env
# заполните .env
pm2 startOrReload ecosystem.config.cjs --update-env
pm2 save
```

`ecosystem.config.cjs` запускает два процесса:

- `race-reminder-bot` — Telegram polling bot;
- `race-reminder-deploy-watch` — GitHub polling watcher.

Watcher раз в `DEPLOY_WATCH_INTERVAL` секунд проверяет `origin/main`. Если появился новый commit, он запускает:

```bash
scripts/deploy_restart.sh
```

Скрипт делает:

1. `git fetch origin main`;
2. `git pull --ff-only`;
3. обновление зависимостей;
4. `pytest -q`;
5. `pm2 startOrReload ecosystem.config.cjs --only race-reminder-bot --update-env`;
6. `pm2 save`.

### Администрирование PM2

```bash
export PATH="$HOME/.local/node-v22/bin:$PATH"
pm2 status
pm2 logs race-reminder-bot
pm2 logs race-reminder-deploy-watch
pm2 restart race-reminder-bot
pm2 stop race-reminder-bot
pm2 save
```

### Логи

Логи PM2 пишутся в:

```text
logs/pm2-out.log
logs/pm2-error.log
logs/pm2-deploy-watch-out.log
logs/pm2-deploy-watch-error.log
logs/deploy_watch.log
logs/deploy_restart.log
```

Полезные команды:

```bash
grep -E "ERROR|Traceback|TelegramNetworkError|Conflict" logs/pm2-*.log
 tail -f logs/deploy_watch.log
 tail -f logs/deploy_restart.log
```

`TelegramNetworkError: Connection reset by peer` в polling может быть разовой сетевой ошибкой и обычно не требует действий, если процесс продолжает работать и нет постоянных `Conflict` или `Traceback`.

### Тесты

```bash
.venv/bin/pytest -q
```

Набор тестов проверяет:

- database layer;
- scheduler;
- форматтеры;
- delivery retry;
- backups;
- RSCG parser;
- search;
- session details;
- i18n completeness.

### Когда нужны Redis и PostgreSQL

Сейчас бот рассчитан на один процесс, поэтому SQLite WAL + L1/L2 cache достаточно.

PostgreSQL стоит добавить, если появятся:

- несколько bot workers;
- большая пользовательская база;
- сложная аналитика;
- необходимость внешнего BI/SQL-доступа;
- проблемы с write contention SQLite.

Redis стоит добавить, если понадобятся:

- распределённый cache между несколькими процессами;
- распределённый throttling;
- внешняя retry queue;
- pub/sub между bot, scheduler и workers.

---

## English

RaceReminder is a Telegram bot for the [RaceDay.watch](https://raceday.watch/) motorsport calendar. It lets users subscribe to racing series and vehicle classes, view today/week schedules, receive reminders, save favorite race weekends, mute uninteresting weekends, and follow SMP RSKG rounds.

### Features

- Subscriptions to RaceDay.watch racing series.
- Subscriptions to vehicle classes such as GT3, Endurance, Single-Seaters, and more.
- Dedicated **SMP RSKG** calendar integration from `rskg.smpracing.ru`.
- `Today`, `Week`, `History`, `Favorites`, and `Not Interested` screens.
- Search across series, vehicle classes, and knowledge-base articles.
- Built-in knowledge base for series, classes, and racing terms.
- Reminders `3 days`, `1 day`, `1 hour`, and at session start.
- Separate controls for qualifying, practice, and test-session notifications.
- Personal reminders for individual sessions.
- Live timing in cards and notifications when RaceDay.watch provides it.
- Broadcast filtering by language.
- Quiet hours to avoid nighttime notifications.
- Weekly Monday digest.
- Admin dashboard with stats, logs, cache controls, broadcasts, and DB backups.
- PM2 deployment with automatic updates when new commits reach `main`.
- Docker Compose for isolated runtime.

### Interface languages

The bot supports two interface languages:

- `ru` — Russian, default;
- `en` — English.

Users choose their language during onboarding and can change it later in Profile. The main user-facing screens, inline buttons, onboarding, profile, subscriptions, search, knowledge base, digests, session cards, notifications, SMP RSKG screens, and favorites are localized.

Note: series names, track names, session names, and broadcast names come from external APIs and are displayed as received. Admin-only operational screens are intended for the bot owner and may remain Russian.

### User flow

1. The user sends `/start`.
2. The bot asks for the interface language.
3. The user chooses a timezone.
4. The bot automatically subscribes new users to a small default set:
   - Formula 1;
   - FIA World Endurance Championship / WEC;
   - IMSA.
5. The user can add or remove subscriptions in `Subscriptions`.
6. `Today` and `Week` are built from the user's subscriptions.
7. The scheduler periodically checks calendars and sends notifications while respecting:
   - timezone;
   - quiet hours;
   - global notification settings;
   - qualifying/practice settings;
   - muted `Not Interested` weekends;
   - already sent notifications.
8. From a session card or notification, users can add a weekend to `Favorites` or mute it via `Not Interested`.

### Commands

#### User commands

- `/start` — start and onboarding.
- `/menu` — main menu.
- `/today` — today's sessions from subscriptions.
- `/week` — racing week from subscriptions.
- `/history` — recent subscription history.
- `/favorites` — favorite race weekends.
- `/subscriptions` — manage subscriptions.
- `/profile` — language, timezone, and notification settings.
- `/rscg` — SMP RSKG calendar.
- `/help` — bot usage help.

#### Admin commands

- `/admin` — admin dashboard.
- `/restart` — pull GitHub changes and restart the PM2 bot process when `ADMIN_RESTART_COMMAND` is configured.
- `/admin_user CHAT_ID` — user card.
- `/admin_broadcast ...` — broadcast to all active users.
- `/admin_send CHAT_ID ...` — send a message to a single user.

### Architecture

```text
Telegram
   │
   ▼
aiogram Dispatcher
   │
   ├── middlewares/
   │   ├── DatabaseMiddleware      # injects DB, cache, runtime state
   │   ├── MetricsMiddleware       # runtime counters and metrics
   │   ├── ThrottlingMiddleware    # anti-spam: 1 msg/sec per user
   │   └── SubscriptionMiddleware  # optional Telegram channel gate
   │
   ├── handlers/
   │   ├── start.py                # onboarding, /start, /menu, /help
   │   ├── profile.py              # language, timezone, notifications, digest
   │   ├── subscriptions.py        # series/class/RSKG subscriptions
   │   ├── digest.py               # today/week/history/favorites/ignored
   │   ├── search.py               # search and knowledge base
   │   ├── session_details.py      # session cards and personal reminders
   │   ├── rscg.py                 # SMP RSKG
   │   └── admin.py                # admin, broadcasts, backups, restart
   │
   ├── scheduler.py                # background jobs
   ├── database.py                 # SQLite WAL layer
   └── utils/
       ├── api.py                  # RaceDay.watch gRPC-Web client
       ├── rscg.py                 # SMP RSKG calendar parser
       ├── formatters.py           # cards, digests, notifications
       ├── i18n.py                 # ru/en interface texts
       ├── kb.py                   # inline keyboards
       ├── knowledge_base.py       # knowledge base content
       ├── events.py               # groups sessions into race weekends
       ├── delivery.py             # sending and retry queue
       ├── cache.py                # L1 memory cache
       ├── metrics.py              # runtime metrics
       └── backups.py              # zipped DB backups to admins
```

### Data sources

#### RaceDay.watch

Main API endpoint:

```env
API_BASE_URL=https://raceday.watch/api
```

The client lives in `utils/api.py` and fetches:

- racing series;
- vehicle classes;
- calendar sessions;
- broadcasts;
- live timing.

RaceDay.watch is accessed through reverse-engineered gRPC-Web requests. To reduce external traffic, the bot uses two cache layers:

- L1 — process memory (`MemoryCache`);
- L2 — SQLite API cache table.

If the API is temporarily unavailable, the bot can use stale cache for up to `API_FALLBACK_STALE_SECONDS`.

#### SMP RSKG

SMP RSKG calendar data is parsed from frontend data at:

```text
https://rskg.smpracing.ru/calendar
```

The parser is implemented in `utils/rscg.py`. It extracts `stages` from Next.js flight chunks and stores results in cache.

### Database

The bot uses SQLite in WAL mode. For a single polling process, this keeps the runtime simple and reliable.

Main tables:

- `users` — user profile, interface language, timezone, broadcast languages, quiet hours, digest, and global notification flags.
- `subscriptions` — `series`, `vehicle_class`, and `rscg` subscriptions.
- `sent_notifications` — deduplication of sent reminders.
- `pending_deliveries` — retry queue for temporary delivery failures.
- `api_cache` — L2 external API cache.
- `event_favorites` — favorite race weekends.
- `ignored_events` — weekends muted until the event ends.
- `session_reminders` — personal reminders for specific sessions.

### Race weekend grouping

RaceDay.watch does not provide a stable explicit `event_id`. RaceReminder groups sessions into race weekends using:

- series;
- track/location;
- date proximity.

This logic lives in `utils/events.py`. Event-level keys are used for `Favorites` and `Not Interested`.

### Scheduler jobs

`APScheduler` runs inside the bot process.

Main jobs:

- `cache_warmup` — warms RaceDay.watch cache.
- `notifications` — sends session reminders.
- `weekly_digest` — sends weekly digest.
- `session_reminders` — sends personal reminders.
- `retry_delivery` — retries temporary delivery failures.
- `rscg_notifications` — sends SMP RSKG reminders.
- `db_cleanup` — removes old technical records.
- `admin_backup` — sends zipped SQLite backups to admins.

### Notifications

Global offsets:

```python
3days = 3 days before start
1day  = 1 day before start
1hour = 1 hour before start
start = at session start
```

The bot avoids duplicates by saving a dedupe key for every sent notification. If Telegram responds with a rate limit or a transient network error, delivery is queued for retry.

### Configuration

Create `.env` from `.env.example`:

```env
BOT_TOKEN=your_bot_token_here
DATABASE_PATH=data/raceday.db
API_BASE_URL=https://raceday.watch/api
LOG_LEVEL=INFO
API_FALLBACK_STALE_SECONDS=604800
LIVE_TIMING_CACHE_TTL=60
ADMIN_RESTART_COMMAND=
DEPLOY_WATCH_INTERVAL=60
CHANNEL_ID=
CHANNEL_LINK=
ADMIN_IDS=123456789,987654321
```

Variables:

- `BOT_TOKEN` — Telegram Bot API token. Required.
- `ADMIN_IDS` — comma-separated Telegram user IDs for admins.
- `DATABASE_PATH` — SQLite database path.
- `API_BASE_URL` — RaceDay.watch API endpoint.
- `LOG_LEVEL` — logging level.
- `API_FALLBACK_STALE_SECONDS` — how long stale API cache can be used after API failures.
- `LIVE_TIMING_CACHE_TTL` — live timing cache TTL in seconds.
- `ADMIN_RESTART_COMMAND` — shell command executed by `/restart`.
- `DEPLOY_WATCH_INTERVAL` — GitHub polling interval in seconds.
- `CHANNEL_ID` and `CHANNEL_LINK` — optional Telegram channel gate.

Never commit `.env`, SQLite databases, WAL files, backup archives, or logs.

### Local development

Recommended:

```bash
uv venv --python 3.14 --seed .venv
uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env
# fill BOT_TOKEN and ADMIN_IDS
.venv/bin/python main.py
```

Alternative with a preinstalled Python 3.14:

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

### Docker Compose

```bash
cp .env.example .env
# fill BOT_TOKEN and ADMIN_IDS
docker compose up --build
```

Runtime files are mounted from the host:

- `./data` → SQLite database, WAL files, and backups;
- `./logs` → PM2/application logs if enabled.

### PM2 deployment

On a server:

```bash
git clone https://github.com/kochkinao/RaceReminder.git /home/hermes/RaceReminder
cd /home/hermes/RaceReminder
uv venv --python 3.14 --seed .venv
uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env
# fill .env
pm2 startOrReload ecosystem.config.cjs --update-env
pm2 save
```

`ecosystem.config.cjs` starts two processes:

- `race-reminder-bot` — Telegram polling bot;
- `race-reminder-deploy-watch` — GitHub polling watcher.

The watcher checks `origin/main` every `DEPLOY_WATCH_INTERVAL` seconds. When it sees a new commit, it runs:

```bash
scripts/deploy_restart.sh
```

The script performs:

1. `git fetch origin main`;
2. `git pull --ff-only`;
3. dependency update;
4. `pytest -q`;
5. `pm2 startOrReload ecosystem.config.cjs --only race-reminder-bot --update-env`;
6. `pm2 save`.

### PM2 operations

```bash
export PATH="$HOME/.local/node-v22/bin:$PATH"
pm2 status
pm2 logs race-reminder-bot
pm2 logs race-reminder-deploy-watch
pm2 restart race-reminder-bot
pm2 stop race-reminder-bot
pm2 save
```

### Logs

PM2 logs are stored in:

```text
logs/pm2-out.log
logs/pm2-error.log
logs/pm2-deploy-watch-out.log
logs/pm2-deploy-watch-error.log
logs/deploy_watch.log
logs/deploy_restart.log
```

Useful commands:

```bash
grep -E "ERROR|Traceback|TelegramNetworkError|Conflict" logs/pm2-*.log
tail -f logs/deploy_watch.log
tail -f logs/deploy_restart.log
```

`TelegramNetworkError: Connection reset by peer` can happen with Telegram long polling. It is usually recoverable if the process stays online and there are no repeated `Conflict` or `Traceback` errors.

### Tests

```bash
.venv/bin/pytest -q
```

The test suite covers:

- database layer;
- scheduler;
- formatters;
- delivery retry;
- backups;
- RSCG parser;
- search;
- session details;
- i18n completeness.

### When to add Redis or PostgreSQL

The current runtime is designed for one bot process. SQLite WAL plus L1/L2 cache is enough for this stage.

Add PostgreSQL when you need:

- multiple bot workers;
- a much larger user base;
- heavier analytics;
- external BI/SQL access;
- relief from SQLite write contention.

Add Redis when you need:

- shared cache across processes;
- distributed throttling;
- external retry queue;
- pub/sub between bot, scheduler, and workers.
