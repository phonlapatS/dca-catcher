"""
Multi-Agent Insight Pipeline for DCA Catcher.

Architecture:
    Data Collector (no LLM) → 3 Specialist Agents (flash-lite) → Composer (flash) → Quality Gate (flash)

Each agent communicates through a SharedContext dict.
Agent 3 reads Agent 1+2 results before producing targets.
Quality Gate scores 0-100 and can remark specific fixes without full regeneration.
"""

import json
import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from google import genai

from src.fetcher import StockSnapshot
from src.scrapers.sentiment import get_fear_greed_index, get_recent_news
from src.transform import EnrichedSignal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration — all tunables in one place
# ---------------------------------------------------------------------------

@dataclass
class PipelineConfig:
    """Central configuration for the Insight Pipeline.

    Every tuneable value lives here instead of being scattered
    across agent classes.  Pass an instance into InsightPipeline
    to override any default.
    """

    # Model tiers (order = priority; first model tried first)
    lite_models: list[str] = field(
        default_factory=lambda: [
            "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite",
            "gemini-3-flash-preview",
        ]
    )
    smart_models: list[str] = field(
        default_factory=lambda: [
            "gemini-3.5-flash",
            "gemini-3.6-flash",
            "gemini-3-flash-preview",
        ]
    )

    # Quality Gate
    quality_pass_threshold: int = 75          # minimum score to pass
    max_retries: int = 2                      # composer revision attempts
    quality_weights: dict[str, int] = field(  # scoring rubric
        default_factory=lambda: {
            "factual": 30,
            "news_references": 25,
            "target_justification": 25,
            "coherence": 20,
        }
    )

    # Target ranges (% below current price)
    target_ranges: dict[str, tuple[float, float]] = field(
        default_factory=lambda: {
            "conservative": (2.0, 5.0),
            "moderate": (5.0, 12.0),
            "deep_value": (12.0, 25.0),
        }
    )

    # News filtering
    max_news_headlines: int = 6
    news_recency_days: int = 7

    # Output
    default_risk_profile: str = "ไม่ได้ระบุ"


# Quality badge tiers (threshold, emoji, label)
QUALITY_TIERS: list[tuple[int, str, str]] = [
    (90, "🟢", "สูงมาก"),
    (75, "🟡", "ดี"),
    (50, "🟠", "ปานกลาง"),
    (0,  "🔴", "ต่ำ"),
]

# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class AgentResult:
    """Standardised output from any agent."""
    agent_name: str
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""
    error: str | None = None
    tokens_used: int = 0


@dataclass
class QualityVerdict:
    """Output of the Quality Gate agent."""
    score: int  # 0-100
    passed: bool
    remarks: list[dict[str, str]] = field(default_factory=list)
    summary: str = ""


# ---------------------------------------------------------------------------
# LLM Caller — centralised, with fallback + retry
# ---------------------------------------------------------------------------

class LLMCaller:
    """Thread-safe, fault-tolerant LLM caller with model fallback.

    Encapsulates the retry-across-models logic so every agent
    can simply call `self.llm.call(prompt)` without caring about
    quota errors or model availability.
    """

    def __init__(self, clients: list[genai.Client], models: list[str]):
        self.clients = clients
        self.models = models

    def call(self, prompt: str) -> str:
        """Try every (client × model) combination. Raise on total failure."""
        last_error: Exception | None = None

        for client in self.clients:
            for model_name in self.models:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                    )
                    return response.text.strip()
                except Exception as e:
                    logger.warning(f"LLMCaller: {model_name} failed — {e}")
                    last_error = e
                    continue

        raise RuntimeError(f"All LLM models exhausted. Last error: {last_error}")

    def call_json(self, prompt: str) -> dict:
        """Call LLM and parse the response as JSON, with cleanup."""
        raw = self.call(prompt)
        cleaned = raw.strip()
        # Strip markdown code fences
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        return json.loads(cleaned)


# ---------------------------------------------------------------------------
# Abstract Base Agent
# ---------------------------------------------------------------------------

