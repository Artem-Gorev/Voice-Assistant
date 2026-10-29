from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SileroConfig:
    model_id: str = "v5_ru"
    voice: str = "xenia"
    sample_rate: int = 24_000
    device: str = "cpu"
    torch_threads: int = 4
    max_text_characters: int = 3_000

    def __post_init__(self):
        if self.model_id != "v5_ru":
            raise ValueError("Модуль поддерживает только Silero TTS v5_ru")

        if self.voice not in {"aidar", "baya", "kseniya", "xenia", "eugene"}:
            raise ValueError(f"Голос Silero '{self.voice}' не поддерживается")

        if self.sample_rate not in {8_000, 24_000, 48_000}:
            raise ValueError("Частота Silero должна быть 8000, 24000 или 48000 Гц")

        if self.torch_threads < 1:
            raise ValueError("torch_threads должен быть не меньше 1")

        if self.max_text_characters < 1:
            raise ValueError("max_text_characters должен быть больше нуля")
