import requests
import feedparser

def get_fear_greed_index() -> str:
    url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get('fear_and_greed', {}).get('rating', 'Unknown')
    except Exception as e:
        return "Unknown"

import urllib.parse
import yfinance as yf

def get_recent_news(ticker: str) -> list[str]:
    news_titles = set()
    
    # 1. Google News RSS (High quality, fast)
    query = urllib.parse.quote(f"{ticker} stock news when:7d")
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    try:
        feed = feedparser.parse(url)
        entries = getattr(feed, 'entries', [])
        for entry in entries[:7]:
            if hasattr(entry, 'title'):
                news_titles.add(entry.title)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Error fetching Google News for {ticker}: {e}")
        pass

    # 2. Yahoo Finance News (Good coverage, sometimes has unique articles)
    try:
        yf_ticker = yf.Ticker(ticker)
        for news in yf_ticker.news[:7]:
            if 'title' in news:
                news_titles.add(news['title'])
    except Exception:
        pass
        
    # 3. Aggregation & Spam Filtering
    filtered_news = []
    # Common clickbait/spam keywords in financial news
    spam_keywords = [
        "Zacks", "Motley Fool", "Looking for a", "Should You Buy", 
        "Is It Time To", "Holdings", "Buy or Sell", "Wall Street Analysts"
    ]
    
    for title in news_titles:
        if not any(spam.lower() in title.lower() for spam in spam_keywords):
            # Clean up Google News publisher suffix (e.g. "Headline - Reuters")
            clean_title = title.split(" - ")[0].strip()
            # De-duplicate similar headlines
            if clean_title not in filtered_news:
                filtered_news.append(clean_title)
            
    return filtered_news[:6]
