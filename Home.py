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

@st.cache_data(ttl=300)
def load_articles():
    url = f"{SUPABASE_URL}/rest/v1/articles?select=id,title,url,published_at,topics,entities,relevance_score,last_analysis_at&last_analysis_at=not.is.null&order=last_analysis_at.desc&limit=100"
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

# 🔍 DEBUG: Confirm what was loaded
st.write("✅ Raw Articles Loaded:", len(df))
st.write(df.head(10))

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


# Topic Trends Visualization
st.subheader("📈 Topic Trends Over Time")

@st.cache_data
def load_topic_trends():
    url = f"{SUPABASE_URL}/rest/v1/topic_trends_weekly?select=topic_id,topic_name,week,article_count"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Accept-Profile": "news"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        df = pd.DataFrame(data)
        df["week"] = pd.to_datetime(df["week"])
        df["topic_name"] = df["topic_name"].apply(lambda t: ", ".join(t.split(", ")[:2]))
        return df
    else:
        st.warning(f"Failed to load topic trends. Status code: {response.status_code}")
        st.text(f"Response content: {response.text}")
        return pd.DataFrame()

trends_df = load_topic_trends()
if not trends_df.empty:
    top_topics = trends_df["topic_name"].value_counts().nlargest(5).index.tolist()
    filtered_trends = trends_df[trends_df["topic_name"].isin(top_topics)]
    line_chart = alt.Chart(filtered_trends).mark_line().encode(
        x=alt.X("week:T", title="Week"),
        y="article_count:Q",
        color="topic_name:N"
    ).properties(height=400)
    st.altair_chart(line_chart, use_container_width=True)