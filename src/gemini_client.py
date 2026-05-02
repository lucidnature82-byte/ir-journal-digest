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


class GeminiClient:
    def __init__(self) -> None:
        self._client = genai.Client(api_key=GEMINI_API_KEY)
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
                logger.warning(
                    "Gemini API error (attempt %d/%d) [%s]: %s",
                    attempt + 1, retries, exc_type, exc,
                )
                if attempt < retries - 1:
                    # Respect the retry_delay from rate-limit errors (429)
                    suggested = _parse_retry_delay(str(exc))
                    backoff = suggested if suggested > 0 else (2 ** (attempt + 2))
                    logger.info("  Retrying in %ds ...", backoff)
                    time.sleep(backoff)
                else:
                    logger.error(
                        "All %d Gemini attempts failed. [%s]: %s",
                        retries, exc_type, exc,
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
                logger.warning(
                    "Gemini API error (attempt %d/%d) [%s]: %s",
                    attempt + 1, retries, type(exc).__name__, exc,
                )
                if attempt < retries - 1:
                    suggested = _parse_retry_delay(str(exc))
                    time.sleep(suggested if suggested > 0 else 2 ** (attempt + 1))
        return None
