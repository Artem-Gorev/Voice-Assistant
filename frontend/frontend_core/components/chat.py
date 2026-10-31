import reflex as rx

from ..state import State
from .common import glass_card
from .calendar import mini_calendar, workload_panel

def render_message(msg: dict) -> rx.Component:

    is_user = msg["role"] == "user"

    return rx.box(

        rx.text(msg["text"], white_space="pre-wrap", line_height="1.55"),

        background=rx.cond(

            is_user,

            "linear-gradient(145deg, rgba(112,151,239,0.94), rgba(104,128,221,0.92))",

            "light-dark(rgba(255,255,255,0.72), rgba(255,255,255,0.075))",

        ),

        color=rx.cond(is_user, "#ffffff", "light-dark(#34415a, #e9efff)"),

        padding="14px 18px", border_radius="16px",

        border_bottom_right_radius=rx.cond(is_user, "6px", "20px"),

        border_bottom_left_radius=rx.cond(is_user, "20px", "6px"),

        border=rx.cond(is_user, "1px solid rgba(255,255,255,0.22)",

                       "1px solid light-dark(rgba(255,255,255,0.82), rgba(255,255,255,0.12))"),

        max_width="min(78%, 680px)",

        align_self=rx.cond(is_user, "flex-end", "flex-start"),

        box_shadow="0 8px 24px rgba(20,35,65,0.08)",

        style={"backdropFilter": "blur(18px)", "WebkitBackdropFilter": "blur(18px)",
               "animation": "messageIn 180ms ease-out"},

    )

