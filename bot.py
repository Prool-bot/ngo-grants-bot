import os
import re
import json
import time
import hashlib
import feedparser
import requests
from bs4 import BeautifulSoup
from google import genai
from google.genai import types as genai_types

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
POSTED_LINKS_FILE = "posted_links.txt"
POSTED_TITLES_FILE = "posted_titles.txt"

# ---------------------------------------------------------------------------
# ДЖЕРЕЛА
# ---------------------------------------------------------------------------
CHASZMIN_RSS  = "https://chaszmin.com.ua/category/granty-tut/feed/"
GURT_RSS      = "https://gurt.org.ua/rss/section/grants/"
PROSTIR_RSS   = "https://www.prostir.ua/?feed=rss2&post_type=grants"
GETGRANT_RSS  = "https://getgrant.ua/grants-and-funding/?feed=rss2"
ISAR_URL      = "https://ednannia.ua/181-contests"
IRF_URL       = "https://www.irf.ua/grants/contests/"
UCF_URL       = "https://ucf.in.ua/programs"
VF_RSS        = "https://veteranfund.com.ua/contests/feed/"
VF_COMPETITIONS = "https://veteranfund.com.ua/competitions/"
UMF_RSS       = "https://uyf.gov.ua/rss/"
UMF_NEWS_URL  = "https://uyf.gov.ua/news"

TG_CHANNELS = [
    ("grantsua",        "Гранти UA"),
    ("grantovyphishky", "Грантові фішки"),
    ("houseofeurope",   "House of Europe"),
    ("grants_here",     "Гранти та можливості"),  # 20K+ підписників, Connection Agency
    ("GrantUP",          "GrantUP"),               # є гранти, але і мікс-контент — фільтруємо
]

# ---------------------------------------------------------------------------
# ФІЛЬТРИ
# ---------------------------------------------------------------------------
EXCLUDE_KEYWORDS = [
    "тендер", "закупівл", "запит цінових пропозицій", "зцп", "rfq", "rfp",
    "rfi", "itb", "цінової пропозиції", "тендерн", "постачання", "поставк",
    "цінову пропозицію", "цінові пропозиції", "цінових пропозицій",
    "конкурсні торги", "разовий договір", "разового договору",
    "постачальник", "оцінка цінових пропозицій",
    "місцева закупівля", "procurement", "запрошує подати пропозиц",
    "запрошує надати пропозиц", "надати цінову пропозиц",
    "запрошує кваліфікованих виконавц", "запрошує постачальник",
    "надання тренерських послуг", "надання консультаційних послуг",
    "надання послуг з проведення", "надання послуг тренера",
    "відбір тренер", "відбір фасилітатор", "відбір консультант",
    "конкурс на надання послуг", "конкурсний відбір тренер",
    "конкурсний відбір консультант", "конкурсний відбір постачальник",
    "запрошення організацій до подання зацікавлень",
    "запрошення до подання зацікавлень",
    "запрошення до висловлення зацікавленост",
    "подання зацікавлень", "висловлення зацікавленост",
    "expression of interest", "request for expression",
    "reoi", "eoi ",
    "пакет закупівель", "запит пропозицій",
    "уфсі", "уфсі/фонд",
    "послуги страхування", "каско", "добровільного страхування",
    "страхування автомобіл", "страхування транспортн",
    "договір про виконавче партнерство",
    "виконавче партнерство між го",
    "реалізує проєктний захід",
    "пошук експерта", "пошук експертки", "пошук експерт",
    "запрошує експерта", "запрошує консультант",
    "набір консультант", "набір тренер",
    "вакансія", "вакансії", "job opening", "position available",
    "спеціаліст/ка", "спеціаліста/ки", "фахівець/фахівчиня",
    "invites you to submit services", "submit services of",
    "надання послуг соціального", "послуги соціального",
    "реєстрація на отримання", "запис на отримання",
    "цільова благодійна допомога",
    "правова підтримка для", "юридична підтримка для",
    "коротко про бф", "коротко про го", "коротко про нго",
    "про діяльність фонду", "хто ми є",
    # тендери на розробку/послуги
    "оновлення вебсайту", "розробку вебсайту", "розробку сайту",
    "оголошує запит на подання пропозицій",
    "запрошує кандидатів надсилати пропозиції щодо виконання",
    "будівельно ремонтних робіт", "будівельно-ремонтних робіт",
    "комерційних пропозицій на комплексну", "збір комерційних пропозицій",
    "запиту комерційних пропозицій", "відкриття запиту комерційних",
    "послуг водія", "послуги водія", "водія подобово",
    "цивільно-правовою угодою", "цивільно-правова угода", "цпх",
    "технічного завдання (тз)", "технічне завдання тз",
    "технічні специфікації робіт",
    # відбір консультантів/фасилітаторів
    "шукаємо зовнішнього консультанта", "шукаємо фасилітатора",
    "зовнішнього консультанта з розробки стратегії",
    # вакансії у форматі запрошення до команди
    "запрошує приєднатися до команди", "запрошує приєднатись до команди",
    "приєднатися до команди", "приєднатись до команди",
    "до команди головного", "до команди бухгалтер",
    "добірка актуальних вакансій", "добірка вакансій",
    # відбір фахівців/експертів/рецензентів
    "відбір фахівців", "відбір незалежних експертів",
    "відбір рецензентів", "відбір експертів",
    "для залучення у проєкти", "для залучення в проєкти",
    # аналітичні/освітні пости з Telegram-каналів
    "плануєш відкрити бізнес", "думаєш переважно про",
    "є два варіанти", "продати бізнес як працюючу систему",
    "appeared first on getgrant",
    "getgrant отримав", "getgrant service отримав",
    "summit grant fest", "мав честь бути запрошеним",
    "анатомія робочих пакетів", "грантова звітність у horizon",
    "living guidelines", "як керувати deliverables",
    "як писати грантову", "помилки у грантових",
    "чому відхиляють", "секрети успішної заявки",
    "national system",
]

EXCLUDE_ORGANIZATIONS = ["конвіктус україна"]

