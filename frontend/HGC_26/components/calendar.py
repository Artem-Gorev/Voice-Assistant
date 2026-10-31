"""Calendar sidebar and expanded calendar dialog."""

import reflex as rx

from ..state import AssistantState as State
from ..theme import theme_color


def calendar_panel() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.text(
                "Календарь",
                font_size="13px",
                font_weight="600",
                text_transform="uppercase",
                color=theme_color(State.is_light_theme, "text_accent"),
                letter_spacing="1px",
            ),
            rx.spacer(),
            rx.button(
                rx.cond(
                    State.is_light_theme,
                    rx.icon(tag="moon", size=17),
                    rx.icon(tag="sun", size=17),
                ),
                on_click=State.toggle_theme,
                title=rx.cond(
                    State.is_light_theme,
                    "Включить тёмную тему",
                    "Включить светлую тему",
                ),
                background=theme_color(State.is_light_theme, "soft_button_bg"),
                color=theme_color(State.is_light_theme, "text_accent"),
                border=rx.cond(
                    State.is_light_theme,
                    "1px solid rgba(173, 143, 110, 0.35)",
                    "1px solid rgba(168, 132, 98, 0.4)",
                ),
                border_radius="50%",
                width="36px",
                height="36px",
                flex_shrink="0",
            ),
            align_items="center",
            width="100%",
        ),
        rx.vstack(
            rx.text(
                State.month_name + " " + State.current_year.to_string(),
                font_size="16px",
                font_weight="600",
                color=theme_color(State.is_light_theme, "text_accent"),
                margin_bottom="10px",
                text_align="center",
                width="100%",
            ),
            rx.grid(
                *[
                    rx.text(
                        day,
                        color=theme_color(State.is_light_theme, "text_muted"),
                        font_size="11px",
                        text_align="center",
                    )
                    for day in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
                ],
                columns="7",
                width="100%",
                margin_bottom="8px",
            ),
            rx.grid(
                rx.foreach(
                    State.calendar_days,
                    lambda day: rx.box(
                        day,
                        color=rx.cond(
                            day == "",
                            "transparent",
                            rx.cond(
                                day == State.today,
                                theme_color(State.is_light_theme, "calendar_today_text"),
                                theme_color(State.is_light_theme, "text_main"),
                            ),
                        ),
                        background=rx.cond(
                            day == "",
                            "transparent",
                            rx.cond(
                                day == State.today,
                                theme_color(State.is_light_theme, "calendar_today"),
                                "transparent",
                            ),
                        ),
                        border_radius="50%",
                        display="flex",
                        align_items="center",
                        justify_content="center",
                        height="30px",
                        width="30px",
                        margin="auto",
                        font_size="13px",
                        font_weight=rx.cond(day == State.today, "bold", "normal"),
                    ),
                ),
                columns="7",
                spacing="1",
                width="100%",
                flex="1",
            ),
            width="100%",
            aspect_ratio="1 / 1",
            background=theme_color(State.is_light_theme, "calendar_bg"),
            border=rx.cond(
                State.is_light_theme,
                "1px solid rgba(173, 143, 110, 0.18)",
                "1px solid rgba(168, 132, 98, 0.2)",
            ),
            border_radius="12px",
            padding="15px",
            margin_bottom="10px",
        ),
        rx.dialog.root(
            rx.dialog.trigger(
                rx.button(
                    "Развернуть календарь",
                    width="100%",
                    background=theme_color(State.is_light_theme, "soft_button_bg"),
                    border=rx.cond(
                        State.is_light_theme,
                        "1px solid rgba(173, 143, 110, 0.35)",
                        "1px solid rgba(168, 132, 98, 0.4)",
                    ),
                    color=theme_color(State.is_light_theme, "text_accent"),
                    padding="12px",
                    border_radius="8px",
                    font_size="13px",
                    font_weight="600",
                    text_transform="uppercase",
                    letter_spacing="1px",
                    cursor="pointer",
                ),
            ),
            rx.dialog.content(
                rx.hstack(
                    rx.vstack(
                        rx.hstack(
                            rx.button(
                                "←",
                                on_click=State.prev_month,
                                background="none",
                                border="none",
                                color=theme_color(State.is_light_theme, "text_accent"),
                                cursor="pointer",
                                font_size="20px",
                            ),
                            rx.box(
                                rx.heading(
                                    State.month_name + " " + State.current_year.to_string(),
                                    font_size="20px",
                                    color=theme_color(State.is_light_theme, "text_accent"),
                                ),
                                width="160px",
                                display="flex",
                                justify_content="center",
                            ),
                            rx.button(
                                "→",
                                on_click=State.next_month,
                                background="none",
                                border="none",
                                color=theme_color(State.is_light_theme, "text_accent"),
                                cursor="pointer",
                                font_size="20px",
                            ),
                            rx.spacer(),
                            rx.dialog.close(
                                rx.button(
                                    "✕",
                                    background="none",
                                    border="none",
                                    color=theme_color(State.is_light_theme, "text_muted"),
                                    cursor="pointer",
                                )
                            ),
                            width="100%",
                            margin_bottom="20px",
                            align_items="center",
                        ),
                        rx.grid(
                            *[
                                rx.text(
                                    day,
                                    color=theme_color(State.is_light_theme, "text_muted"),
                                    font_size="12px",
                                    text_align="center",
                                )
                                for day in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
                            ],
                            columns="7",
                            spacing="2",
                            width="100%",
                            margin_bottom="10px",
                        ),
                        rx.grid(
                            rx.foreach(
                                State.calendar_days,
                                lambda day: rx.box(
                                    day,
                                    background=rx.cond(
                                        day == "",
                                        "transparent",
                                        rx.cond(
                                            State.selected_day == day,
                                            theme_color(State.is_light_theme, "calendar_selected"),
                                            theme_color(State.is_light_theme, "calendar_cell"),
                                        ),
                                    ),
                                    color=rx.cond(
                                        day == "",
                                        "transparent",
                                        rx.cond(
                                            State.selected_day == day,
                                            theme_color(State.is_light_theme, "calendar_selected_text"),
                                            theme_color(State.is_light_theme, "text_main"),
                                        ),
                                    ),
                                    font_weight=rx.cond(
                                        State.selected_day == day, "bold", "normal"
                                    ),
                                    border_radius="8px",
                                    display="flex",
                                    align_items="center",
                                    justify_content="center",
                                    cursor=rx.cond(day == "", "default", "pointer"),
                                    _hover={
                                        "background": rx.cond(
                                            day == "",
                                            "transparent",
                                            theme_color(
                                                State.is_light_theme, "calendar_selected"
                                            ),
                                        )
                                    },
                                    on_click=State.select_day(day),
                                    height="50px",
                                ),
                            ),
                            columns="7",
                            spacing="2",
                            flex="1",
                            width="100%",
                        ),
                        flex="1",
                        padding="30px",
                        border_right=rx.cond(
                            State.is_light_theme,
                            "1px solid rgba(173, 143, 110, 0.18)",
                            "1px solid rgba(168, 132, 98, 0.2)",
                        ),
                        height="100%",
                    ),
                    rx.vstack(
                        rx.text(
                            rx.cond(
                                State.selected_day == "",
                                "Выберите день",
                                f"События на {State.selected_day} {State.month_name_genitive}",
                            ),
                            font_size="14px",
                            text_transform="uppercase",
                            color=theme_color(State.is_light_theme, "text_muted"),
                            margin_bottom="20px",
                            letter_spacing="1px",
                        ),
                        rx.cond(
                            State.api_error != "",
                            rx.text(
                                State.api_error,
                                color=theme_color(State.is_light_theme, "error_text"),
                                font_size="12px",
                            ),
                            rx.fragment(),
                        ),
                        rx.foreach(
                            State.events,
                            lambda event: rx.box(
                                rx.text(
                                    event["time"],
                                    color=theme_color(State.is_light_theme, "text_accent"),
                                    font_size="12px",
                                    display="block",
                                    margin_bottom="4px",
                                ),
                                rx.text(
                                    event["text"],
                                    color=theme_color(State.is_light_theme, "text_main"),
                                    font_size="14px",
                                ),
                                background=theme_color(State.is_light_theme, "event_bg"),
                                border_left=rx.cond(
                                    State.is_light_theme,
                                    "3px solid #c3a27b",
                                    "3px solid #a88462",
                                ),
                                padding="12px",
                                border_radius="6px",
                                margin_bottom="10px",
                                width="100%",
                            ),
                        ),
                        width="300px",
                        padding="30px",
                        background=theme_color(State.is_light_theme, "calendar_bg"),
                        height="100%",
                        flex_shrink="0",
                    ),
                    height="500px",
                    width="800px",
                    max_width="90vw",
                ),
                background=theme_color(State.is_light_theme, "modal_content"),
                border=rx.cond(
                    State.is_light_theme,
                    "1px solid rgba(173, 143, 110, 0.25)",
                    "1px solid rgba(168, 132, 98, 0.4)",
                ),
                padding="0",
                max_width="fit-content",
                overflow="hidden",
            ),
        ),
        rx.text(
            "Ближайшие",
            font_size="13px",
            font_weight="600",
            text_transform="uppercase",
            color=theme_color(State.is_light_theme, "text_accent"),
            letter_spacing="1px",
            margin_top="16px",
            margin_bottom="8px",
        ),
        rx.vstack(
            rx.box(
                rx.text(
                    "Сегодня, 15:00",
                    color=theme_color(State.is_light_theme, "text_accent"),
                    font_weight="600",
                    font_size="11px",
                    text_transform="uppercase",
                    display="block",
                    margin_bottom="4px",
                ),
                rx.text(
                    "Встреча с командой",
                    color=theme_color(State.is_light_theme, "text_main"),
                    font_size="13px",
                    line_height="1.4",
                ),
                background=theme_color(State.is_light_theme, "item_bg"),
                border_left=rx.cond(
                    State.is_light_theme,
                    "3px solid #c3a27b",
                    "3px solid #a88462",
                ),
                border_radius="8px",
                padding="14px",
                width="100%",
                cursor="pointer",
            ),
            rx.box(
                rx.text(
                    "Завтра, 10:00",
                    color=theme_color(State.is_light_theme, "text_accent"),
                    font_weight="600",
                    font_size="11px",
                    text_transform="uppercase",
                    display="block",
                    margin_bottom="4px",
                ),
                rx.text(
                    "Позвонить Ивану",
                    color=theme_color(State.is_light_theme, "text_main"),
                    font_size="13px",
                    line_height="1.4",
                ),
                background=theme_color(State.is_light_theme, "item_bg"),
                border_left=rx.cond(
                    State.is_light_theme,
                    "3px solid #c3a27b",
                    "3px solid #a88462",
                ),
                border_radius="8px",
                padding="14px",
                width="100%",
                cursor="pointer",
            ),
            width="100%",
            gap="12px",
        ),
        width="340px",
        height="100vh",
        background=theme_color(State.is_light_theme, "panel_bg"),
        style={"backdropFilter": "blur(16px)", "WebkitBackdropFilter": "blur(16px)"},
        border_left=rx.cond(
            State.is_light_theme,
            "1px solid rgba(152, 119, 82, 0.14)",
            "1px solid rgba(232, 216, 195, 0.1)",
        ),
        padding="24px 20px",
        gap="12px",
        z_index="10",
    )
