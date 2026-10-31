import re
from calendar import monthrange
from datetime import date


_ORDINAL_DAYS = (
    "первого", "второго", "третьего", "четвертого", "пятого", "шестого",
    "седьмого", "восьмого", "девятого", "десятого", "одиннадцатого",
    "двенадцатого", "тринадцатого", "четырнадцатого", "пятнадцатого",
    "шестнадцатого", "семнадцатого", "восемнадцатого", "девятнадцатого",
    "двадцатого", "двадцать первого", "двадцать второго", "двадцать третьего",
    "двадцать четвертого", "двадцать пятого", "двадцать шестого",
    "двадцать седьмого", "двадцать восьмого", "двадцать девятого",
    "тридцатого", "тридцать первого",
)
_MONTHS_GENITIVE = (
    "января", "февраля", "марта", "апреля", "мая", "июня", "июля",
    "августа", "сентября", "октября", "ноября", "декабря",
)
_MONTHS_BY_NAME = {name: index for index, name in enumerate(_MONTHS_GENITIVE, 1)}
_LIST_ORDINALS = (
    "первое", "второе", "третье", "четвёртое", "пятое", "шестое", "седьмое", "восьмое", "девятое", "десятое",
)

_UNITS = (
    "ноль", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять",
)
_TEENS = (
    "десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать",
    "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать",
)
_TENS = {
    2: "двадцать", 3: "тридцать", 4: "сорок", 5: "пятьдесят", 6: "шестьдесят",
    7: "семьдесят", 8: "восемьдесят", 9: "девяносто",
}
_HOUR_GENITIVE = (
    "нуля", "одного", "двух", "трех", "четырех", "пяти", "шести", "семи",
    "восьми", "девяти", "десяти", "одиннадцати", "двенадцати", "тринадцати",
    "четырнадцати", "пятнадцати", "шестнадцати", "семнадцати", "восемнадцати",
    "девятнадцати", "двадцати", "двадцати одного", "двадцати двух",
    "двадцати трех", "двадцати четырех",
)
_YEAR_UNITS = (
    "", "первого", "второго", "третьего", "четвертого", "пятого", "шестого",
    "седьмого", "восьмого", "девятого",
)
_YEAR_TEENS = (
    "десятого", "одиннадцатого", "двенадцатого", "тринадцатого",
    "четырнадцатого", "пятнадцатого", "шестнадцатого", "семнадцатого",
    "восемнадцатого", "девятнадцатого",
)
_YEAR_TENS = {
    2: ("двадцать", "двадцатого"),
    3: ("тридцать", "тридцатого"),
    4: ("сорок", "сорокового"),
    5: ("пятьдесят", "пятидесятого"),
    6: ("шестьдесят", "шестидесятого"),
    7: ("семьдесят", "семидесятого"),
    8: ("восемьдесят", "восьмидесятого"),
    9: ("девяносто", "девяностого"),
}


def _number_to_words(value: int) -> str:
    if value < 10:
        return _UNITS[value]
    if value < 20:
        return _TEENS[value - 10]
    tens, units = divmod(value, 10)
    return _TENS[tens] if units == 0 else f"{_TENS[tens]} {_UNITS[units]}"