GETGRANT_ANALYTICS_MARKERS = [
    "як отримати", "як подати заявку", "як написати", "як керувати",
    "покрокова інструкція", "практичний гід", "що потрібно знати",
    "топ-", "рейтинг ", "огляд грантів", "аналіз грантів",
    "підсумки ", "результати конкурсу", "переможці конкурсу",
    "history of", "анатомія ", "секрети ", "помилки ",
    "зміни у правилах", "нові вимоги до",
    "mon запускає", "мон запускає", "нан україни оголошує",
]

TG_JUNK_MARKERS = [
    "замовити консультацію", "мій курс", "мої курси",
    "придбати курс", "навчання у мене", "записатись до мене",
    "підписатись на інстаграм", "підписуйтесь на інстаграм",
    "написати нам",
    "запит цінових пропозицій", "тендер на закупівлю",
    # вакансії у Telegram-каналах
    "добірка актуальних вакансій", "добірка вакансій",
    "приєднатися до команди", "приєднатись до команди",
    # відбір експертів/рецензентів
    "відбір незалежних експертів", "відбір рецензентів",
    "відбір фахівців",
    # аналітичні пости не про гранти
    "плануєш відкрити бізнес",
    # @GrantUP специфічний нерелевантний контент
    "підтримайте нашу роботу підпискою", "підтримайте нашу роботу",
    "причиною більшої поширеності", "хвороби паркінсона",
    "стала відомою після відео", "аналітикиня ",
    "центру досліджень східної",
    "розповідаємо, чому", "дякуємо, клар",
    # @GrantUP новини про держфінансування, вікіпедію і патріотичний контент
    "у вікіджерелах", "у вікіпедії", "вікімандри", "вікіджерела",
    "вичитуючи твори", "опрацюванню творів",
    "визначено перелік",
    # патріотичні/новинні пости (не гранти)
    "коли україну накриває", "тримають лінію фронту",
    "дякуємо кожному, хто тримає фронт",
    "українські військові вміють", "у польових умовах",
    "хвиля спеки", "дрон, який створює",
    "стала відомою після", "запалила команду",
    "підтримайте нашу роботу", "визначено список",
    "отримають державне фінансування", "отримають держфінансування",
    "виділено ", "виділено млрд", "виділено млн",
    "усі новини освіти і науки",
    # @grantovyphishky особисті пости та звіти (не оголошення конкурсів)
    "хочу нарешті поділитися", "хочу поділитися, як пройшов",
    "як пройшов мій", "мій дводенний практикум",
    "відгуки учасників були", "мої коментарі й",
    # @grantovyphishky аналітика про грантодавців (не оголошення конкурсів)
    "аналіз грантодавця:", "аналіз грантодавця ",
    "розібрали структуру фонду", "у статті getgrant",
    # @houseofeurope репортажі про завершені гранти (не нові конкурси)
    "іменем вмираючого народу", "запалила команду",
    "набрав 800 тисяч переглядів", "розповіла нам, як",
]


# ---------------------------------------------------------------------------
# ХЕШТЕГИ — автоматична категоризація грантів
# ---------------------------------------------------------------------------

HASHTAG_RULES = [
    ("#ветерани",   ["ветеран", "ветеранськ", "варто+", "military", "veteran", "впо", "внутрішньо переміщен"]),
    ("#молодь",     ["молодь", "молодіж", "студент", "youth", "young", "підліток", "школяр"]),
    ("#культура",   ["культур", "мистецтв", "митц", "кіно", "театр", "музик", "літератур", "heritage",
                     "creative", "арт", "художн", "architecture", "design", "film"]),
    ("#медіа",      ["медіа", "журналіст", "ЗМІ", "преса", "видання", "мовлен", "редакц", "journalism",
                     "media", "broadcasting", "documentary"]),
    ("#наука",      ["наук", "дослідж", "університет", "академі", "research", "science", "phd",
                     "стипенді", "fellowship", "аспірант"]),
    ("#бізнес",     ["бізнес", "підприємц", "МСБ", "МСП", "стартап", "startup", "business",
                     "підприємств", "фермер", "агро", "виробництв"]),
    ("#ГО",         ["громадськ організац", "нго", "нко", "го ", " го,", "civil society",
                     "некомерційн", "благодійн", "фонд підтримки"]),
    ("#відновлення",["відновлен", "reconstruction", "rebuild", "громад", "реінтеграц", "деокупац"]),
    ("#освіта",     ["освіт", "навчальн", "школ", "коледж", "education", "training", "викладач"]),
    ("#екологія",   ["еколог", "довкілл", "environment", "зелен", "клімат", "climate", "energy",
                     "енергоефектив", "відновлювальн"]),
]


def generate_hashtags(title: str, description: str) -> str:
    """Визначає категорії гранту і повертає рядок хештегів (максимум 3)."""
    combined = (title + " " + description).lower()
    matched = []
    for hashtag, keywords in HASHTAG_RULES:
        if any(kw.lower() in combined for kw in keywords):
            matched.append(hashtag)
        if len(matched) >= 3:
            break
    return " ".join(matched) if matched else ""


def is_excluded(text: str) -> bool:
    t = text.lower()
    return (
        any(kw in t for kw in EXCLUDE_KEYWORDS)
        or any(org in t for org in EXCLUDE_ORGANIZATIONS)
    )


def is_getgrant_analytics(title: str, description: str) -> bool:
    combined = (title + " " + description).lower()
    return any(m in combined for m in GETGRANT_ANALYTICS_MARKERS)


def is_tg_junk(text: str) -> bool:
    t = text.lower()
    return any(m in t for m in TG_JUNK_MARKERS) or is_excluded(text)


# ---------------------------------------------------------------------------
# ТРЕКІНГ
# ---------------------------------------------------------------------------

def load_posted_links() -> set:
    try:
        with open(POSTED_LINKS_FILE, "r", encoding="utf-8") as f:
            return set(f.read().splitlines())
    except FileNotFoundError:
        return set()


def save_posted_link(link: str) -> None:
    with open(POSTED_LINKS_FILE, "a", encoding="utf-8") as f:
        f.write(link + "\n")


def load_posted_titles() -> set:
    try:
        with open(POSTED_TITLES_FILE, "r", encoding="utf-8") as f:
            return set(f.read().splitlines())
    except FileNotFoundError:
        return set()


def title_hash(title: str) -> str:
    normalized = re.sub(r"\s+", " ", title.strip().lower())[:80]
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()


