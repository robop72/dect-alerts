from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")
templates.env.filters["ceil_minutes"] = lambda s: max(1, round(s / 60))
