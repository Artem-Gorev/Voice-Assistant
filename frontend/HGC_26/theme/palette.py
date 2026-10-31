"""Theme palettes and shared styling helpers."""

import reflex as rx

DARK_COLORS = {
    "bg_gradient": "linear-gradient(135deg, #3a2e26 0%, #2a211b 50%, #1c1612 100%)",
    "panel_bg": "rgba(20, 15, 12, 0.6)",
    "panel_border": "rgba(232, 216, 195, 0.1)",
    "text_main": "#e8d8c3",
    "text_accent": "#c4a787",
    "text_muted": "#7a6656",
    "item_bg": "rgba(60, 45, 35, 0.5)",
    "item_border": "#a88462",
    "user_msg_bg": "rgba(140, 95, 65, 0.85)",
    "user_msg_text": "#ffffff",
    "ai_msg_bg": "rgba(35, 26, 20, 0.9)",
    "ai_msg_text": "#e8d8c3",
    "message_border": "rgba(196, 167, 135, 0.3)",
    "message_shadow": "0 4px 15px rgba(0, 0, 0, 0.3)",
    "input_bg": "rgba(20, 15, 12, 0.8)",
    "input_border": "rgba(168, 132, 98, 0.4)",
    "input_shadow": "0 4px 20px rgba(0, 0, 0, 0.4)",
    "btn_send_bg": "#a88462",
    "btn_send_text": "#1c1612",
    "modal_content": "rgba(35, 26, 20, 0.95)",
    "calendar_bg": "rgba(20, 15, 12, 0.5)",
    "calendar_cell": "rgba(60, 45, 35, 0.3)",
    "calendar_selected": "#a88462",
    "calendar_selected_text": "#1c1612",
    "calendar_today": "#a88462",
    "calendar_today_text": "#ffffff",
    "event_bg": "rgba(60, 45, 35, 0.6)",
    "soft_button_bg": "rgba(168, 132, 98, 0.15)",
    "soft_button_active_bg": "rgba(168, 132, 98, 0.35)",
    "soft_button_border": "rgba(168, 132, 98, 0.4)",
    "recording_bg": "rgba(180, 70, 60, 0.8)",
    "error_text": "#fca5a5",
}

LIGHT_COLORS = {
    "bg_gradient": "linear-gradient(135deg, #f3e8d7 0%, #eee0cc 55%, #f7efe5 100%)",
    "panel_bg": "rgba(249, 243, 234, 0.92)",
    "panel_border": "rgba(152, 119, 82, 0.14)",
    "text_main": "#53483c",
    "text_accent": "#92714e",
    "text_muted": "#9c8b77",
    "item_bg": "rgba(255, 253, 249, 0.92)",
    "item_border": "#c3a27b",
    "user_msg_bg": "#dfc9ad",
    "user_msg_text": "#554a3e",
    "ai_msg_bg": "#fffdf9",
    "ai_msg_text": "#5b5146",
    "message_border": "rgba(167, 137, 104, 0.12)",
    "message_shadow": "0 8px 24px rgba(127, 100, 70, 0.08)",
    "input_bg": "rgba(255, 253, 249, 0.96)",
    "input_border": "rgba(173, 143, 110, 0.16)",
    "input_shadow": "0 8px 26px rgba(127, 100, 70, 0.10)",
    "btn_send_bg": "#b7956c",
    "btn_send_text": "#fffdf9",
    "modal_content": "#fbf7f0",
    "calendar_bg": "rgba(255, 253, 249, 0.65)",
    "calendar_cell": "rgba(221, 203, 178, 0.24)",
    "calendar_selected": "#b7956c",
    "calendar_selected_text": "#fffdf9",
    "calendar_today": "#b7956c",
    "calendar_today_text": "#ffffff",
    "event_bg": "rgba(255, 253, 249, 0.82)",
    "soft_button_bg": "rgba(183, 149, 108, 0.12)",
    "soft_button_active_bg": "rgba(183, 149, 108, 0.25)",
    "soft_button_border": "rgba(173, 143, 110, 0.35)",
    "recording_bg": "#bd6257",
    "error_text": "#b45349",
}


def theme_color(is_light: rx.Var[bool], name: str) -> rx.Var[str]:
    """Return the palette color matching the active UI theme."""
    return rx.cond(is_light, LIGHT_COLORS[name], DARK_COLORS[name])


GLOBAL_STYLE = {"::-webkit-scrollbar": {"display": "none"}}
