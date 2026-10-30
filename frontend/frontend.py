import calendar
from datetime import datetime
import reflex as rx

# Глобальные стили для скроллбара
style = {
    "::-webkit-scrollbar": {
        "display": "none",
    }
}

# --- 1. ПАЛИТРА ЦВЕТОВ ---
COLORS = {
    "bg_gradient": "linear-gradient(135deg, #3a2e26 0%, #2a211b 50%, #1c1612 100%)",
    "panel_bg": "rgba(20, 15, 12, 0.6)",
    "panel_border": "rgba(232, 216, 195, 0.1)",
    "text_main": "#e8d8c3",
    "text_accent": "#c4a787",
    "text_muted": "#7a6656",
    "item_bg": "rgba(60, 45, 35, 0.5)",
    "item_border": "#a88462",
    "user_msg_bg": "rgba(140, 95, 65, 0.85)",
    "ai_msg_bg": "rgba(35, 26, 20, 0.9)",
    "input_bg": "rgba(20, 15, 12, 0.8)",
    "input_border": "rgba(168, 132, 98, 0.4)",
    "btn_send_bg": "#a88462",
    "modal_content": "rgba(35, 26, 20, 0.95)",
}

# --- 2. СОСТОЯНИЕ ---
class State(rx.State):
    messages: list[dict] = [
        {"role": "ai", "text": "Привет! Я твой голосовой ассистент. Чем могу помочь?"},
        {"role": "user", "text": "Напомни мне завтра в 10 утра позвонить Ивану."},
        {"role": "ai", "text": "Готово! Я создал напоминание на завтра, 10:00 — «Позвонить Ивану»."},
    ]
    
    user_input: str = ""
    input_key: int = 0
    selected_day: str = ""
    
    current_month: int = datetime.now().month
    current_year: int = datetime.now().year
    today: str = str(datetime.now().day)

    @rx.var
    def month_name(self) -> str:
        months = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
        return months[self.current_month - 1]

    @rx.var
    def month_name_genitive(self) -> str:
        months = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]
        return months[self.current_month - 1]

    @rx.var
    def calendar_days(self) -> list[str]:
        cal = calendar.monthcalendar(self.current_year, self.current_month)
        days = []
        for week in cal:
            for day in week:
                if day == 0:
                    days.append("")
                else:
                    days.append(str(day))
        return days

    def prev_month(self):
        if self.current_month == 1:
            self.current_month = 12
            self.current_year -= 1
        else:
            self.current_month -= 1
        self.selected_day = ""

    def next_month(self):
        if self.current_month == 12:
            self.current_month = 1
            self.current_year += 1
        else:
            self.current_month += 1
        self.selected_day = ""

    def select_day(self, day: str):
        if day:
            self.selected_day = day

    def set_user_input(self, val: str):
        self.user_input = val

    def send_message(self):
        if self.user_input.strip():
            self.messages = self.messages + [{"role": "user", "text": self.user_input}]
            self.user_input = ""
            self.input_key += 1
            self.messages = self.messages + [{"role": "ai", "text": "Я пока не умею отвечать, но скоро научусь!"}]


# --- 3. КОМПОНЕНТЫ ---
def render_message(msg: dict) -> rx.Component:
    is_user = msg["role"] == "user"
    return rx.box(
        rx.text(msg["text"], white_space="pre-wrap"),
        background=rx.cond(is_user, COLORS["user_msg_bg"], COLORS["ai_msg_bg"]),
        color=rx.cond(is_user, "#ffffff", COLORS["text_main"]),
        padding="16px 20px",
        border_radius="16px",
        border_bottom_right_radius=rx.cond(is_user, "4px", "16px"),
        border_bottom_left_radius=rx.cond(is_user, "16px", "4px"),
        border=rx.cond(is_user, "none", f"1px solid rgba(196, 167, 135, 0.3)"),
        max_width="70%",
        align_self=rx.cond(is_user, "flex-end", "flex-start"),
        box_shadow="0 4px 15px rgba(0, 0, 0, 0.3)",
    )

