import reflex as rx

if __package__:
    from .frontend_core.audio_api import audio_api_transformer
    from .frontend_core.components.calendar import calendar_view
    from .frontend_core.components.chat import chat_view
    from .frontend_core.components.common import glass_card, nav_button, style
    from .frontend_core.state import State
else:
    from frontend_core.audio_api import audio_api_transformer
    from frontend_core.components.calendar import calendar_view
    from frontend_core.components.chat import chat_view
    from frontend_core.components.common import glass_card, nav_button, style
    from frontend_core.state import State


def index() -> rx.Component:

    return rx.box(

        rx.vstack(

            glass_card(

                rx.hstack(

                    rx.hstack(

                        rx.box(
                            rx.vstack(*[
                                rx.hstack(*[
                                    rx.box(width="3px", height="3px", border_radius="0px",
                                           background="#7399ef" if pixel == "1" else "transparent")
                                    for pixel in row
                                ], spacing="1")
                                for row in ("01110", "10001", "10000", "10111", "01110")
                            ], spacing="1", align="center", justify="center"),
                            width="38px", height="38px",
                            background="light-dark(rgba(255,255,255,0.85), rgba(130,160,255,0.15))",
                            border="1px solid light-dark(rgba(255,255,255,0.9), rgba(255,255,255,0.16))",
                            border_radius="10px", display="flex", align_items="center",
                            justify_content="center"),

                        rx.text("GORKY", font_size="15px", font_weight="800", letter_spacing="2px",
                                color="light-dark(#2c3a55, #f2f5ff)"),
                        align="center",
                        position="absolute", left="50%",
                        transform="translateX(-50%)"),

                    rx.spacer(),

                    rx.hstack(nav_button("Ассистент", "message-circle", "chat"),

                              nav_button("Календарь", "calendar-days", "calendar"),

                              background="light-dark(rgba(225,232,245,0.58), rgba(10,15,28,0.28))",

                              border="1px solid light-dark(rgba(255,255,255,0.72), rgba(255,255,255,0.09))",

                              border_radius="14px", padding="4px", spacing="1"),

                    width="100%", align="center", wrap="nowrap",
                    position="relative", min_height="48px"),

                width="100%", padding="8px 12px"),

            rx.cond(State.active_view == "chat", chat_view(), calendar_view()),

            width="100%", height="100%", min_height="0", max_width="1180px", padding="12px",

            align="stretch", spacing="2", margin="0 auto",
            style={"display": "flex", "flexDirection": "column", "minHeight": "0",
                   "overflow": "hidden"},

        ),

        width="100%", height="100vh", overflow="hidden",

        background="radial-gradient(ellipse at 12% 8%, light-dark(rgba(160,195,255,0.42), rgba(71,101,171,0.30)), transparent 42%), radial-gradient(ellipse at 90% 88%, light-dark(rgba(202,222,255,0.65), rgba(85,74,145,0.28)), transparent 44%), light-dark(#e8eef8, #101522)",

        color="light-dark(#253047, #f2f5ff)",

        style={**style, "colorScheme": "light dark", "backgroundAttachment": "fixed"},
        on_mount=[State.initialize_app, rx.call_script(r"""
            (() => {
                if (window.__gorkyClockTimer) clearInterval(window.__gorkyClockTimer);
                const updateGorkyClock = () => {
                    const now = new Date();
                    const line = document.getElementById("aura-current-time-line");
                    if (line) {
                        const minutes = Math.max(0, Math.min(14 * 60,
                            now.getHours() * 60 + now.getMinutes() - 7 * 60));
                        line.style.top = (minutes * 0.7 + 4) + "px";
                    }
                };
                updateGorkyClock();
                window.__gorkyClockTimer = setInterval(updateGorkyClock, 1000);
            })();
        """)],

    )


app = rx.App(api_transformer=audio_api_transformer)
app.add_page(index)
