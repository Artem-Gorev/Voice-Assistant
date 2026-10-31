import reflex as rx

from ..state import State

style = {

    "::-webkit-scrollbar": {"width": "0px", "height": "0px", "display": "none"},

    "@keyframes pulse": {

        "0%": {"boxShadow": "0 0 0 0 rgba(255, 77, 77, 0.55)"},

        "70%": {"boxShadow": "0 0 0 8px rgba(255, 77, 77, 0)"},

        "100%": {"boxShadow": "0 0 0 0 rgba(255, 77, 77, 0)"},

    },

    "@keyframes messageIn": {
        "0%": {"opacity": "0", "transform": "translateY(6px)"},
        "100%": {"opacity": "1", "transform": "translateY(0)"},
    },

    "@keyframes recordingGlow": {
        "0%": {"boxShadow": "0 0 0 0 rgba(120,157,243,0.52)", "transform": "scale(0.92)"},
        "65%": {"boxShadow": "0 0 0 7px rgba(120,157,243,0)", "transform": "scale(1.08)"},
        "100%": {"boxShadow": "0 0 0 0 rgba(120,157,243,0)", "transform": "scale(0.92)"},
    },

}

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

def glass_card(*children, **kwargs):

    base = {

        "background": "light-dark(rgba(255,255,255,0.58), rgba(30,34,46,0.48))",

        "border": "1px solid light-dark(rgba(255,255,255,0.78), rgba(255,255,255,0.13))",

        "border_radius": "18px",
        "transition": "transform 180ms ease, box-shadow 180ms ease, background 180ms ease",

        "box_shadow": "0 18px 55px rgba(0,0,0,0.10), inset 0 1px 0 rgba(255,255,255,0.35)",

        "style": {"backdropFilter": "blur(28px) saturate(155%)", "WebkitBackdropFilter": "blur(28px) saturate(155%)"},

    }

    base.update(kwargs)

    return rx.box(*children, **base)

def nav_button(label: str, icon: str, value: str):

    return rx.button(

        rx.hstack(rx.icon(tag=icon, size=17), rx.text(label, font_size="14px", font_weight="600"),

                  align="center", spacing="2"),

        on_click=State.show_chat if value == "chat" else State.show_calendar,

        background=rx.cond(

            State.active_view == value,

            "light-dark(rgba(255,255,255,0.82), rgba(255,255,255,0.16))",

            "transparent",

        ),

        color="light-dark(#253047, #f2f5ff)",

        border=rx.cond(State.active_view == value,

                       "1px solid light-dark(rgba(255,255,255,0.95), rgba(255,255,255,0.18))",

                       "1px solid transparent"),

        border_radius="12px", padding="10px 16px", cursor="pointer",

        box_shadow=rx.cond(State.active_view == value, "0 4px 18px rgba(0,0,0,0.08)", "none"),

        transition="all 180ms ease",

    )
