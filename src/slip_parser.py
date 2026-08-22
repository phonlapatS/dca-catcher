import json
import logging
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


class GeminiSlipParser:
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.model = "gemini-2.5-flash"

    async def parse_slip(self, image_bytes: bytes) -> dict | None:
        prompt = (
            "You are a financial OCR agent specializing in Thai broker apps like Dime. "
            "Read this US stock trade slip. Extract the ticker, action (BUY/SELL), execution price in USD, and volume. "
            "Return ONLY a strict JSON object with keys: symbol, action, price, volume. "
            "If it's not a trade slip, return an empty JSON object {}."
        )
        try:
            response = await self.client.models.generate_content_async(
                model=self.model,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                    prompt,
                ],
            )
            raw_text = response.text.strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            elif raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            raw_text = raw_text.strip()

            data = json.loads(raw_text)
            if not data.get("symbol"):
                return None
            return data
        except Exception as e:
            logger.error(f"Failed to parse slip: {e}")
            return None
