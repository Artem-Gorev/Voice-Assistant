import argparse
import logging
import sys

import sounddevice as sd

from backend.ai_service.tts import SileroConfig, SpeechSynthesizer

logging.basicConfig(level=logging.INFO, format="[ %(levelname)s ] %(message)s")
logger = logging.getLogger("TTS_Sample")


def parser():
    arg_parser = argparse.ArgumentParser(description="Синтез и воспроизведение речи моделью Silero TTS v5_ru",
                                         formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    arg_parser.add_argument("-t", "--text", type=str, default="Добрый день, Дмитрий. Всё, что вы пожелаете, выполню.", help="Текст для озвучивания")
    arg_parser.add_argument("-v", "--voice", choices=["aidar", "baya", "kseniya", "xenia", "eugene"], default="xenia", help="Голос Silero")
    arg_parser.add_argument("-sr", "--sample-rate", type=int, choices=[8_000, 24_000, 48_000], default=24_000, help="Частота синтезированного аудио")
    arg_parser.add_argument("-d", "--device", choices=["cpu", "cuda", "mps"], default="cpu", help="Устройство для инференса")
    arg_parser.add_argument("-th", "--torch-threads", type=int, default=4, help="Количество потоков PyTorch")
    return arg_parser.parse_args()


def main():
    args = parser()

    try:
        config = SileroConfig(voice=args.voice, sample_rate=args.sample_rate, device=args.device, torch_threads=args.torch_threads)
        synthesizer = SpeechSynthesizer.create(model_name="silero", config=config, logger=logger)

        logger.info(f"Синтез текста: {args.text}")
        result = synthesizer.synthesize(args.text)
        sd.play(result.samples, samplerate=result.sample_rate)
        sd.wait()

        logger.info(f"Длительность аудио: {result.duration_seconds:.2f} сек.")
        logger.info(f"Время синтеза: {result.processing_time_seconds:.2f} сек.")
        logger.info(f"Real-time factor: {result.realtime_factor:.3f}")
        logger.info("Аудио воспроизведено из памяти, файлы не создавались")
        return 0

    except Exception as error:
        logger.exception(f"Ошибка синтеза речи: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
