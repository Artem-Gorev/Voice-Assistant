import argparse
import logging
from collections.abc import Sequence

from dotenv import load_dotenv

from backend.voice_assistant import VoiceAssistant

logging.basicConfig(level=logging.INFO, format="[ %(levelname)s ] %(message)s")
logger = logging.getLogger("voice_assistant")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Голосовой ассистент для задач и встреч")
    parser.add_argument("--voice-input", action="store_true", help="Включить запись с микрофона по команде /voice")
    parser.add_argument("--voice-output", "--speak", dest="voice_output", action="store_true", help="Озвучивать ответы через Silero TTS")
    parser.add_argument("--text-output", action=argparse.BooleanOptionalAction, default=True, help="Показывать текстовые ответы в логе")
    parser.add_argument("--record-seconds", type=float, default=10.0, help="Длительность записи одного запроса")
    parser.add_argument("--sample-rate", type=int, default=16_000, help="Частота записи с микрофона")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.record_seconds <= 0 or args.sample_rate < 8_000:
        logger.error("Длительность должна быть положительной, частота — не ниже 8000 Гц.")
        return 2
    if not args.text_output and not args.voice_output:
        logger.error("Нужно включить хотя бы один способ ответа: текстовый или голосовой.")
        return 2

    load_dotenv()
    assistant = None
    try:
        assistant = VoiceAssistant(logger=logger, voice_input=args.voice_input, speak=args.voice_output,
                                   record_seconds=args.record_seconds, sample_rate=args.sample_rate)
        logger.info("Ассистент запущен. Для выхода введите /exit.")

        while True:
            try:
                logger.info("Введите запрос, /voice для записи или /exit для выхода.")
                user_text = input().strip()
                if user_text.lower() in {"/exit", "выход", "quit"}:
                    break

                if user_text.lower() == "/voice":
                    if not args.voice_input:
                        logger.error("Микрофон выключен. Перезапустите с флагом --voice-input.")
                        continue
                    logger.info("Говорите после сигнала.")
                    user_input = assistant.record_audio()
                    text = assistant.process_input(user_input, sample_rate=args.sample_rate)
                else:
                    if not user_text:
                        continue
                    text = assistant.process_input(user_text)

                assistant.run(text, text_output=args.text_output, voice_output=args.voice_output)
            except (EOFError, KeyboardInterrupt):
                logger.info("Завершение работы по запросу пользователя.")
                break
            except Exception as error:
                logger.exception(f"Ошибка обработки запроса: {error}")

        return 0
    except Exception as error:
        logger.exception(f"Не удалось запустить голосового ассистента: {error}")
        return 1
    finally:
        if assistant is not None:
            assistant.close()


if __name__ == "__main__":
    raise SystemExit(main())
