import json
import logging
import os
import re
import time
from typing import Optional

from google import genai
from google.genai import types

from . import config
from .config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

_INTER_CALL_DELAY = 1.0  # 분당 최대 60회 -> 안전 마진 확보

# 환경변수 GEMINI_MODEL이 있으면 우선 적용, 없으면 config.py 값 사용
_MODEL_NAME: str = os.environ.get("GEMINI_MODEL") or config.GEMINI_MODEL


def _parse_retry_delay(error_str: str) -> int:
    """Extract retry_delay seconds from a Gemini 429 error message, or return 0."""
    m = re.search(r"retry_delay\s*\{[^}]*seconds:\s*(\d+)", error_str)
    return int(m.group(1)) if m else 0


def _extract_http_status(exc: Exception) -> Optional[int]:
    """Best-effort extraction of HTTP status code from a Gemini SDK exception."""
    exc_str = str(exc)
    # google.genai errors embed the status code in various ways
    for pattern in (
        r"\b(400|401|403|404|429|500|503)\b",
        r"status[_\s]+code[:\s]+(\d{3})",
        r"HTTP[_\s]+(\d{3})",
    ):
        m = re.search(pattern, exc_str, re.IGNORECASE)
        if m:
            return int(m.group(1))
    # Also check exception class name for clues
    name = type(exc).__name__.lower()
    if "notfound" in name or "not_found" in name:
        return 404
    if "resourceexhausted" in name or "quota" in name:
        return 429
    if "permissiondenied" in name:
        return 403
    if "unauthenticated" in name:
        return 401
    return None


class GeminiClient:
    def __init__(self) -> None:
        self._client = genai.Client(api_key=GEMINI_API_KEY)
        self.last_error_code: Optional[int] = None  # HTTP status of most recent failure
        self.last_error_type: str = ""               # exception class name
        key_hint = (GEMINI_API_KEY[:8] + "...") if GEMINI_API_KEY else "(empty!)"
        logger.info("GeminiClient ready: model=%s, key_prefix=%s", _MODEL_NAME, key_hint)

    def generate_json(self, prompt: str, retries: int = 3) -> Optional[dict]:
        raw_text = ""
        for attempt in range(retries):
            try:
                time.sleep(_INTER_CALL_DELAY)
                response = self._client.models.generate_content(
                    model=_MODEL_NAME,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                    ),
                )
                raw_text = response.text
                logger.debug("Gemini OK (attempt %d) response[:200]: %s",
                             attempt + 1, raw_text[:200])
                return json.loads(raw_text)

            except json.JSONDecodeError as exc:
                logger.warning(
                    "JSON parse error (attempt %d/%d): %s | raw[:200]: %.200s",
                    attempt + 1, retries, exc, raw_text,
                )
                if attempt == retries - 1:
                    return {"_raw": raw_text, "_error": str(exc)}

            except Exception as exc:
                exc_type = type(exc).__name__
                self.last_error_code = _extract_http_status(exc)
                self.last_error_type = exc_type
                logger.warning(
                    "Gemini API error (attempt %d/%d) [%s] HTTP=%s: %s",
                    attempt + 1, retries, exc_type, self.last_error_code, exc,
                )
                if attempt < retries - 1:
                    # Respect the retry_delay from rate-limit errors (429)
                    suggested = _parse_retry_delay(str(exc))
                    backoff = suggested if suggested > 0 else (2 ** (attempt + 2))
                    logger.info("  Retrying in %ds ...", backoff)
                    time.sleep(backoff)
                else:
                    logger.error(
                        "All %d Gemini attempts failed. [%s] HTTP=%s: %s",
                        retries, exc_type, self.last_error_code, exc,
                    )
                    return None

        return None

    def generate_text(self, prompt: str, retries: int = 3) -> Optional[str]:
        for attempt in range(retries):
            try:
                time.sleep(_INTER_CALL_DELAY)
                response = self._client.models.generate_content(
                    model=_MODEL_NAME,
                    contents=prompt,
                )
                return response.text
            except Exception as exc:
                exc_type = type(exc).__name__
                self.last_error_code = _extract_http_status(exc)
                self.last_error_type = exc_type
                logger.warning(
                    "Gemini API error (attempt %d/%d) [%s] HTTP=%s: %s",
                    attempt + 1, retries, exc_type, self.last_error_code, exc,
                )
                if attempt < retries - 1:
                    suggested = _parse_retry_delay(str(exc))
                    time.sleep(suggested if suggested > 0 else 2 ** (attempt + 1))
        return None
