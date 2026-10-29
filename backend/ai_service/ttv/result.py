from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class TextVectors:
    vectors: np.ndarray
    texts: tuple[str, ...]
    processing_time_seconds: float
    model_name: str

    @property
    def dimension(self) -> int:
        return int(self.vectors.shape[1])

    @property
    def vector(self) -> np.ndarray:
        if len(self.texts) != 1:
            raise ValueError("Результат содержит несколько векторов. Используйте поле vectors")
        return self.vectors[0]


@dataclass(frozen=True, slots=True)
class SearchResult:
    index: int
    text: str
    score: float
