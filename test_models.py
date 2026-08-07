import asyncio
import os
from src.fetcher import MarketDataFetcher
from src.transform import DataTransformer
from src.grader import SignalGrader
from src.bot import GRADE_EMOJIS, GRADE_LABELS

async def main():
    print("🚀 Running Model Comparison Test...\n")
    
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("⚠️ No GEMINI_API_KEY found.")
        return
        
    print("1️⃣ Fetching data for NVDA...")
    fetcher = MarketDataFetcher()
    snapshots = fetcher.fetch(["NVDA"])
    
    transformer = DataTransformer()
    enriched = transformer.enrich(snapshots)
    signal = enriched["NVDA"]
    
    models = ["gemini-3.5-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite"]
    
    print("\n=======================================================")
    print(f"📊 Testing NVDA Data:")
    print(f"Price: ${signal.snapshot.current_price}, Drawdown: {signal.snapshot.drawdown_pct}%")
    print("=======================================================\n")
    
    for model_name in models:
        print(f"🤖 Testing Model: {model_name.upper()}")
        # We pass only a single model in the list to force it to use that exact model
        grader = SignalGrader(api_key=api_key, models=[model_name])
        
        result = grader.grade(signal)
        
        emoji = GRADE_EMOJIS.get(result.grade, "❓")
        label = GRADE_LABELS.get(result.grade, "Unknown")
        
        print(f"  {emoji} Grade: {result.grade}/4 — {label} (Confidence: {result.confidence}%)")
        print(f"  💡 Advice:\n    {result.advice}")
        print("  📝 Reasons:")
        for r in result.reasons:
            print(f"     • {r}")
        
        if result.buy_targets:
            print("  🎯 Buy Targets:")
            for t in result.buy_targets:
                print(f"     • 🎯 {t}")
                
        print("-" * 55 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
