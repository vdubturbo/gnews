import os
import requests
from dotenv import load_dotenv
from datetime import datetime
import openai
import time
import json
import yaml

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = openai.OpenAI(api_key=OPENAI_API_KEY)

def load_keyword_topic_mapping():
    try:
        with open("keyword_topic_mapping.yaml", "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"⚠️ Failed to load keyword-topic mapping: {e}")
        return {}

KEYWORD_TOPIC_MAP = load_keyword_topic_mapping()

def classify_additional_topics(summary_text):
    assigned_topics = set()
    text_lower = summary_text.lower()
    for keyword, topic in KEYWORD_TOPIC_MAP.items():
        if keyword.lower() in text_lower:
            assigned_topics.add(topic)
    return list(assigned_topics)

def fetch_summaries_to_enrich():
    url = f"{SUPABASE_URL}/rest/v1/articles?select=id,summary&scraped=eq.true&summary=not.is.null"
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
        "- relevance_score: integer from 1 to 10, where 1 = irrelevant to government or budgetary concerns, 5 = tangentially related, and 10 = highly relevant to U.S. federal procurement, policy, or agencies\n"
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

def update_article_enrichment(article_id, enriched_data, summary_text):
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

        original_topics = set(parsed.get("topics", []))
        keyword_topics = set(classify_additional_topics(summary_text))
        all_topics = list(original_topics.union(keyword_topics))

        raw_score = parsed.get("relevance_score", 5)
        if raw_score >= 9:
            relevance_score = 8
        elif raw_score >= 7:
            relevance_score = 7
        elif raw_score >= 5:
            relevance_score = 6
        else:
            relevance_score = 5

        data = {
            "topics": all_topics,
            "entities": entities,
            "relevance_score": relevance_score,
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
            update_article_enrichment(article["id"], enriched, article["summary"])
        print("🕒 Sleeping 3 seconds to be polite...")
        time.sleep(3)

if __name__ == "__main__":
    main()