class BaseAgent(ABC):
    """Every specialist agent inherits from this."""

    name: str = "BaseAgent"

    def __init__(self, llm: LLMCaller, config: PipelineConfig | None = None):
        self.llm = llm
        self.config = config or PipelineConfig()

    @abstractmethod
    def run(self, context: dict[str, Any]) -> AgentResult:
        """Execute this agent's task using shared context."""
        ...

    def _safe_run(self, context: dict[str, Any]) -> AgentResult:
        """Wrap run() with error handling so one agent crash doesn't kill the pipeline."""
        try:
            return self.run(context)
        except Exception as e:
            logger.error(f"Agent '{self.name}' crashed: {e}", exc_info=True)
            return AgentResult(
                agent_name=self.name,
                success=False,
                error=str(e),
            )


# ---------------------------------------------------------------------------
# Agent 1: Fundamental Analyst
# ---------------------------------------------------------------------------

class FundamentalAgent(BaseAgent):
    """Analyses P/E, PEG, margins, debt, volume, drawdown."""

    name = "Fundamental Analyst"

    def run(self, context: dict[str, Any]) -> AgentResult:
        prompt = f"""You are a Fundamental Stock Analyst. Analyse ONLY the fundamental data below.
Output a JSON object with these exact keys:
- "valuation": string (Thai) — is the stock cheap, fair, or expensive? Why?
- "growth_quality": string (Thai) — is the growth sustainable? Revenue growth vs margins.
- "financial_health": string (Thai) — debt level, margin stability.
- "volume_signal": string (Thai) — is current volume normal or anomalous?
- "risk_level": "LOW" | "MODERATE" | "HIGH"

Data:
- Symbol: {context['symbol']}
- Current Price: ${context['price']}
- Volume: {context['volume']:,}
- ATH: ${context['ath_price']}
- Drawdown: {context['drawdown_pct']}%
- P/E Ratio: {context.get('pe_ratio', 'N/A')}
- PEG Ratio: {context.get('peg_ratio', 'N/A')}
- Revenue Growth: {context.get('revenue_growth', 'N/A')}
- Profit Margins: {context.get('profit_margins', 'N/A')}
- Debt to Equity: {context.get('debt_to_equity', 'N/A')}

Return ONLY valid JSON. No markdown, no explanation outside JSON."""

        data = self.llm.call_json(prompt)
        return AgentResult(agent_name=self.name, success=True, data=data)


# ---------------------------------------------------------------------------
# Agent 2: News & Sentiment Analyst
# ---------------------------------------------------------------------------

class NewsAnalystAgent(BaseAgent):
    """Validates news relevance and scores impact."""

    name = "News & Sentiment Analyst"

    def run(self, context: dict[str, Any]) -> AgentResult:
        news_list = context.get("news_headlines", [])
        if not news_list:
            return AgentResult(
                agent_name=self.name,
                success=True,
                data={
                    "validated_news": [],
                    "overall_sentiment": "NEUTRAL",
                    "sentiment_summary": "ไม่พบข่าวล่าสุดสำหรับหุ้นตัวนี้",
                },
            )

        news_str = "\n".join(f"- {n}" for n in news_list)
        prompt = f"""You are a Financial News Analyst specialising in NER-based news validation.

Your tasks:
1. For EACH headline, determine if it is truly about {context['symbol']} (not just mentioning it in passing).
2. For validated headlines, assess the impact: POSITIVE, NEGATIVE, or NEUTRAL.
3. Provide a brief Thai explanation of WHY it matters to an investor.
4. Determine the overall sentiment: BULLISH, BEARISH, or NEUTRAL.

Headlines:
{news_str}

Fear & Greed Index: {context.get('fear_greed', 'Unknown')}

Return ONLY valid JSON with this schema:
{{
    "validated_news": [
        {{"title": "...", "relevant": true/false, "impact": "POSITIVE/NEGATIVE/NEUTRAL", "reason": "Thai string"}},
        ...
    ],
    "overall_sentiment": "BULLISH/BEARISH/NEUTRAL",
    "sentiment_summary": "Thai string summarising the news landscape"
}}"""

        data = self.llm.call_json(prompt)
        return AgentResult(agent_name=self.name, success=True, data=data)