def chat_view():

    return rx.hstack(

        rx.vstack(

glass_card(

                rx.scroll_area(

                    rx.vstack(
                        rx.foreach(State.messages, render_message),
                        rx.cond(
                            State.is_processing,
                            rx.text("Запрос обрабатывается…", color="#9bb9ff",
                                    font_size="13px", padding="8px 12px",
                                    animation="messageIn 180ms ease-out"),
                            rx.fragment(),
                        ),
                        width="100%", padding="12px", gap="10px"),

                    type="scroll", scrollbars="vertical",

                    style={"height": "100%", "minHeight": "0", "minWidth": "0",
                           "flex": "1 1 0%", "overflowY": "auto", "overflowX": "hidden"}),

                width="100%", flex="1", min_height="0", height="0px", padding="3px",
                style={"minHeight": "0", "overflow": "hidden", "flex": "1 1 0%"}),

            rx.cond(
                State.startup_status != "",
                rx.text(State.startup_status, font_size="11px",
                        color="light-dark(#71809c, #aab7d5)", padding_x="10px"),
                rx.fragment(),
            ),

            glass_card(

                rx.form(

                    rx.hstack(
                        rx.button(
                            rx.icon(tag=rx.cond(State.voice_output, "volume-2", "volume-x"), size=18),
                            type="button", on_click=State.toggle_voice_output,
                            title=rx.cond(State.voice_output, "Отключить озвучивание", "Включить озвучивание"),
                            background=rx.cond(State.voice_output,
                                "linear-gradient(145deg, #8eb5ff, #6e8bea)",
                                "light-dark(rgba(103,143,235,0.13), rgba(123,158,255,0.16))"),
                            color=rx.cond(State.voice_output, "#ffffff", "#82a6ff"),
                            border_radius="12px", width="42px", height="42px",
                        ),
                        rx.box(
                            rx.text_area(
                                placeholder=rx.cond(State.is_recording, "",
                                                   "Напишите сообщение или задайте вопрос…"),
                                value=State.user_input, on_change=State.set_user_input,
                                enter_key_submit=True, flex="1",
                                background="transparent !important", border="none !important",
                                box_shadow="none !important", outline="none !important",
                                color="light-dark(#253047, #f2f5ff)",
                                resize="none", rows="1", auto_height=True,
                                height="auto", max_height="132px", overflow_y="auto",
                                min_height="42px", width="100%", padding="10px 4px",
                                key=State.input_key,
                                style={"overflowY": "auto", "overflowX": "hidden",
                                       "resize": "none", "scrollbarWidth": "none",
                                       "msOverflowStyle": "none",
                                       "&::-webkit-scrollbar": {"display": "none", "width": "0px"}},
                                disabled=State.is_recording),
                            rx.cond(
                                State.is_recording,
                                rx.hstack(
                                    rx.hstack(*[
                                        rx.box(id=f"voice-wave-{i}", width="3px", height="4px",
                                               min_height="4px",
                                               background="linear-gradient(180deg, #b5cbff, #6e91f1)",
                                               border_radius="full", transition="height 70ms linear",
                                               box_shadow="0 0 7px rgba(123,158,255,0.35)")
                                        for i in range(36)],
                                        width="100%", height="28px", align="center",
                                        justify="between", spacing="1", flex="1",
                                        min_width="0", overflow="hidden"),
                                    position="absolute", left="7px", right="7px",
                                    top="50%", width="auto", transform="translateY(-50%)",
                                    height="38px", padding="0 10px", align="center",
                                    justify="center", spacing="0", border_radius="11px",
                                    border="1px solid light-dark(rgba(117,145,205,0.24), rgba(150,174,239,0.2))",
                                    background="linear-gradient(110deg, light-dark(rgba(233,239,250,0.98), rgba(34,42,62,0.98)), light-dark(rgba(222,232,250,0.92), rgba(28,37,58,0.98)))",
                                    box_shadow="inset 0 1px 0 rgba(255,255,255,0.14), 0 5px 18px rgba(15,25,50,0.14)",
                                    style={"pointerEvents": "none", "animation": "messageIn 180ms ease-out"}),
                                rx.fragment()),
                            position="relative", flex="1", min_width="0",
                            background="light-dark(rgba(226,233,246,0.24), rgba(255,255,255,0.025))",
                            border_radius="13px", padding="0 8px"),
                        rx.cond(
                            State.is_recording,
                            rx.button(rx.icon(tag="x", size=25), type="button",
                                      on_click=State.cancel_recording,
                                      background="light-dark(rgba(225,67,87,0.14), rgba(255,83,105,0.20))",
                                      color="light-dark(#c52f49, #ff7186)",
                                      border="2px solid light-dark(rgba(197,47,73,0.48), rgba(255,113,134,0.62))",
                                      border_radius="12px", width="42px", height="42px",
                                      box_shadow="0 2px 10px rgba(220,55,80,0.18)"),
                            rx.button(rx.icon(tag="mic", size=18), type="button",
                                      on_click=State.start_recording,
                                      disabled=State.is_processing,
                                      background="light-dark(rgba(103,143,235,0.13), rgba(123,158,255,0.16))",
                                      color="#82a6ff", border_radius="12px",
                                      width="42px", height="42px")),
                        rx.cond(
                            State.is_recording,
                            rx.text("00:00", id="voice-recording-timer",
                                    font_size="12px", font_weight="700", font_family="monospace",
                                    color="#89a9ff", min_width="42px"),
                            rx.fragment()),
                        rx.button(rx.icon(tag=rx.cond(State.is_recording, "send", "arrow-up"), size=19),
                                  type="button",
                                  title=rx.cond(State.is_recording, "Отправить голосовое сообщение", "Отправить сообщение"),
                                  on_click=rx.cond(State.is_recording, State.stop_recording, State.send_message),
                                  disabled=State.is_processing,
                                  background="linear-gradient(145deg, #8eb5ff, #6e8bea)",
                                  color="#ffffff", border_radius="12px", width="42px", height="42px",
                                  transition="transform 160ms ease, box-shadow 160ms ease, background 160ms ease"),
                        width="100%", align="center", spacing="2"),

                    on_submit=State.send_message, width="100%"),

                width="100%", padding="6px 8px", style={"flexShrink": 0}),

            width="100%", height="100%", flex="1 1 0%", min_height="0",

            style={"display": "flex", "flexDirection": "column",
                   "height": "100%", "minHeight": "0", "minWidth": "0",
                   "maxHeight": "100%", "overflow": "hidden"},

            align="stretch", spacing="2"),

        rx.vstack(

            mini_calendar(),

            glass_card(
                rx.vstack(
                    rx.text("Ближайшие встречи", font_size="10px", letter_spacing="1.4px",
                            font_weight="700", color="light-dark(#71809c, #aab7d5)"),
                    rx.cond(
                        State.upcoming_events.length() > 0,
                        rx.vstack(
                            rx.foreach(
                                State.upcoming_events,
                                lambda event: rx.hstack(
                                    rx.icon(tag="calendar-days", color="#789df3", size=17),
                                    rx.vstack(
                                        rx.text(event["date_label"], font_size="11px",
                                                color="light-dark(#71809c, #aab7d5)"),
                                        rx.text(event["title"], font_size="13px", font_weight="600",
                                                color="light-dark(#34415a, #eff3ff)"),
                                        spacing="0", align="start",
                                    ),
                                    align="center", spacing="2", width="100%",
                                ),
                            ),
                            width="100%", spacing="3",
                        ),
                        rx.text("Ближайших встреч нет", font_size="12px",
                                color="light-dark(#8490a5, #9eabc7)"),
                    ),
                    width="100%", spacing="3",
                ),
                padding="11px", width="100%",
            ),

            workload_panel(),

            width="290px", min_width="260px", height="100%",

            align="stretch", spacing="2"),

        width="100%", height="100%", min_height="0", min_width="0",
        align="stretch", spacing="3",
        style={"height": "100%", "minHeight": "0", "minWidth": "0",
               "overflow": "hidden", "alignItems": "stretch"},

    )
