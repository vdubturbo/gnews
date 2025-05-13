import os
import requests
import json
from dotenv import load_dotenv
from datetime import datetime, timedelta
import time


# Load environment variables from .env
load_dotenv()
API_KEY = os.getenv("GNEWS_API_KEY")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def get_eligible_queries(tier="primary"):
    from datetime import timezone
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Accept-Profile": "news"
    }

    url = f"{SUPABASE_URL}/rest/v1/search_queries?active=eq.true&tier=eq.{tier}"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print("❌ Failed to fetch search queries:", response.text)
        return []

    queries = response.json()
    now = datetime.now(timezone.utc)
    eligible = []
    for q in queries:
        last_run = datetime.fromisoformat(q["last_run_at"]).astimezone(timezone.utc) if q["last_run_at"] else None
        min_interval = q.get("min_interval_hours", 24)
        if not last_run or (now - last_run) > timedelta(hours=min_interval):
            eligible.append(q)

    return eligible

def fetch_news(query="technology", max_results=3):
    url = f"https://gnews.io/api/v4/search?q={query}&lang=en&max={max_results}&token={API_KEY}"
    response = requests.get(url)

    if response.status_code != 200:
        print(f"❌ Error {response.status_code}: {response.text}")
        return {}

    return response.json()


# Insert articles into Supabase
import requests

def insert_articles_to_supabase(articles):
    insert_count = 0
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
        "Content-Profile": "news"
    }

    for article in articles:
        data = {
            "title": article.get("title"),
            "url": article.get("url"),
            "description": article.get("description"),
            "source": article.get("source", {}).get("name"),
            "published_at": article.get("publishedAt"),
            "content_snippet": article.get("content"),
            "scraped": False,
        }

        print("🔗 POSTing to:", f"{SUPABASE_URL}/rest/v1/articles")
        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/articles",
            headers=headers,
            json=data
        )

        if response.status_code in [200, 201]:
            print(f"✅ Inserted: {data['title']}")
            insert_count += 1
        elif response.status_code == 409:
            print(f"⚠️ Duplicate: {data['title']}")
        else:
            print(f"❌ Failed: {data['title']} — {response.status_code} {response.text}")
    return insert_count

if __name__ == "__main__":
    eligible_queries = get_eligible_queries()
    if not eligible_queries:
        print("ℹ️ No eligible primary queries — attempting secondary tier instead...")
        eligible_queries = get_eligible_queries(tier="secondary")
    for query_entry in eligible_queries:
        query_text = query_entry["query"]
        print(f"\n🔍 Running query: {query_text}")
        articles = fetch_news(query=query_text)
        if "articles" in articles:
            print(f"✅ Fetched {len(articles['articles'])} articles for '{query_text}'")
            for a in articles["articles"]:
                print(f"- {a['title']} ({a['source']['name']})")

            # with open(f"news_output_{query_text.replace(' ', '_')}.json", "w") as f:
            #     json.dump(articles, f, indent=2)
            inserted = insert_articles_to_supabase(articles["articles"])
            # Update query metadata
            update_url = f"{SUPABASE_URL}/rest/v1/search_queries?id=eq.{query_entry['id']}"
            update_data = {
                "last_run_at": datetime.utcnow().isoformat(),
                "run_count": query_entry.get("run_count", 0) + 1
            }
            update_headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
                "Content-Profile": "news"
            }
            update_response = requests.patch(update_url, headers=update_headers, json=update_data)
            if update_response.status_code not in [200, 204]:
                print(f"⚠️ Failed to update query metadata: {update_response.status_code} {update_response.text}")
            if inserted < 10:
                print(f"📉 Low insert count for '{query_text}' — only {inserted} new articles.")
                print("🔁 Attempting fallback queries (tier: secondary)...")
                fallback_queries = get_eligible_queries(tier="secondary")
                for fallback in fallback_queries:
                    fb_query_text = fallback["query"]
                    print(f"\n🔍 Running fallback query: {fb_query_text}")
                    articles = fetch_news(query=fb_query_text)
                    if "articles" in articles:
                        print(f"✅ Fetched {len(articles['articles'])} articles for fallback '{fb_query_text}'")
                        inserted = insert_articles_to_supabase(articles["articles"])

                        # Update fallback query metadata
                        fb_update_url = f"{SUPABASE_URL}/rest/v1/search_queries?id=eq.{fallback['id']}"
                        fb_update_data = {
                            "last_run_at": datetime.utcnow().isoformat(),
                            "run_count": fallback.get("run_count", 0) + 1
                        }
                        fb_update_response = requests.patch(fb_update_url, headers=update_headers, json=fb_update_data)
                        if fb_update_response.status_code not in [200, 204]:
                            print(f"⚠️ Failed to update fallback query metadata: {fb_update_response.status_code} {fb_update_response.text}")
                    else:
                        print(f"⚠️ No results for fallback query '{fb_query_text}'")
                    print("🕒 Sleeping 3 seconds to avoid rate limiting...")
                    time.sleep(3)
        else:
            print(f"⚠️ No results for '{query_text}'")
        print("🕒 Sleeping 3 seconds to avoid rate limiting...")
        time.sleep(3)
    print("🚀 Finished all eligible queries.")