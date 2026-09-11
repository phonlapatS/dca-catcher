import json
import logging
import re
from dataclasses import dataclass

from google import genai

from src.transform import EnrichedSignal
from src.insight_pipeline import LLMCaller, PipelineConfig

logger = logging.getLogger(__name__)


@dataclass
class GradeResult:
    symbol: str
    score: int          # 1-10 (Investment Attractiveness)
    confidence: int     # 0-100
    advice: str         # Thai-language advice from Gemini
    reasons: list[str]  # Reason tags, e.g. ["✅ RSI < 30", "⚠️ Low volume"]
    buy_targets: list[float] # e.g. [170.0, 160.0, 150.0]


class SignalGrader:
    """Uses Google Gemini to grade enriched stock signals.

    Delegates all LLM calls to the shared ``LLMCaller`` from
    ``insight_pipeline`` so that model lists, API key rotation,
    and quota fallback are defined in exactly one place.
    """

    def __init__(self, api_keys: list[str], config: PipelineConfig | None = None):
        """Configure the grader with shared LLMCaller instances."""
        from google import genai

        self.config = config or PipelineConfig()
        clients = [genai.Client(api_key=key) for key in api_keys]
        if not clients:
            logger.warning("No Gemini API keys provided! Grader will fail.")

        # Fast caller for quick scans, smart caller for advice/reports
        self.scan_llm = LLMCaller(clients, self.config.lite_models)
        self.advice_llm = LLMCaller(clients, self.config.smart_models)

    def grade(self, signal: EnrichedSignal, news: list[str] = None, risk_profile: str = None) -> GradeResult:
        """Send enriched signal dimensions to Gemini for grading.

        Constructs a prompt with the 3 dimension scores and asks Gemini
        to return a JSON response with score, confidence, advice, and reasons.
        Uses shared LLMCaller for automatic model fallback.
        """
        prompt = self._build_prompt(signal, news, risk_profile)
        try:
            data = self.scan_llm.call_json(prompt)
            return self._parse_data(data, signal.symbol)
        except Exception as e:
            logger.error(f"All Gemini models failed for {signal.symbol}: {e}")
            return GradeResult(
                symbol=signal.symbol,
                score=5,
                confidence=0,
                advice=f"Gemini API error: {e}",
                reasons=["⚠️ ไม่สามารถติดต่อ AI ได้ (API Error)"],
                buy_targets=[],
            )

    def _build_prompt(self, signal: EnrichedSignal, news: list[str] = None, risk_profile: str = None) -> str:
        """Build the Gemini prompt from enriched signal data and news.

        The prompt instructs Gemini to:
        1. Analyze the 3 dimensions (PRICE, FLOW, CONTEXT), indicators, and news
        2. Filter news using NER (Named Entity Recognition)
        3. Return JSON with: score (1-10), confidence (0-100),
           advice (Thai string), reasons (list of strings), and exactly 3 buy_targets.
        """
        dimensions_summary = []
        for name, score in signal.dimensions.items():
            dimensions_summary.append(
                f"- {name}: Label={score.label}, Score={score.score}, Reason={score.reason}"
            )
        dims_str = "\n".join(dimensions_summary)

        indicators_str = []
        if getattr(signal.snapshot, 'rsi', None) is not None:
            indicators_str.append(f"- RSI: {signal.snapshot.rsi}")
        if getattr(signal.snapshot, 'ma_50', None) is not None:
            indicators_str.append(f"- MA_50: {signal.snapshot.ma_50}")
        if getattr(signal.snapshot, 'bb_lower', None) is not None:
            indicators_str.append(f"- BB_lower: {signal.snapshot.bb_lower}")
        indicators_text = "\n".join(indicators_str) if indicators_str else "- No calculated indicators available"

        news_text = ""
        if news:
            top_news = news[:5]
            news_items = "\n".join([f"- {n}" for n in top_news])
            news_text = f"\nNews Headlines (Top 5):\n{news_items}"
            
        profile_text = f"\nUser Risk Profile:\n- The user's preferred DCA strategy is: '{risk_profile}'. Please adjust your Buy Targets and Advice to align with this strategy." if risk_profile else ""

        prompt = f"""You are a professional financial AI assisting with DCA investments. All explanations must be in Thai and extremely concise (Get to the point).

Analyze: {signal.symbol}
- Price: ${signal.snapshot.current_price}
- ATH Drawdown: {signal.snapshot.drawdown_pct}%
{profile_text}
Fundamental: P/E: {getattr(signal.snapshot, 'trailing_pe', 'N/A')}, PEG: {getattr(signal.snapshot, 'peg_ratio', 'N/A')}, Margin: {getattr(signal.snapshot, 'profit_margins', 'N/A')}, D/E: {getattr(signal.snapshot, 'debt_to_equity', 'N/A')}, FCF: {getattr(signal.snapshot, 'free_cash_flow', 'N/A')}
Indicators: {indicators_text}
Volume Flow: Anomaly={getattr(signal.snapshot, 'is_volume_anomaly', False)}, Current={signal.snapshot.volume}, 20dAvg={getattr(signal.snapshot, 'volume_20d_avg', 'N/A')}
{news_text}

Instructions:
1. Evaluate indicators and news.
2. Calculate "score" (1-10) and "confidence" (0-100).
3. Determine exactly 3 "buy_targets" (prices) that are realistic.
4. Keep 'advice' to exactly 1 short sentence summarizing the trend and action based strictly on data. Do not repeat obvious phrases like "เหมาะกับ DCA" because the user already knows this.
5. Keep 'reasons' to exactly 2 short bullet points (1 fundamental, 1 technical). You MUST use the exact metrics/numbers provided above to support your reason and prevent hallucination.

Return ONLY valid JSON matching this schema:
{{
    "score": <integer 1 to 10>,
    "confidence": <integer 0 to 100>,
    "advice": "<1 short sentence>",
    "reasons": ["<tag 1>", "<tag 2>"],
    "buy_targets": [<float>, <float>, <float>]
}}
"""
        return prompt

    def _parse_data(self, data: dict, symbol: str) -> GradeResult:
        """Build GradeResult from a parsed JSON dict."""
        return GradeResult(
            symbol=symbol,
            score=int(data.get("score", 5)),
            confidence=int(data.get("confidence", 0)),
            advice=str(data.get("advice", "No advice provided")),
            reasons=list(data.get("reasons", [])),
            buy_targets=list(data.get("buy_targets", [])),
        )

    def _parse_response(self, text: str, symbol: str) -> GradeResult:
        """Parse raw text/JSON from Gemini (backward compatibility helper)."""
        try:
            cleaned = text.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
                cleaned = re.sub(r"\s*```$", "", cleaned)
            data = json.loads(cleaned)
            return self._parse_data(data, symbol)
        except Exception as e:
            return GradeResult(
                symbol=symbol,
                score=5,
                confidence=0,
                advice=f"Failed to parse AI output: {e}",
                reasons=["⚠️ Parse error"],
                buy_targets=[],
            )
            
    def generate_insight_report(self, signal: EnrichedSignal, news: list[str], targets: list[float], risk_profile: str = None, fear_greed: str = "Unknown") -> str:
        """Legacy single-prompt insight report.

        .. deprecated::
            Use ``InsightPipeline.generate()`` instead for the Multi-Agent
            pipeline with Quality Gate.  This method is kept for backward
            compatibility only.
        """
        logger.warning("generate_insight_report is deprecated — use InsightPipeline.generate() instead.")
        indicators_str = []
        if getattr(signal.snapshot, 'rsi', None) is not None:
            indicators_str.append(f"RSI: {signal.snapshot.rsi}")
        if getattr(signal.snapshot, 'ma_50', None) is not None:
            indicators_str.append(f"MA50: {signal.snapshot.ma_50}")
        indicators_text = ", ".join(indicators_str) if indicators_str else "N/A"
        news_text = "\n".join(f"- {n}" for n in (news or [])[:3])

        prompt = f"""Write a Thai Deep Dive investment report for {signal.symbol}.
Price: ${signal.snapshot.current_price} | ATH Drawdown: {signal.snapshot.drawdown_pct}%
P/E: {getattr(signal.snapshot, 'trailing_pe', 'N/A')} | Indicators: {indicators_text}
Buy Targets: {targets}
Fear & Greed Index: {fear_greed}
News: {news_text}

Output ONLY a beautifully formatted Markdown report with emojis. No JSON. No introductory chat."""

        try:
            return self.advice_llm.call(prompt)
        except Exception:
            return "❌ ขออภัย ไม่สามารถสร้างบทวิเคราะห์เชิงลึกได้ในขณะนี้ เนื่องจากระบบ AI ขัดข้อง"

    def generate_advice(self, risk_profile: str, horizon: str, goal: str, sectors: list[str], count: str = "5", budget: str = "ไม่ระบุ") -> str:
        """Generate a personalized portfolio advice based on user survey.
        
        Args:
            risk_profile: User's risk tolerance string (e.g., 'รับความเสี่ยงได้ปานกลาง')
            horizon: Investment timeframe (e.g., '3-5 ปี')
            goal: Primary investment goal (e.g., 'เน้นเติบโต')
            sectors: List of 3 selected sectors (e.g., ['เทคโนโลยี', 'สุขภาพ', 'พลังงาน'])
            count: Number of stocks to recommend (e.g., '3', '5', '7', '10')
            budget: Monthly DCA budget (e.g., 'ประมาณ 3,000 บาท/เดือน')
            
        Returns:
            A formatted Markdown string containing the AI's stock recommendations and plan.
        """
        sectors_str = ", ".join(sectors)
        prompt = f"""You are a professional wealth manager. Keep output in Thai and extremely concise (Get to the point).

User Profile:
- Risk: {risk_profile if risk_profile else 'ไม่ได้ระบุ'}
- Horizon: {horizon}
- Goal: {goal}
- Sectors: {sectors_str}
- Size: {count} stocks
- Budget: {budget}

Output exactly this Markdown structure:

📊 **พอร์ตการลงทุน (Budget: {budget})**

**🎯 หุ้นแนะนำ {count} ตัว:**
1. **[Ticker 1]** ([Allocation %]) - [เหตุผล 1 ประโยค พร้อมระบุ P/E ปัจจุบัน หรือข้อมูลซัพพอร์ตสั้นๆ]
...

**📝 สรุปกลยุทธ์:**
[1-2 ประโยคสรุปการจัดสรร (เช่น 70% Growth / 30% Dividend) พร้อมประมาณการผลตอบแทนคาดหวังแบบสั้นสุดๆ]

Make sure the {count} stocks fit the profile. Provide the output directly, no introductory chat.
"""
        
        try:
            return self.advice_llm.call(prompt)
        except Exception as e:
            return f"⚠️ ขออภัยครับ AI ระบบขัดข้อง ไม่สามารถจัดพอร์ตให้ได้ในขณะนี้: {e}"
