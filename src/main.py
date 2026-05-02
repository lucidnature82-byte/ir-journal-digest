"""Entry point: python -m src.main [--force-resummarize] [--debug]"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from .config import GEMINI_API_KEY, JOURNALS, GEMINI_MODEL, USE_GEMINI_RECONFIRM
from .fetch_pubmed import fetch_articles, search_pmids
from .gemini_client import GeminiClient
from .classify import confirm_with_gemini, keyword_match
from .summarize import summarize_article
from .render import render_all

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"


# ── Logging ───────────────────────────────────────────────────────────────────

def _setup_logging(month_str: str, debug: bool = False) -> None:
    LOGS_DIR.mkdir(exist_ok=True)
    log_file = LOGS_DIR / f"{month_str}.log"

    level = logging.DEBUG if debug else logging.INFO
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    handlers: list[logging.Handler] = [
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
    logging.basicConfig(level=level, format=fmt, handlers=handlers, force=True)


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


def _needs_processing(article: dict, force_resummarize: bool = False) -> bool:
    s = article.get("summary")
    if s is None:
        return True
    if isinstance(s, dict) and "_error" in s:
        return True
    if force_resummarize:
        # Re-process even successfully summarized articles
        return True
    return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    # Windows 콘솔(cp949)이 라틴 확장 문자를 처리 못하는 문제 방지
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="IR Journal Digest  -  monthly PubMed fetch & summarize")
    parser.add_argument(
        "--force-resummarize",
        action="store_true",
        help="Re-summarize all articles, including those already summarized",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable DEBUG-level logging (very verbose)",
    )
    parser.add_argument(
        "--month",
        default=None,
        metavar="YYYY-MM",
        help="Process a specific month instead of the current one (e.g. 2026-04)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Process only the first N articles (useful for quick test runs)",
    )
    args = parser.parse_args()

    month_str = args.month or datetime.now().strftime("%Y-%m")
    _setup_logging(month_str, debug=args.debug)
    logger = logging.getLogger(__name__)

    logger.info("=== IR Journal Digest | month=%s force=%s debug=%s limit=%s ===",
                month_str, args.force_resummarize, args.debug, args.limit)

    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY is not set. Create a .env file with GEMINI_API_KEY=<key>")
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
        empty_titles = sum(1 for a in articles if not a["title"])
        empty_abstracts = sum(1 for a in articles if not a["abstract"])
        logger.info(
            "  %s: %d articles fetched  (empty title: %d, empty abstract: %d)",
            journal_name, len(articles), empty_titles, empty_abstracts,
        )
        for a in articles:
            a["journal"] = journal_name
            all_articles[a["pmid"]] = a

    # Preserve articles from previous runs not re-fetched this time
    for pmid, art in existing.items():
        if pmid not in all_articles:
            all_articles[pmid] = art

    # ── Process ───────────────────────────────────────────────────────────────
    to_process = [
        a for pmid, a in all_articles.items()
        if pmid not in existing or _needs_processing(existing[pmid], args.force_resummarize)
    ]

    # Carry over completed summaries from existing data (unless force-resummarize)
    if not args.force_resummarize:
        for pmid, art in all_articles.items():
            if pmid in existing and not _needs_processing(existing[pmid]):
                all_articles[pmid] = existing[pmid]

    # ── 예상 Gemini 호출 수 안내 ──────────────────────────────────────────────
    has_abstract = sum(1 for a in to_process if a.get("abstract"))
    reconfirm_calls = has_abstract if USE_GEMINI_RECONFIRM else 0  # classify 2nd-pass
    summary_calls = has_abstract                                    # 요약은 항상 시도
    total_calls = reconfirm_calls + summary_calls

    _FREE_TIER_LIMITS = {
        "gemini-1.5-flash":      1500,  # 실측: 1500회/일 (권장)
        "gemini-1.5-flash-8b":   1500,  # 실측: 1500회/일
        "gemini-1.5-pro":          50,
        "gemini-2.5-flash":        20,  # 실측: 20회/일 (프리뷰 제한)
        "gemini-2.5-flash-lite":   20,  # 미확인 (2.5계열 동일 추정)
        "gemini-2.0-flash":         0,  # 2026년 무료 한도 없음 (유료 전용)
    }
    daily_limit = _FREE_TIER_LIMITS.get(GEMINI_MODEL, "?")
    reconfirm_note = "재확인 ON" if USE_GEMINI_RECONFIRM else "재확인 OFF (키워드만)"

    logger.info(
        "총 %d편 처리 예정 (abstract 있음: %d편). "
        "예상 Gemini 호출: %d회 (요약 %d + 분류 %d, %s). "
        "Free Tier 일일 한도: %s회 (%s)",
        len(to_process), has_abstract,
        total_calls, summary_calls, reconfirm_calls, reconfirm_note,
        daily_limit, GEMINI_MODEL,
    )
    if isinstance(daily_limit, int) and daily_limit == 0:
        logger.error(
            "현재 모델(%s)은 무료 티어 한도가 0입니다. "
            "config.py에서 모델을 변경하세요 (예: gemini-2.5-flash).",
            GEMINI_MODEL,
        )
    elif isinstance(daily_limit, int) and total_calls > daily_limit:
        logger.warning(
            "예상 호출(%d)이 일일 한도(%d)를 초과합니다. "
            "gemini-2.5-flash-lite(1000회/일)로 변경하거나 abstract 없는 논문을 제외하세요.",
            total_calls, daily_limit,
        )

    if args.limit:
        to_process = to_process[:args.limit]
        logger.info("--limit %d 적용: %d편만 처리합니다.", args.limit, len(to_process))

    client = GeminiClient()

    stats = {"classify_match": 0, "classify_confirmed": 0, "summary_ok": 0, "summary_null": 0}
    # Circuit breaker: abort if Gemini fails this many times in a row (quota exhausted)
    _QUOTA_ABORT_THRESHOLD = 5
    consecutive_failures = 0

    for idx, article in enumerate(to_process, 1):
        pmid = article["pmid"]
        title = article["title"]
        abstract = article["abstract"]

        print(
            f"\n[{idx}/{len(to_process)}] PMID={pmid}  "
            f"title_len={len(title)}  abstract_len={len(abstract)}"
        )
        if title:
            print(f"  Title: {title[:100]}")
        else:
            print("  Title: (EMPTY)")

        if not title and not abstract:
            logger.warning("PMID %s: both title and abstract are empty - skipping", pmid)
            all_articles[pmid] = article
            _save(data_file, all_articles)
            continue

        # Stage-1: keyword match
        matched, category = keyword_match(title, abstract)

        if matched:
            stats["classify_match"] += 1
            print(f"  Keyword match: {category} - confirming with Gemini...")
            confirmed = confirm_with_gemini(client, title, abstract, category)
            article["is_interest"] = confirmed
            article["interest_category"] = category if confirmed else None
            if confirmed:
                stats["classify_confirmed"] += 1
                print(f"  Gemini confirmed: {category}")
            else:
                print("  Gemini: not confirmed (false positive)")
        else:
            print("  No keyword match")

        # Stage-2: summarize (all articles, not just is_interest)
        detailed = article["is_interest"]
        article["summary"] = summarize_article(
            client, title, abstract, detailed=detailed, pmid=pmid
        )

        if article["summary"] is not None:
            stats["summary_ok"] += 1
            consecutive_failures = 0
        else:
            stats["summary_null"] += 1
            consecutive_failures += 1
            if consecutive_failures >= _QUOTA_ABORT_THRESHOLD:
                logger.error(
                    "Gemini failed %d times in a row. "
                    "Likely cause: free-tier daily quota exhausted (ResourceExhausted 429). "
                    "Progress saved. Re-run with --force-resummarize after quota resets "
                    "(typically midnight UTC) or upgrade your API plan at "
                    "https://ai.dev/rate-limit",
                    _QUOTA_ABORT_THRESHOLD,
                )
                all_articles[pmid] = article
                _save(data_file, all_articles)
                break

        # Save incrementally so progress survives interruption
        all_articles[pmid] = article
        _save(data_file, all_articles)
        print("  Saved.")

    logger.info(
        "Processing complete: keyword_match=%d, gemini_confirmed=%d, "
        "summary_ok=%d, summary_null=%d",
        stats["classify_match"], stats["classify_confirmed"],
        stats["summary_ok"], stats["summary_null"],
    )

    # ── Render HTML ───────────────────────────────────────────────────────────
    logger.info("Rendering HTML...")
    render_all(DATA_DIR)
    logger.info("Done. Output → docs/")


if __name__ == "__main__":
    main()
