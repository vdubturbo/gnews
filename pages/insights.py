import os
import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from dotenv import load_dotenv
import altair as alt

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

st.set_page_config(page_title="News Insights Dashboard", layout="wide")

@st.cache_data
def load_articles():
    url = f"{SUPABASE_URL}/rest/v1/articles?select=id,title,published_at,topics,entities,relevance_score&scraped=eq.true&summary=not.is.null"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Accept-Profile": "news"
    }
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        st.error(f"Failed to load articles: {response.status_code}")
        return pd.DataFrame()
    df = pd.DataFrame(response.json())
    df["published_at"] = pd.to_datetime(df["published_at"])
    return df

df = load_articles()

st.title("📈 Trend & Insights Dashboard")

if df.empty:
    st.warning("No data available.")
    st.stop()

# Topic Frequency Over Time
st.subheader("Topic Frequency Over Time")
topic_scale = st.radio("Group topics by", ["Day", "Week", "Month"], horizontal=True, key="topic_scale")
freq = {"Day":"D", "Week":"W-MON", "Month":"M"}[topic_scale]
topic_df = df.explode("topics").dropna(subset=["topics"])
topic_counts = (
    topic_df
    .groupby([pd.Grouper(key="published_at", freq=freq), "topics"])
    .size()
    .reset_index(name="count")
)
topic_chart = alt.Chart(topic_counts).mark_line().encode(
    x=alt.X("published_at:T", timeUnit= {"Day":"yearmonthdate", "Week":"yearweek", "Month":"yearmonth"}[topic_scale], title=topic_scale),
    y="count:Q",
    color="topics:N"
).properties(height=400)
st.altair_chart(topic_chart, use_container_width=True)

# Entity Mentions Over Time
st.subheader("Entity Mentions Over Time")
entity_scale = st.radio("Group entities by", ["Day", "Week", "Month"], horizontal=True, key="entity_scale")
freq2 = {"Day":"D", "Week":"W-MON", "Month":"M"}[entity_scale]
def extract_entities(df, entity_type, freq):
    records = []
    for _, row in df.iterrows():
        for ent in (row.get("entities") or {}).get(entity_type, {}):
            records.append({"period": row["published_at"], "entity": ent})
    return (
        pd.DataFrame(records)
        .groupby([pd.Grouper(key="period", freq=freq), "entity"])
        .size()
        .reset_index(name="count")
    )

entity_counts = extract_entities(df, "agencies", freq2)
entity_chart = alt.Chart(entity_counts).mark_line().encode(
    x=alt.X("period:T", timeUnit= {"Day":"yearmonthdate", "Week":"yearweek", "Month":"yearmonth"}[entity_scale], title=entity_scale),
    y="count:Q",
    color="entity:N"
).properties(height=400)
st.altair_chart(entity_chart, use_container_width=True)

# Average Relevance Over Time
st.subheader("Average Relevance Score Over Time")
score_scale = st.radio("Group relevance by", ["Day", "Week", "Month"], horizontal=True, key="score_scale")
freq3 = {"Day":"D", "Week":"W-MON", "Month":"M"}[score_scale]
score_avg = (
    df
    .groupby(pd.Grouper(key="published_at", freq=freq3))["relevance_score"]
    .mean()
    .reset_index(name="relevance_score")
)
score_chart = alt.Chart(score_avg).mark_line().encode(
    x=alt.X("published_at:T", timeUnit= {"Day":"yearmonthdate", "Week":"yearweek", "Month":"yearmonth"}[score_scale], title=score_scale),
    y="relevance_score:Q"
).properties(height=300)
st.altair_chart(score_chart, use_container_width=True)