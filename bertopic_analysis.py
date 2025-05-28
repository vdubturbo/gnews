import os
import json
import pandas as pd
from supabase import create_client, Client
from bertopic import BERTopic
from datetime import datetime
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import CountVectorizer

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_SCHEMA = "news"

assert SUPABASE_URL and SUPABASE_KEY, "Supabase credentials missing from .env"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Load keyword-to-topic mapping
try:
    with open("topic_mappings.json") as f:
        topic_map = json.load(f)
except FileNotFoundError:
    print("⚠️ Mapping file 'topic_mappings.json' not found. Proceeding without keyword remapping.")
    topic_map = {}

# Fetch summaries and timestamps
def fetch_articles(limit=500):
    response = supabase.schema("news").table("articles") \
        .select("id, summary, published_at") \
        .filter("summary", "not.is", "null") \
        .order("published_at", desc=True) \
        .limit(limit) \
        .execute()
    return pd.DataFrame(response.data)

df = fetch_articles()

if df.empty:
    print("⚠️ No summarized articles found.")
    exit()

# Convert timestamps
df["published_at"] = pd.to_datetime(df["published_at"])

# Generate embeddings and model topics
print("🔍 Fitting BERTopic model...")
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
vectorizer_model = CountVectorizer(stop_words="english", ngram_range=(1, 2))
topic_model = BERTopic(embedding_model=embedding_model, vectorizer_model=vectorizer_model, min_topic_size=10)

topics, probs = topic_model.fit_transform(df["summary"].tolist())

# Attach topics to DataFrame
df["topic"] = topics

# Show top topics
print("\n🧠 Top Topics:")
print(topic_model.get_topic_info().head(10))

# Upsert into Supabase bertopic_topics table
print("⬆️  Upserting topic labels to Supabase...")
for i, row in df.iterrows():
    topic_id = row["topic"]
    article_id = row["id"]
    topic_info = topic_model.get_topic(topic_id)
    keywords = [kw for kw, _ in topic_info]
    mapped_keywords = [topic_map.get(k.lower(), k) for k in keywords[:3]]
    topic_name = ", ".join(mapped_keywords)
    probability = probs[i] if probs is not None else None

    supabase.schema("news").table("bertopic_topics").upsert({
        "article_id": article_id,
        "topic_id": topic_id,
        "topic_keywords": keywords,
        "topic_name": topic_name,
        "probability": float(probability) if probability is not None else None,
    }).execute()

# Optional: visualize
try:
    fig = topic_model.visualize_barchart(top_n_topics=10)
    fig.write_html("topic_barchart.html")
    print("\n📊 Topic bar chart saved to topic_barchart.html")
except Exception as e:
    print(f"⚠️ Visualization error: {e}")

# Optional: Save topic model
topic_model.save("bertopic_model")

# Optional: Save topic-labeled data
df.to_csv("topic_labeled_articles.csv", index=False)
print("✅ Topic-labeled articles saved to topic_labeled_articles.csv")