def is_title_duplicate(title: str, posted_titles: set) -> bool:
    return title_hash(title) in posted_titles


def save_title_hash(title: str, posted_titles: set, posted_keywords: list) -> None:
    h = title_hash(title)
    if h not in posted_titles:
        posted_titles.add(h)
        with open(POSTED_TITLES_FILE, "a", encoding="utf-8") as f:
            f.write(h + "\n")
    save_keyword_set(title, posted_keywords)


# ---------------------------------------------------------------------------
# TELEGRAM
# ---------------------------------------------------------------------------

POSTED_KEYWORDS_FILE = "posted_keywords.txt"


def extract_key_words(title: str) -> frozenset:
    STOP_WORDS = {
        "грант", "гранти", "грантів", "грантовий", "грантова", "грантове",
        "конкурс", "конкурси", "конкурсу", "конкурсний",
        "програма", "програми", "програму", "проєкт", "проєкти",
        "для", "на", "та", "і", "й", "від", "до", "з", "із", "по",
        "що", "як", "або", "чи", "the", "and", "for", "with",
        "підтримка", "підтримки", "фінансування", "можливість",
        "оголошує", "оголошення", "запрошує",
        "ukraine", "україна", "україни", "українських", "українські",
    }
    t = title.lower()
    t = "".join(c if (c.isalnum() or c == " ") else " " for c in t)
    words = t.split()
    return frozenset(w for w in words if w not in STOP_WORDS and len(w) > 3)


def load_posted_keywords() -> list:
    try:
        with open(POSTED_KEYWORDS_FILE, "r", encoding="utf-8") as f:
            result = []
            for line in f:
                line = line.strip()
                if line:
                    result.append(frozenset(line.split("|")))
            return result
    except FileNotFoundError:
        return []


def save_keyword_set(title: str, posted_keywords: list) -> None:
    kw = extract_key_words(title)
    if kw:
        posted_keywords.append(kw)
        with open(POSTED_KEYWORDS_FILE, "a", encoding="utf-8") as f:
            f.write("|".join(sorted(kw)) + "\n")


def is_semantic_duplicate(title: str, posted_keywords: list, threshold: int = 2) -> bool:
    kw = extract_key_words(title)
    if len(kw) < 2:
        return False
    for existing_kw in posted_keywords:
        common = kw & existing_kw
        if len(common) >= threshold:
            return True
    return False


def send_telegram_message(message: str) -> requests.Response:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    return requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    })


# ---------------------------------------------------------------------------
# AI-ПЕРЕФОРМАТУВАННЯ (Gemini)
# ---------------------------------------------------------------------------

AI_SYSTEM_PROMPT = """Ти редактор Telegram-каналу про гранти для українських НГО.
Розбери пост на структуровані секції за схемою нижче. Правила:
- Прибери рекламні хвости, заклики підписатись на джерело, зайвий емодзі-спам
- Заповнюй лише ті поля, для яких є дані в оригінальному тексті — інакше null.
  НІКОЛИ не вигадуй і не додумуй факти
- Списки (funding, audience, supported, evaluation_criteria,
  application_requirements) — короткі пункти без початкового "•", без крапки в кінці
- extra_links — тільки URL, які буквально присутні в оригінальному тексті
  (наприклад окрема сторінка з умовами, форма подання, критерії відбору),
  НЕ включай туди основне посилання на джерело — воно додається окремо
- intro — 1-2 речення контексту (хто дає грант, на що), без дублювання title
- Стиль: стисло, по суті, українською, без markdown-розмітки (без **, ##,```)"""

AI_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "intro": {"type": "string", "nullable": True},
        "deadline": {"type": "string", "nullable": True},
        "geography": {"type": "string", "nullable": True},
        "funding": {"type": "array", "items": {"type": "string"}, "nullable": True},
        "audience": {"type": "array", "items": {"type": "string"}, "nullable": True},
        "audience_excluded": {"type": "string", "nullable": True},
        "supported": {"type": "array", "items": {"type": "string"}, "nullable": True},
        "evaluation_criteria": {"type": "array", "items": {"type": "string"}, "nullable": True},
        "application_requirements": {"type": "array", "items": {"type": "string"}, "nullable": True},
        "decision_date": {"type": "string", "nullable": True},
        "notes": {"type": "string", "nullable": True},
        "extra_links": {
            "type": "array",
            "nullable": True,
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "url": {"type": "string"},
                },
                "required": ["label", "url"],
            },
        },
    },
    "required": ["title", "intro"],
}

_ai_client = None

def _get_ai_client():
    global _ai_client
    if _ai_client is None:
        _ai_client = genai.Client(api_key=GEMINI_API_KEY)
    return _ai_client

def reformat_post(raw_text: str, source: str) -> dict:
    """Переформатовує пост через Gemini. При будь-якій помилці — fallback
    на плоский варіант (тільки intro = оригінальний текст), щоб пост усе
    одно опублікувався, нехай і без розбивки на секції."""
    fallback = {"title": None, "intro": raw_text, "deadline": None,
                "geography": None, "funding": None, "audience": None,
                "audience_excluded": None, "supported": None,
                "evaluation_criteria": None, "application_requirements": None,
                "decision_date": None, "notes": None, "extra_links": None}
    if not GEMINI_API_KEY:
        return fallback
    try:
        client = _get_ai_client()
        resp = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=f"Оригінальний пост (джерело: {source}):\n---\n{raw_text}\n---",
            config=genai_types.GenerateContentConfig(
                system_instruction=AI_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=AI_RESPONSE_SCHEMA,
            ),
        )
        data = json.loads(resp.text)
        fallback.update({k: v for k, v in data.items() if v is not None})
        return fallback
    except Exception as e:
        print(f"[AI reformat failed] {source}: {e}")
        return fallback

def _bullets(items) -> str:
    return "\n".join(f"• {it}" for it in items) if items else ""

class _SkippedDuplicate:
    """Легкий сурогат requests.Response для випадку, коли пост відсіявся
    на stage 2 (дублікат після AI-нормалізації). status_code=200 навмисно —
    виклики-джерела й далі роблять save_posted_link(link) і не намагаються
    обробити цей URL повторно на наступному прогоні cron."""
    status_code = 200
    text = "skipped: duplicate after AI normalization"


