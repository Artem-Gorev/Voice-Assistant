"""Reusable interface component."""

import reflex as rx

from ..state import AssistantState as State
from ..theme import theme_color


def render_message(msg: dict) -> rx.Component:
    is_user = msg["role"] == "user"
    return rx.box(
        rx.text(msg["text"], white_space="pre-wrap"),
        background=rx.cond(
            is_user,
            theme_color(State.is_light_theme, "user_msg_bg"),
            theme_color(State.is_light_theme, "ai_msg_bg"),
        ),
        color=rx.cond(
            is_user,
            theme_color(State.is_light_theme, "user_msg_text"),
            theme_color(State.is_light_theme, "ai_msg_text"),
        ),
        padding="16px 20px",
        border_radius="16px",
        border_bottom_right_radius=rx.cond(is_user, "4px", "16px"),
        border_bottom_left_radius=rx.cond(is_user, "16px", "4px"),
        border=rx.cond(
            is_user,
            "none",
            rx.cond(
                State.is_light_theme,
                "1px solid rgba(167, 137, 104, 0.12)",
                "1px solid rgba(196, 167, 135, 0.3)",
            ),
        ),
        max_width="70%",
        align_self=rx.cond(is_user, "flex-end", "flex-start"),
        box_shadow=theme_color(State.is_light_theme, "message_shadow"),
    )


def chat_panel() -> rx.Component:
    return rx.vstack(
        rx.scroll_area(
            rx.vstack(
                rx.foreach(State.messages, render_message),
                width="100%",
                padding="40px",
                gap="24px",
            ),
            rx.cond(
                State.processing_status != "",
                rx.text(
                    State.processing_status,
                    color=theme_color(State.is_light_theme, "text_muted"),
                    opacity="0.65",
                    font_size="13px",
                    align_self="flex-start",
                    padding_left="40px",
                    animation="pulse 1.5s ease-in-out infinite",
                ),
                rx.fragment(),
            ),
            rx.cond(
                State.api_error != "",
                rx.text(
                    State.api_error,
                    color=theme_color(State.is_light_theme, "error_text"),
                    opacity="0.9",
                    font_size="13px",
                    align_self="flex-start",
                    padding_left="40px",
                ),
                rx.fragment(),
            ),
            type="scroll",
            scrollbars="vertical",
            style={"height": "100%", "flex": "1"},
        ),
        rx.form(
            rx.el.input(
                type="hidden",
                name="request_id",
                value=State.request_id,
                display="none",
            ),
            rx.hstack(
                rx.text_area(
                    placeholder=rx.cond(
                        State.is_recording,
                        "Идёт запись — нажмите микрофон, чтобы отправить",
                        rx.cond(
                            State.is_transcribing,
                            "Распознаю голос...",
                            "Введите задачу или вопрос...",
                        ),
                    ),
                    name="message",
                    value=State.user_input,
                    on_change=State.set_user_input,
                    disabled=State.is_recording | State.is_transcribing | State.recording_starting,
                    enter_key_submit=True,
                    flex="1",
                    background="transparent !important",
                    border="none !important",
                    box_shadow="none !important",
                    outline="none !important",
                    color=theme_color(State.is_light_theme, "text_main"),
                    _placeholder={"color": theme_color(State.is_light_theme, "text_muted")},
                    resize="none",
                    rows="1",
                    auto_height=True,
                    min_height="0",
                    padding="8px 0",
                    key=State.input_key,
                ),
                rx.button(
                    rx.cond(
                        State.speak_replies,
                        rx.icon(tag="volume-2", size=20),
                        rx.icon(tag="volume-x", size=20),
                    ),
                    type="button",
                    on_click=State.toggle_speech,
                    title=rx.cond(
                        State.speak_replies,
                        "Озвучивание ответов включено",
                        "Включить озвучивание ответов",
                    ),
                    background=rx.cond(
                        State.speak_replies,
                        theme_color(State.is_light_theme, "soft_button_active_bg"),
                        theme_color(State.is_light_theme, "soft_button_bg"),
                    ),
                    color=theme_color(State.is_light_theme, "text_accent"),
                    border_radius="50%",
                    width="42px",
                    height="42px",
                    flex_shrink="0",
                ),
                rx.button(
                    rx.cond(
                        State.is_recording,
                        rx.icon(tag="square", size=18),
                        rx.icon(tag="mic", size=20),
                    ),
                    type="button",
                    on_click=State.toggle_recording,
                    disabled=State.is_transcribing | State.recording_starting | State.is_sending,
                    title=rx.cond(
                        State.is_recording,
                        "Остановить запись и отправить",
                        "Записать голосовое сообщение",
                    ),
                    background=rx.cond(
                        State.is_recording,
                        theme_color(State.is_light_theme, "recording_bg"),
                        theme_color(State.is_light_theme, "soft_button_bg"),
                    ),
                    color=rx.cond(
                        State.is_recording,
                        "white",
                        theme_color(State.is_light_theme, "text_accent"),
                    ),
                    border_radius="50%",
                    width="42px",
                    height="42px",
                    flex_shrink="0",
                ),
                rx.button(
                    rx.icon(tag="send", size=20),
                    type="submit",
                    disabled=State.is_sending | State.is_recording | State.is_transcribing,
                    background=theme_color(State.is_light_theme, "btn_send_bg"),
                    color=theme_color(State.is_light_theme, "btn_send_text"),
                    border_radius="50%",
                    width="42px",
                    height="42px",
                    flex_shrink="0",
                ),
                width="100%",
                align_items="flex-end",
            ),
            on_submit=State.send_message,
            width="100%",
            max_width="800px",
            background=theme_color(State.is_light_theme, "input_bg"),
            border=rx.cond(
                State.is_light_theme,
                "1px solid rgba(173, 143, 110, 0.16)",
                "1px solid rgba(168, 132, 98, 0.4)",
            ),
            border_radius="24px",
            padding="8px 8px 8px 20px",
            box_shadow=theme_color(State.is_light_theme, "input_shadow"),
        ),
        width="100%",
        height="100vh",
        padding="20px 40px 30px",
        justify_content="center",
        align_items="center",
        flex="1",
        z_index="5",
    )
