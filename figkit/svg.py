from xml.sax.saxutils import escape


def document(
    width: float, height: float, title: str, desc: str, css: str, defs: str, body: str,
    freeze_at: float | None = None,
) -> str:
    if freeze_at is not None:
        css += "*{animation-play-state:paused!important}"
    css += "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:g} {height:g}" '
        f'width="{width:g}" height="{height:g}" role="img" aria-labelledby="title desc">'
        f'<title id="title">{escape(title)}</title><desc id="desc">{escape(desc)}</desc>'
        f"<style>{css}</style><defs>{defs}</defs>{body}</svg>\n"
    )


def delay(seconds: float, freeze_at: float | None) -> str:
    return f"animation-delay:{seconds - (freeze_at or 0.0):.3f}s"
