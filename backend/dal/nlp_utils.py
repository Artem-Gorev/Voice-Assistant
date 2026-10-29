import re
from typing import Optional

try:
    import pymorphy3
    _morph = pymorphy3.MorphAnalyzer()
except Exception:
    _morph = None

MEETING_TRIGGERS = [
    "встреч", "созвон", "демо", "обсудить", "планёрк", "планерк",
    "синхрон", "интервью", "митинг"
]


def lemmatize_text(text: Optional[str]) -> str:
    if not isinstance(text, str) or not text.strip():
        return ""

    words = re.findall(r"[а-яА-Яa-zA-Z0-9]+", text.lower())
    if not words:
        return ""

    if _morph:
        try:
            return " ".join([_morph.parse(w)[0].normal_form for w in words])
        except Exception:
            pass

    return " ".join(words)


def classify_event(text: Optional[str]) -> str:
    if not isinstance(text, str):
        return "task"

    lower = text.lower()

    if any(t in lower for t in MEETING_TRIGGERS):
        return "meeting"

    if lower.startswith("напомн") or " напомн" in lower:
        return "reminder"

    return "task"
