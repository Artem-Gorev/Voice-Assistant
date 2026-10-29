from datetime import datetime
from typing import Any

from dotenv import load_dotenv

from backend.ai_service.llm import LLMConfig, LLMOrchestrator


def format_response(reply_text: str | None) -> str:
    if reply_text:
        return reply_text
    return ""


def main() -> None:
    load_dotenv()

    config = LLMConfig.from_env()
    if not config.credentials:
        raise RuntimeError("GIGACHAT_CREDENTIALS отсутствует в .env")

    llm = LLMOrchestrator(config=config)
    now = datetime.now()

    requests = [
        "Привет, как дела?",
        "Поставь встречу на завтра с 14:00 до 15:00",
        "Какие у меня планы на завтра?",
        "Найди встречу с научником",
        "Напомни купить продукты",
    ]

    for text in requests:
        print(f"\nПользователь: {text}")

        result = llm.process(
            text,
            session_id="test_user",
            current_dt=now,
        )

        print("LLM JSON:")
        print(result.model_dump_json(indent=2, exclude_none=True))
        print("Ответ:", format_response(result.reply_text))


if __name__ == "__main__":
    main()
