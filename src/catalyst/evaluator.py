import json
import logging
from typing import Optional
from google import genai
from google.genai import types

from src.catalyst.models import CatalystArticle, CatalystVerdict, ConnectedAsset

logger = logging.getLogger(__name__)


class CatalystEvaluator:
    """Dual-Perspective AI Evaluator and Supply Chain Spillover Mapper (Powered by Gemini)."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self._client = None
        if api_key:
            self._client = genai.Client(api_key=api_key)

    async def _call_gemini(self, prompt: str) -> str:
        """Helper method to invoke Gemini API with temperature=0.0 (async), with fallbacks."""
        if not self._client:
            raise ValueError("Gemini API key is not configured")

        models = ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-3-flash-preview"]
        last_error = None

        import asyncio
        for model_name in models:
            for attempt in range(2):
                try:
                    response = await self._client.aio.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            temperature=0.0,
                            response_mime_type="application/json",
                        ),
                    )
                    return response.text or "{}"
                except Exception as e:
                    last_error = e
                    if "503" in str(e) or "429" in str(e):
                        logger.warning(f"CatalystEvaluator: {model_name} rate limited (attempt {attempt+1}). Retrying in 2s...")
                        await asyncio.sleep(2)
                    else:
                        logger.warning(f"CatalystEvaluator: {model_name} failed with {e}")
                        break  # Try next model if hard error
        
        raise RuntimeError(f"All models failed in CatalystEvaluator. Last error: {last_error}")

    async def evaluate_catalyst(
        self, article: CatalystArticle, timeline_context: str = ""
    ) -> CatalystVerdict:
        """Evaluates fundamental materiality, dual perspective (Bull/Bear), and supply chain links."""
        prompt = f"""You are an institutional financial analyst specialized in event-driven catalysts, supply chain spillovers, and disciplined Dollar-Cost Averaging (DCA).

Analyze this breaking corporate news:
- Symbol: ${article.symbol}
- Publisher: {article.publisher}
- Published At: {article.published_at.isoformat()}
- Headline: {article.headline}
- Snippet: {article.raw_snippet}
{timeline_context}

Instructions:
1. Is this a material event that fundamentally alters business value or long-term revenue? (is_material: boolean, materiality_score: 1.0 to 10.0. Reject clickbait/Zacks/MotleyFool junk with is_material=False and low score).
2. Classify scope into: MACRO, SECTOR, or MICRO.
3. Classify event_category into: CLINICAL_TRIAL, EARNINGS, M_AND_A, REGULATORY, CONTRACT, RISK_EVENT, MACRO_EVENT.
4. Assess confidence_score (0-100) based on source reliability (Rumor vs Official).
5. Provide impact_summary in Thai (1-2 sentences explaining causality: how/why this affects the price).
6. Determine sentiment (POSITIVE, NEGATIVE, or NEUTRAL).
7. Dual-Perspective Analysis in Thai:
   - bull_catalysts: Growth opportunity and strategic value.
   - bear_risks: Latent risks, execution hurdles, or gap-up overreaction risks.
   - dca_guidance: Prudent DCA entry levels and accumulation advice.
   - thai_summary: 1-2 sentence factual Thai news summary.
8. Supply Chain & Economic Links:
   - connected_stocks: List of related companies (Suppliers, Customers, Competitors, Sympathy Peers) that will experience spillover effects.

Return strict JSON adhering to this schema:
{{
  "is_material": true,
  "materiality_score": 9.0,
  "confidence_score": 90.0,
  "scope": "MICRO",
  "sentiment": "POSITIVE",
  "event_category": "EARNINGS",
  "impact_summary": "...",
  "bull_catalysts": "...",
  "bear_risks": "...",
  "dca_guidance": "...",
  "thai_summary": "...",
  "connected_stocks": [
    {{
      "symbol": "TICKER",
      "relationship": "SUPPLIER | CUSTOMER | COMPETITOR | SYMPATHY_PEER",
      "impact_direction": "POSITIVE | NEGATIVE",
      "rationale_thai": "..."
    }}
  ]
}}
"""
        try:
            raw_json = await self._call_gemini(prompt)
            from src.utils import extract_json_from_llm
            data = extract_json_from_llm(raw_json)
            return CatalystVerdict(**data)
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)[:200]
            
            # Source detection for Admin
            source = "Unknown"
            if "503" in error_msg or "429" in error_msg or "google" in str(type(e)).lower():
                source = "Google Gemini API (AI)"
            elif "asyncpg" in str(type(e)).lower() or "sqlalchemy" in str(type(e)).lower():
                source = "Supabase PostgreSQL (Database)"
            elif "fly" in error_msg.lower():
                source = "Fly.io (Server)"
                
            admin_debug_info = f"🚨 [System Error: {source}]\nType: {error_type}\nDetails: {error_msg}"
            logger.error(f"Error evaluating catalyst for {article.symbol}: {e}")
            
            return CatalystVerdict(
                is_material=False,
                materiality_score=1.0,
                confidence_score=0.0,
                scope="MICRO",
                sentiment="NEUTRAL",
                event_category="RISK_EVENT",
                impact_summary=f"เกิดข้อผิดพลาดในการประมวลผลข้อมูล\n\n{admin_debug_info}",
                bull_catalysts="ไม่สามารถประเมินได้",
                bear_risks=admin_debug_info,
                dca_guidance="ระงับการดำเนินการชั่วคราว จนกว่าระบบจะกลับมาเป็นปกติ",
                thai_summary=f"เกิดข้อผิดพลาดในการวิเคราะห์ข่าว: {source}",
                connected_stocks=[]
            )