def build_and_send(emoji: str, title: str, link: str, description: str,
                    source_label: str, posted_titles: set, posted_keywords: list,
                    deadline_hint: str = "") -> requests.Response:
    """Єдина точка виходу: AI-розбір на секції → stage-2 дедуп на
    нормалізованому заголовку → збірка HTML-повідомлення → надсилання.
    Довгі секції (notes, критерії, вимоги) відкидаються першими, якщо
    повідомлення не влазить у ліміт Telegram (4096 симв.)."""
    ai = reformat_post(f"{title}\n\n{description}", source_label)
    final_title = ai.get("title") or title
    deadline = ai.get("deadline") or deadline_hint

    # Stage 2: дедуп на AI-нормалізованому заголовку — спільний пул для
    # всіх джерел, ловить той самий грант із різних сайтів/каналів,
    # навіть якщо їхні сирі заголовки сформульовані по-різному.
    if is_title_duplicate(final_title, posted_titles) or is_semantic_duplicate(final_title, posted_keywords):
        print(f"[{source_label}] Skipped (дубль після AI-нормалізації): {final_title[:60]}")
        return _SkippedDuplicate()

    header = f"{emoji} <b>{final_title}</b>"

    meta = []
    if deadline:
        meta.append(f"📅 <b>Дедлайн:</b> {deadline}")
    if ai.get("geography"):
        meta.append(f"🌍 <b>Географія:</b> {ai['geography']}")

    # (пріоритет, текст секції) — пріоритет 1 = найважливіше, викидається останнім
    sections = []
    if ai.get("intro"):
        sections.append((1, ai["intro"]))
    if meta:
        sections.append((1, "\n".join(meta)))
    if ai.get("funding"):
        sections.append((2, "💰 <b>Фінансування:</b>\n" + _bullets(ai["funding"])))
    if ai.get("audience"):
        block = "👥 <b>Хто може податися:</b>\n" + _bullets(ai["audience"])
        if ai.get("audience_excluded"):
            block += f"\n{ai['audience_excluded']}"
        sections.append((2, block))
    if ai.get("supported"):
        sections.append((3, "💡 <b>Що підтримується:</b>\n" + _bullets(ai["supported"])))
    if ai.get("decision_date"):
        sections.append((3, f"📆 <b>Рішення про фінансування:</b> {ai['decision_date']}"))
    if ai.get("evaluation_criteria"):
        sections.append((4, "🔬 <b>Оцінюватимуть:</b>\n" + _bullets(ai["evaluation_criteria"])))
    if ai.get("application_requirements"):
        sections.append((4, "📝 <b>У заявці потрібно надати:</b>\n" + _bullets(ai["application_requirements"])))
    if ai.get("notes"):
        sections.append((5, ai["notes"]))

    links_block = f"🔗 <a href=\"{link}\">{source_label}</a>"
    for l in (ai.get("extra_links") or []):
        url, label = l.get("url"), l.get("label")
        if url and label:
            links_block += f"\n🔗 <a href=\"{url}\">{label}</a>"

    body_for_hashtags = " ".join(
        [ai.get("intro") or ""] + (ai.get("funding") or []) + (ai.get("supported") or [])
    )
    hashtags = generate_hashtags(final_title, body_for_hashtags)

    reserved = len(header) + len(links_block) + (len(hashtags) + 4 if hashtags else 0) + 20
    budget = 4000 - reserved  # запас нижче ліміту Telegram у 4096

    kept, used = [], 0
    for _, text in sorted(sections, key=lambda s: s[0]):
        if used + len(text) + 2 <= budget:
            kept.append(text)
            used += len(text) + 2

    parts = [header] + kept + [links_block]
    if hashtags:
        parts.append(hashtags)
    msg = "\n\n".join(parts)

    resp = send_telegram_message(msg)
    print(resp.text)
    if resp.status_code == 200:
        save_title_hash(final_title, posted_titles, posted_keywords)
    return resp


# ---------------------------------------------------------------------------
# УТИЛІТИ
# ---------------------------------------------------------------------------

def collect_paragraphs(container, min_len: int = 80, exclude: list = None,
                        cap: int = 3000) -> str:
    """Збирає текст УСІХ <p> контейнера (а не лише першого), щоб AI бачив
    повний опис гранту (умови, аудиторію, критерії), а не один абзац."""
    exclude = exclude or []
    chunks, total = [], 0
    for p in container.find_all("p"):
        t = p.get_text(" ", strip=True)
        if len(t) < min_len or any(ex in t.lower() for ex in exclude):
            continue
        chunks.append(t)
        total += len(t)
        if total >= cap:
            break
    return " ".join(chunks)[:cap]


def fetch_html(url: str, timeout: int = 60, retries: int = 2):
    import warnings
    try:
        from bs4 import XMLParsedAsHTMLWarning
        warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
    except ImportError:
        pass
    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=timeout,
                                headers={"User-Agent": "Mozilla/5.0 ngo-grants-bot/1.0"})
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "html.parser")
        except Exception as e:
            if attempt < retries - 1:
                print(f"[fetch_html] Retry {attempt+1} for {url}: {e}")
                time.sleep(5)
            else:
                print(f"[fetch_html] ERROR {url}: {e}")
                return None


DEADLINE_PATTERNS = [
    r"[Дд]едлайн[а-яіїєʼ'\s:]*[:\s]+([^.\n]{3,80})",
    r"[Кк]інцевий термін[а-яіїєʼ'\s]*[:\s]+([^.\n]{3,80})",
    r"[Тт]ермін подачі[а-яіїєʼ'\s]*[:\s]+([^.\n]{3,80})",
    r"[Тт]ермін подання[а-яіїєʼ'\s]*[:\s]+([^.\n]{3,80})",
]

UKRAINIAN_MONTHS = {
    "січня": 1, "лютого": 2, "березня": 3, "квітня": 4,
    "травня": 5, "червня": 6, "липня": 7, "серпня": 8,
    "вересня": 9, "жовтня": 10, "листопада": 11, "грудня": 12,
    "січень": 1, "лютий": 2, "березень": 3, "квітень": 4,
    "травень": 5, "червень": 6, "липень": 7, "серпень": 8,
    "вересень": 9, "жовтень": 10, "листопад": 11, "грудень": 12,
}


