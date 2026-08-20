import re
from typing import Optional


class DensityFilter:
    """Zero-Token Fact Density & Informativeness Filter Gate (Inspired by ClickGuard / arXiv:2607.20463)."""

    # Fact-bearing patterns
    FACT_PATTERNS = [
        r"\b\d+[\d,.]*%",                                       # 44%, 12.5%
        r"\$\d+[\d,.]*(?:[BMK]|billion|million)?\b",            # $30B, $500M, $1.4 billion
        r"\bphase\s*[123]\b",                                    # Phase 1, Phase 2, Phase 3
        r"\b(?:fda|sec|ftc|ema)\b",                             # Regulators
        r"\b(?:approval|approved|cleared|breakthrough)\b",       # Regulatory milestones
        r"\b(?:primary\s+endpoint|clinical\s+trial|topline)\b",  # Oncology / trials
        r"\b(?:earnings|revenue|eps|guidance|q[1-4])\b",         # Corporate financials
        r"\b(?:acquisition|merger|acquired|bought|deal)\b",      # M&A
        r"\b(?:contract|partnership|agreement|collaboration)\b",# Commercial deals
        r"\b(?:investigation|subpoena|lawsuit|recall)\b",       # Risk events
    ]

    # Clickbait / low-density patterns to penalize
    CLICKBAIT_PATTERNS = [
        r"should\s+you\s+buy",
        r"before\s+it\s+explodes",
        r"to\s+watch\s+this\s+week",
        r"millionaire[- ]maker",
        r"top\s+picks?",
        r"is\s+it\s+time\s+to\s+buy",
        r"here(?:'s|\s+is)\s+why",
        r"expert\s+shares?",
    ]

    # Ticker extraction patterns: $TICKER or (TICKER)
    TICKER_PATTERNS = [
        r"\$([A-Z]{1,5})\b",
        r"\(([A-Z]{1,5})\)",
    ]

    def extract_ticker(self, text: str) -> Optional[str]:
        """Extracts ticker symbol from headline or text."""
        for pattern in self.TICKER_PATTERNS:
            match = re.search(pattern, text)
            if match:
                ticker = match.group(1).upper()
                if ticker not in {"A", "I", "AN", "THE", "FOR", "AND", "OR", "USA", "USD", "EST", "EDT", "BKK", "CEO", "CFO", "FDA", "SEC", "EPS"}:
                    return ticker
        return None

    def is_high_density(self, headline: str, snippet: str = "") -> bool:
        """Evaluates whether the article possesses high factual density or is routine noise/clickbait."""
        full_text = f"{headline} {snippet}".lower()

        # Check for clickbait penalty
        for cb in self.CLICKBAIT_PATTERNS:
            if re.search(cb, full_text):
                # If clickbait pattern is matched, require at least 3 strong fact patterns to override
                fact_matches = sum(1 for fp in self.FACT_PATTERNS if re.search(fp, full_text))
                return fact_matches >= 3

        # Normal evaluation: check fact token count
        fact_matches = sum(1 for fp in self.FACT_PATTERNS if re.search(fp, full_text))
        return fact_matches >= 1
