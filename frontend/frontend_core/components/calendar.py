from datetime import datetime

import reflex as rx

from ..state import State
from .common import glass_card


def calendar_grid(days, selectable=False, compact=False):
    shown_month = State.full_month if selectable else State.current_month
    shown_year = State.full_year if selectable else State.current_year
    event_days = State.full_month_event_days if selectable else State.current_month_event_days

    return rx.grid(

        rx.foreach(

            days,

            lambda day, index: rx.box(

                rx.vstack(
                    rx.text(day, font_size="13px" if compact else "14px",
                            font_weight=rx.cond(day == State.today, "700", "500")),
                    rx.cond(
                        (day != "") & event_days.contains(day),
                        rx.box(width="4px", height="4px", border_radius="50%",
                               background=rx.cond(day == State.today, "#ffffff", "#78aefb")),
                        rx.box(width="4px", height="4px"),
                    ),
                    align="center", justify="center", spacing="0",
                ),

                background=rx.cond(

                    day == "", "transparent",

                    rx.cond(

                        (shown_month == datetime.now().month) &

                        (shown_year == datetime.now().year) &

                        (day == State.today),

                        "linear-gradient(145deg, #78aefb, #657fe8)",

                        rx.cond(State.selected_day == day,

                                "light-dark(rgba(93,139,226,0.20), rgba(117,158,255,0.22))",

                                "transparent")

                    )

                ),

                color=rx.cond(

                    day == "", "transparent",

                    rx.cond(

                        (shown_month == datetime.now().month) &

                        (shown_year == datetime.now().year) &

                        (day == State.today),

                        "#ffffff",
                        rx.cond((index % 7) >= 5, "#55a9ee",
                                "light-dark(#34415a, #e8edff)"))

                ),

                border=rx.cond((day != "") & (State.selected_day != "") & (State.selected_day == day),

                               "1px solid light-dark(rgba(83,125,210,0.45), rgba(130,166,255,0.45))",

                               "1px solid transparent"),

                border_radius="12px" if compact else "15px",

                display="flex", align_items="center", justify_content="center",

                width="100%", height="100%", min_width="0", min_height="0",

                cursor=rx.cond(day == "", "default", "pointer"),

                on_click=State.select_calendar_day(day) if selectable else None,

            )

        ),

        columns="7", width="100%",

        grid_template_columns="repeat(7, minmax(0, 1fr))",

        grid_template_rows="repeat(6, minmax(0, 1fr))",

        gap="4px" if compact else "6px",

        align_content="stretch", justify_content="stretch",

        height="210px" if compact else "100%",

        flex="0 0 auto" if compact else "1",

        min_height="0", min_width="0",

    )


def mini_calendar():

    weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

    return glass_card(

        rx.vstack(

            rx.hstack(

                rx.button(rx.icon(tag="chevron-left", size=26), on_click=State.prev_month,
                          background="light-dark(rgba(226,233,246,0.72), rgba(255,255,255,0.07))",
                          color="light-dark(#53617a, #d5def0)",
                          border="1px solid light-dark(rgba(255,255,255,0.7), rgba(255,255,255,0.1))",
                          border_radius="12px", width="38px", height="38px", flex_shrink="0"),

                rx.text(State.month_name + " " + State.current_year.to_string(),

                        font_weight="700", color="light-dark(#34415a, #eff3ff)",

                        width="170px", min_width="170px", text_align="center", flex_shrink="0"),

                rx.button(rx.icon(tag="chevron-right", size=26), on_click=State.next_month,
                          background="light-dark(rgba(226,233,246,0.72), rgba(255,255,255,0.07))",
                          color="light-dark(#53617a, #d5def0)",
                          border="1px solid light-dark(rgba(255,255,255,0.7), rgba(255,255,255,0.1))",
                          border_radius="12px", width="38px", height="38px", flex_shrink="0"),

                width="100%", align="center", justify="center", spacing="2", wrap="nowrap"),

            rx.grid(*[rx.text(d, text_align="center", font_size="10px",

                              color="light-dark(#8490a5, #9eabc7)") for d in weekdays],

                    columns="7", width="100%", grid_template_columns="repeat(7, minmax(0, 1fr))"),

            calendar_grid(State.calendar_days, compact=True),

            spacing="2", width="100%"),

        padding="10px", width="100%",

    )