def extract_deadline(text: str) -> str:
    for pattern in DEADLINE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip().rstrip(".,;")
    return ""


def is_deadline_passed(deadline_str: str) -> bool:
    from datetime import date
    today = date.today()
    text = deadline_str.strip().lower()
    match = re.search(
        r"(\d{1,2})\s+(" + "|".join(UKRAINIAN_MONTHS.keys()) + r")\s+(\d{4})", text)
    if match:
        try:
            return date(int(match.group(3)),
                        UKRAINIAN_MONTHS[match.group(2)],
                        int(match.group(1))) < today
        except ValueError:
            pass
    match = re.search(r"(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})", text)
    if match:
        try:
            return date(int(match.group(3)),
                        int(match.group(2)),
                        int(match.group(1))) < today
        except ValueError:
            pass
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if match:
        try:
            return date(int(match.group(1)),
                        int(match.group(2)),
                        int(match.group(3))) < today
        except ValueError:
            pass
    return False


def clean_html_description(raw_html: str) -> str:
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


DIGEST_SPLIT_PATTERN = re.compile(r"\s*>{2,}\s*|\s*›{2,}\s*")


def split_digest_into_items(description: str) -> list:
    parts = DIGEST_SPLIT_PATTERN.split(description)
    items = [p.strip() for p in parts if p.strip()]
    return items if items else [description.strip()]


def make_item_title(item_text: str, fallback_title: str, max_len: int = 90) -> str:
    first_sentence = re.split(r"(?<=[.!?])\s+", item_text.strip())[0].strip()
    if not first_sentence:
        return fallback_title
    return first_sentence[:max_len].rstrip() + ("..." if len(first_sentence) > max_len else "")


def build_simple_message(item_title: str, link: str, description: str,
                         source_label: str) -> str:
    deadline = extract_deadline(description)
    summary = description[:600] + "..." if len(description) > 600 else description
    msg = f"📌 <b>{item_title}</b>\n"
    if deadline:
        msg += f"📅 <b>Дедлайн:</b> {deadline}\n"
    msg += f"\n{summary}\n\n🔗 <a href=\"{link}\">{source_label}</a>\n"
    hashtags = generate_hashtags(item_title, description)
    if hashtags:
        msg += f"\n{hashtags}"
    return msg


# ---------------------------------------------------------------------------
# CHASZMIN
# ---------------------------------------------------------------------------

JUNK_MARKERS = [
    "ПІДРУЧНИК", "ПОСІБНИК", "ПОРАДНИК", "КАТАЛОГ ФОНДІВ",
    "ШКОЛА ГРАНТОЗНАВСТВА", "Подати заявку ТУТ", "HOW TO GET",
    "Можливо, ви захочете", "Замовити оформлення",
    "Ми допомагаємо в оформленні",
]


def is_junk(sentence: str) -> bool:
    return any(m.lower() in sentence.lower() for m in JUNK_MARKERS)


def process_chaszmin_entry(title: str, link: str) -> str:
    page = requests.get(link, timeout=30)
    soup = BeautifulSoup(page.text, "html.parser")
    article = soup.find("article")
    text = article.get_text(" ", strip=True) if article else soup.get_text(" ", strip=True)

    deadline = "не зазначено"
    m = re.search(r"ДЕДЛАЙН:\s*(.*?)\s*(ДЕ:|ГАЛУЗІ:)", text, re.IGNORECASE)
    if m:
        deadline = m.group(1).strip()

    location = "не зазначено"
    m = re.search(r"ДЕ:\s*(.*?)\s*ГАЛУЗІ:", text, re.IGNORECASE)
    if m:
        location = m.group(1).strip()

    sectors = "не зазначено"
    m = re.search(r"ГАЛУЗІ:\s*(.*?)(Ми допомагаємо|Сума|Для кого|$)", text, re.IGNORECASE)
    if m:
        sectors = m.group(1).strip()

    target = ""
    m = re.search(
        r"Для кого[:\s]*(.*?)(До участі допускаються|Сума|Дедлайн[:\s]|$)",
        text, re.IGNORECASE)
    if m:
        raw = m.group(1).strip()
        sentences = re.split(r"(?<=[.!?])\s+", raw)
        clean = []
        for s in sentences:
            s = s.strip()
            if not s:
                continue
            if is_junk(s):
                break
            clean.append(s)
        target = " ".join(clean).strip()
        if len(target) > 400:
            target = target[:400] + "..."

    search_zone = text
    fk = re.search(r"Для кого", search_zone, re.IGNORECASE)
    fk_pos = fk.start() if fk else len(search_zone)
    last_cut = 0
    head = search_zone[:fk_pos]
    for marker in [r"Замовити оформлення грантової заявки", r"Подати заявку ТУТ"]:
        ms = list(re.finditer(marker, head, re.IGNORECASE))
        if ms:
            last_cut = max(last_cut, ms[-1].end())
    search_zone = search_zone[last_cut:fk_pos]

    summary = ""
    for p in re.split(r"(?<=[.!?])\s+", search_zone):
        p = p.strip()
        if len(p) < 80 or is_junk(p):
            continue
        summary = p
        break
    if not summary:
        summary = title
    if len(summary) > 800:
        summary = summary[:800] + "..."

    msg = f"\n🌍 <b>{title}</b>\n📅 <b>Дедлайн:</b> {deadline}\n🌍 <b>Де:</b> {location}\n🎯 <b>Галузі:</b> {sectors}\n"
    if target:
        msg += f"\n👥 <b>Для кого:</b>\n{target}\n"
    msg += f"\n💡 <b>Деталі:</b>\n{summary}\n🔗 <a href=\"{link}\">Деталі гранту</a>\n"
    return msg