def _integer_to_words(value: int) -> str:
    if value >= 1_000_000:
        return str(value)
    if value >= 1_000:
        thousands, remainder = divmod(value, 1_000)
        last_two = thousands % 100
        last = thousands % 10
        noun = "тысяч" if 11 <= last_two <= 14 or last == 0 or last >= 5 else ("тысяча" if last == 1 else "тысячи")
        prefix = "одна" if thousands == 1 else ("две" if thousands == 2 else _integer_to_words(thousands))
        suffix = _integer_to_words(remainder) if remainder else ""
        return f"{prefix} {noun} {suffix}".strip()
    if value < 100:
        return _number_to_words(value)
    hundreds = ("", "сто", "двести", "триста", "четыреста", "пятьсот", "шестьсот", "семьсот", "восемьсот", "девятьсот")
    remainder = value % 100
    return f"{hundreds[value // 100]} {_number_to_words(remainder)}".strip() if remainder else hundreds[value // 100]


def _count_to_words(match: re.Match[str]) -> str:
    value = int(match.group(1))
    noun = match.group(2).lower()
    last_two = value % 100
    last = value % 10
    if noun.startswith("повтор"):
        forms = ("повторение", "повторения", "повторений")
    elif noun.startswith("событ"):
        forms = ("событие", "события", "событий")
    elif noun.startswith("встреч"):
        forms = ("встреча", "встречи", "встреч")
    else:
        forms = ("задача", "задачи", "задач")
    form = forms[2] if 11 <= last_two <= 14 or last == 0 or last >= 5 else (forms[0] if last == 1 else forms[1])
    return f"{_integer_to_words(value)} {form}"


def _list_number_to_words(match: re.Match[str]) -> str:
    value = int(match.group(1))
    if 1 <= value <= len(_LIST_ORDINALS):
        return f"{_LIST_ORDINALS[value - 1]}. "
    return f"{_integer_to_words(value)}. "


def _minute_noun(value: int) -> str:
    last_two = value % 100
    if 11 <= last_two <= 14:
        return "минут"
    if value % 10 == 1:
        return "минута"
    if 2 <= value % 10 <= 4:
        return "минуты"
    return "минут"


def _year_to_words(year: int) -> str:
    if not 2000 <= year <= 2099:
        return ""
    remainder = year - 2000
    if remainder == 0:
        return "две тысячи года"
    if remainder < 10:
        ending = _YEAR_UNITS[remainder]
    elif remainder < 20:
        ending = _YEAR_TEENS[remainder - 10]
    else:
        tens, units = divmod(remainder, 10)
        tens_word, exact_ending = _YEAR_TENS[tens]
        ending = exact_ending if units == 0 else f"{tens_word} {_YEAR_UNITS[units]}"
    return f"две тысячи {ending} года"


def _time_to_words(match: re.Match[str]) -> str:
    prefix = (match.group(1) or "").lower()
    hour, minute = int(match.group(2)), int(match.group(3))
    if hour > 23 or minute > 59:
        return match.group(0)
    if hour == 0 and minute == 0:
        midnight = {"с": "полуночи", "до": "полуночи", "к": "полуночи"}.get(prefix, "полночь")
        return f"{prefix} {midnight}".strip()

    if hour == 0:
        hour_word = {"с": "полуночи", "до": "полуночи", "к": "полуночи"}.get(prefix, "полночь")
        minute_phrase = f" {_number_to_words(minute)} {_minute_noun(minute)}"
        return f"{prefix} {hour_word}{minute_phrase}".strip()

    if prefix in {"с", "до"}:
        hour_word = f"{_HOUR_GENITIVE[hour]} часов"
    elif prefix == "к":
        hour_word = f"{_HOUR_GENITIVE[hour]} часам"
    elif prefix == "в":
        hour_word = {1: "один час", 2: "два часа", 3: "три часа", 4: "четыре часа"}.get(
            hour, f"{_number_to_words(hour)} часов"
        )
    else:
        hour_word = {1: "один час", 2: "два часа", 3: "три часа", 4: "четыре часа"}.get(
            hour, f"{_number_to_words(hour)} часов"
        )
    minute_phrase = ""
    if minute:
        minute_phrase = f" {_number_to_words(minute)} {_minute_noun(minute)}"
    return f"{prefix} {hour_word}{minute_phrase}".strip()


def normalize_text_for_speech(text: str) -> str:
    def replace_named_date(match: re.Match[str]) -> str:
        day = int(match.group(1))
        month = _MONTHS_BY_NAME[match.group(2).lower()]
        year = int(match.group(3)) if match.group(3) else None
        validation_year = year or 2024
        if not 1 <= day <= monthrange(validation_year, month)[1]:
            return match.group(0)
        phrase = f"{_ORDINAL_DAYS[day - 1]} {_MONTHS_GENITIVE[month - 1]}"
        if year:
            phrase = f"{phrase} {_year_to_words(year)}".strip()
        return phrase

    def replace_date(match: re.Match[str]) -> str:
        day, month = int(match.group(1)), int(match.group(2))
        year = int(match.group(3)) if match.group(3) else 2024
        if not 1 <= month <= 12 or not 1 <= day <= monthrange(year, month)[1]:
            return match.group(0)
        phrase = f"{_ORDINAL_DAYS[day - 1]} {_MONTHS_GENITIVE[month - 1]}"
        if match.group(3):
            phrase = f"{phrase} {_year_to_words(year)}".strip()
        return phrase

    def replace_iso_date(match: re.Match[str]) -> str:
        try:
            value = date.fromisoformat(match.group(0))
        except ValueError:
            return match.group(0)
        return (
            f"{_ORDINAL_DAYS[value.day - 1]} {_MONTHS_GENITIVE[value.month - 1]} "
            f"{_year_to_words(value.year)}"
        ).strip()

    text = re.sub(r"\s*;\s*", ". ", text)
    text = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", replace_iso_date, text)
    text = re.sub(r"\b(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?\b", replace_date, text)
    text = re.sub(
        r"\b(\d{1,2})\.?\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)(?:\s+(\d{4})(?:\s+года?)?)?\b",
        replace_named_date,
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\b(в|к|с|до)?\s*(\d{1,2}):(\d{2})\b", _time_to_words, text, flags=re.IGNORECASE)
    text = re.sub(r"\b(\d+)\s+(повторени[яй]|событи[яй]|встреч[аиу]|задач[аиу])\b", _count_to_words, text, flags=re.IGNORECASE)
    text = re.sub(r"(?<![\d.])(\d{1,2})\.\s+(?=[а-яёa-z«])", _list_number_to_words, text, flags=re.IGNORECASE)
    return re.sub(r"(?<![\w.])(\d+)(?![\w.])", lambda match: _integer_to_words(int(match.group(1))), text)
