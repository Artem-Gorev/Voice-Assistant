"""Reflex application entry point."""

import reflex as rx

from .pages.home import index
from .theme import GLOBAL_STYLE

app = rx.App(style=GLOBAL_STYLE)
app.add_page(index)
