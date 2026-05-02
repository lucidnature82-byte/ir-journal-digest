import logging
from typing import Optional

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

# ── Pydantic schemas ──────────────────────────────────────────────────────────

class BasicSummary(BaseModel):
    title_ko: str
    one_line: str
    design: str
    subjects: str
    intervention: str
    results: str
    implication: str


class DetailedSummary(BasicSummary):
    detailed_results: str
    critique: str
    clinical_application: str


# ── Prompts ───────────────────────────────────────────────────────────────────

_BASIC_SCHEMA = """{
  "title_ko": "한글 번역 제목",
  "one_line": "한 줄 요약",
  "design": "연구 디자인 (RCT/전향적/후향적/증례/메타분석 등)",
  "subjects": "대상 / N수",
  "intervention": "시술 또는 중재",
  "results": "주요 결과 (수치 포함)",
  "implication": "임상적 함의"
}"""

_DETAILED_SCHEMA = """{
  "title_ko": "한글 번역 제목",
  "one_line": "한 줄 요약",
  "design": "연구 디자인 (RCT/전향적/후향적/증례/메타분석 등)",
  "subjects": "대상 / N수",
  "intervention": "시술 또는 중재",
  "results": "주요 결과 (수치 포함)",
  "implication": "임상적 함의",
  "detailed_results": "상세 결과 (subgroup 분석, 합병증, 추적 기간 포함)",
  "critique": "비판적 코멘트 (limitation, 기존 연구와의 비교)",
  "clinical_application": "임상 적용 시사점"
}"""

_SYSTEM = (
    "당신은 인터벤션 영상의학 전문의입니다. "
    "의학 용어는 반드시 한글(영어) 병기하세요 (예: 간동맥화학색전술(TACE)). "
    "수치와 통계는 원문 그대로 정확히 기재하세요."
)


def _build_prompt(title: str, abstract: str, detailed: bool) -> str:
    schema = _DETAILED_SCHEMA if detailed else _BASIC_SCHEMA
    title_line = f"논문 제목: {title}" if title else "논문 제목: (제목 없음  -  초록 기반으로 요약)"
    return (
        f"{_SYSTEM}\n\n"
        "다음 논문을 한국어로 요약하고 아래 JSON 스키마에 맞게 출력하세요.\n\n"
        f"{title_line}\n"
        f"초록: {abstract}\n\n"
        f"JSON 출력:\n{schema}"
    )


def summarize_article(
    client,
    title: str,
    abstract: str,
    detailed: bool = False,
    pmid: str = "",
) -> Optional[dict]:
    tag = f"PMID {pmid}" if pmid else f"'{title[:50]}'"

    if not abstract:
        logger.warning("[%s] No abstract  -  skipping summarization", tag)
        return None

    if not title:
        logger.info("[%s] Title empty  -  summarizing from abstract only (len=%d)", tag, len(abstract))

    mode = "detailed" if detailed else "basic"
    logger.info("[%s] Calling Gemini for %s summary (abstract_len=%d)...", tag, mode, len(abstract))

    prompt = _build_prompt(title, abstract, detailed)
    raw = client.generate_json(prompt)

    if raw is None:
        logger.error("[%s] Gemini returned None - summary will be null", tag)
        return None

    if "_error" in raw:
        logger.warning("[%s] JSON parse failed. raw[:200]=%.200s", tag, raw.get("_raw", ""))
        return raw  # preserve for debugging

    schema_cls = DetailedSummary if detailed else BasicSummary
    try:
        schema_cls.model_validate(raw)
        logger.info("[%s] Summary OK (%s)", tag, mode)
    except ValidationError as exc:
        logger.warning("[%s] Schema validation warning: %s", tag, exc)

    return raw
