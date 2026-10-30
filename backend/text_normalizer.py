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

_UNITS = (
    "ноль", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять",
)
_TEENS = (
    "десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать",
    "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать",
)
_TENS = {
    2: "двадцать", 3: "тридцать", 4: "сорок", 5: "пятьдесят",
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
        return f"{prefix} полночь".strip()

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

    text = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", replace_iso_date, text)
    text = re.sub(r"\b(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?\b", replace_date, text)
    return re.sub(r"\b(в|к|с|до)?\s*(\d{1,2}):(\d{2})\b", _time_to_words, text, flags=re.IGNORECASE)
