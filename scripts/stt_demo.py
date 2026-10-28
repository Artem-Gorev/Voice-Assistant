import argparse
import logging
import sys

import sounddevice as sd

from stt import SpeechRecognizer, TOneConfig

logging.basicConfig(level=logging.INFO, format="[ %(levelname)s ] %(message)s")
logger = logging.getLogger("STT_Sample")


def parser():
    arg_parser = argparse.ArgumentParser(description="Распознавание речи с микрофона моделью T-one",
                                         formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    arg_parser.add_argument("-d", "--duration", type=float, default=10.0, help="Продолжительность записи в секундах")
    arg_parser.add_argument("-sr", "--sample-rate", type=int, default=16_000, help="Частота записи микрофона")
    arg_parser.add_argument("-dec", "--decoder", choices=["greedy", "beam_search"], default="greedy", help="Тип CTC-декодера")
    return arg_parser.parse_args()


def main():
    args = parser()

    try:
        if not 0.15 <= args.duration <= 60:
            raise ValueError("Продолжительность записи должна быть от 0.15 до 60 секунд")
        if args.sample_rate < 8_000:
            raise ValueError("Частота записи должна быть не меньше 8000 Гц")

        config = TOneConfig(decoder=args.decoder)
        recognizer = SpeechRecognizer.create(model_name="t_one", config=config, logger=logger)

        logger.info(f"Запись с микрофона в течение {args.duration:g} сек.")
        audio = sd.rec(int(args.duration * args.sample_rate), samplerate=args.sample_rate, channels=1, dtype="float32")
        sd.wait()

        logger.info("Распознавание речи моделью T-one")
        result = recognizer.transcribe(audio=audio, sample_rate=args.sample_rate)

        logger.info(f"Текст: {result.text}")
        logger.info(f"Длительность аудио: {result.audio_duration_seconds:.2f} сек.")
        logger.info(f"Время обработки: {result.processing_time_seconds:.2f} сек.")
        logger.info(f"Real-time factor: {result.realtime_factor:.3f}")
        return 0
    except Exception as error:
        logger.exception(f"Ошибка распознавания речи: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
