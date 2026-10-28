from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class TOneConfig:
    model_id: str = "t-tech/T-one"
    decoder: Literal["greedy", "beam_search"] = "greedy"
    target_sample_rate: int = 8_000
    min_audio_seconds: float = 0.15
    max_audio_seconds: float = 60.0

    def __post_init__(self) -> None:
        if self.model_id != "t-tech/T-one":
            raise ValueError("Модуль поддерживает только модель t-tech/T-one")

        if self.target_sample_rate != 8_000:
            raise ValueError("T-one поддерживает частоту только 8000 Гц")

        if self.min_audio_seconds <= 0:
            raise ValueError("min_audio_seconds должен быть больше нуля")

        if self.max_audio_seconds <= self.min_audio_seconds:
            raise ValueError("max_audio_seconds должен быть больше min_audio_seconds")
