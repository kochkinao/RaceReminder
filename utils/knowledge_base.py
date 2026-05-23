from __future__ import annotations

import re
import unicodedata

from utils.i18n import DEFAULT_UI_LANG, normalize_ui_lang, tr

type LocalizedText = dict[str, str]
type KnowledgeEntry = dict[str, str | list[str] | LocalizedText]


def _normalize(s: str) -> str:
    s = s.lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("ß", "ss")
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return s


def _loc(ru: str, en: str) -> LocalizedText:
    return {"ru": ru, "en": en}


def _entry(
    *,
    group: str,
    emoji: str,
    short_ru: str,
    short_en: str,
    long_ru: str,
    long_en: str,
    used_in_ru: str = "",
    used_in_en: str = "",
    highlight_ru: str = "",
    highlight_en: str = "",
    similar: list[str] | None = None,
    website: str = "",
) -> KnowledgeEntry:
    data: KnowledgeEntry = {
        "group": group,
        "emoji": emoji,
        "short": _loc(short_ru, short_en),
        "long": _loc(long_ru, long_en),
    }
    if used_in_ru or used_in_en:
        data["used_in"] = _loc(used_in_ru, used_in_en)
    if highlight_ru or highlight_en:
        data["highlight"] = _loc(highlight_ru, highlight_en)
    if similar:
        data["similar"] = similar
    if website:
        data["website"] = website
    return data


