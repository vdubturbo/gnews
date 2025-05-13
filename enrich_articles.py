import os
import requests
from dotenv import load_dotenv
from datetime import datetime
import openai
import time
import json

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = openai.OpenAI(api_key=OPENAI_API_KEY)

def fetch_summaries_to_enrich():
    url = f"{SUPABASE_URL}/rest/v1/articles?select=id,summary&scraped=eq.true&summary=not.is.null&topics=is.null"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Accept-Profile": "news"
    }
    response = requests.get(url, headers=headers)
    return response.json() if response.status_code == 200 else []

def enrich_summary(summary_text):
    prompt = (
        "You are an expert in government news analysis. Given the article summary below, respond ONLY in valid JSON format with the following keys. Do not include markdown backticks. Do not use JSON objects with values only (e.g., {\"Entity\"}); instead use key-value pairs like {\"Entity\": {}} or lists:\n"
        "- topics: list of strings\n"
        "- entities: an object with keys: agencies, companies, people, programs\n"
        "- relevance_score: integer from 1 to 10\n"
        "- budget_mentions: list of strings (may be empty)\n\n"
        f"Summary: {summary_text}"
    )

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an expert in government news analysis."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=600
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"❌ OpenAI error: {e}")
        return None

def normalize_entity_group(entity_group):
    if isinstance(entity_group, list) or isinstance(entity_group, set):
        return {str(item): {} for item in entity_group if isinstance(item, str)}
    elif isinstance(entity_group, dict):
        normalized = {}
        for k, v in entity_group.items():
            if isinstance(v, dict):
                normalized[k] = v
            elif isinstance(v, str) and k == v:
                normalized[k] = {}
            else:
                try:
                    normalized[str(k)] = {}
                except Exception:
                    continue
        return normalized
    return {}

def update_article_enrichment(article_id, enriched_data):
    import re

    url = f"{SUPABASE_URL}/rest/v1/articles?id=eq.{article_id}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
        "Content-Profile": "news"
    }

    try:
        # Strip Markdown code fences if present
        if enriched_data.startswith("```"):
            enriched_data = enriched_data.strip().strip("`").strip("json").strip()
        # Fix object blocks that are actually sets (e.g., {"Some Agency"}) by converting them to {"Some Agency": {}}
        enriched_data = re.sub(
            r'"\w+":\s*{\s*"([^"]+)"\s*}', 
            r'"\1": {}', 
            enriched_data
        )
        parsed = json.loads(enriched_data)
        entities = parsed.get("entities", {})
        for group in ["agencies", "companies", "people", "programs"]:
            entities[group] = normalize_entity_group(entities.get(group, {}))

        data = {
            "topics": parsed.get("topics"),
            "entities": entities,
            "relevance_score": parsed.get("relevance_score"),
            "budget_mentions": parsed.get("budget_mentions")
        }
    except json.JSONDecodeError as e:
        print(f"⚠️ JSON parse error for article {article_id}: {e}")
        print(f"↪️ Raw response: {enriched_data}")
        return

    response = requests.patch(url, headers=headers, json=data)
    if response.status_code not in [200, 204]:
        print(f"⚠️ Failed to update article {article_id}: {response.status_code} {response.text}")
    else:
        print(f"✅ Successfully updated article {article_id}")

def main():
    articles = fetch_summaries_to_enrich()
    for article in articles:
        print(f"🔍 Enriching article {article['id']}")
        enriched = enrich_summary(article["summary"])
        if enriched:
            update_article_enrichment(article["id"], enriched)
        print("🕒 Sleeping 3 seconds to be polite...")
        time.sleep(3)

if __name__ == "__main__":
    main()