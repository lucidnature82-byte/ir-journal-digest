import json
import logging
import shutil
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
DOCS_DIR = BASE_DIR / "docs"


def _format_month_ko(month_str: str) -> str:
    dt = datetime.strptime(month_str, "%Y-%m")
    return f"{dt.year}년 {dt.month}월"


def _format_authors(authors: list[str], max_n: int = 3) -> str:
    if not authors:
        return ""
    if len(authors) <= max_n:
        return ", ".join(authors)
    return ", ".join(authors[:max_n]) + " et al."


def _sort_articles(articles: list[dict]) -> list[dict]:
    interest = [a for a in articles if a.get("is_interest")]
    other = [a for a in articles if not a.get("is_interest")]
    interest.sort(key=lambda x: x.get("pub_date", ""), reverse=True)
    other.sort(key=lambda x: x.get("pub_date", ""), reverse=True)
    return interest + other


def _build_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["format_authors"] = _format_authors
    return env


def render_all(data_dir: Path) -> None:
    env = _build_env()

    months_data = []
    for data_file in sorted(data_dir.glob("*.json"), reverse=True):
        month_str = data_file.stem
        with open(data_file, encoding="utf-8") as f:
            raw = json.load(f)
        articles = _sort_articles(raw)
        interest_count = sum(1 for a in articles if a.get("is_interest"))
        months_data.append({
            "month": month_str,
            "month_label": _format_month_ko(month_str),
            "articles": articles,
            "count": len(articles),
            "interest_count": interest_count,
        })

    if not months_data:
        logger.warning("No data files found — skipping render.")
        return

    # Ensure docs structure
    DOCS_DIR.mkdir(exist_ok=True)
    (DOCS_DIR / ".nojekyll").touch()
    archive_dir = DOCS_DIR / "archive"
    archive_dir.mkdir(exist_ok=True)

    # Copy static assets
    static_out = DOCS_DIR / "static"
    static_out.mkdir(exist_ok=True)
    for f in STATIC_DIR.glob("*"):
        shutil.copy2(f, static_out / f.name)

    # Render monthly pages
    month_tmpl = env.get_template("month.html.j2")
    for m in months_data:
        html = month_tmpl.render(**m, now=datetime.now(), root="../")
        out_path = archive_dir / f"{m['month']}.html"
        out_path.write_text(html, encoding="utf-8")
        logger.info("Rendered %s", out_path)

    # Render index
    index_tmpl = env.get_template("index.html.j2")
    html = index_tmpl.render(months=months_data, now=datetime.now(), root="")
    (DOCS_DIR / "index.html").write_text(html, encoding="utf-8")
    logger.info("Rendered docs/index.html")
