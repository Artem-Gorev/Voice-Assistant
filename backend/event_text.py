import re


def clean_event_title(title: str) -> str:
    if not _looks_like_command_title(title):
        return title

    cleaned = re.sub(
        r"^(?:(?:я\s+)?хочу\s+|(?:я\s+)?планирую\s+|собираюсь\s+|"
        r"(?:ну\s+)?(?:хорошо\s+)?(?:пожалуйста\s+)?"
        r"(?:поставь|запланируй|создай|напомни|добавь|запиши)\s+)",
        "",
        title,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\b\d{1,2}[./]\d{1,2}(?:[./]\d{4})?\b", " ", cleaned)
    cleaned = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", " ", cleaned)
    cleaned = re.sub(
        r"\b(?:мне|что\s+у\s+меня|эту\s+задачу|эту\s+встречу|это\s+дело|эту|задачу|событие|на\s+эту\s+неделю)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\b\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|"
        r"сентября|октября|ноября|декабря)(?:\s+\d{4})?\s*(?:года?|г\.)?\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", " ", cleaned)
    cleaned = re.sub(r"\b(?:в|к|с)?\s*\d{1,2}:\d{2}\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"\b(?:на\s+)?(?:сегодня|завтра|послезавтра)\b", " ", cleaned, flags=re.IGNORECASE
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.!?;:—-\t\n")
    cleaned = re.sub(r"^(?:на|в|к|с)\s+", "", cleaned, flags=re.IGNORECASE)
    return cleaned[0].upper() + cleaned[1:] if cleaned else ""


def _looks_like_command_title(title: str) -> bool:
    normalized = title.casefold().strip()
    return (
        len(normalized) > 70
        or bool(re.match(r"^(?:хорошо\s+)?(?:поставь|запланируй|создай|напомни|добавь|запиши)\b", normalized))
        or bool(re.match(r"^(?:мне\s+)?(?:эту\s+)?задачу\b", normalized))
        or bool(re.match(r"^(?:(?:я\s+)?хочу|(?:я\s+)?планирую|собираюсь)\b", normalized))
        or bool(re.search(r"\b(?:что\s+у\s+меня|\d{1,2}\s+[а-яё]+|\d{1,2}[./]\d{1,2}|\d{1,2}:\d{2}|завтра|сегодня|послезавтра)\b", normalized))
    )
