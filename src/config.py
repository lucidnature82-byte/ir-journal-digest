import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
NCBI_API_KEY: str = os.environ.get("NCBI_API_KEY", "")

GEMINI_MODEL: str = "gemini-2.0-flash"

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