# ---------------------------------------------------------------------------
# Agent 3: Risk & Target Strategist
# ---------------------------------------------------------------------------

class RiskTargetAgent(BaseAgent):
    """Sets 3 realistic DCA targets using Agent 1 + 2 outputs."""

    name = "Risk & Target Strategist"

    def run(self, context: dict[str, Any]) -> AgentResult:
        # Read Agent 1 + 2 results (inter-agent communication)
        fundamental = context.get("agent_1_fundamental", {})
        news = context.get("agent_2_news", {})
        ranges = self.config.target_ranges

        prompt = f"""You are a DCA Risk & Target Strategist. Your job is to set 3 realistic buy target prices.

You MUST base your targets on the combined analysis below. Do NOT guess.

Symbol: {context['symbol']}
Current Price: ${context['price']}
ATH: ${context['ath_price']}
Drawdown: {context['drawdown_pct']}%
User Risk Profile: {context.get('risk_profile', 'ไม่ได้ระบุ')}

--- Fundamental Analysis (from Agent 1) ---
{json.dumps(fundamental, ensure_ascii=False, indent=2) if fundamental else 'ไม่มีข้อมูล (Agent 1 ล้มเหลว)'}

--- News Sentiment (from Agent 2) ---
{json.dumps(news, ensure_ascii=False, indent=2) if news else 'ไม่มีข้อมูล (Agent 2 ล้มเหลว)'}

Rules:
- Target 1: Conservative entry (small dip, {ranges['conservative'][0]}-{ranges['conservative'][1]}% below current price)
- Target 2: Moderate entry (meaningful pullback, {ranges['moderate'][0]}-{ranges['moderate'][1]}% below current price)
- Target 3: Deep value entry (significant correction, {ranges['deep_value'][0]}-{ranges['deep_value'][1]}% below current price)
- Adjust ranges based on user's risk profile and the fundamental/news context.
- If fundamentals are strong and news is bullish, targets can be tighter.
- If fundamentals are weak or news is bearish, targets should be wider.

Return ONLY valid JSON:
{{
    "targets": [float, float, float],
    "target_explanations": [
        "Thai string explaining target 1",
        "Thai string explaining target 2",
        "Thai string explaining target 3"
    ],
    "overall_strategy": "Thai string — how should a DCA investor play this?"
}}"""

        data = self.llm.call_json(prompt)
        return AgentResult(agent_name=self.name, success=True, data=data)


# ---------------------------------------------------------------------------
# Composer Agent
# ---------------------------------------------------------------------------

