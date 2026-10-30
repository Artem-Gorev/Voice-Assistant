import re


LOOKUP_MARKERS = (
    "мне нужно",
    "мне надо",
    "у меня",
    "отправ",
    "отчёт",
    "отчет",
    "позвон",
    "звонок",
    "встреч",
    "задач",
    "событ",
    "план",
    "напомн",
    "купить",
    "запланир",
)

NON_SEARCH_TERMS = {
    "когда", "мне", "нужно", "надо", "необходимо", "пора", "следует",
    "у", "меня", "на", "в", "этой", "эту", "этот", "следующей",
    "следующий", "ближайший", "ближайшую", "неделе", "неделю", "месяце",
    "месяц", "сегодня", "завтра", "послезавтра", "понедельник", "вторник",
    "среду", "среда", "четверг", "пятницу", "пятница", "субботу", "суббота",
    "воскресенье",
}


def extract_event_lookup_query(text: str) -> str | None:
    normalized = " ".join(text.lower().split())
    if not re.match(r"^(?:а\s+)?когда\b", normalized):
        return None
    if not any(marker in normalized for marker in LOOKUP_MARKERS):
        return None

    query = re.sub(r"^(?:а\s+)?когда\s+", "", normalized)
    query = re.sub(
        r"^(?:мне\s+)?(?:нужно|надо|необходимо|пора|следует)\s+",
        "",
        query,
    )
    query = re.sub(r"^у\s+меня\s+", "", query)
    query = re.sub(r"[?!.,;:]+$", "", query).strip()

    meaningful_words = [
        word
        for word in re.findall(r"[а-яёa-z0-9]+", query)
        if word not in NON_SEARCH_TERMS
    ]
    if not meaningful_words:
        return None
    return query
