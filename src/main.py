"""Entry point: python -m src.main"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from .config import GEMINI_API_KEY, JOURNALS
from .fetch_pubmed import fetch_articles, search_pmids
from .gemini_client import GeminiClient
from .classify import confirm_with_gemini, keyword_match
from .summarize import summarize_article
from .render import render_all

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"


# ── Logging ───────────────────────────────────────────────────────────────────

def _setup_logging(month_str: str) -> None:
    LOGS_DIR.mkdir(exist_ok=True)
    log_file = LOGS_DIR / f"{month_str}.log"

    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    handlers: list[logging.Handler] = [
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
    logging.basicConfig(level=logging.INFO, format=fmt, handlers=handlers)


# ── Data helpers ──────────────────────────────────────────────────────────────

def _load_existing(data_file: Path) -> dict[str, dict]:
    if not data_file.exists():
        return {}
    with open(data_file, encoding="utf-8") as f:
        articles: list[dict] = json.load(f)
    return {a["pmid"]: a for a in articles}


def _save(data_file: Path, articles: dict[str, dict]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(list(articles.values()), f, ensure_ascii=False, indent=2)


def _needs_processing(article: dict) -> bool:
    s = article.get("summary")
    if s is None:
        return True
    if isinstance(s, dict) and "_error" in s:
        return True
    return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    month_str = datetime.now().strftime("%Y-%m")
    _setup_logging(month_str)
    logger = logging.getLogger(__name__)

    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY is not set. Exiting.")
        sys.exit(1)

    data_file = DATA_DIR / f"{month_str}.json"
    existing = _load_existing(data_file)
    logger.info("Loaded %d existing articles from %s", len(existing), data_file)

    # ── Fetch ─────────────────────────────────────────────────────────────────
    all_articles: dict[str, dict] = {}
    for journal_name, journal_query in JOURNALS.items():
        logger.info("Fetching %s ...", journal_name)
        pmids = search_pmids(journal_query)
        articles = fetch_articles(pmids)
        for a in articles:
            a["journal"] = journal_name
            all_articles[a["pmid"]] = a
        logger.info("  %s: %d articles fetched", journal_name, len(articles))

    # Preserve articles from previous runs that weren't re-fetched
    for pmid, art in existing.items():
        if pmid not in all_articles:
            all_articles[pmid] = art

    # ── Process ───────────────────────────────────────────────────────────────
    to_process = [
        a for pmid, a in all_articles.items()
        if pmid not in existing or _needs_processing(existing[pmid])
    ]

    # Carry over completed summaries from existing data
    for pmid, art in all_articles.items():
        if pmid in existing and not _needs_processing(existing[pmid]):
            all_articles[pmid] = existing[pmid]

    logger.info("Articles to process: %d", len(to_process))

    client = GeminiClient()

    for idx, article in enumerate(to_process, 1):
        pmid = article["pmid"]
        title = article["title"]
        print(f"\n[{idx}/{len(to_process)}] {title[:80]}")

        # Stage-1: keyword match
        matched, category = keyword_match(title, article["abstract"])

        if matched:
            print(f"  → Keyword match: {category} — confirming with Gemini...")
            confirmed = confirm_with_gemini(client, title, article["abstract"], category)
            article["is_interest"] = confirmed
            article["interest_category"] = category if confirmed else None
            tag = f"✓ {category}" if confirmed else "✗ not confirmed"
            print(f"  → Gemini: {tag}")
        else:
            print("  → No interest-area match")

        # Stage-2: summarize
        detailed = article["is_interest"]
        mode = "detailed" if detailed else "basic"
        print(f"  → Summarizing ({mode})...")
        article["summary"] = summarize_article(
            client, title, article["abstract"], detailed=detailed
        )

        # Save incrementally so progress survives interruption
        all_articles[pmid] = article
        _save(data_file, all_articles)
        print("  → Saved.")

    # ── Render HTML ───────────────────────────────────────────────────────────
    logger.info("Rendering HTML...")
    render_all(DATA_DIR)
    logger.info("Done. Output → docs/")


if __name__ == "__main__":
    main()
