import logging
from typing import Optional

from .config import (
    HEPATOBILIARY_KEYWORDS,
    HEPATIC_CONTEXT,
    ABLATION_TERMS,
    NONVASCULAR_KEYWORDS,
    USE_GEMINI_RECONFIRM,
)

logger = logging.getLogger(__name__)

_CATEGORY_DESC = {
    "hepatobiliary": (
        "간담도 인터벤션 (간동맥화학색전술, 고주파절제술, 방사선색전술, HCC 치료 등)"
    ),
    "nonvascular": (
        "비혈관 인터벤션 (담도, 신루설치술, 요관 스텐트, 배액술, 위루술 등)"
    ),
}


def keyword_match(title: str, abstract: str) -> tuple[bool, Optional[str]]:
    """Stage-1: fast keyword scan.  Returns (matched, category)."""
    text = f"{title} {abstract}".lower()

    logger.debug(
        "keyword_match: title_len=%d, abstract_len=%d, combined_len=%d",
        len(title), len(abstract), len(text),
    )

    if not title and not abstract:
        logger.warning("keyword_match: both title and abstract are empty  -  cannot match")
        return False, None

    for kw in NONVASCULAR_KEYWORDS:
        if kw.lower() in text:
            logger.debug("  NONVASCULAR hit: '%s'", kw)
            return True, "nonvascular"

    for kw in HEPATOBILIARY_KEYWORDS:
        kw_lower = kw.lower()
        if kw_lower in text:
            if kw in ABLATION_TERMS:
                ctx_hits = [ctx for ctx in HEPATIC_CONTEXT if ctx in text]
                if ctx_hits:
                    logger.debug("  HEPATOBILIARY hit: '%s' + hepatic context %s", kw, ctx_hits)
                    return True, "hepatobiliary"
                else:
                    logger.debug(
                        "  Ablation term '%s' found but no hepatic context (skipped)", kw
                    )
            else:
                logger.debug("  HEPATOBILIARY hit: '%s'", kw)
                return True, "hepatobiliary"

    logger.debug("  No keyword matched")
    return False, None


def confirm_with_gemini(client, title: str, abstract: str, category: str) -> bool:
    """Stage-2: ask Gemini to reduce false positives.
    Skipped when USE_GEMINI_RECONFIRM=False in config.py.
    """
    if not USE_GEMINI_RECONFIRM:
        logger.debug("confirm_with_gemini: skipped (USE_GEMINI_RECONFIRM=False)")
        return True  # trust keyword match as-is

    desc = _CATEGORY_DESC.get(category, category)
    snippet = abstract[:600] if abstract else "(초록 없음)"
    title_display = title if title else "(제목 없음)"

    prompt = (
        f"다음 논문이 '{desc}'에 관한 논문인지 판단하세요.\n\n"
        f"제목: {title_display}\n"
        f"초록: {snippet}\n\n"
        '반드시 JSON으로만 답하세요:\n'
        '{"is_relevant": true 또는 false, "reason": "한 줄 이유"}'
    )

    result = client.generate_json(prompt)
    if result is None:
        logger.error("confirm_with_gemini: Gemini returned None  -  defaulting to False")
        return False

    if "_error" in result:
        logger.error("confirm_with_gemini: JSON parse error  -  defaulting to False. raw=%.100s",
                     result.get("_raw", ""))
        return False

    if isinstance(result.get("is_relevant"), bool):
        relevant: bool = result["is_relevant"]
        logger.debug("Gemini confirm → %s (%s)", relevant, result.get("reason", ""))
        return relevant

    logger.warning("confirm_with_gemini: unexpected response format: %s", result)
    return False
