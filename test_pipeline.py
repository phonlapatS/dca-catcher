import asyncio
from src.fetcher import MarketDataFetcher
from src.transform import DataTransformer
import json
from dataclasses import asdict

async def main():
    print("🚀 Running Phase 1 Pipeline Test...\n")
    
    # 1. Fetch
    print("1️⃣ EXTRACT: Fetching market data from Yahoo Finance...")
    symbols = ["NVDA", "AAPL", "PTT.BK"]
    fetcher = MarketDataFetcher()
    snapshots = fetcher.fetch(symbols)
    
    for sym, snap in snapshots.items():
        print(f"  - {sym}: ${snap.current_price} (ATH: ${snap.ath_price}, Drawdown: {snap.drawdown_pct}%)")
        
    print("\n2️⃣ TRANSFORM: Enriching data into 3 dimensions...")
    transformer = DataTransformer()
    enriched = transformer.enrich(snapshots)
    
    for sym, signal in enriched.items():
        print(f"\n📊 {sym} Enriched Signal:")
        print(json.dumps(asdict(signal), indent=2, ensure_ascii=False))
        
    print("\n3️⃣ ANALYZE: Sending to Gemini AI for final grading...")
    import os
    from src.grader import SignalGrader
    
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("⚠️ No GEMINI_API_KEY found in environment variables.")
        print("To see the AI grading, run the script like this:")
        print('export GEMINI_API_KEY="your_api_key_here" && python test_pipeline.py')
        return
        
    grader = SignalGrader(api_key=api_key, model_name="gemini-3.5-flash")
    
    for sym, signal in enriched.items():
        print(f"\n🧠 Grading {sym}...")
        result = grader.grade(signal)
        
        # Display the final output exactly as it would look
        from src.bot import GRADE_EMOJIS, GRADE_LABELS
        emoji = GRADE_EMOJIS.get(result.grade, "❓")
        label = GRADE_LABELS.get(result.grade, "Unknown")
        
        print(f"  {emoji} {sym} Analysis Result:")
        print(f"  Grade: {result.grade}/4 — {label}")
        print(f"  Confidence: {result.confidence}%")
        print(f"  💡 Advice: {result.advice}")
        print("  📝 Reasons:")
        for r in result.reasons:
            print(f"     • {r}")

if __name__ == "__main__":
    asyncio.run(main())