def workload_panel():
    return glass_card(
        rx.vstack(
            rx.text("Загруженность недели", font_size="10px", letter_spacing="1.4px",
                    font_weight="700", color="light-dark(#71809c, #aab7d5)"),
            rx.grid(
                rx.foreach(
                    State.week_days_data,
                    lambda day: rx.vstack(
                        rx.text(day["label"], font_size="11px",
                                color="light-dark(#71809c, #aab7d5)"),
                        rx.box(
                            rx.text(day["count"].to(int).to_string(), font_size="11px", font_weight="700",
                                    color=rx.cond(day["count"].to(int) > 0, "#ffffff",
                                                  "light-dark(#71809c, #aab7d5)")),
                            width="100%", height="28px", border_radius="9px",
                            display="flex", align_items="center", justify_content="center",
                            background=rx.cond(
                                day["count"].to(int) > 0,
                                "linear-gradient(145deg, #8eb5ff, #6e8bea)",
                                "light-dark(rgba(112,151,239,0.10), rgba(112,151,239,0.12))",
                            ),
                        ),
                        align="center", spacing="1",
                    ),
                ),
                columns="7", width="100%", gap="5px",
                grid_template_columns="repeat(7, minmax(0, 1fr))",
            ),
            spacing="2", width="100%",
        ),
        padding="10px", width="100%",
    )


def week_view():

    return glass_card(

        rx.vstack(

            rx.hstack(

                rx.button(rx.icon(tag="chevron-left", size=26), on_click=State.previous_week,

                          background="light-dark(rgba(226,233,246,0.72), rgba(255,255,255,0.07))",

                          color="light-dark(#53617a, #d5def0)", border="1px solid light-dark(rgba(255,255,255,0.7), rgba(255,255,255,0.1))",

                          border_radius="12px", width="38px", height="38px"),

                rx.heading(State.week_range_label, size="4",

                           color="light-dark(#34415a, #eff3ff)"),

                rx.button(rx.icon(tag="chevron-right", size=26), on_click=State.next_week,

                          background="light-dark(rgba(226,233,246,0.72), rgba(255,255,255,0.07))",

                          color="light-dark(#53617a, #d5def0)", border="1px solid light-dark(rgba(255,255,255,0.7), rgba(255,255,255,0.1))",

                          border_radius="12px", width="38px", height="38px"),

                rx.spacer(),

                width="100%", align="center"),

            rx.hstack(
                rx.box(width="58px", min_width="58px"),
                rx.grid(
                    rx.foreach(
                        State.week_days_data,
                        lambda day: rx.vstack(
                            rx.text(day["label"], font_size="10px",
                                    color="light-dark(#8490a5, #9eabc7)"),
                            rx.text(day["date"], font_size="18px", font_weight="700",
                                    color=rx.cond(day["is_today"], "#78aefb",
                                                  "light-dark(#34415a, #eff3ff)")),
                            width="100%", min_width="0", align="center", spacing="0",
                            background=rx.cond(
                                day["is_today"],
                                "light-dark(rgba(120,174,251,0.16), rgba(120,174,251,0.18))",
                                "transparent",
                            ),
                            padding="9px 2px", border_radius="13px 13px 0 0",
                            border=rx.cond(
                                day["is_today"],
                                "1px solid light-dark(rgba(120,174,251,0.22), rgba(120,174,251,0.24))",
                                "1px solid transparent",
                            ),
                        ),
                    ),
                    columns="7", width="100%", flex="1", min_width="0",
                    grid_template_columns="repeat(7, minmax(0, 1fr))", gap="0px"),
                width="100%", align="stretch", spacing="0"),

            rx.hstack(

              rx.vstack(

                *[rx.text(f"{hour:02d}:00", font_size="10px", line_height="1",

                          color="light-dark(#8490a5, #9eabc7)", height="42px",

                          width="46px", text_align="right", padding_top="0px")

                  for hour in range(7, 22)],

                width="58px", min_width="58px", align="end", spacing="0",

                padding_top="4px", padding_right="12px"),

              rx.grid(

                rx.foreach(

                    State.week_days_data,

                    lambda day: rx.box(
                        rx.foreach(
                            State.calendar_events,
                            lambda event: rx.cond(
                                event["date"] == day["iso"],
                                rx.box(
                                    rx.vstack(
                                        rx.text(event["title"], font_size="11px", font_weight="600",
                                                overflow="hidden", white_space="nowrap",
                                                text_overflow="ellipsis"),
                                        rx.text(event["time"], font_size="10px"),
                                        spacing="1", align="start",
                                    ),
                                    position="absolute", top=event["top"], left="3px", right="3px",
                                    height=event["height"], min_height="30px", overflow="hidden",
                                    background=rx.cond(
                                        event["active"].to(bool),
                                        "light-dark(rgba(112,151,239,0.25), rgba(112,151,239,0.28))",
                                        "light-dark(rgba(130,140,158,0.18), rgba(130,140,158,0.20))",
                                    ),
                                    border="1px solid light-dark(rgba(112,151,239,0.45), rgba(112,151,239,0.48))",
                                    border_radius="9px", padding="6px", z_index="2",
                                ),
                                rx.fragment(),
                            ),
                        ),
                        rx.cond(
                            day["is_today"],
                            rx.box(
                                rx.box(width="7px", height="7px", border_radius="50%",
                                       background="#3988f6", position="absolute",
                                       left="-3px", top="-3px"),
                                width="100%", height="2px", background="#3988f6",
                                position="absolute", left="0", right="0", top="0px",
                                id="aura-current-time-line", z_index="5",
                                box_shadow="0 0 8px rgba(57,136,246,0.45)"),
                            rx.fragment(),
                        ),
                        width="100%", height="630px", min_height="630px",
                        position="relative", padding="4px", overflow="hidden",
                        background="transparent", border_radius="12px 12px 0 0",
                        border_left="1px solid light-dark(rgba(80,100,140,0.12), rgba(255,255,255,0.08))",
                        style={"backgroundImage": rx.cond(
                            day["is_today"],
                            "linear-gradient(180deg, light-dark(rgba(120,174,251,0.16), rgba(120,174,251,0.18)) 0%, light-dark(rgba(120,174,251,0.045), rgba(120,174,251,0.055)) 100%), repeating-linear-gradient(to bottom, transparent 0px, transparent 40px, light-dark(rgba(80,100,140,0.22), rgba(255,255,255,0.15)) 42px)",
                            "repeating-linear-gradient(to bottom, transparent 0px, transparent 41px, light-dark(rgba(80,100,140,0.18), rgba(255,255,255,0.12)) 42px)")},
                    ),

                ),

                columns="7", width="100%", flex="1", min_width="0",

                grid_template_columns="repeat(7, minmax(0, 1fr))", gap="0px"),

              width="100%", align="start", spacing="0"),

            width="100%", spacing="2"),

        padding="12px", width="100%", overflow_x="auto",

        style={"scrollbarWidth": "none", "msOverflowStyle": "none",

               "&::-webkit-scrollbar": {"display": "none", "width": "0px", "height": "0px"}})