KNOWLEDGE_BASE: dict[str, KnowledgeEntry] = {
    "Formula 1": _entry(
        group="series",
        emoji="🔴",
        short_ru="Высший класс мирового автоспорта. Примерно 24 этапа по всему миру.",
        short_en="The top tier of global motorsport. Around 24 rounds across the world.",
        long_ru="Formula 1 — вершина автоспорта с самыми быстрыми кольцевыми болидами, сложной аэродинамикой и крупнейшими заводскими командами.",
        long_en="Formula 1 is the pinnacle of motorsport with the fastest circuit cars, extreme aerodynamics, and the biggest factory teams.",
        used_in_ru="Главный экран, дайджесты, поиск, подписки по сериям.",
        used_in_en="Main screens, digests, search, and series subscriptions.",
        highlight_ru="Монако, Монца, Сузука, Сильверстоун",
        highlight_en="Monaco, Monza, Suzuka, Silverstone",
        similar=["Formula 2", "Formula 3", "IndyCar Series"],
        website="https://www.formula1.com",
    ),
    "Formula 2": _entry(
        group="series",
        emoji="🟠",
        short_ru="Главная молодёжная формульная серия под Формулой-1.",
        short_en="The main feeder single-seater series below Formula 1.",
        long_ru="Formula 2 использует единые шасси и моторы, поэтому большее влияние оказывают пилот и работа команды. Часто именно отсюда гонщики переходят в F1.",
        long_en="Formula 2 uses spec chassis and engines, so driver skill and team execution matter heavily. Many drivers step into F1 from here.",
        used_in_ru="Полезно, если в расписании видите уикенды поддержки F1.",
        used_in_en="Useful when you see F1 support races in the schedule.",
        similar=["Formula 1", "Formula 3", "Indy NXT"],
        website="https://www.fiaformula2.com",
    ),
    "Formula 3": _entry(
        group="series",
        emoji="🟡",
        short_ru="Ещё одна ступень на пути к Formula 2 и Formula 1.",
        short_en="Another development step on the path to Formula 2 and Formula 1.",
        long_ru="Formula 3 — международная молодёжная серия, где пилоты учатся работать с аэродинамикой, шинами и длинным чемпионатом.",
        long_en="Formula 3 is an international junior series where drivers learn aero management, tyre handling, and championship racing.",
        used_in_ru="Часто проходит вместе с Formula 1 и Formula 2.",
        used_in_en="Often runs on the same weekends as Formula 1 and Formula 2.",
        similar=["Formula 2", "Formula 4"],
        website="https://www.fiaformula3.com",
    ),
    "Formula 4": _entry(
        group="series",
        emoji="🧒",
        short_ru="Базовая ступень международных формульных гонок.",
        short_en="An entry-level step in international single-seater racing.",
        long_ru="Formula 4 — серия для юных пилотов, где они осваивают работу с открытыми колёсами, телеметрией и гоночным уикендом.",
        long_en="Formula 4 is a junior series where young drivers learn open-wheel racing, telemetry, and race weekend structure.",
        used_in_ru="Важна для понимания уикендов SMP F4 и поддержки крупных чемпионатов.",
        used_in_en="Useful for understanding SMP F4 weekends and support series events.",
        similar=["Formula 3", "SMP RSKG"],
    ),
    "IndyCar Series": _entry(
        group="series",
        emoji="🏎️",
        short_ru="Американские гонки открытых колёс: овалы, уличные трассы и стационарные кольца.",
        short_en="American open-wheel racing on ovals, street circuits, and road courses.",
        long_ru="IndyCar объединяет разные типы трасс в одном чемпионате. Главная гонка сезона — Indianapolis 500.",
        long_en="IndyCar combines multiple circuit types in one championship. The biggest race is the Indianapolis 500.",
        used_in_ru="Полезно, если хотите сравнить американские формулы с F1.",
        used_in_en="Useful if you want to compare American open-wheel racing with F1.",
        highlight_ru="Indianapolis 500, Long Beach GP",
        highlight_en="Indianapolis 500, Long Beach GP",
        similar=["Formula 1", "Indy NXT"],
        website="https://www.indycar.com",
    ),
    "Indy NXT": _entry(
        group="series",
        emoji="🟣",
        short_ru="Молодёжная серия под IndyCar.",
        short_en="The main feeder series below IndyCar.",
        long_ru="Indy NXT готовит пилотов к IndyCar: похожая среда, трассы и гоночные уикенды, но меньшая мощность и проще техника.",
        long_en="Indy NXT prepares drivers for IndyCar with similar circuits and weekend flow, but simpler and slower cars.",
        used_in_ru="Нужна, если следите за будущими пилотами IndyCar.",
        used_in_en="Useful if you follow future IndyCar talent.",
        similar=["IndyCar Series", "Formula 2"],
    ),
    "FIA World Endurance Championship": _entry(
        group="series",
        emoji="🏆",
        short_ru="Чемпионат мира по гонкам на выносливость с прототипами и GT.",
        short_en="The world endurance championship with prototypes and GT cars.",
        long_ru="WEC включает знаменитый Ле-Ман 24 часа и многоклассовые гонки, где одновременно выступают гиперкары и GT-экипажи.",
        long_en="WEC includes the famous 24 Hours of Le Mans and multi-class races where hypercars and GT crews compete together.",
        used_in_ru="Важен для понимания терминов Hypercar, LMH, LMDh и многоклассовых стартов.",
        used_in_en="Important for understanding Hypercar, LMH, LMDh, and multi-class racing.",
        highlight_ru="Le Mans 24h, Spa 6h, Fuji 6h",
        highlight_en="Le Mans 24h, Spa 6h, Fuji 6h",
        similar=["IMSA SportsCar Championship", "Asian Le Mans Series", "Hypercar"],
        website="https://www.fiawec.com",
    ),
    "IMSA SportsCar Championship": _entry(
        group="series",
        emoji="🇺🇸",
        short_ru="Американский многоклассовый чемпионат по гонкам на выносливость.",
        short_en="The leading American multi-class endurance championship.",
        long_ru="IMSA объединяет прототипы и GT-классы, а ключевые гонки сезона — Daytona 24h, Sebring 12h и Petit Le Mans.",
        long_en="IMSA combines prototypes and GT classes, with Daytona 24h, Sebring 12h, and Petit Le Mans as marquee events.",
        used_in_ru="Здесь часто встречаются термины GTP, GTD и GTD Pro.",
        used_in_en="This is where you often see GTP, GTD, and GTD Pro.",
        highlight_ru="Daytona 24h, Sebring 12h, Petit Le Mans",
        highlight_en="Daytona 24h, Sebring 12h, Petit Le Mans",
        similar=["FIA World Endurance Championship", "GTP", "GT3"],
        website="https://www.imsa.com",
    ),
    "Asian Le Mans Series": _entry(
        group="series",
        emoji="🌏",
        short_ru="Азиатский чемпионат на выносливость с прототипами и GT.",
        short_en="An Asian endurance series with prototypes and GT cars.",
        long_ru="Asian Le Mans Series короче по календарю, но устроен по тем же принципам многоклассовых гонок на выносливость.",
        long_en="The Asian Le Mans Series has a shorter calendar but follows the same multi-class endurance principles.",
        used_in_ru="Помогает понять международную лестницу endurance-чемпионатов.",
        used_in_en="Helpful for understanding the international endurance ladder.",
        similar=["FIA World Endurance Championship", "IMSA SportsCar Championship"],
        website="https://www.asianlemansseries.com",
    ),
    "GT World Challenge Europe": _entry(
        group="series",
        emoji="🏆",
        short_ru="Европейский GT3-чемпионат: спринты и эндуранс.",
        short_en="A European GT3 championship with sprint and endurance racing.",
        long_ru="GT World Challenge Europe — один из главных мировых GT3-турниров, где участвуют клиентские команды разных производителей.",
        long_en="GT World Challenge Europe is one of the main global GT3 championships, featuring customer teams from multiple manufacturers.",
        used_in_ru="Полезно для понимания того, что такое GT3 и endurance-формат.",
        used_in_en="Useful for understanding GT3 and endurance-style racing.",
        highlight_ru="24h Spa, Nürburgring, Monza",
        highlight_en="24h Spa, Nürburgring, Monza",
        similar=["DTM", "GT3", "Endurance Racing"],
        website="https://www.gt-world-challenge-europe.com",
    ),
    "DTM": _entry(
        group="series",
        emoji="🇩🇪",
        short_ru="Европейский чемпионат на GT3-технике с короткими гонками.",
        short_en="A European championship using GT3 machinery in shorter race formats.",
        long_ru="DTM исторически был туринговой серией, а сейчас использует GT3-регламент и ориентирован на спринтовый формат.",
        long_en="DTM was historically a touring championship and now runs GT3 regulations with a sprint-oriented format.",
        used_in_ru="Полезно, если встречаете GT3 и туринговые серии в одном интерфейсе.",
        used_in_en="Useful when you see GT3 and touring labels in the same interface.",
        similar=["GT World Challenge Europe", "GT3"],
        website="https://www.dtm.com",
    ),
    "Supercars Championship": _entry(
        group="series",
        emoji="🦘",
        short_ru="Главная австралийская кузовная серия. Bathurst 1000 — её культовая гонка.",
        short_en="Australia's premier touring-style series. Bathurst 1000 is its iconic event.",
        long_ru="Supercars — отдельный австралийский мир с мощными седанами, длинными гонками и очень плотной борьбой.",
        long_en="Supercars is a distinct Australian racing world with powerful sedans, long races, and very close competition.",
        used_in_ru="Хороший пример кузовных гонок вне Европы и США.",
        used_in_en="A good example of touring-style racing outside Europe and the US.",
        highlight_ru="Bathurst 1000, Adelaide, Sydney",
        highlight_en="Bathurst 1000, Adelaide, Sydney",
        similar=["Touring Cars", "TCR"],
        website="https://www.supercars.com.au",
    ),
    "NASCAR Cup Series": _entry(
        group="series",
        emoji="🏁",
        short_ru="Главная американская серия сток-каров с упором на овалы.",
        short_en="The top American stock car series focused mainly on oval racing.",
        long_ru="NASCAR Cup Series — это тяжёлые кузовные машины, плотный пелотон, рестарты и особая культура американских овалов.",
        long_en="The NASCAR Cup Series features heavy stock cars, pack racing, restarts, and a distinct American oval culture.",
        used_in_ru="Полезно для понимания термина Stock Cars и Oval Racing.",
        used_in_en="Useful for understanding Stock Cars and oval racing.",
        highlight_ru="Daytona 500, Coca-Cola 600",
        highlight_en="Daytona 500, Coca-Cola 600",
        similar=["Stock Cars", "Oval Racing", "IndyCar Series"],
        website="https://www.nascar.com",
    ),
    "FIA World Rally Championship": _entry(
        group="series",
        emoji="🚗",
        short_ru="Чемпионат мира по ралли на дорогах общего пользования и спецучастках.",
        short_en="The world championship for rally on roads and special stages.",
        long_ru="WRC отличается от кольцевых серий тем, что гонки проходят на спецучастках по одному экипажу, а покрытие может быть гравием, снегом или асфальтом.",
        long_en="WRC differs from circuit series because cars run individual special stages on gravel, snow, or asphalt rather than racing wheel-to-wheel on a track.",
        used_in_ru="Нужно для понимания разницы между Rally, Rallycross и circuit racing.",
        used_in_en="Useful for understanding the difference between Rally, Rallycross, and circuit racing.",
        highlight_ru="Monte Carlo, Finland, Safari Rally Kenya",
        highlight_en="Monte Carlo, Finland, Safari Rally Kenya",
        similar=["WRC2", "Rally", "Rallycross"],
        website="https://www.wrc.com",
    ),
    "MotoGP": _entry(
        group="series",
        emoji="🏍️",
        short_ru="Высший класс мотогонок на прототипах.",
        short_en="The highest level of prototype motorcycle racing.",
        long_ru="MotoGP — чемпионат мира для самых быстрых шоссейно-кольцевых мотоциклов, с сильным акцентом на электронику, резину и стиль пилотирования.",
        long_en="MotoGP is the world championship for the fastest prototype road-racing motorcycles, with heavy emphasis on electronics, tyres, and riding style.",
        used_in_ru="Важно, если в боте вы следите не только за автомобилями, но и за мотоциклами.",
        used_in_en="Important if you follow both cars and motorcycles in the bot.",
        highlight_ru="Mugello, Qatar, Assen",
        highlight_en="Mugello, Qatar, Assen",
        similar=["Moto2", "Moto3", "WorldSBK", "Motorcycles"],
        website="https://www.motogp.com",
    ),
    "Moto2": _entry(
        group="series",
        emoji="🏍️",
        short_ru="Средний класс чемпионата мира MotoGP.",
        short_en="The middle class in the MotoGP world championship ladder.",
        long_ru="Moto2 считается важным этапом подготовки к MotoGP: техника близка по логике, но проще и медленнее.",
        long_en="Moto2 is a key development step toward MotoGP with simpler but conceptually similar machinery.",
        used_in_ru="Полезно для понимания структуры мотогоночного уикенда.",
        used_in_en="Useful for understanding the MotoGP support race ladder.",
        similar=["MotoGP", "Moto3"],
    ),
    "Moto3": _entry(
        group="series",
        emoji="🏍️",
        short_ru="Начальная мировая серия в дорожном мотоспорте.",
        short_en="The entry-level world championship class in road racing.",
        long_ru="Moto3 — лёгкие мотоциклы и плотные пелотоны, часто с самыми драматичными финишами всего мотоуикенда.",
        long_en="Moto3 uses lightweight bikes and often produces the tightest packs and most dramatic finishes of the weekend.",
        used_in_ru="Помогает понять младшие мотоклассы, если они есть в расписании.",
        used_in_en="Helpful for understanding junior bike classes in the schedule.",
        similar=["Moto2", "MotoGP"],
    ),
    "WorldSBK": _entry(
        group="series",
        emoji="🏍️",
        short_ru="Чемпионат мира по супербайку на серийной основе.",
        short_en="The world superbike championship based on production motorcycles.",
        long_ru="В отличие от MotoGP, WorldSBK использует мотоциклы, более близкие к дорожным моделям, хотя и глубоко доработанные для гонок.",
        long_en="Unlike MotoGP, WorldSBK uses racing versions of bikes that are much closer to road-going production models.",
        used_in_ru="Полезно для понимания разницы между прототипами и серийной техникой в мотоспорте.",
        used_in_en="Useful for understanding the difference between prototypes and production-based bikes in motorcycle racing.",
        similar=["MotoGP", "Motorcycles"],
        website="https://www.worldsbk.com",
    ),
    "SMP RSKG": _entry(
        group="national",
        emoji="🏎️",
        short_ru="Главная российская серия кольцевых гонок с кузовными классами, GT4 и эндурансом.",
        short_en="Russia's main circuit racing series with touring classes, GT4, and endurance events.",
        long_ru="СМП РСКГ — российский национальный чемпионат, где в одном календаре могут соседствовать кузовные классы, GT4, спортпрототипы CN и отдельные эндуранс-старты.",
        long_en="SMP RSKG is the main Russian national circuit championship, combining touring classes, GT4, CN prototypes, and selected endurance events within one calendar.",
        used_in_ru="Используется в отдельном разделе РСКГ и в уведомлениях по этапам.",
        used_in_en="Used in the dedicated SMP RSKG section and round notifications.",
        highlight_ru="Moscow Raceway, Казань Ринг Каньон, Игора Драйв, Грозная",
        highlight_en="Moscow Raceway, Kazan Ring Canyon, Igora Drive, Groznaya",
        similar=["TCR", "GT4", "CN Prototypes", "Endurance Racing"],
        website="https://rskg.smpracing.ru",
    ),
    "GT3": _entry(
        group="classes",
        emoji="🏆",
        short_ru="Самый распространённый мировой GT-класс для клиентских команд.",
        short_en="The most widespread global GT class for customer racing teams.",
        long_ru="GT3 — быстрые купе и суперкары, построенные по единому балансу производительности. В этом классе гоняются Ferrari, Porsche, Mercedes-AMG, BMW, Lamborghini и другие.",
        long_en="GT3 features fast coupes and supercars balanced by performance rules. Brands include Ferrari, Porsche, Mercedes-AMG, BMW, Lamborghini, and more.",
        used_in_ru="Встречается в DTM, GT World Challenge, IMSA, спринтах и эндурансе.",
        used_in_en="Seen in DTM, GT World Challenge, IMSA, and both sprint and endurance racing.",
        similar=["GT4", "Touring Cars", "Endurance Racing"],
    ),
    "GT4": _entry(
        group="classes",
        emoji="🥈",
        short_ru="Более доступный и медленный класс GT по сравнению с GT3.",
        short_en="A more accessible and slower GT class compared with GT3.",
        long_ru="GT4 ближе к дорожным моделям, дешевле в эксплуатации и часто используется как вход в мир GT-гонок.",
        long_en="GT4 cars stay closer to road models, cost less to run, and often serve as an entry point into GT racing.",
        used_in_ru="Встречается в РСКГ, национальных GT-сериях и как поддержка крупных чемпионатов.",
        used_in_en="Seen in SMP RSKG, national GT series, and support events around larger championships.",
        similar=["GT3", "SMP RSKG"],
    ),
    "TCR": _entry(
        group="classes",
        emoji="🚙",
        short_ru="Мировой стандарт переднеприводных туринговых машин.",
        short_en="A global standard for front-wheel-drive touring cars.",
        long_ru="TCR — кузовные автомобили, построенные на базе серийных хэтчбеков и седанов. Класс популярен из-за плотной борьбы и понятной техники.",
        long_en="TCR uses production-based hatchbacks and sedans. The class is popular because of close racing and familiar-looking machinery.",
        used_in_ru="Часто встречается в РСКГ и международных туринговых сериях.",
        used_in_en="Frequently appears in SMP RSKG and international touring championships.",
        similar=["Touring Cars", "SMP RSKG"],
    ),
    "Hypercar": _entry(
        group="classes",
        emoji="🚀",
        short_ru="Главный прототипный класс современного WEC.",
        short_en="The top prototype class in the modern WEC.",
        long_ru="Hypercar — высший класс WEC, объединяющий машины по регламентам LMH и LMDh. Это самые престижные прототипы в мировом эндурансе.",
        long_en="Hypercar is the top class in WEC, combining LMH and LMDh machinery. These are the flagship prototypes of global endurance racing.",
        used_in_ru="Нужен для понимания гонок WEC и Ле-Мана.",
        used_in_en="Useful for understanding WEC and Le Mans.",
        similar=["LMH", "LMDh", "GTP", "LMP2"],
    ),
    "LMP2": _entry(
        group="classes",
        emoji="🔬",
        short_ru="Прототипный класс ниже Hypercar.",
        short_en="A prototype class below Hypercar.",
        long_ru="LMP2 использует единые или близкие по философии компоненты, поэтому акцент смещается на пилота, инженеров и работу экипажа.",
        long_en="LMP2 relies on spec-style components, so driver skill, engineering, and crew execution become especially important.",
        used_in_ru="Часто встречается в endurance-чемпионатах и Ле-Мане.",
        used_in_en="Common in endurance series and at Le Mans.",
        similar=["Hypercar", "CN Prototypes", "Endurance Racing"],
    ),
    "GTP": _entry(
        group="classes",
        emoji="🚀",
        short_ru="Высший класс IMSA для современных гибридных прототипов.",
        short_en="The top IMSA class for modern hybrid prototypes.",
        long_ru="GTP — американское обозначение для машин, близких по философии к WEC Hypercar/LMDh. Это главная техника в IMSA.",
        long_en="GTP is IMSA's top class for hybrid prototypes, closely related in concept to WEC Hypercar and LMDh machinery.",
        used_in_ru="Главный термин в IMSA-расписаниях и уведомлениях.",
        used_in_en="A key term in IMSA schedules and notifications.",
        similar=["Hypercar", "LMDh", "LMH"],
    ),
    "LMH": _entry(
        group="formats",
        emoji="⚙️",
        short_ru="Le Mans Hypercar — один из технических регламентов класса Hypercar.",
        short_en="Le Mans Hypercar, one of the technical regulations inside the Hypercar class.",
        long_ru="LMH позволяет производителям строить более уникальные машины для WEC и Ле-Мана. Это техническая формула, а не отдельный чемпионат.",
        long_en="LMH allows manufacturers to build more bespoke cars for WEC and Le Mans. It is a technical rule set, not a separate championship.",
        used_in_ru="Полезно, если видите обсуждение Toyota, Ferrari или Peugeot в WEC.",
        used_in_en="Useful when you see Toyota, Ferrari, or Peugeot discussed in WEC.",
        similar=["Hypercar", "LMDh"],
    ),
    "LMDh": _entry(
        group="formats",
        emoji="⚙️",
        short_ru="Le Mans Daytona h — технический регламент для Hypercar/GTP.",
        short_en="Le Mans Daytona h, a technical regulation used in Hypercar and GTP.",
        long_ru="LMDh использует стандартизированные элементы шасси и гибридной системы, чтобы производителям было проще входить в endurance-чемпионаты WEC и IMSA.",
        long_en="LMDh uses more standardised chassis and hybrid elements, making it easier for manufacturers to enter WEC and IMSA endurance racing.",
        used_in_ru="Часто встречается в новостях о Porsche, BMW, Cadillac, Acura и Alpine.",
        used_in_en="Frequently appears in coverage of Porsche, BMW, Cadillac, Acura, and Alpine.",
        similar=["Hypercar", "LMH", "GTP"],
    ),
    "CN Prototypes": _entry(
        group="classes",
        emoji="🔬",
        short_ru="Лёгкие спортпрототипы национального и клубного уровня.",
        short_en="Lightweight sports prototypes used in national and club-level racing.",
        long_ru="Прототипы CN меньше и проще топовых endurance-машин, но дают классическое ощущение прототипных гонок: малая масса, аэродинамика и высокая скорость в поворотах.",
        long_en="CN prototypes are smaller and simpler than top endurance machines but still deliver the classic prototype feel: low weight, aero, and high cornering speed.",
        used_in_ru="Встречаются в РСКГ и других локальных прототипных сериях.",
        used_in_en="Seen in SMP RSKG and other local prototype competitions.",
        similar=["LMP2", "SMP RSKG"],
    ),
    "Touring Cars": _entry(
        group="classes",
        emoji="🚙",
        short_ru="Кузовные машины, основанные на серийных моделях.",
        short_en="Closed-wheel race cars based on production road models.",
        long_ru="Туринговые классы обычно используют четырёхдверные или компактные кузова, узнаваемые силуэты и плотную контактную борьбу.",
        long_en="Touring classes usually use four-door or compact body styles, recognisable silhouettes, and very close racing.",
        used_in_ru="Полезно для понимания TCR, РСКГ и национальных кузовных чемпионатов.",
        used_in_en="Useful for understanding TCR, SMP RSKG, and national touring championships.",
        similar=["TCR", "Stock Cars"],
    ),
    "Single-Seaters": _entry(
        group="classes",
        emoji="🏎️",
        short_ru="Болиды с открытыми колёсами и одним местом для пилота.",
        short_en="Open-wheel cars with a single seat for the driver.",
        long_ru="К single-seaters относятся Formula 1, Formula 2, Formula 3, IndyCar и многие младшие формульные серии.",
        long_en="Single-seaters include Formula 1, Formula 2, Formula 3, IndyCar, and many junior formula categories.",
        used_in_ru="Нужно, чтобы понимать различие между формулами и кузовными сериями.",
        used_in_en="Useful for distinguishing formula racing from closed-wheel championships.",
        similar=["Formula 1", "Formula 2", "IndyCar Series"],
    ),
    "Stock Cars": _entry(
        group="classes",
        emoji="🏁",
        short_ru="Американский класс тяжёлых кузовных машин для овалов и спидвеев.",
        short_en="An American style of heavy closed-wheel cars built for ovals and speedways.",
        long_ru="Stock cars визуально напоминают серийные машины, но внутри это специальные гоночные конструкции, рассчитанные на контактную борьбу и длительные заезды.",
        long_en="Stock cars may resemble road cars visually, but underneath they are dedicated race machines built for contact-heavy, long-distance racing.",
        used_in_ru="Прежде всего встречаются в NASCAR.",
        used_in_en="Primarily associated with NASCAR.",
        similar=["NASCAR Cup Series", "Touring Cars", "Oval Racing"],
    ),
    "Motorcycles": _entry(
        group="classes",
        emoji="🏍️",
        short_ru="Мотогоночные дисциплины: от MotoGP до супербайка.",
        short_en="Motorcycle racing disciplines ranging from MotoGP to superbikes.",
        long_ru="Если в боте вы следите за двухколёсными сериями, важно понимать, что мотоциклы делятся на прототипы и производственные классы так же, как автомобили.",
        long_en="If you follow bike series in the bot, it helps to know that motorcycles also split into prototype and production-based categories, much like cars do.",
        used_in_ru="Общее пояснение для MotoGP, Moto2, Moto3 и WorldSBK.",
        used_in_en="A general explainer for MotoGP, Moto2, Moto3, and WorldSBK.",
        similar=["MotoGP", "Moto2", "Moto3", "WorldSBK"],
    ),
    "Endurance": _entry(
        group="classes",
        emoji="⏱️",
        short_ru="Класс или группа серий, связанных с длинными гонками на выносливость.",
        short_en="A class or family of series connected with long-distance endurance racing.",
        long_ru="Если в боте вы видите класс Endurance, обычно речь о гонках, где важны ресурс техники, стратегия, смены пилотов и стабильность на длинной дистанции.",
        long_en="If you see Endurance as a class in the bot, it usually points to racing where durability, strategy, driver changes, and long-run consistency matter most.",
        used_in_ru="Встречается в фильтрах классов и рядом с сериями WEC, IMSA и GT-эндуранса.",
        used_in_en="Seen in class filters and around WEC, IMSA, and GT endurance racing.",
        similar=["Endurance Racing", "Hypercar", "LMP2"],
    ),
    "Prototypes": _entry(
        group="classes",
        emoji="🔬",
        short_ru="Прототипы — это не дорожные машины, а специальные гоночные конструкции.",
        short_en="Prototypes are purpose-built race cars, not production road-based machines.",
        long_ru="Прототипные машины создаются только для гонок и обычно быстрее кузовных классов за счёт массы, аэродинамики и компоновки.",
        long_en="Prototype race cars are designed only for competition and are usually faster than GT or touring cars because of weight, aero, and packaging freedom.",
        used_in_ru="Полезно для понимания Hypercar, LMP2, GTP и CN.",
        used_in_en="Useful for understanding Hypercar, LMP2, GTP, and CN machinery.",
        similar=["Hypercar", "LMP2", "CN Prototypes"],
    ),
    "Electric": _entry(
        group="classes",
        emoji="⚡",
        short_ru="Электрические гоночные классы и серии.",
        short_en="Electric racing classes and series.",
        long_ru="Электрические гонки отличаются особенностями работы батареи, рекуперации, мощности на круге и энергетической стратегии.",
        long_en="Electric racing brings its own challenges around battery use, regeneration, power deployment, and energy strategy.",
        used_in_ru="Прежде всего встречается рядом с Formula E и другими электросериями.",
        used_in_en="Mostly appears around Formula E and other electric championships.",
        similar=["Formula E", "Single-Seaters"],
    ),
    "Endurance Racing": _entry(
        group="formats",
        emoji="⏱️",
        short_ru="Гонки на выносливость — это длинные заезды с несколькими пилотами и пит-стопами.",
        short_en="Endurance racing means long-distance events with multiple drivers and pit strategy.",
        long_ru="Главный акцент здесь не только на скорости круга, но и на ресурсе машины, стратегии, сменах пилотов и стабильности экипажа на длинной дистанции.",
        long_en="The focus is not only lap speed but also machine durability, strategy, driver changes, and crew consistency over a long distance.",
        used_in_ru="Помогает понимать WEC, IMSA, GT endurance и отдельные эндуранс-старты РСКГ.",
        used_in_en="Useful for WEC, IMSA, GT endurance, and dedicated SMP RSKG endurance events.",
        similar=["FIA World Endurance Championship", "IMSA SportsCar Championship", "Hypercar"],
    ),
    "Sprint Race": _entry(
        group="formats",
        emoji="💨",
        short_ru="Короткая гонка с акцентом на атаку с первых кругов.",
        short_en="A short race with emphasis on immediate attacking from the first laps.",
        long_ru="Спринты обычно короче обычных гонок, поэтому здесь меньше места для осторожной стратегии и больше для прямой борьбы.",
        long_en="Sprint races are shorter than standard feature events, so there is less room for conservative strategy and more for direct fighting.",
        used_in_ru="Встречается в F1, GT, РСКГ и других сериях как отдельный формат уикенда.",
        used_in_en="Seen in F1, GT, SMP RSKG, and other series as a distinct weekend format.",
        similar=["Endurance Racing"],
    ),
    "Qualifying": _entry(
        group="formats",
        emoji="🎯",
        short_ru="Сессия, где определяется стартовый порядок гонки.",
        short_en="The session used to decide the starting order for the race.",
        long_ru="Квалификация — это не гонка, а борьба за лучшее время круга. Именно отсюда берутся поул-позиция и стартовая решётка.",
        long_en="Qualifying is not the race itself but a fight for the fastest lap time. This is where pole position and the starting grid come from.",
        used_in_ru="В боте квалификации можно включать и выключать отдельно от гонок.",
        used_in_en="In the bot, qualifying sessions can be turned on or off separately from races.",
        similar=["Practice", "Sprint Race"],
    ),
    "Practice": _entry(
        group="formats",
        emoji="🛠️",
        short_ru="Тренировочная сессия перед квалификацией и гонкой.",
        short_en="A practice session before qualifying and the race.",
        long_ru="На практике команды подбирают настройки, проверяют шины и готовятся к более важным сессиям уикенда.",
        long_en="Practice is used to tune the car, evaluate tyres, and prepare for the more important sessions of the weekend.",
        used_in_ru="В боте практики можно скрывать или показывать отдельно.",
        used_in_en="In the bot, practice sessions can be shown or hidden separately.",
        similar=["Qualifying"],
    ),
    "Oval Racing": _entry(
        group="formats",
        emoji="🔄",
        short_ru="Гонки на овальных трассах с постоянной высокой скоростью.",
        short_en="Racing on oval circuits with sustained high speed.",
        long_ru="Овалы бывают короткими, средними и суперовалами. Здесь особенно важны аэродинамика в трафике, рестарты и работа в плотной группе машин.",
        long_en="Ovals come in short, intermediate, and superspeedway forms. Aerodynamics in traffic, restarts, and pack behaviour are especially important here.",
        used_in_ru="Ключевой термин для NASCAR и части календаря IndyCar.",
        used_in_en="A key term for NASCAR and part of the IndyCar calendar.",
        similar=["Stock Cars", "NASCAR Cup Series", "IndyCar Series"],
    ),
    "Rally": _entry(
        group="formats",
        emoji="🧭",
        short_ru="Гонки по спецучасткам вне обычных кольцевых трасс.",
        short_en="Racing on special stages away from conventional circuits.",
        long_ru="В ралли экипаж едет не рядом с соперниками колесо в колесо, а по одному, с штурманом и стенограммой.",
        long_en="In rally, crews do not race side by side on a circuit. They run one by one with a co-driver and pace notes.",
        used_in_ru="Помогает отличать WRC от кольцевых гонок в боте.",
        used_in_en="Useful for distinguishing WRC from circuit racing in the bot.",
        similar=["FIA World Rally Championship", "Rallycross"],
    ),
    "Rallycross": _entry(
        group="formats",
        emoji="🌧️",
        short_ru="Короткие контактные заезды на смешанном покрытии.",
        short_en="Short contact-heavy races on mixed surfaces.",
        long_ru="Rallycross сочетает асфальт и грунт на компактных трассах, а гонки проходят в плотной борьбе сразу нескольких машин.",
        long_en="Rallycross mixes asphalt and dirt on compact circuits, with several cars racing together in close combat.",
        used_in_ru="Нужно для понимания, чем rallycross отличается от классического rally.",
        used_in_en="Useful for understanding how rallycross differs from traditional rally.",
        similar=["Rally", "FIA World Rally Championship"],
    ),
}

