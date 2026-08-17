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

        prompt = f"""You are a professional financial analyst AI assisting with Dollar-Cost Averaging (DCA) investment decisions. All explanations, reasons, and advice must be in Thai.

Analyze the stock signal for symbol: {signal.symbol}

Market Snapshot:
- Current Price: ${signal.snapshot.current_price}
- Volume: {signal.snapshot.volume}
- ATH Price: ${signal.snapshot.ath_price}
- Drawdown from ATH: {signal.snapshot.drawdown_pct}%
{profile_text}

Fundamental Data (if available):
- P/E Ratio (Trailing): {getattr(signal.snapshot, 'trailing_pe', 'N/A')}
- PEG Ratio: {getattr(signal.snapshot, 'peg_ratio', 'N/A')}
- Revenue Growth: {getattr(signal.snapshot, 'revenue_growth', 'N/A')}
- Profit Margins: {getattr(signal.snapshot, 'profit_margins', 'N/A')}
- Debt to Equity: {getattr(signal.snapshot, 'debt_to_equity', 'N/A')}

Indicators:
{indicators_text}

Dimensions:
{dims_str}
{news_text}

1. Evaluate the combined dimensions (PRICE, FLOW, CONTEXT), indicators, and news.
2. Filter the news using NER (Named Entity Recognition) to ensure the news is truly about {signal.symbol} and not just noise. Only consider "true news" in your analysis.
3. Calculate an overall "Investment Attractiveness Score" from 1 to 10 (1 = Avoid, 10 = Strong Buy).
4. Calculate exactly 3 suggested buy target prices (DCA entry points). **CRITICAL:** The targets must be REALISTIC based on current volatility, volume, and news sentiment. Do not place them too close to the current price (e.g. less than 1% drop) unless the trend is extremely strong. Do not place them unrealistically far (e.g. 50% drop) unless there is a severe crisis. Ensure consistency with the user's risk profile.
5. Output concise Thai reasoning.
6. Return ONLY a valid raw JSON object (without markdown code formatting or extraneous text) matching this lean schema:
{{
    "score": <integer 1 to 10>,
    "confidence": <integer 0 to 100>,
    "advice": "<Thai string containing practical DCA investment advice>",
    "reasons": ["<Thai tag string 1 with ✅ or ⚠️>", "<Thai tag string 2>"],
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
        prompt = self._build_prompt(signal, news, risk_profile)
        prompt += f"\n\n--- INSTRUCTION OVERRIDE ---\n"
        prompt += f"The AI previously selected these 3 buy targets: {targets}\n"
        prompt += f"The current CNN Fear & Greed Index is: {fear_greed}\n"
        prompt += "Write a comprehensive Thai-language Deep Dive Report.\n"
        prompt += "Output ONLY a beautifully formatted Markdown report with emojis. No JSON."

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
        prompt = f"""You are a professional wealth manager and financial AI assistant. All explanations must be in Thai.

The user needs a customized stock portfolio recommendation. Here is their profile:
- Risk Profile: {risk_profile if risk_profile else 'ไม่ได้ระบุ'}
- Time Horizon: {horizon}
- Investment Goal: {goal}
- Preferred Sectors: {sectors_str}
- Number of Stocks Requested: {count}
- Monthly DCA Budget: {budget}

Please generate a highly professional and tailored investment plan. Your output must exactly follow this Markdown structure:

📊 **พอร์ตการลงทุนที่ออกแบบมาเพื่อคุณโดยเฉพาะ**
(โปรไฟล์: [สรุปโปรไฟล์สั้นๆ] | งบลงทุน: {budget})

**🎯 รายชื่อหุ้น {count} ตัว (Custom Portfolio):**
1. **[Ticker 1]** - [เหตุผลที่ตรงกับความต้องการและธีมที่เลือก 1-2 บรรทัด]
... (List exactly {count} stocks)

**📝 แผนการลงทุน & สัดส่วนพอร์ต (Action Plan):**
[แนะนำว่าควรแบ่งเงินซื้อตัวไหนกี่เปอร์เซ็นต์ (เช่น Core & Satellite) และวิธีการแบ่งเงิน {budget} ไปลงทุนในหุ้นแต่ละตัวต่อเดือน]

**📈 คาดการณ์การเติบโต vs เงินเฟ้อ (Growth Projection):**
[วิเคราะห์เปรียบเทียบผลตอบแทนคาดหวังของพอร์ตนี้เทียบกับเงินเฟ้อเฉลี่ย 3% ต่อปี ให้เห็นภาพว่าเงินทุนรวมจากการ DCA เดือนละ {budget} จะงอกเงยประมาณเท่าไหร่ตาม Time Horizon ({horizon}) ที่กำหนด]

Make sure the {count} recommended stocks are real, well-known US or global stocks that strictly fit their risk profile, horizon, goal, and the 3 chosen sectors. Provide the output directly, no introductory or concluding chat.
"""
        
        try:
            return self.advice_llm.call(prompt)
        except Exception as e:
            return f"⚠️ ขออภัยครับ AI ระบบขัดข้อง ไม่สามารถจัดพอร์ตให้ได้ในขณะนี้: {e}"
