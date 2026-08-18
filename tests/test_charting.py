import pytest
from src.charting import ChartGenerator

def test_chart_generator_valid():
    # Test chart generation for a real symbol
    targets = [120.0, 110.0, 100.0]
    chart_bytes = ChartGenerator.generate_target_chart(
        symbol="AAPL",
        current_price=125.0,
        targets=targets,
        period="1mo"
    )
    assert chart_bytes is not None
    assert isinstance(chart_bytes, bytes)
    assert len(chart_bytes) > 1000
    # PNG signature check
    assert chart_bytes[:8] == b'\x89PNG\r\n\x1a\n'

def test_chart_generator_invalid_symbol():
    chart_bytes = ChartGenerator.generate_target_chart(
        symbol="INVALID_SYMBOL_XYZ_12345",
        current_price=10.0,
        targets=[9.0, 8.0, 7.0]
    )
    assert chart_bytes is None

def test_chart_generator_adaptive_timeframe_expansion():
    # Target significantly lower than 3-month range to trigger 6M/1Y expansion
    chart_bytes = ChartGenerator.generate_target_chart(
        symbol="AAPL",
        current_price=220.0,
        targets=[210.0, 195.0, 160.0]  # $160 is below 3M low for AAPL
    )
    assert chart_bytes is not None
    assert isinstance(chart_bytes, bytes)
    assert chart_bytes[:8] == b'\x89PNG\r\n\x1a\n'

def test_chart_generator_empty_targets():
    # Test when targets list is empty
    chart_bytes = ChartGenerator.generate_target_chart(
        symbol="AAPL",
        current_price=220.0,
        targets=[]
    )
    assert chart_bytes is not None
    assert isinstance(chart_bytes, bytes)