def run_chaszmin(posted_links: set, posted_titles: set, posted_keywords: list) -> None:
    feed = feedparser.parse(CHASZMIN_RSS)
    if not feed.entries:
        print("[chaszmin] No entries")
        return
    for entry in reversed(feed.entries[:10]):
        title = entry.title.strip()
        link = entry.link
        if link in posted_links:
            continue
        if is_excluded(title):
            print(f"[chaszmin] Skipped: {title}")
            save_posted_link(link)
            posted_links.add(link)
            continue
        # Chaszmin не проходить через AI-переформат (свій регекс-парсинг),
        # тож stage 2 тут звіряється просто на власному заголовку джерела.
        if is_title_duplicate(title, posted_titles) or is_semantic_duplicate(title, posted_keywords):
            print(f"[chaszmin] Skipped (дубль з іншого джерела): {title[:60]}")
            save_posted_link(link)
            posted_links.add(link)
            continue
        print(f"[chaszmin] Processing: {title}")
        try:
            msg = process_chaszmin_entry(title, link)
            resp = send_telegram_message(msg)
            print(resp.text)
            if resp.status_code == 200:
                save_posted_link(link)
                posted_links.add(link)
                save_title_hash(title, posted_titles, posted_keywords)
        except Exception as e:
            print(f"[chaszmin] ERROR {link}: {e}")


# ---------------------------------------------------------------------------
# RSS ДЖЕРЕЛА (GURT / PROSTIR / GETGRANT)
# ---------------------------------------------------------------------------

def run_simple_source(rss_url: str, source_label: str, posted_links: set,
                      posted_titles: set, posted_keywords: list,
                      limit: int = 20, analytics_filter: bool = False) -> None:
    feed = feedparser.parse(rss_url)
    if not feed.entries:
        print(f"[{source_label}] No entries")
        return

    for entry in reversed(feed.entries[:limit]):
        post_title = entry.title.strip()
        link = entry.link
        raw_desc = getattr(entry, "description", "") or getattr(entry, "summary", "")
        description = clean_html_description(raw_desc)
        if not description:
            description = post_title

        if is_excluded(post_title):
            item_key = f"{link}#0"
            if item_key not in posted_links:
                print(f"[{source_label}] Skipped by title: {post_title}")
                save_posted_link(item_key)
                posted_links.add(item_key)
            continue

        if analytics_filter and is_getgrant_analytics(post_title, description):
            item_key = f"{link}#0"
            if item_key not in posted_links:
                print(f"[{source_label}] Skipped (аналітика): {post_title[:60]}")
                save_posted_link(item_key)
                posted_links.add(item_key)
            continue

        items = split_digest_into_items(description)

        for idx, item_text in enumerate(items):
            item_key = f"{link}#{idx}"
            if item_key in posted_links:
                continue

            item_title = make_item_title(item_text, post_title)

            if (is_excluded(post_title) or is_excluded(item_title)
                    or is_excluded(item_text) or is_excluded(description)):
                print(f"[{source_label}] Skipped item: {item_title[:60]}")
                save_posted_link(item_key)
                posted_links.add(item_key)
                continue

            print(f"[{source_label}] Processing: {item_title}")
            try:
                resp = build_and_send("📌", item_title, link, item_text, source_label,
                                       posted_titles, posted_keywords)
                if resp.status_code == 200:
                    save_posted_link(item_key)
                    posted_links.add(item_key)
            except Exception as e:
                print(f"[{source_label}] ERROR {item_key}: {e}")


# ---------------------------------------------------------------------------
# ІСАР Єднання
# ---------------------------------------------------------------------------

def run_isar(posted_links: set, posted_titles: set, posted_keywords: list) -> None:
    soup = fetch_html(ISAR_URL)
    if not soup:
        return

    links_found = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "tryvaiut-hrantovi-konkursy/" in href and href != "/tryvaiut-hrantovi-konkursy":
            if href.startswith("/"):
                href = "https://ednannia.ua" + href
            links_found.add((href, a.get_text(strip=True)))

    for link, title in sorted(links_found):
        if not title or len(title) < 5 or link in posted_links:
            continue
        if is_excluded(title):
            print(f"[ІСАР] Skipped: {title}")
            save_posted_link(link)
            posted_links.add(link)
            continue
        try:
            page = fetch_html(link)
            if not page:
                continue
            page_text = page.get_text(" ", strip=True)
            deadline_str = extract_deadline(page_text)
            if deadline_str and is_deadline_passed(deadline_str):
                print(f"[ІСАР] Skipped (дедлайн минув): {title}")
                save_posted_link(link)
                posted_links.add(link)
                continue
            description = ""
            content = page.find("div", class_=re.compile(r"item-page|article|content"))
            description = collect_paragraphs(content if content else page)
            if not description:
                description = title
            print(f"[ІСАР] Processing: {title}")
            resp = build_and_send("📌", title, link, description, "ІСАР Єднання — джерело",
                                   posted_titles, posted_keywords, deadline_hint=deadline_str)
            if resp.status_code == 200:
                save_posted_link(link)
                posted_links.add(link)
            time.sleep(2)
        except Exception as e:
            print(f"[ІСАР] ERROR {link}: {e}")


# ---------------------------------------------------------------------------
# МФ «Відродження»
# ---------------------------------------------------------------------------

def run_irf(posted_links: set, posted_titles: set, posted_keywords: list) -> None:
    import xml.etree.ElementTree as ET

    contest_urls = []
    soup = fetch_html("https://www.irf.ua/grants/contests/")
    if soup:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/contest/" in href:
                if href.startswith("/"):
                    href = "https://www.irf.ua" + href
                if href.startswith("https://www.irf.ua/contest/") and href not in contest_urls:
                    contest_urls.append(href)

    if not contest_urls:
        try:
            import warnings
            from bs4 import XMLParsedAsHTMLWarning
            warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
            r = requests.get("https://www.irf.ua/sitemap.xml", timeout=30,
                             headers={"User-Agent": "Mozilla/5.0 ngo-grants-bot/1.0"})
            if r.status_code == 200:
                root = ET.fromstring(r.content)
                ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
                for loc in root.findall(".//sm:loc", ns):
                    url = loc.text.strip() if loc.text else ""
                    if url.startswith("https://www.irf.ua/contest/") and url not in contest_urls:
                        contest_urls.append(url)
        except Exception as e:
            print(f"[МФВ] Sitemap error: {e}")

    if not contest_urls:
        print("[МФВ] Не вдалось знайти конкурси")
        return

    print(f"[МФВ] Знайдено {len(contest_urls)} конкурсів")
    for link in contest_urls:
        if link in posted_links:
            continue
        try:
            page = fetch_html(link)
            if not page:
                continue
            h1 = page.find("h1")
            title = h1.get_text(" ", strip=True) if h1 else link
            page_text = page.get_text(" ", strip=True)
            page_text_lower = page_text.lower()
            if any(x in page_text_lower for x in
                   ["завершення конкурсу", "конкурс завершено", "завершений конкурс"]):
                print(f"[МФВ] Skipped (завершений): {title}")
                save_posted_link(link)
                posted_links.add(link)
                continue
            deadline_str = extract_deadline(page_text)
            if deadline_str and is_deadline_passed(deadline_str):
                print(f"[МФВ] Skipped (дедлайн минув): {title}")
                save_posted_link(link)
                posted_links.add(link)
                continue
            if is_excluded(title) or is_excluded(page_text[:300]):
                print(f"[МФВ] Skipped (фільтр): {title}")
                save_posted_link(link)
                posted_links.add(link)
                continue
            print(f"[МФВ] Processing: {title}")
            description = collect_paragraphs(page, exclude=["завершення конкурсу"])
            if not description:
                description = title
            resp = build_and_send("📌", title, link, description, "МФ «Відродження» — джерело",
                                   posted_titles, posted_keywords, deadline_hint=deadline_str)
            if resp.status_code == 200:
                save_posted_link(link)
                posted_links.add(link)
            time.sleep(2)
        except Exception as e:
            print(f"[МФВ] ERROR {link}: {e}")


