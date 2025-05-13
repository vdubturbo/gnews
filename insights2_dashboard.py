

import os
import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer " + SUPABASE_KEY,
    "Accept-Profile": "news"
}

st.set_page_config(page_title="🧠 Weekly Brief & Spike Monitor", layout="wide")
st.title("🧠 Weekly Brief & Spike Monitor")

def fetch_topic_counts(days):
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    url = f"{SUPABASE_URL}/rest/v1/articles?select=topics,published_at&scraped=eq.true&summary=not.is.null&published_at=gte.{since}"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        st.error("Failed to fetch article data")
        return {}
    data = resp.json()
    counts = {}
    for row in data:
        for topic in row.get("topics") or []:
            counts[topic] = counts.get(topic, 0) + 1
    return counts

def detect_spikes(current, previous, factor=2):
    spikes = []
    for topic, count in current.items():
        prev = previous.get(topic, 0)
        if (prev == 0 and count >= factor) or (prev > 0 and count / prev >= factor):
            spikes.append({"topic": topic, "last_week": prev, "this_week": count})
    return spikes

def generate_summary(current_counts, spikes):
    prompt = (
        "You are an AI analyst of federal policy news.\n\n"
        "Here are article topic counts for the last week:\n"
        f"{json.dumps(current_counts, indent=2)}\n\n"
        "And here are topics that have spiked compared to the prior week:\n"
        f"{json.dumps(spikes, indent=2)}\n\n"
        "Write a concise summary of key developments and notable spikes."
    )
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an expert news analyst."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.5
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"❌ Error generating summary: {e}"

with st.spinner("Fetching data and generating summary..."):
    this_week = fetch_topic_counts(7)
    last_week = fetch_topic_counts(14)
    spikes = detect_spikes(this_week, last_week)
    summary = generate_summary(this_week, spikes)

st.subheader("📌 AI-Generated Weekly Summary")
st.markdown(summary)

st.subheader("⚠️ Detected Topic Spikes (≥ 2× increase)")
if spikes:
    st.dataframe(pd.DataFrame(spikes))
else:
    st.success("No significant spikes detected this week.")