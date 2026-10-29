from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RuBertTiny2Config:
    model_id: str = "cointegrated/rubert-tiny2"
    device: str = "auto"
    batch_size: int = 32
    max_length: int | None = None
    normalize: bool = True
    local_files_only: bool = False
    cache_dir: str | None = None
    torch_threads: int | None = 4

    def __post_init__(self) -> None:
        if self.model_id != "cointegrated/rubert-tiny2":
            raise ValueError("Модуль поддерживает только cointegrated/rubert-tiny2")

        if self.device not in {"auto", "cpu", "cuda", "mps"}:
            raise ValueError("device должен иметь значение auto, cpu, cuda или mps")

        if self.batch_size < 1:
            raise ValueError("batch_size должен быть не меньше 1")

        if self.max_length is not None and self.max_length < 2:
            raise ValueError("max_length должен быть не меньше 2")

        if self.torch_threads is not None and self.torch_threads < 1:
            raise ValueError("torch_threads должен быть не меньше 1")
