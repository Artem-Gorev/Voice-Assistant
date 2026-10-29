import json
import re
from datetime import datetime
from typing import Any

from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

from .base import LanguageModel
from .config import LLMConfig
from .prompts import build_system_prompt as create_system_prompt
from .result import LLMResult
from .session import DialogSession, SessionStore
from .simulator import NLUSimulator


def make_fallback_response() -> LLMResult:
    return LLMResult(
        action="chat",
        data={},
        reply_text=(
            "К сожалению, произошла ошибка обработки команды. "
            "Повторите, пожалуйста."
        ),
    )


FALLBACK_RESPONSE = make_fallback_response()


def parse_json_payload(raw_text: str) -> dict[str, Any]:
    cleaned = raw_text.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(cleaned[start : end + 1])

    raise ValueError(f"Не удалось обнаружить валидный JSON в ответе: {raw_text}")


@LanguageModel.register("gigachat")
class LLMOrchestrator(LanguageModel):
    _extract_json = staticmethod(parse_json_payload)

    def __init__(self, config: LLMConfig | None = None, logger=None,
                 session_store: SessionStore | None = None):
        super().__init__(config or LLMConfig.from_env(), logger)
        self._sessions = session_store or SessionStore()
        self._simulator = NLUSimulator()
        self._client = None

        if not self._config.mock_mode and self._config.credentials:
            try:
                self._client = GigaChat(
                    credentials=self._config.credentials,
                    scope=self._config.scope,
                    model=self._config.model,
                    verify_ssl_certs=self._config.verify_ssl_certs,
                )
                self._logger.info("[LLM]: Клиент GigaChat успешно инициализирован")
            except Exception as error:
                self._logger.warning(
                    f"[LLM]: Не удалось инициализировать клиент GigaChat: {error}"
                )
        else:
            self._logger.info("[LLM]: Запуск в режиме NLU-симулятора")

    @property
    def sessions(self) -> SessionStore:
        return self._sessions

    @property
    def simulator(self) -> NLUSimulator:
        return self._simulator

    @simulator.setter
    def simulator(self, value: NLUSimulator | None) -> None:
        self._simulator = value

    def build_system_prompt(self, current_dt: datetime | None = None) -> str:
        return create_system_prompt(current_dt or datetime.now())

    def process(self, user_text: str, session_id: str = "default",
                current_dt: datetime | None = None) -> LLMResult:
        now = current_dt or datetime.now()
        session = self._sessions.get(session_id)
        self._logger.info(f"[LLM]: Обработка запроса (сессия '{session_id}'): '{user_text}'")

        try:
            if self._config.mock_mode or self._client is None:
                simulated_raw = self._simulator.process(user_text, session, now)
                result = LLMResult.model_validate(simulated_raw)
                self._update_fsm(session_id, result)
                self._logger.info(f"[LLM]: Распознано действие: '{result.action}'")
                return result

            system_prompt = self.build_system_prompt(now)
            messages = [Messages(role=MessagesRole.SYSTEM, content=system_prompt)]

            if session and session.missing_field == "start_time":
                messages.append(
                    Messages(
                        role=MessagesRole.USER,
                        content=self._build_session_context(user_text, session),
                    )
                )
            else:
                messages.append(Messages(role=MessagesRole.USER, content=user_text))

            response = self._client.chat(Chat(messages=messages, temperature=0.1))
            raw_content = response.choices[0].message.content
            result = LLMResult.model_validate(parse_json_payload(raw_content))

            self._update_fsm(session_id, result)
            self._logger.info(f"[LLM]: Распознано действие: '{result.action}'")
            return result

        except Exception as error:
            self._logger.exception(f"[LLM]: Ошибка обработки запроса: {error}")
            return make_fallback_response()

    def _build_session_context(self, user_text: str, session: DialogSession) -> str:
        title = session.partial_data.get("title", "")
        last_reply = session.last_reply_text or ""
        self._logger.info(f"[LLM]: Слот-филлинг для события '{title}'")
        return (
            "[КОНТЕКСТ ДИАЛОГА]\n"
            f"Ранее пользователь просил запланировать событие: '{title}'.\n"
            f"Ассистент задал вопрос: '{last_reply}'.\n"
            f"Сейчас пользователь ответил: '{user_text}'.\n"
            f"Объедини название из контекста ('{title}') с указанным временем "
            "и сформируй действие 'create_event'."
        )

    def _update_fsm(self, session_id: str, response: LLMResult) -> None:
        if response.action == "clarify":
            data = response.data
            self._sessions.save(
                session_id,
                DialogSession(
                    missing_field=data.get("missing_field", "start_time"),
                    partial_data=data.get("partial_data", {}),
                    last_reply_text=response.reply_text,
                ),
            )
        else:
            self._sessions.delete(session_id)

