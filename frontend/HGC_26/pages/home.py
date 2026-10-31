"""Main assistant page composition."""

import reflex as rx

from ..components.calendar import calendar_panel
from ..components.chat import chat_panel
from ..state import AssistantState
from ..theme import theme_color


def index() -> rx.Component:
    return rx.hstack(
        chat_panel(),
        calendar_panel(),
        width="100%",
        height="100vh",
        background=theme_color(AssistantState.is_light_theme, "bg_gradient"),
        spacing="0",
        overflow="hidden",
    )
