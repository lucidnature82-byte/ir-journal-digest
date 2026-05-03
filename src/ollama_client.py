import json
import logging
import time
from typing import Optional

import ollama

from . import config

logger = logging.getLogger(__name__)

_MODEL = config.OLLAMA_MODEL
_HOST = config.OLLAMA_HOST
_TIMEOUT = config.OLLAMA_TIMEOUT
_TEMPERATURE = config.OLLAMA_TEMPERATURE


def _classify_error(exc: Exception) -> tuple[Optional[int], str]:
    """Return (error_code, hint) from an Ollama exception."""
    msg = str(exc).lower()
    if "connection refused" in msg or "connect" in msg or "connectionerror" in type(exc).__name__.lower():
        return -1, "Ollama가 실행 중인지 확인하세요 (터미널에서 'ollama serve' 실행)"
    if "not found" in msg or "pull" in msg:
        return 404, f"모델이 없습니다. 'ollama pull {_MODEL}' 을 실행하세요"
    if "timeout" in msg or "timed out" in msg:
        return 408, f"응답 시간 초과 — GPU가 바쁘거나 모델이 너무 큽니다. config.py의 OLLAMA_TIMEOUT({_TIMEOUT}s)을 늘려보세요"
    return 500, f"Ollama 오류: {exc}"


class OllamaClient:
    """Ollama local LLM client. Drop-in replacement for GeminiClient."""

    def __init__(self) -> None:
        self.last_error_code: Optional[int] = None
        self.last_error_type: str = ""
        self._client = ollama.Client(host=_HOST, timeout=_TIMEOUT)
        logger.info("OllamaClient ready: model=%s, host=%s, timeout=%ds", _MODEL, _HOST, _TIMEOUT)

    def generate_json(self, prompt: str, retries: int = 3) -> Optional[dict]:
        raw_text = ""
        for attempt in range(retries):
            try:
                response = self._client.generate(
                    model=_MODEL,
                    prompt=prompt,
                    format="json",
                    options={"temperature": _TEMPERATURE},
                )
                raw_text = response.response
                logger.debug("Ollama OK (attempt %d) response[:200]: %s", attempt + 1, raw_text[:200])
                return json.loads(raw_text)

            except json.JSONDecodeError as exc:
                logger.warning(
                    "JSON parse error (attempt %d/%d): %s | raw[:200]: %.200s",
                    attempt + 1, retries, exc, raw_text,
                )
                if attempt == retries - 1:
                    return {"_raw": raw_text, "_error": str(exc)}

            except Exception as exc:
                self.last_error_type = type(exc).__name__
                self.last_error_code, hint = _classify_error(exc)
                logger.warning(
                    "Ollama error (attempt %d/%d) [%s]: %s",
                    attempt + 1, retries, self.last_error_type, hint,
                )
                if attempt < retries - 1:
                    backoff = 2 ** (attempt + 1)
                    logger.info("  Retrying in %ds ...", backoff)
                    time.sleep(backoff)
                else:
                    logger.error("All %d Ollama attempts failed. %s", retries, hint)
                    return None

        return None

    def generate_text(self, prompt: str, retries: int = 3) -> Optional[str]:
        for attempt in range(retries):
            try:
                response = self._client.generate(
                    model=_MODEL,
                    prompt=prompt,
                    options={"temperature": _TEMPERATURE},
                )
                return response.response

            except Exception as exc:
                self.last_error_type = type(exc).__name__
                self.last_error_code, hint = _classify_error(exc)
                logger.warning(
                    "Ollama error (attempt %d/%d) [%s]: %s",
                    attempt + 1, retries, self.last_error_type, hint,
                )
                if attempt < retries - 1:
                    time.sleep(2 ** (attempt + 1))
                else:
                    logger.error("All %d Ollama attempts failed. %s", retries, hint)

        return None
