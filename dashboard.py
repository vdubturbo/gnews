

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

st.set_page_config(page_title="Federal News Intelligence", layout="wide")

@st.cache_data
def load_articles():
    url = f"{SUPABASE_URL}/rest/v1/articles?select=id,title,url,published_at,topics,entities,relevance_score&scraped=eq.true&summary=not.is.null"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Accept-Profile": "news"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        df = pd.DataFrame(data)
        df["published_at"] = pd.to_datetime(df["published_at"])
        return df
    else:
        st.error(f"Failed to load articles: {response.status_code}")
        return pd.DataFrame()


st.title("📊 Federal News Intelligence Dashboard")
st.markdown("### Navigation")
col1, col2 = st.columns(2)
with col1:
    if st.button("📈 Trends & Insights"):
        st.markdown("[Click here to open](./insights_dashboard.py)", unsafe_allow_html=True)
with col2:
    if st.button("🧠 Weekly Summary"):
        st.markdown("[Click here to open](./insights2_dashboard.py)", unsafe_allow_html=True)

df = load_articles()
st.metric("Total Articles", len(df))

# Filter sidebar
st.sidebar.header("Filter Articles")
start_date = st.sidebar.date_input("Start date", df["published_at"].min().date() if not df.empty else datetime.today().date())
end_date = st.sidebar.date_input("End date", df["published_at"].max().date() if not df.empty else datetime.today().date())
topics = st.sidebar.multiselect("Topics", sorted(set(tag for sublist in df["topics"].dropna() for tag in sublist)))
min_score = st.sidebar.slider("Minimum Relevance Score", 1, 10, 1)

# Filtered data
filtered = df[
    (df["published_at"].dt.date >= start_date) &
    (df["published_at"].dt.date <= end_date) &
    (df["relevance_score"] >= min_score)
]

if topics:
    filtered = filtered[filtered["topics"].apply(lambda x: bool(set(x or []) & set(topics)))]

# Main section
st.subheader("Filtered Articles")
st.dataframe(filtered[["published_at", "title", "relevance_score", "topics"]])

# Topic frequency chart
if not df.empty:
    all_topics = pd.Series(tag for sublist in df["topics"].dropna() for tag in sublist)
    topic_counts = all_topics.value_counts().reset_index()
    topic_counts.columns = ["Topic", "Count"]
    st.subheader("Top Topics")
    chart = alt.Chart(topic_counts).mark_bar().encode(
        x=alt.X("Topic:N", sort="-y", axis=alt.Axis(labelAngle=0)),
        y="Count:Q"
    ).properties(height=400)
    st.altair_chart(chart, use_container_width=True)