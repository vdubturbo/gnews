import os
import requests
import feedparser
from datetime import datetime
from dotenv import load_dotenv

import ssl
ssl._create_default_https_context = ssl._create_unverified_context

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

RSS_FEEDS = [
    "https://feeds.npr.org/1014/rss.xml",
    "https://www.govexec.com/rss/management/",
    "https://www.govexec.com/rss/oversight/",
    "https://www.govexec.com/rss/technology/",
    "https://www.govexec.com/rss/defense/",
    "https://www.govexec.com/rss/workforce/",
    "https://www.govexec.com/rss/pay-benefits/"
]

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates",
    "Content-Profile": "news",
    "Accept-Profile": "news"
}

def get_search_keywords():
    query_url = f"{SUPABASE_URL}/rest/v1/search_queries?select=query"
    response = requests.get(query_url, headers=HEADERS)
    if response.status_code != 200:
        print("❌ Failed to fetch search queries from Supabase")
        print("Status:", response.status_code)
        print("Response:", response.text)
        return []
    return [item["query"].lower() for item in response.json()]

def fetch_rss_articles(keywords):
    articles = []
    tokens = set()
    for phrase in keywords:
        tokens.update(phrase.lower().split())
    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        print(f"📡 {feed_url} → {len(feed.entries)} entries", end="")
        if feed.bozo:
            print(f" ⚠️ BozoException: {feed.bozo_exception}")
        else:
            print()
        for entry in feed.entries:
            text = (entry.title + entry.get("summary", "")).lower()
            matched = [token for token in tokens if token in text]
            if matched:
                print(f"✅ Match: {entry.title} → {matched}")
                article = {
                    "title": entry.title,
                    "url": entry.link,
                    "description": entry.get("summary", ""),
                    "source": feed.feed.get("title", "RSS"),
                    "published_at": entry.get("published", datetime.utcnow().isoformat()),
                    "content_snippet": entry.get("summary", ""),
                    "scraped": False
                }
                articles.append(article)
            else:
                print(f"❌ No match: {entry.title}")
    return articles

def insert_articles_to_supabase(articles):
    inserted = 0
    for article in articles:
        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/articles",
            headers=HEADERS,
            json=article
        )
        if response.status_code in [200, 201]:
            print(f"✅ Inserted: {article['title']}")
            inserted += 1
        elif response.status_code == 409:
            print(f"⚠️ Duplicate: {article['title']}")
        else:
            print(f"❌ Failed: {article['title']} — {response.status_code} {response.text}")
    return inserted

if __name__ == "__main__":
    print("📥 Fetching RSS feed articles...")
    keywords = get_search_keywords()
    print(f"🗝️ Loaded {len(keywords)} search keywords")
    print(keywords)
    if not keywords:
        print("⚠️ No search keywords found. Exiting.")
    else:
        articles = fetch_rss_articles(keywords)
        print(f"🔎 Found {len(articles)} matching articles")
        inserted = insert_articles_to_supabase(articles)
        print(f"🚀 Finished — {inserted} new articles inserted.")