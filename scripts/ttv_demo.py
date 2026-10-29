import argparse
import logging
import sys
from time import perf_counter

from backend.ai_service.ttv import RuBertTiny2Config, TextVectorizer

DEFAULT_TEXT = "Найди задачу, где надо связаться с Ваней по контракту"

DEFAULT_TEXTS = [
    "Позвонить Ивану и обсудить условия договора",
    "Подготовить презентацию и связаться с Олегом в Телеграме",
    "Купить билеты на поезд до конца недели",
    "Встреча с дизайнером в четверг в одиннадцать",
]

logging.basicConfig(level=logging.INFO, format="[ %(levelname)s ] %(message)s")
logger = logging.getLogger("TTV_Sample")


def parser():
    arg_parser = argparse.ArgumentParser(description="Семантический поиск моделью cointegrated/rubert-tiny2",
                                         formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    arg_parser.add_argument("-q", "--query", type=str, default=DEFAULT_TEXT,
                            help="Поисковый запрос")
    arg_parser.add_argument("-t", "--texts", nargs="+", default=DEFAULT_TEXTS, help="Тексты, по которым выполняется поиск")
    arg_parser.add_argument("-k", "--top-k", type=int, default=3, help="Количество результатов")
    arg_parser.add_argument("-d", "--device", choices=["auto", "cpu", "cuda", "mps"], default="auto",
                            help="Устройство для инференса")
    arg_parser.add_argument("-b", "--batch-size", type=int, default=16, help="Размер пакета")
    arg_parser.add_argument("-ml", "--max-length", type=int, default=None, help="Максимальная длина токенизированного текста")
    arg_parser.add_argument("--local-files-only", action="store_true", help="Использовать только локальный кэш модели")
    return arg_parser.parse_args()


def main():
    args = parser()

    try:
        config = RuBertTiny2Config(device=args.device, batch_size=args.batch_size, max_length=args.max_length,
                                   local_files_only=args.local_files_only)
        vectorizer = TextVectorizer.create(model_name="rubert_tiny2", config=config, logger=logger)

        load_started = perf_counter()
        dimension = vectorizer.dimension
        load_time = perf_counter() - load_started

        search_started = perf_counter()
        results = vectorizer.search(args.query, args.texts, top_k=args.top_k)
        search_time = perf_counter() - search_started

        logger.info(f"Устройство: {vectorizer.device}")
        logger.info(f"Размер вектора: {dimension}")
        logger.info(f"Загрузка модели: {load_time:.3f} сек.")
        logger.info(f"Семантический поиск: {search_time:.3f} сек.")
        logger.info(f"Запрос: {args.query}")
        for position, result in enumerate(results, start=1):
            logger.info(f"{position}. score={result.score:.4f} | {result.text}")
        return 0

    except Exception as error:
        logger.exception(f"Ошибка векторизации текста: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
