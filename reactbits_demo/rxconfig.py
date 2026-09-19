import reflex as rx

config = rx.Config(
    app_name="reactbits_demo",
    plugins=[
        rx.plugins.RadixThemesPlugin(
            theme=rx.theme(appearance="dark", accent_color="violet", gray_color="mauve", radius="large"),
        ),
    ],
    disable_plugins=[rx.plugins.SitemapPlugin],
)
