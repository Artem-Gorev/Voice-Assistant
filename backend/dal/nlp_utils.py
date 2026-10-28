"""Утилиты для обработки естественного языка (NLP) при работе с событиями."""

import re
from typing import Optional

# Инициализация морфологического анализатора для нормализации слов
try:
    import pymorphy3
    _morph = pymorphy3.MorphAnalyzer()
except Exception:
    _morph = None


def lemmatize_text(text: Optional[str]) -> str:
    """Лемматизация текста для нечёткого поиска."""
    if not isinstance(text, str) or not text.strip():
        return ""

    # Выделение слов без знаков препинания
    words = re.findall(r"[а-яА-Яa-zA-Z0-9]+", text.lower())
    if not words:
        return ""

    # Приведение слов к начальной форме
    if _morph:
        try:
            return " ".join([_morph.parse(w)[0].normal_form for w in words])
        except Exception:
            pass

    # Резервный возврат при ошибке морфологического анализатора
    return " ".join(words)


def classify_event(text: Optional[str]) -> str:
    """Определение типа события по ключевым маркерам в тексте."""
    if not isinstance(text, str):
        return "task"

    lower = text.lower()

    # Ключевые маркеры встреч и созвонов
    meeting_triggers = [
        "встреч", "созвон", "демо", "обсудить", "планёрк", "планерк",
        "синхрон", "интервью", "митинг"
    ]
    if any(t in lower for t in meeting_triggers):
        return "meeting"

    # Проверка маркеров напоминаний
    if lower.startswith("напомн") or " напомн" in lower:
        return "reminder"

    # Тип по умолчанию для остальных событий
    return "task"
