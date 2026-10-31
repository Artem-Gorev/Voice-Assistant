import sys
from pathlib import Path

import reflex as rx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

config = rx.Config(
    app_name="voice_assistant",
    app_module_import="app",
    frontend_packages=[
        "@tailwindcss/postcss@4.3.0",
        "@tailwindcss/typography@0.5.20",
        "tailwindcss@4.3.0",
    ],
    env_file="../.env",
    plugins=[rx.plugins.RadixThemesPlugin(), rx.plugins.SitemapPlugin()],
)
