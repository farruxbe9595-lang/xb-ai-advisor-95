import html
def esc(value:object)->str: return html.escape(str(value), quote=False)
