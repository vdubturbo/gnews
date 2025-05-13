import os
import requests
from dotenv import load_dotenv
from datetime import datetime
import openai
import time

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY
client = openai.OpenAI(api_key=OPENAI_API_KEY)

def fetch_articles_to_analyze():
    url = f"{SUPABASE_URL}/rest/v1/articles?scraped=eq.true&summary=is.null&select=id,full_content"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Accept-Profile": "news"
    }
    response = requests.get(url, headers=headers)
    return response.json() if response.status_code == 200 else []

def analyze_article(content):
    prompt = (
        "You are an AI assistant helping analyze federal policy and spending news.\n\n"
        "Summarize the article below, then list relevant topics and key named entities (people, agencies, programs, etc).\n\n"
        f"Article:\n{content[:4000]}"
    )

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a government news analyst."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"❌ OpenAI error: {e}")
        return None

def update_article_analysis(article_id, summary_text):
    url = f"{SUPABASE_URL}/rest/v1/articles?id=eq.{article_id}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
        "Content-Profile": "news"
    }
    data = {
        "summary": summary_text,
        "last_analysis_at": datetime.utcnow().isoformat()
    }
    response = requests.patch(url, headers=headers, json=data)
    if response.status_code not in [200, 204]:
        print(f"⚠️ Failed to update article {article_id}: {response.status_code} {response.text}")

def main():
    articles = fetch_articles_to_analyze()
    for article in articles:
        print(f"🧠 Analyzing article {article['id']}")
        result = analyze_article(article["full_content"])
        if result:
            update_article_analysis(article["id"], result)
        print("⏳ Waiting 3 seconds to rate-limit OpenAI...")
        time.sleep(3)

if __name__ == "__main__":
    main()