SERIES_KB = KNOWLEDGE_BASE


def get_series_info(name: str) -> KnowledgeEntry | None:
    if name in KNOWLEDGE_BASE:
        return KNOWLEDGE_BASE[name]
    norm = _normalize(name)
    return next(
        (v for key, v in KNOWLEDGE_BASE.items() if _normalize(key) in norm or norm in _normalize(key)),
        None,
    )


def _text(value: str | LocalizedText | None, lang: str) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        lang = normalize_ui_lang(lang)
        return value.get(lang) or value.get(DEFAULT_UI_LANG) or next(iter(value.values()), "")
    return value


def format_card(name: str, info: KnowledgeEntry | None = None, lang: str = DEFAULT_UI_LANG) -> str:
    data = info or get_series_info(name) or {}
    lines = [f"{data.get('emoji', '🏁')} <b>{name}</b>"]
    if short_text := _text(data.get("short"), lang):
        lines.append(f"<i>{short_text}</i>")
    if long_text := _text(data.get("long"), lang):
        lines.append(f"\n{long_text}")
    if used_in := _text(data.get("used_in"), lang):
        lines.append(
            f"\n📍 <b>{'Where You Will See It' if lang == 'en' else 'Где это встречается'}:</b> {used_in}"
        )
    if highlight := _text(data.get("highlight"), lang):
        lines.append(
            f"\n🌟 <b>{'Key Examples' if lang == 'en' else 'Примеры и ориентиры'}:</b> {highlight}"
        )
    if similar := data.get("similar"):
        lines.append(
            f"{'🔗 <b>Related Topics:</b>' if lang == 'en' else '🔗 <b>Смотрите также:</b>'} {', '.join(similar)}"
        )
    if website := data.get("website"):
        lines.append(
            f"🌐 <a href='{website}'>{tr(lang, 'generic.official_website')}</a>"
        )
    return "\n".join(lines)
