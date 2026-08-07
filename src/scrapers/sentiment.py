import requests
import feedparser

def get_fear_greed_index() -> str:
    url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data['fear_and_greed']['rating']
    except Exception as e:
        return "Unknown"

def get_recent_news(ticker: str) -> list[str]:
    url = f"https://news.google.com/rss/search?q={ticker}&hl=en-US&gl=US&ceid=US:en"
    try:
        feed = feedparser.parse(url)
        return [entry.title for entry in feed.entries[:5]]
    except Exception as e:
        return []
