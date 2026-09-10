import json
import logging
from typing import Optional
from google import genai
from google.genai import types

from src.catalyst.models import CatalystArticle, CatalystVerdict, ConnectedAsset

logger = logging.getLogger(__name__)


class CatalystEvaluator:
    """Dual-Perspective AI Evaluator and Supply Chain Spillover Mapper (Powered by Gemini)."""

    def __init__(self, api_keys: list[str] | str | None = None):
        self.api_keys = []
        self._clients = []
        if isinstance(api_keys, str):
            self.api_keys = [api_keys]
        elif isinstance(api_keys, list):
            self.api_keys = api_keys
            
        for key in self.api_keys:
            self._clients.append(genai.Client(api_key=key))

    async def _call_gemini(self, prompt: str) -> str:
        """Helper method to invoke Gemini API across rotated keys and models."""
        if not self._clients:
            raise ValueError("Gemini API key is not configured")

        models = ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-3-flash-preview"]
        last_error = None

        import asyncio
        for client in self._clients:
            for model_name in models:
                for attempt in range(2):
                    try:
                        response = await client.aio.models.generate_content(
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
        
        raise RuntimeError(f"All clients/models failed in CatalystEvaluator. Last error: {last_error}")

    async def evaluate_catalyst(
        self, article: CatalystArticle, timeline_context: str = ""
    ) -> CatalystVerdict:
        """Evaluates fundamental materiality, dual perspective (Bull/Bear), and supply chain links."""
        prompt = f"""Analyze this corporate news. Keep all Thai text to 1 sentence each. Reject clickbait.
- Symbol: ${article.symbol} | Publisher: {article.publisher}
- Headline: {article.headline}
- Snippet: {article.raw_snippet}
{timeline_context}

Return strict JSON:
{{
  "is_material": "<bool: does this fundamentally alter business value?>",
  "materiality_score": "<1.0-10.0: reject clickbait/Zacks/MotleyFool with low score>",
  "confidence_score": "<0-100: rumor=30, official=90+>",
  "scope": "<MACRO|SECTOR|MICRO>",
  "sentiment": "<POSITIVE|NEGATIVE|NEUTRAL>",
  "event_category": "<CLINICAL_TRIAL|EARNINGS|M_AND_A|REGULATORY|CONTRACT|RISK_EVENT|MACRO_EVENT>",
  "impact_summary": "<1 Thai sentence: how/why this affects price>",
  "bull_catalysts": "<1 Thai sentence: growth opportunity>",
  "bear_risks": "<1 Thai sentence: hidden risks>",
  "dca_guidance": "<1 Thai sentence: entry advice>",
  "thai_summary": "<1 Thai sentence: factual news summary>",
  "connected_stocks": [{{"symbol":"TICKER","relationship":"SUPPLIER|CUSTOMER|COMPETITOR|SYMPATHY_PEER","impact_direction":"POSITIVE|NEGATIVE","rationale_thai":"..."}}]
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

    async def evaluate_catalysts_batch(
        self, articles: list[CatalystArticle], timeline_context: str = ""
    ) -> list[CatalystVerdict]:
        """Evaluates multiple articles in a single API call to save RPM."""
        if not articles:
            return []
            
        articles_json = []
        for i, article in enumerate(articles):
            articles_json.append({
                "id": i,
                "symbol": article.symbol,
                "publisher": article.publisher,
                "headline": article.headline,
                "snippet": article.raw_snippet
            })
            
        import json
        articles_str = json.dumps(articles_json, ensure_ascii=False, indent=2)

        prompt = f"""You are an institutional financial analyst. Evaluate this batch of news. Keep text in Thai extremely concise (Get to the point).

Articles:
{articles_str}
{timeline_context}

Instructions for EACH article:
1. is_material: boolean, materiality_score: 1.0-10.0.
2. scope: MACRO, SECTOR, MICRO.
3. event_category: CLINICAL_TRIAL, EARNINGS, M_AND_A, etc.
4. confidence_score (0-100).
5. impact_summary: strictly 1 short sentence.
6. sentiment: POSITIVE, NEGATIVE, NEUTRAL.
7. bull_catalysts, bear_risks, dca_guidance, thai_summary: strictly 1 short sentence each.
8. connected_stocks: array of dicts (symbol, relationship, impact_direction, rationale_thai).

Return a strict JSON ARRAY where each object corresponds to an article ID and adheres exactly to this schema:
[
  {{
    "id": 0,
    "verdict": {{
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
      "connected_stocks": []
    }}
  }}
]
"""
        try:
            raw_json = await self._call_gemini(prompt)
            from src.utils import extract_json_from_llm
            data = extract_json_from_llm(raw_json)
            
            # Reconstruct list of verdicts in original order
            verdicts = []
            results_dict = {item["id"]: item.get("verdict", {}) for item in data}
            
            for i, article in enumerate(articles):
                v_dict = results_dict.get(i)
                if v_dict:
                    try:
                        verdicts.append(CatalystVerdict(**v_dict))
                    except Exception as err:
                        logger.error(f"Failed to parse verdict {i}: {err}")
                        verdicts.append(CatalystVerdict(is_material=False, materiality_score=0.0, confidence_score=0.0, scope="MICRO", sentiment="NEUTRAL", event_category="RISK_EVENT", impact_summary="Parsing Error", bull_catalysts="-", bear_risks="-", dca_guidance="-", thai_summary=article.headline, connected_stocks=[]))
                else:
                    verdicts.append(CatalystVerdict(is_material=False, materiality_score=0.0, confidence_score=0.0, scope="MICRO", sentiment="NEUTRAL", event_category="RISK_EVENT", impact_summary="Parsing Error", bull_catalysts="-", bear_risks="-", dca_guidance="-", thai_summary=article.headline, connected_stocks=[]))
                    
            return verdicts
            
        except Exception as e:
            logger.error(f"Error evaluating batch catalysts: {e}")
            # Fallback to empty verdicts
            return [CatalystVerdict(is_material=False, materiality_score=0.0, confidence_score=0.0, scope="MICRO", sentiment="NEUTRAL", event_category="RISK_EVENT", impact_summary="Error evaluating batch catalysts", bull_catalysts="-", bear_risks="-", dca_guidance="-", thai_summary=a.headline, connected_stocks=[]) for a in articles]

