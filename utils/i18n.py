from __future__ import annotations

from html import escape

UI_RU = "ru"
UI_EN = "en"
DEFAULT_UI_LANG = UI_RU

UI_LANGUAGE_OPTIONS: list[tuple[str, str]] = [
    ("Русский", UI_RU),
    ("English", UI_EN),
]

_TEXTS: dict[str, dict[str, str]] = {
    "app.main_menu": {
        UI_RU: "🏁 <b>Главное меню</b>\n\nЗдесь собраны экраны по вашим подпискам.\nЕсли хотите изменить состав гонок и уведомлений, начните с <b>Подписок</b> и <b>Профиля</b>.",
        UI_EN: "🏁 <b>Main Menu</b>\n\nThese screens are built from your subscriptions.\nIf you want to change which races and reminders you get, start with <b>Subscriptions</b> and <b>Profile</b>.",
    },
    "app.main_menu_empty": {
        UI_RU: "🏁 <b>Главное меню</b>\n\nПохоже, у вас пока нет подписок.\n\n<b>С чего начать:</b>\n1. Откройте <b>Подписки</b> и добавьте серии, классы или СМП РСКГ.\n2. При необходимости используйте <b>Поиск</b> или <b>Базу знаний</b>.\n3. Потом возвращайтесь в <b>Сегодня</b> и <b>Неделю</b>.",
        UI_EN: "🏁 <b>Main Menu</b>\n\nIt looks like you do not have any subscriptions yet.\n\n<b>Start here:</b>\n1. Open <b>Subscriptions</b> and add series, classes, or SMP RSKG.\n2. Use <b>Search</b> or the <b>Knowledge Base</b> if needed.\n3. Then come back to <b>Today</b> and <b>Week</b>.",
    },
    "menu.today": {UI_RU: "📅 Сегодня", UI_EN: "📅 Today"},
    "menu.week": {UI_RU: "📆 Неделя", UI_EN: "📆 Week"},
    "menu.subscriptions": {UI_RU: "⭐ Подписки", UI_EN: "⭐ Subscriptions"},
    "menu.search": {UI_RU: "🔍 Поиск", UI_EN: "🔍 Search"},
    "menu.knowledge_base": {UI_RU: "📚 База знаний", UI_EN: "📚 Knowledge Base"},
    "menu.favorites": {UI_RU: "❤️ Избранное", UI_EN: "❤️ Favorites"},
    "menu.rscg": {UI_RU: "🏎️ СМП РСКГ", UI_EN: "🏎️ SMP RSKG"},
    "menu.help": {UI_RU: "ℹ️ Как это работает", UI_EN: "ℹ️ How It Works"},
    "menu.profile": {UI_RU: "⚙️ Профиль", UI_EN: "⚙️ Profile"},
    "menu.back": {UI_RU: "◀️ Назад", UI_EN: "◀️ Back"},
    "menu.back_to_menu": {UI_RU: "◀️ Меню", UI_EN: "◀️ Menu"},
    "menu.back_to_subscriptions": {UI_RU: "◀️ Подписки", UI_EN: "◀️ Subscriptions"},
    "menu.back_to_history": {UI_RU: "◀️ К истории", UI_EN: "◀️ Back to History"},
    "menu.back_to_session": {UI_RU: "◀️ К сессии", UI_EN: "◀️ Back to Session"},
    "menu.back_to_knowledge_base": {UI_RU: "◀️ База знаний", UI_EN: "◀️ Knowledge Base"},
    "menu.back_to_list": {UI_RU: "◀️ К списку", UI_EN: "◀️ Back to List"},
    "menu.done": {UI_RU: "✅ Готово", UI_EN: "✅ Done"},
    "menu.all_subscriptions": {UI_RU: "📋 Все подписки", UI_EN: "📋 All Subscriptions"},
    "menu.series": {UI_RU: "🏎️ Серии", UI_EN: "🏎️ Series"},
    "menu.classes": {UI_RU: "🏷️ Классы", UI_EN: "🏷️ Classes"},
    "menu.my_subscriptions": {UI_RU: "📋 Мои подписки", UI_EN: "📋 My Subscriptions"},
    "menu.qualifying": {UI_RU: "Квалификации", UI_EN: "Qualifying"},
    "menu.practice": {UI_RU: "Практики", UI_EN: "Practice"},
    "menu.qualifying_and_tests": {UI_RU: "Практики и тесты", UI_EN: "Practice and Testing"},
    "menu.broadcast_languages": {UI_RU: "🌐 Языки трансляций", UI_EN: "🌐 Broadcast Languages"},
    "menu.notification_details": {UI_RU: "🔔 Уведомления о квалификациях и практиках", UI_EN: "🔔 Notifications of qualifications and practices"},
    "menu.digest_time": {UI_RU: "✏️ Время дайджеста", UI_EN: "✏️ Digest Time"},
    "menu.quiet_hours": {UI_RU: "✏️ Тихие часы", UI_EN: "✏️ Quiet Hours"},
    "menu.enter_manually": {UI_RU: "✍️ Ввести вручную", UI_EN: "✍️ Enter Manually"},
    "menu.races": {UI_RU: "Гонки", UI_EN: "Races"},
    "menu.all": {UI_RU: "Все", UI_EN: "All"},
    "menu.by_series": {UI_RU: "🏎️ По серии", UI_EN: "🏎️ By Series"},
    "menu.by_class": {UI_RU: "🏷️ По классу", UI_EN: "🏷️ By Class"},
    "menu.reset_filter": {UI_RU: "❌ Сбросить фильтр", UI_EN: "❌ Reset Filter"},
    "menu.select_series": {UI_RU: "Выберите серию", UI_EN: "Choose a series"},
    "menu.select_class": {UI_RU: "Выберите класс", UI_EN: "Choose a class"},
    "menu.favorite_add": {UI_RU: "❤️ В избранное", UI_EN: "❤️ Add to Favorites"},
    "menu.favorite_remove": {UI_RU: "💔 Убрать из избранного", UI_EN: "💔 Remove from Favorites"},
    "menu.remind": {UI_RU: "🔔 Напомнить", UI_EN: "🔔 Remind Me"},
    "menu.remind_1day": {UI_RU: "За сутки", UI_EN: "1 Day Before"},
    "menu.remind_1hour": {UI_RU: "За час", UI_EN: "1 Hour Before"},
    "menu.remind_start": {UI_RU: "На старт", UI_EN: "At Start"},
    "menu.subscribe": {UI_RU: "✅ Подписаться", UI_EN: "✅ Subscribe"},
    "menu.unsubscribe": {UI_RU: "❌ Отписаться", UI_EN: "❌ Unsubscribe"},
    "menu.language": {UI_RU: "🌐 Язык", UI_EN: "🌐 Language"},
    "menu.timezone": {UI_RU: "🌍 Часовой пояс", UI_EN: "🌍 Timezone"},
    "menu.without_broadcasts": {UI_RU: "Гонки без трансляции", UI_EN: "Sessions Without Broadcasts"},
    "menu.monday_digest": {UI_RU: "Дайджест по понедельникам", UI_EN: "Monday Digest"},
    "menu.quiet_hours_state": {UI_RU: "Тихие часы", UI_EN: "Quiet Hours"},
    "onboarding.choose_language": {
        UI_RU: "🌐 <b>Выберите язык</b>\n\nЯ переключу интерфейс и сообщения бота на него.",
        UI_EN: "🌐 <b>Choose your language</b>\n\nI will switch the bot interface and messages to it.",
    },
    "onboarding.welcome": {
        UI_RU: "🏁 <b>Добро пожаловать в RaceDay Bot!</b>\n\nЯ слежу за гоночным календарём и присылаю уведомления о гонках.\n\n<b>Что умею:</b>\n• 📅 Еженедельный дайджест по понедельникам\n• 🔔 Напоминания за 3 дня, сутки и час до старта\n• 📺 Ссылки на трансляции с фильтром по языку\n• 📚 База знаний о популярных сериях\n• 🔍 Поиск гонок и серий\n\nПо умолчанию подпишу на Formula 1, MotoGP, WEC и IMSA.\n\nДля начала выберите <b>часовой пояс</b>:",
        UI_EN: "🏁 <b>Welcome to RaceDay Bot!</b>\n\nI track the racing calendar and send reminders about upcoming sessions.\n\n<b>What I can do:</b>\n• 📅 Weekly digest every Monday\n• 🔔 Reminders 3 days, 1 day, and 1 hour before the start\n• 📺 Broadcast links filtered by language\n• 📚 Knowledge base for popular series\n• 🔍 Search for races and series\n\nBy default I will subscribe you to Formula 1, MotoGP, WEC, and IMSA.\n\nFirst, choose your <b>timezone</b>:",
    },
    "onboarding.welcome_back": {UI_RU: "👋 С возвращением!", UI_EN: "👋 Welcome back!"},
    "onboarding.subscribing": {UI_RU: "⏳ Подписываю на популярные серии...", UI_EN: "⏳ Subscribing you to popular series..."},
    "onboarding.setup_done": {
        UI_RU: "✅ <b>Настройка завершена!</b>\n\nВы подписаны на:\n{subs_text}\n\nИспользуйте /menu для навигации.",
        UI_EN: "✅ <b>Setup complete!</b>\n\nYou are subscribed to:\n{subs_text}\n\nUse /menu to navigate.",
    },
    "onboarding.subscriptions_failed": {
        UI_RU: "  (не удалось загрузить список серий)",
        UI_EN: "  (failed to load the series list)",
    },
    "onboarding.checking_subscription": {UI_RU: "Проверяем подписку...", UI_EN: "Checking subscription..."},
    "onboarding.enter_timezone": {
        UI_RU: "Введите ваш часовой пояс, например: <code>Europe/Berlin</code>",
        UI_EN: "Enter your timezone, for example: <code>Europe/Berlin</code>",
    },
    "error.unknown_timezone": {
        UI_RU: "❌ Неизвестный часовой пояс <code>{value}</code>. Попробуйте снова.",
        UI_EN: "❌ Unknown timezone <code>{value}</code>. Try again.",
    },
    "profile.title": {UI_RU: "⚙️ <b>Личный кабинет</b>", UI_EN: "⚙️ <b>Profile</b>"},
    "help.title": {
        UI_RU: "ℹ️ <b>Как работает бот</b>",
        UI_EN: "ℹ️ <b>How the Bot Works</b>",
    },
    "help.body": {
        UI_RU: "1. Подпишитесь на серии, классы или СМП РСКГ в разделе <b>Подписки</b>.\n2. В <b>Профиле</b> настройте язык интерфейса, языки трансляций и типы напоминаний.\n3. <b>Сегодня</b> показывает ближайшие события по вашим подпискам.\n4. <b>Неделя</b> показывает обзор недели по вашим подпискам.\n5. <b>Поиск</b> помогает быстро найти и добавить серию или класс.\n6. <b>Языки трансляций</b> фильтруют только ссылки на трансляции, но не скрывают сами гонки.\n7. Квалификации и практики можно включать и выключать отдельно.\n8. <b>СМП РСКГ</b> работает как подписка на серию целиком: внутри доступны этапы и напоминания по ним.",
        UI_EN: "1. Subscribe to series, classes, or SMP RSKG in <b>Subscriptions</b>.\n2. In <b>Profile</b>, configure the interface language, broadcast languages, and reminder types.\n3. <b>Today</b> shows upcoming events from your subscriptions.\n4. <b>Week</b> shows a weekly overview from your subscriptions.\n5. <b>Search</b> helps you quickly find and add a series or class.\n6. <b>Broadcast languages</b> filter only broadcast links, not the races themselves.\n7. Qualifying and practice can be turned on and off separately.\n8. <b>SMP RSKG</b> works as a full-series subscription with rounds and reminders inside it.",
    },
    "profile.summary": {
        UI_RU: "Здесь настраивается поведение бота: язык, уведомления, дайджесты и фильтры.\nСостав серий и классов меняется в <b>Подписках</b>.\n\n🖥 Язык интерфейса: <b>{ui_lang_name}</b>\n🌍 Часовой пояс: <code>{timezone}</code>\n🌐 Языки: <b>{langs}</b>\n📅 Дайджест: {digest_state} в {digest_time}\n🔕 Тихие часы: {quiet_state} ({quiet_start}:00–{quiet_end}:00)",
        UI_EN: "This is where you configure how the bot behaves: language, reminders, digests, and filters.\nThe list of series and classes is managed in <b>Subscriptions</b>.\n\n🖥 Interface language: <b>{ui_lang_name}</b>\n🌍 Timezone: <code>{timezone}</code>\n🌐 Languages: <b>{langs}</b>\n📅 Digest: {digest_state} at {digest_time}\n🔕 Quiet hours: {quiet_state} ({quiet_start}:00–{quiet_end}:00)",
    },
    "profile.interface_language_title": {
        UI_RU: "🌐 <b>Язык интерфейса</b>\nВыберите язык меню и сообщений бота:",
        UI_EN: "🌐 <b>Interface Language</b>\nChoose the language for the bot menu and messages:",
    },
    "profile.language_updated": {
        UI_RU: "✅ Язык интерфейса обновлён",
        UI_EN: "✅ Interface language updated",
    },
    "profile.broadcast_languages_title": {
        UI_RU: "🌐 <b>Языки трансляций</b>\nМожно выбрать несколько:",
        UI_EN: "🌐 <b>Broadcast Languages</b>\nYou can select multiple:",
    },
    "profile.choose_timezone": {UI_RU: "Выберите часовой пояс:", UI_EN: "Choose a timezone:"},
    "profile.invalid_timezone": {UI_RU: "❌ Неверный часовой пояс. Попробуйте снова.", UI_EN: "❌ Invalid timezone. Try again."},
    "profile.timezone_updated": {UI_RU: "✅ Часовой пояс: <code>{value}</code>", UI_EN: "✅ Timezone: <code>{value}</code>"},
    "profile.digest_time_prompt": {
        UI_RU: "Введите время дайджеста в формате <code>HH:MM</code>, например <code>08:00</code>",
        UI_EN: "Enter the digest time in <code>HH:MM</code> format, for example <code>08:00</code>",
    },
    "profile.invalid_time": {UI_RU: "❌ Неверный формат. Пример: <code>08:30</code>", UI_EN: "❌ Invalid format. Example: <code>08:30</code>"},
    "profile.digest_time_updated": {UI_RU: "✅ Время дайджеста: <b>{value}</b>", UI_EN: "✅ Digest time: <b>{value}</b>"},
    "profile.quiet_hours_prompt": {
        UI_RU: "Введите тихие часы в формате <code>START END</code>\nНапример: <code>23 7</code> — с 23:00 до 07:00",
        UI_EN: "Enter quiet hours in the format <code>START END</code>\nFor example: <code>23 7</code> means from 23:00 to 07:00",
    },
    "profile.invalid_quiet_hours": {UI_RU: "❌ Неверный формат. Пример: <code>23 7</code>", UI_EN: "❌ Invalid format. Example: <code>23 7</code>"},
    "profile.quiet_hours_updated": {UI_RU: "✅ Тихие часы: {start}:00 – {end}:00", UI_EN: "✅ Quiet hours: {start}:00 – {end}:00"},
    "subscriptions.title": {
        UI_RU: "⭐ <b>Управление подписками</b>\nПодписки определяют, какие гонки попадают в ваши экраны и уведомления.",
        UI_EN: "⭐ <b>Manage Subscriptions</b>\nSubscriptions decide which races appear in your screens and reminders.",
    },
    "subscriptions.none": {UI_RU: "У вас нет подписок.", UI_EN: "You have no subscriptions."},
    "subscriptions.mine": {UI_RU: "📋 <b>Ваши подписки:</b>", UI_EN: "📋 <b>Your Subscriptions:</b>"},
    "subscriptions.series_label": {UI_RU: "<b>Серии:</b>", UI_EN: "<b>Series:</b>"},
    "subscriptions.classes_label": {UI_RU: "<b>Классы:</b>", UI_EN: "<b>Classes:</b>"},
    "subscriptions.rscg_label": {UI_RU: "<b>Национальные серии:</b>", UI_EN: "<b>National Series:</b>"},
    "subscriptions.notify_title": {
        UI_RU: "🔔 <b>Уведомления о квалификациях и практиках</b>\nВыберите подписку, для которой хотите настроить уведомления.",
        UI_EN: "🔔 <b>Notifications of qualifications and practices</b>\nChoose a subscription to configure non-race notifications.",
    },
    "subscriptions.notify_empty": {
        UI_RU: "🔔 <b>Уведомления о квалификациях и практиках</b>\n\nЭтот раздел работает для обычных серий и классов.\nПодходящих подписок пока нет.",
        UI_EN: "🔔 <b>Notifications of qualifications and practices</b>\n\nThis section works for regular series and classes.\nThere are no matching subscriptions yet.",
    },
    "subscriptions.notify_card": {
        UI_RU: "🔔 <b>Негоночные уведомления</b>\n\n{kind}: <b>{name}</b>\nКвалификации: {qual_state}\nПрактики и тесты: {practice_state}\n\nУведомления о самих гонках остаются включёнными.",
        UI_EN: "🔔 <b>Non-race Notifications</b>\n\n{kind}: <b>{name}</b>\nQualifying: {qual_state}\nPractice and testing: {practice_state}\n\nRace notifications remain enabled.",
    },
    "subscriptions.kind_series": {UI_RU: "Серия", UI_EN: "Series"},
    "subscriptions.kind_class": {UI_RU: "Класс", UI_EN: "Class"},
    "subscriptions.kind_national": {UI_RU: "Национальная серия", UI_EN: "National Series"},
    "subscriptions.not_found": {UI_RU: "Подписка не найдена", UI_EN: "Subscription not found"},
    "subscriptions.setting_updated": {UI_RU: "Настройка обновлена", UI_EN: "Setting updated"},
    "subscriptions.unknown_setting": {UI_RU: "Неизвестная настройка", UI_EN: "Unknown setting"},
    "subscriptions.series_screen": {UI_RU: "🏎️ <b>Серии</b>\nВыберите группу, чтобы не листать все серии подряд.", UI_EN: "🏎️ <b>Series</b>\nChoose a group so you do not have to scroll through everything."},
    "subscriptions.choose_subgroup": {UI_RU: "Выберите подгруппу.", UI_EN: "Choose a subgroup."},
    "subscriptions.series_hint": {UI_RU: "✅ — подписаны | ℹ️ — подробнее", UI_EN: "✅ — subscribed | ℹ️ — details"},
    "subscriptions.series_not_found": {UI_RU: "Серия не найдена", UI_EN: "Series not found"},
    "subscriptions.class_screen": {UI_RU: "🏷️ <b>Классы автомобилей</b>\n✅ — подписаны", UI_EN: "🏷️ <b>Vehicle Classes</b>\n✅ — subscribed"},
    "subscriptions.class_not_found": {UI_RU: "Класс не найден", UI_EN: "Class not found"},
    "digest.today_header": {UI_RU: "📅 <b>Мой гоночный день</b>", UI_EN: "📅 <b>My Racing Day</b>"},
    "digest.week_header": {UI_RU: "📆 <b>Моя гоночная неделя</b>", UI_EN: "📆 <b>My Racing Week</b>"},
    "digest.history_header": {UI_RU: "📖 <b>История по подпискам</b>", UI_EN: "📖 <b>Subscription History</b>"},
    "digest.summary": {
        UI_RU: "{header}\n\nНайдено <b>{count}</b> сессий на {period}.\nПодписок: серии — <b>{series_count}</b>, классы — <b>{class_count}</b>.\n\nВыберите серию или класс, чтобы сузить дайджест.",
        UI_EN: "{header}\n\nFound <b>{count}</b> sessions for the {period}.\nSubscriptions: series — <b>{series_count}</b>, classes — <b>{class_count}</b>.\n\nChoose a series or class to narrow the digest.",
    },
    "digest.period_today": {UI_RU: "день", UI_EN: "day"},
    "digest.period_week": {UI_RU: "неделю", UI_EN: "week"},
    "digest.filter": {UI_RU: "Фильтр", UI_EN: "Filter"},
    "digest.loading": {UI_RU: "Загружаю...", UI_EN: "Loading..."},
    "digest.setting_updated": {UI_RU: "Настройка обновлена", UI_EN: "Setting updated"},
    "digest.no_filter_results": {UI_RU: "😴 Ничего не найдено по выбранному фильтру.", UI_EN: "😴 Nothing matched the selected filter."},
    "digest.no_subscriptions_today": {
        UI_RU: "📅 <b>Мой гоночный день</b>\n\nУ вас пока нет подписок, поэтому мне нечего показывать на сегодня.\n\nДобавьте серии, классы или СМП РСКГ, и здесь появятся ближайшие события.",
        UI_EN: "📅 <b>My Racing Day</b>\n\nYou do not have any subscriptions yet, so there is nothing to show for today.\n\nAdd series, classes, or SMP RSKG and upcoming events will appear here.",
    },
    "digest.no_subscriptions_week": {
        UI_RU: "📆 <b>Моя гоночная неделя</b>\n\nУ вас пока нет подписок, поэтому недельный обзор пуст.\n\nНачните с подписок, и бот соберёт для вас неделю гонок автоматически.",
        UI_EN: "📆 <b>My Racing Week</b>\n\nYou do not have any subscriptions yet, so the weekly overview is empty.\n\nStart with subscriptions and the bot will build your racing week automatically.",
    },
    "digest.no_subscriptions_history": {
        UI_RU: "📖 <b>История по подпискам</b>\n\nИстория появится после того, как вы подпишетесь хотя бы на одну серию, класс или СМП РСКГ.",
        UI_EN: "📖 <b>Subscription History</b>\n\nHistory will appear after you subscribe to at least one series, class, or SMP RSKG.",
    },
    "digest.history_period": {UI_RU: "Период: последние <b>7 дней</b>", UI_EN: "Period: last <b>7 days</b>"},
    "digest.history_filter_label": {UI_RU: "Фильтр: <b>{label}</b>", UI_EN: "Filter: <b>{label}</b>"},
    "digest.filter_all": {UI_RU: "все сессии", UI_EN: "all sessions"},
    "digest.filter_race": {UI_RU: "только гонки", UI_EN: "races only"},
    "digest.filter_qualifying": {UI_RU: "только квалификации", UI_EN: "qualifying only"},
    "digest.filter_practice": {UI_RU: "только практики", UI_EN: "practice only"},
    "digest.filter_series": {UI_RU: "серия: {name}", UI_EN: "series: {name}"},
    "digest.filter_class": {UI_RU: "класс: {name}", UI_EN: "class: {name}"},
    "digest.pick_series_title": {UI_RU: "🏎️ <b>Фильтр по серии</b>\n\nВыберите фильтр:", UI_EN: "🏎️ <b>Filter by Series</b>\n\nChoose a filter:"},
    "digest.pick_class_title": {UI_RU: "🏷️ <b>Фильтр по классу</b>\n\nВыберите фильтр:", UI_EN: "🏷️ <b>Filter by Class</b>\n\nChoose a filter:"},
    "digest.no_matching_subs": {UI_RU: "Нет подходящих подписок для фильтра.", UI_EN: "No matching subscriptions for this filter."},
    "search.prompt": {
        UI_RU: "🔍 <b>Поиск серий и классов</b>\n\nВведите название серии или класса автомобилей.\nНапример: <i>Formula 1</i>, <i>GT3</i>, <i>WEC</i>",
        UI_EN: "🔍 <b>Search Series and Classes</b>\n\nEnter a series or vehicle class name.\nFor example: <i>Formula 1</i>, <i>GT3</i>, <i>WEC</i>",
    },
    "search.results": {
        UI_RU: "🔍 <b>Результаты поиска</b>\n\nЗапрос: <b>{query}</b>\nНайдено: серии — <b>{series_count}</b>, классы — <b>{class_count}</b>, статьи базы знаний — <b>{kb_count}</b>\n\n✅ / 💔 — подписка, 📚 — открыть справку.",
        UI_EN: "🔍 <b>Search Results</b>\n\nQuery: <b>{query}</b>\nFound: series — <b>{series_count}</b>, classes — <b>{class_count}</b>, knowledge base articles — <b>{kb_count}</b>\n\n✅ / 💔 manage subscriptions, 📚 opens the explainer.",
    },
    "search.kb_only_results": {
        UI_RU: "🔍 <b>Результаты поиска</b>\n\nЗапрос: <b>{query}</b>\nПодписок по этому запросу не найдено, но есть <b>{kb_count}</b> статей базы знаний.\n\nОткройте справку ниже, чтобы быстро разобраться в термине или серии.",
        UI_EN: "🔍 <b>Search Results</b>\n\nQuery: <b>{query}</b>\nNo subscription targets matched this query, but there are <b>{kb_count}</b> knowledge base articles.\n\nOpen the explainer below to understand the term or series quickly.",
    },
    "search.nothing_found": {
        UI_RU: "😕 Ничего не найдено по запросу <b>{query}</b>\n\nПопробуйте другой запрос или воспользуйтесь базой знаний.",
        UI_EN: "😕 Nothing found for <b>{query}</b>\n\nTry another query or use the knowledge base.",
    },
    "search.refresh_failed": {UI_RU: "Не удалось обновить результаты. Повторите поиск.", UI_EN: "Could not refresh the results. Run the search again."},
    "search.item_not_found": {UI_RU: "Элемент не найден", UI_EN: "Item not found"},
    "search.query_label": {UI_RU: "Запрос", UI_EN: "Query"},
    "search.kb_title": {
        UI_RU: "📚 <b>База знаний</b>\n\nЗдесь собраны серии, классы и термины, которые встречаются в боте. Сначала выберите раздел.",
        UI_EN: "📚 <b>Knowledge Base</b>\n\nThis section contains series, classes, and terms used across the bot. Start by choosing a section.",
    },
    "search.kb_group_title": {
        UI_RU: "📚 <b>База знаний</b>\n\nВыберите тему из раздела ниже.",
        UI_EN: "📚 <b>Knowledge Base</b>\n\nChoose a topic from the section below.",
    },
    "generic.kb_not_found": {
        UI_RU: "Статья базы знаний не найдена",
        UI_EN: "Knowledge base article not found",
    },
    "rscg.list_title": {
        UI_RU: "🏎️ <b>СМП РСКГ</b>\n\nПодписка работает на всю серию, а ниже можно открыть карточки отдельных этапов.",
        UI_EN: "🏎️ <b>SMP RSKG</b>\n\nThe subscription applies to the whole series, and below you can open individual round cards.",
    },
    "rscg.name": {
        UI_RU: "СМП РСКГ",
        UI_EN: "SMP RSKG",
    },
    "rscg.empty": {
        UI_RU: "😕 Календарь СМП РСКГ пока недоступен.",
        UI_EN: "😕 SMP RSKG calendar is not available yet.",
    },
    "rscg.subscribed": {
        UI_RU: "✅ Подписка на СМП РСКГ включена",
        UI_EN: "✅ Subscribed to SMP RSKG",
    },
    "rscg.unsubscribed": {
        UI_RU: "❌ Подписка на СМП РСКГ отключена",
        UI_EN: "❌ Unsubscribed from SMP RSKG",
    },
    "rscg.stage_not_found": {
        UI_RU: "Этап РСКГ не найден",
        UI_EN: "SMP RSKG round not found",
    },
    "favorites.empty": {UI_RU: "❤️ <b>Избранное</b>\n\nПока пусто. Добавляйте интересные сессии из карточки `Подробнее`.", UI_EN: "❤️ <b>Favorites</b>\n\nNothing here yet. Add interesting sessions from the details card."},
    "favorites.title": {UI_RU: "❤️ <b>Избранные сессии</b>", UI_EN: "❤️ <b>Favorite Sessions</b>"},
    "favorites.missing": {UI_RU: "Некоторые старые сессии ({count}) уже недоступны в текущих окнах API.", UI_EN: "Some older sessions ({count}) are no longer available in the current API windows."},
    "session.not_found": {UI_RU: "Сессия не найдена", UI_EN: "Session not found"},
    "session.no_filtered_data": {UI_RU: "😕 Для этой сессии нет данных, подходящих под ваши текущие фильтры.", UI_EN: "😕 No session data matches your current filters."},
    "session.favorite_added": {UI_RU: "❤️ Добавлено в избранное", UI_EN: "❤️ Added to favorites"},
    "session.favorite_removed": {UI_RU: "💔 Убрано из избранного", UI_EN: "💔 Removed from favorites"},
    "session.reminder_title": {UI_RU: "🔔 <b>Персональные напоминания</b>", UI_EN: "🔔 <b>Personal Reminders</b>"},
    "session.start": {UI_RU: "Старт", UI_EN: "Start"},
    "session.reminder_prompt": {UI_RU: "Выберите напоминания, которые хотите получать именно по этой сессии.", UI_EN: "Choose which reminders you want for this specific session."},
    "session.reminder_create_failed": {UI_RU: "Не удалось создать напоминание", UI_EN: "Could not create reminder"},
    "session.reminder_time_passed": {UI_RU: "Это время уже прошло для выбранной сессии.", UI_EN: "That time has already passed for the selected session."},
    "session.reminder_removed": {UI_RU: "❌ Напоминание {label} удалено", UI_EN: "❌ Reminder {label} removed"},
    "session.reminder_enabled": {UI_RU: "✅ Напоминание {label} включено", UI_EN: "✅ Reminder {label} enabled"},
    "session.reminder_label_1day": {UI_RU: "за сутки", UI_EN: "for 1 day before"},
    "session.reminder_label_1hour": {UI_RU: "за час", UI_EN: "for 1 hour before"},
    "session.reminder_label_start": {UI_RU: "на старт", UI_EN: "for start"},
    "generic.official_website": {UI_RU: "Официальный сайт", UI_EN: "Official Website"},
    "generic.session": {UI_RU: "Сессия", UI_EN: "Session"},
    "generic.back_to_sections": {UI_RU: "◀️ К разделам", UI_EN: "◀️ Sections"},
    "generic.enabled": {UI_RU: "вкл", UI_EN: "on"},
    "generic.disabled": {UI_RU: "выкл", UI_EN: "off"},
    "generic.unknown_setting": {UI_RU: "Неизвестная настройка", UI_EN: "Unknown setting"},
    "generic.series_not_found": {UI_RU: "Серия не найдена", UI_EN: "Series not found"},
}


def normalize_ui_lang(value: str | None) -> str:
    return value if value in {UI_RU, UI_EN} else DEFAULT_UI_LANG


def get_ui_lang(user: dict | None = None, fallback: str = DEFAULT_UI_LANG) -> str:
    if not user:
        return fallback
    return normalize_ui_lang(user.get("ui_lang"))


def tr(lang: str, key: str, **kwargs: object) -> str:
    lang = normalize_ui_lang(lang)
    value = _TEXTS.get(key, {}).get(lang) or _TEXTS.get(key, {}).get(DEFAULT_UI_LANG) or key
    return value.format(**kwargs)


def bool_text(lang: str, enabled: bool) -> str:
    return tr(lang, "generic.enabled" if enabled else "generic.disabled")


def safe(value: str) -> str:
    return escape(value)