class ComposerAgent(BaseAgent):
    """Composes a polished Thai report from all agent outputs."""

    name = "Report Composer"

    def run(self, context: dict[str, Any]) -> AgentResult:
        fundamental = context.get("agent_1_fundamental", {})
        news = context.get("agent_2_news", {})
        targets = context.get("agent_3_targets", {})

        prompt = f"""You are a Master Investment Strategist writing a comprehensive Thai-language report.

Your role: Synthesise the analysis from 3 specialist analysts into ONE cohesive, easy-to-read article.

--- Raw Market Data ---
Symbol: {context['symbol']}
Current Price: ${context['price']}
Volume: {context['volume']:,}
ATH: ${context['ath_price']}
Drawdown: {context['drawdown_pct']}%
P/E: {context.get('pe_ratio', 'N/A')}
PEG: {context.get('peg_ratio', 'N/A')}
Fear & Greed Index: {context.get('fear_greed', 'Unknown')}

--- Agent 1: Fundamental Analysis ---
{json.dumps(fundamental, ensure_ascii=False, indent=2)}

--- Agent 2: News & Sentiment ---
{json.dumps(news, ensure_ascii=False, indent=2)}

--- Agent 3: Risk & Target Strategy ---
{json.dumps(targets, ensure_ascii=False, indent=2)}

Writing Guidelines:
1. Write in normal, easy-to-understand Thai (ภาษาคนธรรมดา เข้าใจง่าย) with deep expertise.
2. The report must flow as a continuous, well-composed article — NOT a list of bullet points.
3. Structure: Context → News Impact → Target Justification → Conclusion.
4. You MUST reference specific news headlines and data points (P/E, Volume, Drawdown) in your narrative.
5. End with the Fear & Greed Index and what it means for this stock.
6. Use emojis tastefully for section headers.

Output ONLY the Markdown report. No JSON. No introductory filler."""

        raw = self.llm.call(prompt)
        return AgentResult(agent_name=self.name, success=True, data={"report": raw}, raw_text=raw)

    def revise(self, context: dict[str, Any], remarks: list[dict[str, str]]) -> AgentResult:
        """Revise ONLY the remarked sections — do not regenerate the whole report."""
        draft = context.get("draft_report", "")
        remarks_str = "\n".join(
            f"- Section '{r['section']}': {r['issue']}" for r in remarks
        )

        prompt = f"""You previously wrote this investment report:

{draft}

The Quality Gate reviewer found these issues:
{remarks_str}

Please fix ONLY the issues listed above. Keep everything else exactly the same.
Output the FULL corrected report (with fixes applied). No JSON. No explanation."""

        raw = self.llm.call(prompt)
        return AgentResult(agent_name=self.name, success=True, data={"report": raw}, raw_text=raw)


# ---------------------------------------------------------------------------
# Quality Gate Agent
# ---------------------------------------------------------------------------

class QualityGateAgent(BaseAgent):
    """Reviews the composed report for accuracy, completeness, and coherence."""

    name = "Quality Gate"

    def run(self, context: dict[str, Any]) -> AgentResult:
        draft = context.get("draft_report", "")
        fundamental = context.get("agent_1_fundamental", {})
        news = context.get("agent_2_news", {})
        targets = context.get("agent_3_targets", {})
        w = self.config.quality_weights
        threshold = self.config.quality_pass_threshold

        prompt = f"""You are a strict Quality Assurance Reviewer for investment reports.

Review the draft report below against the source data. Score it 0-100.

--- Source Data ---
Symbol: {context['symbol']}, Price: ${context['price']}, P/E: {context.get('pe_ratio', 'N/A')}, Drawdown: {context['drawdown_pct']}%
Fundamental Analysis: {json.dumps(fundamental, ensure_ascii=False)}
News Analysis: {json.dumps(news, ensure_ascii=False)}
Target Strategy: {json.dumps(targets, ensure_ascii=False)}
Fear & Greed: {context.get('fear_greed', 'Unknown')}

--- Draft Report ---
{draft}

Scoring Criteria (total 100):
- Factual Accuracy ({w['factual']} pts): Do prices, P/E, volume match source data? No hallucinated numbers?
- News References ({w['news_references']} pts): Does the report mention the validated news from Agent 2?
- Target Justification ({w['target_justification']} pts): Are the 3 targets explained with data-backed reasoning?
- Coherence & Flow ({w['coherence']} pts): Does it read as a continuous article in easy Thai?

Return ONLY valid JSON:
{{
    "score": <int 0-100>,
    "factual_score": <int 0-{w['factual']}>,
    "news_score": <int 0-{w['news_references']}>,
    "target_score": <int 0-{w['target_justification']}>,
    "coherence_score": <int 0-{w['coherence']}>,
    "passed": <bool>,
    "remarks": [
        {{"section": "...", "issue": "Thai string describing what to fix"}},
        ...
    ],
    "summary": "Thai string — overall assessment"
}}

Set "passed" to true if score >= {threshold}. Set "passed" to false otherwise."""

        data = self.llm.call_json(prompt)
        verdict = QualityVerdict(
            score=data.get("score", 0),
            passed=data.get("passed", False),
            remarks=data.get("remarks", []),
            summary=data.get("summary", ""),
        )
        return AgentResult(
            agent_name=self.name,
            success=True,
            data=data,
        )