# ---------------------------------------------------------------------------
# УКФ
# ---------------------------------------------------------------------------

def run_ucf(posted_links: set, posted_titles: set, posted_keywords: list) -> None:
    soup = fetch_html(UCF_URL)
    if not soup:
        print("[УКФ] Не вдалось завантажити")
        return

    contest_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/m_programs/" in href or "/programs/" in href:
            if href.startswith("/"):
                href = "https://ucf.in.ua" + href
            if href not in contest_links and "ucf.in.ua" in href:
                contest_links.append(href)

    if not contest_links:
        print("[УКФ] Жодного конкурсу")
        return

    print(f"[УКФ] Знайдено {len(contest_links)} програм")
    UCF_JUNK = ["ви можете поставити питання", "отримати на нього відповідь",
                "напишіть нам", "підписка на новини"]

    for link in contest_links[:15]:
        if link in posted_links:
            continue
        try:
            page = fetch_html(link)
            if not page:
                continue
            h1 = page.find("h1")
            title = h1.get_text(" ", strip=True) if h1 else ""
            if not title:
                continue
            if is_excluded(title):
                save_posted_link(link)
                posted_links.add(link)
                continue
            page_text = page.get_text(" ", strip=True)
            deadline_str = extract_deadline(page_text)
            if deadline_str and is_deadline_passed(deadline_str):
                save_posted_link(link)
                posted_links.add(link)
                continue
            description = collect_paragraphs(page, min_len=100, exclude=UCF_JUNK)
            if not description:
                for div in page.find_all(["div", "section"]):
                    t = div.get_text(" ", strip=True)
                    if len(t) > 150 and not any(j in t.lower() for j in UCF_JUNK):
                        description = t[:3000]
                        break
            if not description:
                description = title
            print(f"[УКФ] Processing: {title[:60]}")
            resp = build_and_send("🎨", title, link, description, "УКФ — джерело",
                                   posted_titles, posted_keywords, deadline_hint=deadline_str)
            if resp.status_code == 200:
                save_posted_link(link)
                posted_links.add(link)
            time.sleep(2)
        except Exception as e:
            print(f"[УКФ] ERROR {link}: {e}")


# ---------------------------------------------------------------------------
# ВЕТЕРАНСЬКИЙ ФОНД
# ---------------------------------------------------------------------------

def run_veteranfund(posted_links: set, posted_titles: set, posted_keywords: list) -> None:
    contest_links = []

    feed = feedparser.parse(VF_RSS)
    if feed.entries:
        print(f"[ВФ] RSS: {len(feed.entries)} записів")
        for entry in reversed(feed.entries[:15]):
            if entry.link not in [l for l, _ in contest_links]:
                contest_links.append((entry.link, entry.title.strip()))
    else:
        soup = fetch_html(VF_COMPETITIONS)
        if soup:
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "/contests/" not in href:
                    continue
                if not href.startswith("http"):
                    href = "https://veteranfund.com.ua" + href
                if href.rstrip("/") in ["https://veteranfund.com.ua/competitions",
                                        "https://veteranfund.com.ua/contests"]:
                    continue
                text = a.get_text(strip=True)
                if href not in [l for l, _ in contest_links]:
                    contest_links.append((href, text))
            if contest_links:
                print(f"[ВФ] HTML: {len(contest_links)} конкурсів")
        else:
            print("[ВФ] Не вдалось завантажити")
            return

    if not contest_links:
        print("[ВФ] Жодного конкурсу")
        return

    INVALID_TITLES = ["українська", "english", "головна", "конкурси", "новини",
                      "more details", "детальніше", "докладніше", "читати далі"]

    for link, nav_title in contest_links:
        if link in posted_links:
            continue
        try:
            page = fetch_html(link)
            if not page:
                continue
            h1 = page.find("h1")
            title = h1.get_text(" ", strip=True) if h1 else ""
            if not title or len(title) < 10 or title.lower().strip() in INVALID_TITLES:
                for tag in ["h2", "h3"]:
                    h = page.find(tag)
                    if h:
                        c = h.get_text(" ", strip=True)
                        if len(c) >= 10 and c.lower() not in INVALID_TITLES:
                            title = c
                            break
            if not title or len(title) < 10 or title.lower().strip() in INVALID_TITLES:
                print(f"[ВФ] Skipped (нерелевантний заголовок): {link[-50:]}")
                save_posted_link(link)
                posted_links.add(link)
                continue
            if is_excluded(title):
                print(f"[ВФ] Skipped (фільтр): {title[:60]}")
                save_posted_link(link)
                posted_links.add(link)
                continue
            page_text = page.get_text(" ", strip=True)
            deadline_str = extract_deadline(page_text)
            if deadline_str and is_deadline_passed(deadline_str):
                print(f"[ВФ] Skipped (дедлайн минув): {title[:50]}")
                save_posted_link(link)
                posted_links.add(link)
                continue
            description = collect_paragraphs(page, min_len=100)
            if not description:
                description = title
            print(f"[ВФ] Processing: {title[:60]}")
            resp = build_and_send("🎖", title, link, description, "Ветеранський фонд — джерело",
                                   posted_titles, posted_keywords, deadline_hint=deadline_str)
            if resp.status_code == 200:
                save_posted_link(link)
                posted_links.add(link)
            time.sleep(2)
        except Exception as e:
            print(f"[ВФ] ERROR {link}: {e}")


