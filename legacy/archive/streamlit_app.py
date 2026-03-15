"""
OpenNutri - Streamlit Dashboard
Batch Crawler Interface
"""

import streamlit as st
import pandas as pd
import time
from crawler.scraper import NutriCrawler
from config import TARGET_URLS


# Page configuration
st.set_page_config(
    page_title="OpenNutri",
    page_icon="🥗",
    layout="wide",
)

# Custom CSS for styling
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: 700;
        background: linear-gradient(90deg, #56ab2f, #a8e063);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 2rem;
    }
    .target-list {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown('<h1 class="main-header">🥗 OpenNutri</h1>', unsafe_allow_html=True)
st.markdown(
    "<p style='text-align: center; color: #666;'>Batch Nutrition Data Crawler</p>",
    unsafe_allow_html=True,
)

st.divider()

# Initialize crawler in session state
if "crawler" not in st.session_state:
    st.session_state.crawler = NutriCrawler()

if "results_df" not in st.session_state:
    st.session_state.results_df = None

# Display target URLs
st.subheader("📋 Target URLs")
targets_df = pd.DataFrame({"URL": TARGET_URLS, "Index": range(1, len(TARGET_URLS) + 1)})
targets_df = targets_df[["Index", "URL"]]
st.dataframe(targets_df, use_container_width=True, hide_index=True)

st.markdown(f"**Total targets:** {len(TARGET_URLS)}")

st.divider()

# Batch crawl button
if st.button("🚀 Start Batch Crawl", use_container_width=True, type="primary"):
    results = []
    
    # Progress bar and status
    progress_bar = st.progress(0)
    status_text = st.empty()
    results_placeholder = st.empty()
    
    for idx, url in enumerate(TARGET_URLS):
        # Update status
        status_text.markdown(f"**Crawling:** `{url}` ({idx + 1}/{len(TARGET_URLS)})")
        
        # Fetch data
        data = st.session_state.crawler.fetch_data(url)
        
        # Append result
        results.append({
            "URL": url,
            "Status": data["status"],
            "HTTP Code": data["status_code"] or "N/A",
            "Title": data["title"] or "N/A",
            "Links Found": len(data["links"]) if data["links"] else 0,
            "Error": data["error"] or "-",
        })
        
        # Update progress
        progress = (idx + 1) / len(TARGET_URLS)
        progress_bar.progress(progress)
        
        # Show intermediate results
        temp_df = pd.DataFrame(results)
        results_placeholder.dataframe(temp_df, use_container_width=True, hide_index=True)
        
        # Small delay for visibility
        time.sleep(0.3)
    
    # Final status
    status_text.markdown("**✅ Batch crawl complete!**")
    
    # Store results
    st.session_state.results_df = pd.DataFrame(results)

# Display previous results if available
if st.session_state.results_df is not None and not st.button("🔄 Clear Results"):
    st.subheader("📊 Crawl Results")
    st.dataframe(st.session_state.results_df, use_container_width=True, hide_index=True)
    
    # Summary stats
    success_count = len(st.session_state.results_df[st.session_state.results_df["Status"] == "Success"])
    failed_count = len(st.session_state.results_df) - success_count
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total URLs", len(st.session_state.results_df))
    col2.metric("Successful", success_count)
    col3.metric("Failed", failed_count)

# Footer
st.divider()
st.markdown(
    "<p style='text-align: center; color: #999; font-size: 0.8rem;'>"
    "OpenNutri © 2025 | Built with Streamlit"
    "</p>",
    unsafe_allow_html=True,
)