import reflex as rx

config = rx.Config(
    app_name="web_app",
    env_file=".env",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
        rx.plugins.RadixThemesPlugin(),
    ]
)