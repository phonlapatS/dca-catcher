import json
import logging
from google import genai
from google.genai import types
from src.insight_pipeline import PipelineConfig

logger = logging.getLogger(__name__)


class GeminiSlipParser:
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.config = PipelineConfig()

    async def parse_slip(self, image_bytes: bytes) -> dict | None:
        prompt = (
            "You are a financial OCR agent specializing in Thai broker apps like Dime. "
            "Read this US stock trade slip. The slip might be in Thai ('ซื้อ' = BUY, 'ขาย' = SELL). "
            "Extract the ticker symbol (e.g., AAPL, NVDA), action (BUY/SELL), execution price in USD, and volume (shares). "
            "Return ONLY a strict JSON object with exactly these keys: symbol, action, price, volume. "
            "If it's absolutely not a trade slip, return an empty JSON object {}."
        )
        
        last_error = None
        # Use the models the user specified in insight_pipeline (smart_models)
        models_to_try = self.config.smart_models
        for model_name in models_to_try:
            try:
                logger.info(f"Trying Gemini vision extraction with model: {model_name}")
                response = await self.client.aio.models.generate_content(
                    model=model_name,
                    contents=[
                        types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                        prompt,
                    ],
                )
                raw_text = response.text.strip()
                from src.utils import extract_json_from_llm
                data = extract_json_from_llm(raw_text)
                if not data.get("symbol"):
                    return None
                return data
            except Exception as e:
                logger.warning(f"Model {model_name} failed: {e}")
                last_error = e
                continue
                
        logger.error(f"All specified models failed. Last error: {last_error}")
        return None
