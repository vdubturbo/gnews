import os
import requests
from newspaper import Article
from datetime import datetime
from dotenv import load_dotenv
import time

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def fetch_unscraped_articles():
    url = f"{SUPABASE_URL}/rest/v1/articles?scraped=eq.false&select=id,url"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Accept-Profile": "news"
    }
    response = requests.get(url, headers=headers)
    return response.json() if response.status_code == 200 else []

def scrape_article_content(url):
    try:
        article = Article(url)
        article.download()
        article.parse()
        return article.text
    except Exception as e:
        print(f"❌ Failed to scrape {url}: {e}")
        return None

def update_article_content(article_id, content):
    url = f"{SUPABASE_URL}/rest/v1/articles?id=eq.{article_id}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
        "Content-Profile": "news"
    }
    data = {
        "full_content": content,
        "scraped": True,
        "last_scrape_attempt_at": datetime.utcnow().isoformat(),
        "scrape_attempts": 1
    }
    response = requests.patch(url, headers=headers, json=data)
    if response.status_code not in [200, 204]:
        print(f"⚠️ Failed to update article {article_id}: {response.status_code} {response.text}")

def main():
    articles = fetch_unscraped_articles()
    for a in articles:
        print(f"🔍 Scraping: {a['url']}")
        content = scrape_article_content(a["url"])
        if content:
            update_article_content(a["id"], content)
        print("🕒 Sleeping 2 seconds to be polite...")
        time.sleep(2)

if __name__ == "__main__":
    main()