# ---------------------------------------------------------------------------
# УМФ
# ---------------------------------------------------------------------------

def run_umf(posted_links: set, posted_titles: set, posted_keywords: list) -> None:
    contest_links = []
    for rss_url in [UMF_RSS, "https://uyf.gov.ua/feed/", "https://uyf.gov.ua/news/feed/"]:
        feed = feedparser.parse(rss_url)
        if feed.entries:
            print(f"[УМФ] RSS: {rss_url}, {len(feed.entries)} записів")
            for entry in feed.entries[:20]:
                if "/programs/" in entry.link and entry.link not in contest_links:
                    contest_links.append(entry.link)
            break
    if not contest_links:
        soup = fetch_html(UMF_NEWS_URL)
        if soup:
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "/programs/" in href:
                    if href.startswith("/"):
                        href = "https://uyf.gov.ua" + href
                    if href not in contest_links:
                        contest_links.append(href)
    if not contest_links:
        pass  # УМФ недоступний через JS-рендеринг
        return
    print(f"[УМФ] Знайдено {len(contest_links)} конкурсів")
    for link in contest_links[:10]:
        if link in posted_links:
            continue
        try:
            page = fetch_html(link)
            if not page:
                continue
            h1 = page.find("h1")
            title = h1.get_text(" ", strip=True) if h1 else ""
            if not title or is_excluded(title):
                save_posted_link(link)
                posted_links.add(link)
                continue
            page_text = page.get_text(" ", strip=True)
            deadline_str = extract_deadline(page_text)
            if deadline_str and is_deadline_passed(deadline_str):
                save_posted_link(link)
                posted_links.add(link)
                continue
            description = collect_paragraphs(page, min_len=100)
            if not description:
                description = title
            print(f"[УМФ] Processing: {title[:60]}")
            resp = build_and_send("🌱", title, link, description, "УМФ — джерело",
                                   posted_titles, posted_keywords, deadline_hint=deadline_str)
            if resp.status_code == 200:
                save_posted_link(link)
                posted_links.add(link)
            time.sleep(2)
        except Exception as e:
            print(f"[УМФ] ERROR {link}: {e}")


# ---------------------------------------------------------------------------
# TELEGRAM КАНАЛИ
# ---------------------------------------------------------------------------

def run_tg_channel(username: str, channel_name: str,
                   posted_links: set, posted_titles: set, posted_keywords: list) -> None:
    from datetime import datetime, timezone, timedelta
    url = f"https://t.me/s/{username}"
    try:
        resp = requests.get(url, timeout=60, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"})
        resp.raise_for_status()
    except Exception as e:
        print(f"[@{username}] Не вдалось завантажити: {e}")
        return

    soup = BeautifulSoup(resp.text, "html.parser")
    messages = soup.find_all("div", class_="tgme_widget_message_wrap")
    if not messages:
        print(f"[@{username}] Повідомлень не знайдено")
        return

    print(f"[@{username}] Знайдено {len(messages)} повідомлень")
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)

    for msg in reversed(messages):
        msg_link_tag = msg.find("a", class_="tgme_widget_message_date")
        if not msg_link_tag:
            continue
        msg_url = msg_link_tag.get("href", "")
        if not msg_url:
            continue

        item_key = f"tg_{username}_{msg_url.split('/')[-1]}"
        if item_key in posted_links:
            continue

        time_tag = msg_link_tag.find("time")
        if time_tag and time_tag.get("datetime"):
            try:
                msg_dt = datetime.fromisoformat(
                    time_tag["datetime"].replace("Z", "+00:00"))
                if msg_dt < cutoff:
                    save_posted_link(item_key)
                    posted_links.add(item_key)
                    continue
            except ValueError:
                pass

        text_div = msg.find("div", class_="tgme_widget_message_text")
        if not text_div:
            save_posted_link(item_key)
            posted_links.add(item_key)
            continue

        text = text_div.get_text(" ", strip=True)
        if len(text) < 30:
            save_posted_link(item_key)
            posted_links.add(item_key)
            continue

        if is_tg_junk(text):
            print(f"[@{username}] Skipped (реклама/тендер): {text[:60]}")
            save_posted_link(item_key)
            posted_links.add(item_key)
            continue

        first_line = text.split("\n")[0].strip()[:90] or text[:90]

        print(f"[@{username}] Processing: {first_line[:60]}")
        deadline = extract_deadline(text)

        try:
            response = build_and_send("📌", first_line, msg_url, text,
                                       f"{channel_name} — джерело",
                                       posted_titles, posted_keywords, deadline_hint=deadline)
            if response.status_code == 200:
                save_posted_link(item_key)
                posted_links.add(item_key)
            time.sleep(2)
        except Exception as e:
            print(f"[@{username}] ERROR {item_key}: {e}")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    posted_links = load_posted_links()
    posted_titles = load_posted_titles()
    posted_keywords = load_posted_keywords()

    run_chaszmin(posted_links, posted_titles, posted_keywords)
    run_simple_source(GURT_RSS,     "ГУРТ — джерело",                posted_links,
                      posted_titles, posted_keywords)
    run_simple_source(PROSTIR_RSS,  "Громадський Простір — джерело", posted_links,
                      posted_titles, posted_keywords)
    run_simple_source(GETGRANT_RSS,  "GetGrant — джерело",           posted_links,
                      posted_titles, posted_keywords, analytics_filter=True)
    run_isar(posted_links, posted_titles, posted_keywords)
    run_irf(posted_links, posted_titles, posted_keywords)
    run_ucf(posted_links, posted_titles, posted_keywords)
    run_veteranfund(posted_links, posted_titles, posted_keywords)
    run_umf(posted_links, posted_titles, posted_keywords)
    for username, channel_name in TG_CHANNELS:
        run_tg_channel(username, channel_name, posted_links, posted_titles, posted_keywords)


if __name__ == "__main__":
    main()