def index() -> rx.Component:
    return rx.hstack(
        # ЦЕНТРАЛЬНАЯ ПАНЕЛЬ (ЧАТ)
        rx.vstack(
            rx.scroll_area(
                rx.vstack(
                    rx.foreach(State.messages, render_message),
                    width="100%", padding="40px", gap="24px",
                ),
                type="scroll",
                scrollbars="vertical",
                style={"height": "100%", "flex": "1"},
            ),
            rx.form(
                rx.hstack(
                    rx.text_area(
                        placeholder="Введите задачу или вопрос...",
                        value=State.user_input,
                        on_change=State.set_user_input,
                        enter_key_submit=True,
                        flex="1",
                        background="transparent !important",
                        border="none !important",
                        box_shadow="none !important",
                        outline="none !important",
                        color=COLORS["text_main"],
                        _placeholder={"color": COLORS["text_muted"]},
                        resize="none",
                        rows="1",
                        auto_height=True,
                        min_height="0",
                        padding="8px 0",
                        key=State.input_key,
                    ),
                    rx.button(
                        rx.icon(tag="mic", size=20),
                        type="button",
                        background="rgba(168, 132, 98, 0.15)", 
                        color=COLORS["text_accent"],
                        border_radius="50%", 
                        width="42px", 
                        height="42px", 
                        flex_shrink="0",
                    ),
                    rx.button(
                        rx.icon(tag="send", size=20),
                        type="submit",
                        background=COLORS["btn_send_bg"], color="#1c1612",
                        border_radius="50%", width="42px", height="42px", flex_shrink="0",
                    ),
                    width="100%", align_items="flex-end",
                ),
                on_submit=State.send_message,
                width="100%", max_width="800px",
                background=COLORS["input_bg"], border=f"1px solid {COLORS['input_border']}",
                border_radius="24px", padding="8px 8px 8px 20px",
                box_shadow="0 4px 20px rgba(0, 0, 0, 0.4)",
            ),
            width="100%", height="100vh", padding="20px 40px 30px", justify_content="center", align_items="center", flex="1", z_index="5",
        ),

        # ПРАВАЯ ПАНЕЛЬ (КАЛЕНДАРЬ)
        rx.vstack(
            rx.text("Календарь", font_size="13px", font_weight="600", text_transform="uppercase", color=COLORS["text_accent"], letter_spacing="1px", margin_bottom="8px"),
            rx.vstack(
                rx.text(
                    State.month_name + " " + State.current_year.to_string(),
                    font_size="16px", font_weight="600", color=COLORS["text_accent"],
                    margin_bottom="10px", text_align="center", width="100%"
                ),
                rx.grid(
                    *[rx.text(day, color=COLORS["text_muted"], font_size="11px", text_align="center") for day in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]],
                    columns="7", width="100%", margin_bottom="8px",
                ),
                rx.grid(
                    rx.foreach(
                        State.calendar_days,
                        lambda day: rx.box(
                            day,
                            color=rx.cond(day == "", "transparent", rx.cond(day == State.today, "#ffffff", COLORS["text_main"])),
                            background=rx.cond(day == "", "transparent", rx.cond(day == State.today, "#a88462", "transparent")),
                            border_radius="50%", display="flex", align_items="center", justify_content="center",
                            height="30px", width="30px", margin="auto", font_size="13px",
                            font_weight=rx.cond(day == State.today, "bold", "normal"),
                        )
                    ),
                    columns="7", spacing="1", width="100%", flex="1",
                ),
                width="100%", aspect_ratio="1 / 1", background="rgba(20, 15, 12, 0.5)",
                border="1px solid rgba(168, 132, 98, 0.2)", border_radius="12px",
                padding="15px", margin_bottom="10px",
            ),
            rx.dialog.root(
                rx.dialog.trigger(
                    rx.button(
                        "Развернуть календарь", width="100%", background="rgba(168, 132, 98, 0.15)", border="1px solid rgba(168, 132, 98, 0.4)",
                        color=COLORS["text_accent"], padding="12px", border_radius="8px",
                        font_size="13px", font_weight="600", text_transform="uppercase", letter_spacing="1px", cursor="pointer",
                    ),
                ),
                rx.dialog.content(
                    rx.hstack(
                        rx.vstack(
                            rx.hstack(
                                rx.button("←", on_click=State.prev_month, background="none", border="none", color=COLORS["text_accent"], cursor="pointer", font_size="20px"),
                                rx.box(
                                    rx.heading(State.month_name + " " + State.current_year.to_string(), font_size="20px", color=COLORS["text_accent"]),
                                    width="160px", display="flex", justify_content="center",
                                ),
                                rx.button("→", on_click=State.next_month, background="none", border="none", color=COLORS["text_accent"], cursor="pointer", font_size="20px"),
                                rx.spacer(),
                                rx.dialog.close(rx.button("✕", background="none", border="none", color=COLORS["text_muted"], cursor="pointer")),
                                width="100%", margin_bottom="20px", align_items="center",
                            ),
                            rx.grid(
                                rx.text("Пн", color=COLORS["text_muted"], font_size="12px", text_align="center"),
                                rx.text("Вт", color=COLORS["text_muted"], font_size="12px", text_align="center"),
                                rx.text("Ср", color=COLORS["text_muted"], font_size="12px", text_align="center"),
                                rx.text("Чт", color=COLORS["text_muted"], font_size="12px", text_align="center"),
                                rx.text("Пт", color=COLORS["text_muted"], font_size="12px", text_align="center"),
                                rx.text("Сб", color=COLORS["text_muted"], font_size="12px", text_align="center"),
                                rx.text("Вс", color=COLORS["text_muted"], font_size="12px", text_align="center"),
                                columns="7", spacing="2", width="100%", margin_bottom="10px",
                            ),
                            rx.grid(
                                rx.foreach(
                                    State.calendar_days,
                                    lambda day: rx.box(
                                        day,
                                        background=rx.cond(day == "", "transparent", rx.cond(State.selected_day == day, "#a88462", "rgba(60, 45, 35, 0.3)")),
                                        color=rx.cond(day == "", "transparent", rx.cond(State.selected_day == day, "#1c1612", COLORS["text_main"])),
                                        font_weight=rx.cond(State.selected_day == day, "bold", "normal"),
                                        border_radius="8px", display="flex", align_items="center", justify_content="center",
                                        cursor=rx.cond(day == "", "default", "pointer"),
                                        _hover={"background": rx.cond(day == "", "transparent", rx.cond(State.selected_day == day, "#a88462", "rgba(168, 132, 98, 0.3)"))},
                                        on_click=State.select_day(day), height="50px",
                                    )
                                ),
                                columns="7", spacing="2", flex="1", width="100%",
                            ),
                            flex="1", padding="30px", border_right="1px solid rgba(168, 132, 98, 0.2)", height="100%",
                        ),
                        rx.vstack(
                            rx.text(
                                rx.cond(State.selected_day == "", "Выберите день", f"События на {State.selected_day} {State.month_name_genitive}"),
                                font_size="14px", text_transform="uppercase", color=COLORS["text_muted"], margin_bottom="20px", letter_spacing="1px"
                            ),
                            rx.box(
                                rx.text("10:00", color=COLORS["text_accent"], font_size="12px", display="block", margin_bottom="4px"),
                                rx.text("Позвонить Ивану", font_size="14px"),
                                background="rgba(60, 45, 35, 0.6)", border_left="3px solid #a88462", padding="12px", border_radius="6px", margin_bottom="10px", width="100%",
                            ),
                            width="300px", padding="30px", background="rgba(20, 15, 12, 0.5)", height="100%", flex_shrink="0",
                        ),
                        height="500px", width="800px", max_width="90vw",
                    ),
                    background=COLORS["modal_content"], border="1px solid rgba(168, 132, 98, 0.4)", padding="0", max_width="fit-content", overflow="hidden",
                ),
            ),
            rx.text("Ближайшие", font_size="13px", font_weight="600", text_transform="uppercase", color=COLORS["text_accent"], letter_spacing="1px", margin_top="16px", margin_bottom="8px"),
            rx.vstack(
                rx.box(
                    rx.text("Сегодня, 15:00", color=COLORS["text_accent"], font_weight="600", font_size="11px", text_transform="uppercase", display="block", margin_bottom="4px"),
                    rx.text("Встреча с командой", font_size="13px", line_height="1.4"),
                    background=COLORS["item_bg"], border_left=f"3px solid {COLORS['item_border']}", border_radius="8px", padding="14px", width="100%", cursor="pointer",
                ),
                rx.box(
                    rx.text("Завтра, 10:00", color=COLORS["text_accent"], font_weight="600", font_size="11px", text_transform="uppercase", display="block", margin_bottom="4px"),
                    rx.text("Позвонить Ивану", font_size="13px", line_height="1.4"),
                    background=COLORS["item_bg"], border_left=f"3px solid {COLORS['item_border']}", border_radius="8px", padding="14px", width="100%", cursor="pointer",
                ),
                width="100%", gap="12px",
            ),
            width="340px", height="100vh", background=COLORS["panel_bg"],
            style={"backdropFilter": "blur(16px)", "WebkitBackdropFilter": "blur(16px)"},
            border_left=f"1px solid {COLORS['panel_border']}", padding="24px 20px", gap="12px", z_index="10",
        ),
        width="100%", height="100vh", background=COLORS["bg_gradient"], spacing="0", overflow="hidden",
    )

app = rx.App(style=style)
app.add_page(index)