# ---------------------------------------------------------------------------
# Insight Pipeline Orchestrator
# ---------------------------------------------------------------------------

class InsightPipeline:
    """Orchestrates the full multi-agent insight generation pipeline.

    Flow:
        1. Data Collection (no LLM)
        2. Specialist Analysis (3 agents, flash-lite)
        3. Composition (flash)
        4. Quality Gate (flash) — retry up to config.max_retries
    """

    def __init__(self, api_keys: list[str], config: PipelineConfig | None = None):
        self.config = config or PipelineConfig()

        clients = [genai.Client(api_key=key) for key in api_keys]
        if not clients:
            raise ValueError("InsightPipeline requires at least one Gemini API key.")

        lite_llm = LLMCaller(clients, self.config.lite_models)
        smart_llm = LLMCaller(clients, self.config.smart_models)

        self.fundamental_agent = FundamentalAgent(lite_llm, self.config)
        self.news_agent = NewsAnalystAgent(lite_llm, self.config)
        self.risk_agent = RiskTargetAgent(lite_llm, self.config)
        self.composer = ComposerAgent(smart_llm, self.config)
        self.quality_gate = QualityGateAgent(smart_llm, self.config)

    def _collect_data(
        self,
        signal: EnrichedSignal,
        news_headlines: list[str],
        fear_greed: str,
        risk_profile: str | None,
    ) -> dict[str, Any]:
        """Phase 1: Build the shared context from raw data (no LLM)."""
        snapshot = signal.snapshot
        return {
            "symbol": signal.symbol,
            "price": snapshot.current_price,
            "volume": snapshot.volume,
            "ath_price": snapshot.ath_price,
            "drawdown_pct": snapshot.drawdown_pct,
            "pe_ratio": getattr(snapshot, "trailing_pe", None),
            "peg_ratio": getattr(snapshot, "peg_ratio", None),
            "revenue_growth": getattr(snapshot, "revenue_growth", None),
            "profit_margins": getattr(snapshot, "profit_margins", None),
            "debt_to_equity": getattr(snapshot, "debt_to_equity", None),
            "news_headlines": news_headlines,
            "fear_greed": fear_greed,
            "risk_profile": risk_profile or self.config.default_risk_profile,
        }

    def generate(
        self,
        signal: EnrichedSignal,
        news_headlines: list[str],
        fear_greed: str,
        risk_profile: str | None = None,
        on_progress: callable = None,
    ) -> tuple[str, dict[str, Any]]:
        """Run the full pipeline and return (report_text, metadata).

        Args:
            signal: Enriched market signal
            news_headlines: Pre-fetched news titles
            fear_greed: CNN Fear & Greed rating string
            risk_profile: User's risk profile string
            on_progress: Optional callback(stage_name: str) for UI updates

        Returns:
            Tuple of (final_report_markdown, pipeline_metadata_dict)
        """
        def progress(msg: str):
            if on_progress:
                on_progress(msg)

        metadata: dict[str, Any] = {"retries": 0, "quality_score": 0}

        # --- Phase 1: Data Collection ---
        progress("📊 กำลังรวบรวมข้อมูลตลาด...")
        context = self._collect_data(signal, news_headlines, fear_greed, risk_profile)

        # --- Phase 2: Specialist Analysis (3 agents) ---
        progress("🔵 Agent 1: กำลังวิเคราะห์ข้อมูลพื้นฐาน...")
        result_1 = self.fundamental_agent._safe_run(context)
        context["agent_1_fundamental"] = result_1.data if result_1.success else {}
        metadata["agent_1"] = {"success": result_1.success, "error": result_1.error}

        progress("🟢 Agent 2: กำลังกรองและวิเคราะห์ข่าว...")
        result_2 = self.news_agent._safe_run(context)
        context["agent_2_news"] = result_2.data if result_2.success else {}
        metadata["agent_2"] = {"success": result_2.success, "error": result_2.error}

        # Agent 3 reads Agent 1+2 results (inter-agent communication)
        progress("🟠 Agent 3: กำลังประเมินความเสี่ยงและตั้งเป้าหมาย...")
        result_3 = self.risk_agent._safe_run(context)
        context["agent_3_targets"] = result_3.data if result_3.success else {}
        metadata["agent_3"] = {"success": result_3.success, "error": result_3.error}
        metadata["targets"] = context.get("agent_3_targets", {}).get("targets", [])
        metadata["price"] = context.get("price")
        metadata["symbol"] = context.get("symbol")

        # --- Phase 3: Composition ---
        progress("📝 กำลังเรียบเรียงบทวิเคราะห์...")
        compose_result = self.composer._safe_run(context)
        if not compose_result.success:
            return self._fallback_report(context, metadata), metadata

        draft = compose_result.data.get("report", "")
        context["draft_report"] = draft

        # --- Phase 4: Quality Gate (with retry loop) ---
        final_report = draft
        for attempt in range(1 + self.config.max_retries):
            progress(f"🔬 Quality Gate: กำลังตรวจสอบรอบที่ {attempt + 1}...")
            qg_result = self.quality_gate._safe_run(context)

            if not qg_result.success:
                logger.warning("Quality Gate agent crashed; skipping QA.")
                metadata["quality_score"] = -1
                metadata["quality_error"] = qg_result.error
                break

            score = qg_result.data.get("score", 0)
            passed = qg_result.data.get("passed", False)
            remarks = qg_result.data.get("remarks", [])
            metadata["quality_score"] = score
            metadata["quality_details"] = qg_result.data

            if passed or score >= self.config.quality_pass_threshold:
                logger.info(f"Quality Gate PASSED with score {score}/100.")
                break

            if attempt < self.config.max_retries and remarks:
                # Revise only the problematic sections
                progress(f"🔄 แก้ไขจุดที่ต้องปรับปรุง ({len(remarks)} จุด)...")
                metadata["retries"] = attempt + 1
                revise_result = self.composer.revise(context, remarks)
                if revise_result.success:
                    final_report = revise_result.data.get("report", final_report)
                    context["draft_report"] = final_report
                else:
                    logger.warning("Revision failed; using previous draft.")
                    break
            else:
                logger.info(f"Quality Gate score {score}/100 after max retries. Proceeding.")
                break

        final_report = context.get("draft_report", final_report)

        # Append quality badge
        badge = self._quality_badge(metadata.get("quality_score", 0))
        final_report += f"\n\n---\n{badge}"

        return final_report, metadata

    def _quality_badge(self, score: int) -> str:
        """Generate a quality confidence badge for the report footer."""
        emoji, label = "🔴", "ต่ำ"
        for threshold, tier_emoji, tier_label in QUALITY_TIERS:
            if score >= threshold:
                emoji, label = tier_emoji, tier_label
                break

        return (
            f"{emoji} **AI Confidence Score:** {score}/100 ({label})\n"
            f"_วิเคราะห์โดย Multi-Agent Pipeline (3 Analysts + Quality Gate)_"
        )

    def _fallback_report(self, context: dict, metadata: dict) -> str:
        """Emergency fallback when Composer completely fails."""
        metadata["fallback"] = True
        symbol = context["symbol"]
        price = context["price"]
        fg = context.get("fear_greed", "Unknown")
        return (
            f"⚠️ **{symbol} — Fallback Report**\n\n"
            f"ระบบ AI ไม่สามารถเรียบเรียงบทวิเคราะห์ฉบับเต็มได้ในขณะนี้\n\n"
            f"📊 ราคาปัจจุบัน: ${price:,.2f}\n"
            f"📉 Drawdown: {context['drawdown_pct']}%\n"
            f"🌡️ Fear & Greed: {fg}\n\n"
            f"กรุณาลองอีกครั้งในภายหลัง หรือใช้ /scan {symbol} เพื่อดูสรุปสั้นๆ"
        )
