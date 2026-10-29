import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LLMConfig:
    provider: str = "gigachat"
    credentials: str | None = None
    scope: str = "GIGACHAT_API_PERS"
    model: str = "GigaChat"
    verify_ssl_certs: bool = False
    mock_mode: bool = False

    @classmethod
    def from_env(cls) -> "LLMConfig":
        return cls(
            credentials=os.getenv("GIGACHAT_CREDENTIALS"),
            scope=os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS"),
            model=os.getenv("GIGACHAT_MODEL", "GigaChat"),
        )

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("provider не должен быть пустым")
        if not self.scope.strip():
            raise ValueError("scope не должен быть пустым")
        if not self.model.strip():
            raise ValueError("model не должен быть пустым")