def calendar_view():

    return rx.vstack(

        rx.hstack(

            rx.hstack(
                rx.heading("Календарь", size="6", color="light-dark(#253047, #f3f6ff)"),
                rx.button("Сегодня", on_click=State.go_to_current_week,
                          background="linear-gradient(145deg, #8eb5ff, #6e8bea)",
                          color="#ffffff", border_radius="10px", padding="7px 11px"),
                spacing="3", align="center"),

            rx.spacer(),

            rx.hstack(

                rx.button("Месяц", on_click=lambda: State.set_calendar_mode("month"),

                          background=rx.cond(
                              State.calendar_mode == "month",
                              "linear-gradient(145deg, #8eb5ff, #6e8bea)",
                              "light-dark(rgba(226,233,246,0.55), rgba(255,255,255,0.05))",
                          ),
                          color=rx.cond(
                              State.calendar_mode == "month",
                              "#ffffff",
                              "light-dark(#53617a, #c4cee3)",
                          ),
                          border=rx.cond(
                              State.calendar_mode == "month",
                              "1px solid rgba(255,255,255,0.28)",
                              "1px solid light-dark(rgba(255,255,255,0.55), rgba(255,255,255,0.08))",
                          ),

                          border_radius="11px", padding="7px 13px", box_shadow=rx.cond(State.calendar_mode == "month", "0 3px 12px rgba(85,120,200,0.22)", "none")),

                rx.button("Неделя", on_click=lambda: State.set_calendar_mode("week"),

                          background=rx.cond(
                              State.calendar_mode == "week",
                              "linear-gradient(145deg, #8eb5ff, #6e8bea)",
                              "light-dark(rgba(226,233,246,0.55), rgba(255,255,255,0.05))",
                          ),
                          color=rx.cond(
                              State.calendar_mode == "week",
                              "#ffffff",
                              "light-dark(#53617a, #c4cee3)",
                          ),
                          border=rx.cond(
                              State.calendar_mode == "week",
                              "1px solid rgba(255,255,255,0.28)",
                              "1px solid light-dark(rgba(255,255,255,0.55), rgba(255,255,255,0.08))",
                          ),

                          border_radius="11px", padding="7px 13px", box_shadow=rx.cond(State.calendar_mode == "week", "0 3px 12px rgba(85,120,200,0.22)", "none")),

                spacing="1"),

            width="100%", align="center", wrap="wrap"),

        rx.cond(

            State.calendar_mode == "month",

            rx.hstack(

                glass_card(

                    rx.vstack(

                        rx.hstack(

                            rx.button(rx.icon(tag="chevron-left", size=26), on_click=State.full_prev_month,

                                      background="light-dark(rgba(226,233,246,0.72), rgba(255,255,255,0.07))",

                                      color="light-dark(#53617a, #d5def0)", border="1px solid light-dark(rgba(255,255,255,0.7), rgba(255,255,255,0.1))",

                                      border_radius="12px", width="38px", min_width="38px", height="38px", flex_shrink="0"),

                            rx.box(
                                rx.heading(
                                    State.full_month_name + " " + State.full_year.to_string(),
                                    size="5",
                                    color="light-dark(#34415a, #eff3ff)",
                                    text_align="center",
                                ),

                                width="250px",
                                min_width="250px",
                                text_align="center",
                                flex_shrink="0",
                            ),

                            rx.button(rx.icon(tag="chevron-right", size=26), on_click=State.full_next_month,

                                      background="light-dark(rgba(226,233,246,0.72), rgba(255,255,255,0.07))",

                                      color="light-dark(#53617a, #d5def0)", border="1px solid light-dark(rgba(255,255,255,0.7), rgba(255,255,255,0.1))",

                                      border_radius="12px", width="38px", min_width="38px", height="38px", flex_shrink="0"),

                            width="100%", justify="center", align="center", spacing="3", wrap="nowrap"),

                        rx.grid(*[

                            rx.text(day, color="light-dark(#8490a5, #9eabc7)",

                                    font_size="12px", font_weight="700", text_align="center")

                            for day in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]],

                            columns="7", width="100%",

                            grid_template_columns="repeat(7, minmax(0, 1fr))", gap="6px"),

                        calendar_grid(State.full_calendar_days, selectable=True),

                        width="100%", height="100%", min_height="0", spacing="2",
                        style={"display": "flex", "flexDirection": "column", "minHeight": "0"}),

                    width="58%", padding="14px", min_height="min(360px, 64vh)", height="64vh",
                    style={"display": "flex", "flexDirection": "column", "minHeight": "min(360px, 64vh)",
                           "maxHeight": "64vh"}),

                glass_card(

                    rx.vstack(

                        rx.text("ВЫБРАННАЯ ДАТА", font_size="10px", letter_spacing="1.5px",

                                font_weight="700", color="light-dark(#71809c, #aab7d5)"),

                        rx.heading(State.selected_date_label, size="5",

                                   color="light-dark(#34415a, #eff3ff)"),

                        rx.foreach(
                            State.selected_day_events,
                            lambda event: rx.text(
                                event,
                                font_size="13px",
                                font_weight="500",
                                color="light-dark(#34415a, #eff3ff)",
                            ),
                        ),

                        rx.cond(State.selected_day_events.length() == 0,
                                rx.text("На эту дату событий нет.", font_size="13px",
                                        color="light-dark(#8994a9, #98a6c3)"),
                                rx.fragment()),

                        align="start", width="100%", spacing="3"),

                    flex="1", padding="16px", min_height="min(360px, 64vh)", height="64vh",
                    style={"minHeight": "min(360px, 64vh)", "maxHeight": "64vh"}),

                width="100%", align="stretch", spacing="3"),

            week_view()),

        width="100%", height="100%", flex="1", min_height="0",

        align="stretch", spacing="2")
