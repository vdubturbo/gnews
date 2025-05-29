


import streamlit as st
import pandas as pd
from supabase import create_client
import os
from datetime import datetime

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.title("🧠 Enriched Article Insights")

# Fetch enriched articles from Supabase
@st.cache_data(ttl=600)
def fetch_enriched_articles(limit=500):
    response = supabase.table("articles") \
        .select("title, published_at, topics, relevance_score, entities") \
        .order("published_at", desc=True) \
        .limit(limit) \
        .execute()
    return pd.DataFrame(response.data)

# Load data
df = fetch_enriched_articles()

if df.empty:
    st.warning("No enriched articles found.")
else:
    # Optional filters
    min_score = st.slider("Minimum Relevance Score", 0, 100, 0)
    df_filtered = df[df["relevance_score"].fillna(0) >= min_score]

    st.dataframe(df_filtered, use_container_width=True)