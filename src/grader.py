import json
import logging
import re
from dataclasses import dataclass

import google.generativeai as genai

from src.transform import EnrichedSignal

logger = logging.getLogger(__name__)


@dataclass
class GradeResult:
    symbol: str
    grade: int          # 1-4 (1=🔴 risky, 2=🟡 moderate, 3=🟢 low risk, 4=🌟 buy now)
    confidence: int     # 0-100
    advice: str         # Thai-language advice from Gemini
    reasons: list[str]  # Reason tags, e.g. ["✅ RSI < 30", "⚠️ Low volume"]
    buy_targets: list[str] # e.g. ["170 (มีความเสี่ยงเล็กน้อย)", "160 (ไม่เสี่ยงเลย)"]


class SignalGrader:
    """Uses Google Gemini to grade enriched stock signals."""

    def __init__(self, api_key: str, models: list[str] = None):
        """Configure Gemini with the provided API key and fallback models."""
        genai.configure(api_key=api_key)
        # Default fallback models based on user quota preferences
        self.models = models or ["gemini-3.5-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite"]

    def grade(self, signal: EnrichedSignal) -> GradeResult:
        """Send enriched signal dimensions to Gemini for grading.

        Constructs a prompt with the 3 dimension scores and asks Gemini
        to return a JSON response with grade, confidence, advice, and reasons.
        Tries multiple models sequentially if quota limits are hit.
        """
        prompt = self._build_prompt(signal)
        last_error = None
        
        for model_name in self.models:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                return self._parse_response(response.text, signal.symbol)
            except Exception as e:
                logger.warning(f"Model {model_name} failed for {signal.symbol}: {e}")
                last_error = e
                continue # Try the next model
                
        # If all models fail, return fallback
        logger.error(f"All Gemini models failed for {signal.symbol}. Last error: {last_error}")
        return GradeResult(
            symbol=signal.symbol,
            grade=2,
            confidence=0,
            advice=f"Gemini API error (All models failed): {last_error}",
            reasons=["⚠️ ไม่สามารถติดต่อ AI ได้ (API Error)"],
        )

    def _build_prompt(self, signal: EnrichedSignal) -> str:
        """Build the Gemini prompt from enriched signal data.

        The prompt instructs Gemini to:
        1. Analyze the 3 dimensions (PRICE, FLOW, CONTEXT)
        2. Return JSON with: grade (1-4), confidence (0-100),
           advice (Thai string), reasons (list of strings)
        3. Cross-analyze conflicts between dimensions
        """
        dimensions_summary = []
        for name, score in signal.dimensions.items():
            dimensions_summary.append(
                f"- {name}: Label={score.label}, Score={score.score}, Reason={score.reason}"
            )
        dims_str = "\n".join(dimensions_summary)

        prompt = f"""You are a professional financial analyst AI assisting with Dollar-Cost Averaging (DCA) investment decisions.

Analyze the stock signal for symbol: {signal.symbol}

Market Snapshot:
- Current Price: ${signal.snapshot.current_price}
- Volume: {signal.snapshot.volume}
- ATH Price: ${signal.snapshot.ath_price}
- Drawdown from ATH: {signal.snapshot.drawdown_pct}%

Analysis Dimensions:
{dims_str}

Instruction:
Evaluate the combined dimensions (PRICE, FLOW, CONTEXT) and cross-analyze any conflicts.
Calculate 3 suggested buy target prices based on the ATH and current price. Provide the price and a short Thai description of the risk at that level (e.g., "170 (มีความเสี่ยงเล็กน้อย)", "160 (ปลอดภัย)", "150 (Play safe)").
Return ONLY a valid raw JSON object (without markdown code formatting or extraneous text) matching this schema:
{{
    "grade": <integer 1 to 4: 1=Risky/High risk, 2=Moderate risk/Hold, 3=Low risk/Good DCA, 4=Strong buy/Now>,
    "confidence": <integer 0 to 100>,
    "advice": "<Thai string containing practical DCA investment advice in Thai language>",
    "reasons": ["<Thai tag string 1 with ✅ or ⚠️ (e.g., ✅ ใกล้ถึงจุดสูงสุดที่เคยทำไว้ก่อนหน้า)>", "<Thai tag string 2>"],
    "buy_targets": ["<Target 1>", "<Target 2>", "<Target 3>"]
}}
"""
        return prompt

    def _parse_response(self, text: str, symbol: str) -> GradeResult:
        """Parse Gemini's JSON response into a GradeResult.

        Handles markdown code fences (```json ... ```) in the response.
        Returns fallback GradeResult on any parse error.
        """
        try:
            cleaned_text = text.strip()
            if cleaned_text.startswith("```"):
                cleaned_text = re.sub(r"^```(?:json)?\s*", "", cleaned_text)
                cleaned_text = re.sub(r"\s*```$", "", cleaned_text)

            data = json.loads(cleaned_text)

            grade = int(data.get("grade", 2))
            confidence = int(data.get("confidence", 0))
            advice = str(data.get("advice", "No advice provided"))
            reasons = list(data.get("reasons", []))
            buy_targets = list(data.get("buy_targets", []))

            return GradeResult(
                symbol=symbol,
                grade=grade,
                confidence=confidence,
                advice=advice,
                reasons=reasons,
                buy_targets=buy_targets,
            )
        except Exception as e:
            logger.warning(f"Failed to parse Gemini response for {symbol}: {e}. Response text: {text!r}")
            return GradeResult(
                symbol=symbol,
                grade=2,
                confidence=0,
                advice=f"Failed to parse response: {e}",
                reasons=["⚠️ Parse error"],
                buy_targets=[],
            )
