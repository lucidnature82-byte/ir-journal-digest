import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
NCBI_API_KEY: str = os.environ.get("NCBI_API_KEY", "")

# 모델 선택 (일일 무료 한도 기준 - 2026년 5월 실측값)
# 'gemini-1.5-flash'       : 1500회/일  (권장: 안정적, 한도 넉넉) ← 현재 선택
# 'gemini-1.5-flash-8b'    : 1500회/일  (가볍고 빠름, 품질 소폭 낮음)
# 'gemini-2.5-flash'       :   20회/일  (프리뷰 제한, 사실상 사용 불가)
# 'gemini-2.0-flash'       :    0회/일  (2026년 무료 한도 없음 → 유료 전용)
GEMINI_MODEL: str = "gemini-1.5-flash"

# True  : 키워드 매칭 후 Gemini 2차 확인 (정확도 +, 호출 수 +)
# False : 키워드 매칭만으로 분류 (호출 수 절약)
USE_GEMINI_RECONFIRM: bool = False

# PubMed journal query strings
JOURNALS: dict[str, str] = {
    "JVIR": '"J Vasc Interv Radiol"[Journal]',
    "CVIR": '"Cardiovasc Intervent Radiol"[Journal]',
}

FETCH_DAYS: int = 30  # look-back window for PubMed search

# ── Interest-area keywords ────────────────────────────────────────────────────

HEPATOBILIARY_KEYWORDS: list[str] = [
    "TACE",
    "transarterial chemoembolization",
    "DEB-TACE",
    "Y-90",
    "yttrium-90",
    "radioembolization",
    "SIRT",
    "TARE",
    "HCC",
    "hepatocellular carcinoma",
    "RFA",
    "MWA",
    "microwave ablation",
    "radiofrequency ablation",
]

# Ablation terms that require a hepatic context to qualify
ABLATION_TERMS: list[str] = [
    "RFA",
    "MWA",
    "microwave ablation",
    "radiofrequency ablation",
]

HEPATIC_CONTEXT: list[str] = [
    "liver",
    "hepatic",
    "hepat",
    "hcc",
    "hepatocellular",
]

NONVASCULAR_KEYWORDS: list[str] = [
    "biliary",
    "PTBD",
    "percutaneous transhepatic",
    "cholangiography",
    "cholangioplasty",
    "nephrostomy",
    "PCN",
    "ureteral stent",
    "antegrade ureteral",
    "abscess drainage",
    "percutaneous drainage",
    "gastrostomy",
    "cecostomy",
]
