import json
import logging
import time
from typing import Optional

import google.generativeai as genai

from .config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)

_INTER_CALL_DELAY = 0.5  # seconds between Gemini calls (free-tier rate limit)


class GeminiClient:
    def __init__(self) -> None:
        self._model = genai.GenerativeModel(GEMINI_MODEL)

    def generate_json(self, prompt: str, retries: int = 3) -> Optional[dict]:
        raw_text = ""
        for attempt in range(retries):
            try:
                time.sleep(_INTER_CALL_DELAY)
                response = self._model.generate_content(
                    prompt,
                    generation_config=genai.GenerationConfig(
                        response_mime_type="application/json",
                    ),
                )
                raw_text = response.text
                return json.loads(raw_text)

            except json.JSONDecodeError as exc:
                logger.warning("JSON parse error (attempt %d/%d): %s", attempt + 1, retries, exc)
                if attempt == retries - 1:
                    return {"_raw": raw_text, "_error": str(exc)}

            except Exception as exc:
                logger.warning("Gemini API error (attempt %d/%d): %s", attempt + 1, retries, exc)
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    logger.error("Giving up after %d attempts.", retries)
                    return None

        return None

    def generate_text(self, prompt: str, retries: int = 3) -> Optional[str]:
        for attempt in range(retries):
            try:
                time.sleep(_INTER_CALL_DELAY)
                response = self._model.generate_content(prompt)
                return response.text
            except Exception as exc:
                logger.warning("Gemini API error (attempt %d/%d): %s", attempt + 1, retries, exc)
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
        return None
