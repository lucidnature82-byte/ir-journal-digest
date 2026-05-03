import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
NCBI_API_KEY: str = os.environ.get("NCBI_API_KEY", "")

# 모델 선택 (2026년 5월 실측 기준)
# 'gemini-2.5-flash-lite'  : 사용 가능 (200 OK 확인) ← 현재 선택 (2.5 품질 + lite 무료 한도)
# 'gemini-flash-latest'    : 사용 가능 (200 OK 확인) — alias라 버전 변동 위험
# 'gemini-2.5-flash'       : 429 (오늘 한도 소진)
# 'gemini-2.0-flash-lite'  : 429 (오늘 한도 소진)
# -- 'gemini-1.5-flash' 은 2026년 5월 기준 retired (404 NOT_FOUND) --
GEMINI_MODEL: str = "gemini-2.5-flash-lite"

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
