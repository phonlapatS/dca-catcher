import pytest
from src.catalyst.verifiers.density_filter import DensityFilter
from src.catalyst.verifiers.market_check import MarketMicrostructureChecker

def test_extract_ticker_symbol():
    filter_gate = DensityFilter()
    assert filter_gate.extract_ticker("Moderna ($MRNA) announces phase 3 results") == "MRNA"
    assert filter_gate.extract_ticker("NVIDIA Corp (NVDA) unveils Blackwell server architecture") == "NVDA"
    assert filter_gate.extract_ticker("Random text with no ticker") is None

def test_density_filter_accepts_factual_headlines():
    filter_gate = DensityFilter()
    # High fact density: FDA, Phase 3, percentages, clinical keywords
    good_headline_1 = "Moderna Reports Positive Phase 3 Trial Results with 44% Risk Reduction"
    good_snippet_1 = "INTerpath-001 study met primary endpoint in melanoma patients."
    assert filter_gate.is_high_density(good_headline_1, good_snippet_1) is True

    # Financial facts: revenue beat, dollar amounts, EPS
    good_headline_2 = "Nvidia Q2 Revenue Jumps 122% to $30.04 Billion, Beats Estimates"
    good_snippet_2 = "Data center revenue rose to $26.3B, board approves $50B share buyback."
    assert filter_gate.is_high_density(good_headline_2, good_snippet_2) is True

def test_density_filter_rejects_clickbait_and_low_density():
    filter_gate = DensityFilter()
    # Clickbait / opinion with zero hard facts
    clickbait_1 = "Should You Buy This Stock Before It Explodes?"
    snippet_1 = "Experts share their thoughts on where the market is heading next."
    assert filter_gate.is_high_density(clickbait_1, snippet_1) is False

    clickbait_2 = "3 Stocks to Watch This Week According to Wall Street"
    snippet_2 = "Here are our top picks for smart investors."
    assert filter_gate.is_high_density(clickbait_2, snippet_2) is False

def test_market_microstructure_check_valid_liquidity():
    checker = MarketMicrostructureChecker()
    # Pre-market price $65.0, pre-market volume 50,000 shares -> Dollar volume = $3.25M (> $2M threshold), Spread 0.4% (< 2.0%)
    is_valid, reason = checker.validate_premarket_liquidity(
        price=65.0,
        premarket_volume=50_000,
        bid_price=64.85,
        ask_price=65.10
    )
    assert is_valid is True
    assert "Passed" in reason

def test_market_microstructure_check_rejects_illiquid():
    checker = MarketMicrostructureChecker()
    # Dollar volume only $65.0 * 500 = $32,500 (< $2M threshold)
    is_valid, reason = checker.validate_premarket_liquidity(
        price=65.0,
        premarket_volume=500,
        bid_price=64.0,
        ask_price=66.0
    )
    assert is_valid is False
    assert "Low Dollar Volume" in reason

def test_market_microstructure_check_rejects_wide_spread():
    checker = MarketMicrostructureChecker()
    # Wide spread 60.0 to 65.0 = 8.0% spread (> 2.0% threshold)
    is_valid, reason = checker.validate_premarket_liquidity(
        price=62.5,
        premarket_volume=100_000,
        bid_price=60.0,
        ask_price=65.0
    )
    assert is_valid is False
    assert "Wide Bid-Ask Spread" in reason
