from datetime import datetime

from dotenv import load_dotenv

from backend.ai_service.llm import LLMConfig, LLMOrchestrator


def main() -> None:
    load_dotenv()

    llm = LLMOrchestrator(config=LLMConfig.from_env())
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
        print(result.model_dump_json(indent=2))
        print("Ответ:", result.reply_text)


if __name__ == "__main__":
    main()