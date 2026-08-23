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
        """Helper method to invoke Gemini API with temperature=0.0 (async)."""
        if not self._client:
            raise ValueError("Gemini API key is not configured")

        response = await self._client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
            ),
        )
        return response.text or "{}"

    async def evaluate_catalyst(
        self, article: CatalystArticle, timeline_context: str = ""
    ) -> CatalystVerdict:
        """Evaluates fundamental materiality, dual perspective (Bull/Bear), and supply chain links."""
        prompt = f"""You are an institutional financial analyst specialized in event-driven catalysts, supply chain spillovers (Cohen & Frazzini economic links), and disciplined Dollar-Cost Averaging (DCA).

Analyze this breaking corporate news:
- Symbol: ${article.symbol}
- Publisher: {article.publisher}
- Published At: {article.published_at.isoformat()}
- Headline: {article.headline}
- Snippet: {article.raw_snippet}
{timeline_context}

Instructions:
1. Is this a material event that fundamentally alters business value or long-term revenue? (is_material: boolean, materiality_score: 1.0 to 10.0)
2. Classify event_category into: CLINICAL_TRIAL, EARNINGS, M_AND_A, REGULATORY, CONTRACT, RISK_EVENT.
3. Dual-Perspective Analysis in Thai:
   - bull_catalysts: Growth opportunity and strategic value.
   - bear_risks: Latent risks, execution hurdles, or gap-up overreaction risks.
   - dca_guidance: Prudent DCA entry levels and accumulation advice (never advise chasing gap-ups).
   - thai_summary: 1-2 sentence factual Thai news summary.
4. Supply Chain & Economic Links:
   - connected_stocks: List of related companies (Suppliers, Customers, Competitors, Sympathy Peers) that will experience spillover effects.

Return strict JSON adhering to this schema:
{{
  "is_material": true,
  "materiality_score": 9.0,
  "event_category": "CLINICAL_TRIAL",
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
            logger.error(f"Error evaluating catalyst for {article.symbol}: {e}")
            return CatalystVerdict(
                is_material=False,
                materiality_score=1.0,
                event_category="RISK_EVENT",
                bull_catalysts="ไม่สามารถประเมินได้",
                bear_risks="เกิดข้อผิดพลาดในการประมวลผลข้อมูล",
                dca_guidance="ระงับการดำเนินการชั่วคราว",
                thai_summary="เกิดข้อผิดพลาดในการวิเคราะห์ข่าว",
                connected_stocks=[]
            )
