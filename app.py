# Streamlit Web App for Bookmark Clustering
import streamlit as st
import asyncio
import json
import pandas as pd
from pathlib import Path
from typing import List, Dict
import tempfile
import os

# Import existing modules
from bookmark_cli.loader import load_chrome_bookmarks, load_chrome_bookmarks_html
from bookmark_cli.normalizer import normalize_url, deduplicate_entries
from bookmark_cli.fetcher import MetadataFetcher
from bookmark_cli.llm_client import LLMClient
from bookmark_cli.categorizer import categorize_bookmarks
from bookmark_cli.exporter import export_to_chrome_html
from bookmark_cli.config import settings

# Cache decorators for expensive operations
@st.cache_data
def load_bookmarks_cached(file_bytes: bytes, is_html: bool) -> List[Dict]:
    """Cache bookmark loading to avoid reprocessing"""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.html' if is_html else '.json') as tmp_file:
        tmp_file.write(file_bytes)
        tmp_path = tmp_file.name
    
    try:
        if is_html:
            bookmarks = load_chrome_bookmarks_html(tmp_path)
        else:
            bookmarks = load_chrome_bookmarks(tmp_path)
        return bookmarks
    finally:
        os.unlink(tmp_path)

@st.cache_data
def normalize_and_deduplicate_cached(bookmarks: List[Dict]) -> tuple:
    """Cache cleaning operations"""
    # Normalize URLs
    for bookmark in bookmarks:
        bookmark['url'] = normalize_url(bookmark['url'])
    
    # Deduplicate
    cleaned, removed = deduplicate_entries(bookmarks)
    return cleaned, removed

# Page configuration
st.set_page_config(
    page_title="Bookmark Clustering",
    page_icon="🔖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .step-header {
        font-size: 1.5rem;
        font-weight: bold;
        color: #2ca02c;
        margin-top: 2rem;
    }
    .stProgress > div > div > div > div {
        background-color: #1f77b4;
    }
    </style>
    """, unsafe_allow_html=True)

# Initialize session state for tracking workflow progress
if 'bookmarks_raw' not in st.session_state:
    st.session_state.bookmarks_raw = None
if 'bookmarks_cleaned' not in st.session_state:
    st.session_state.bookmarks_cleaned = None
if 'bookmarks_categorized' not in st.session_state:
    st.session_state.bookmarks_categorized = None
if 'current_step' not in st.session_state:
    st.session_state.current_step = 1
if 'uploaded_file_name' not in st.session_state:
    st.session_state.uploaded_file_name = None
if 'processing_status' not in st.session_state:
    st.session_state.processing_status = {
        'import': False,
        'clean': False,
        'categorize': False,
        'export': False
    }

# Main header
st.markdown('<div class="main-header">🔖 Bookmark Clustering with AI</div>', unsafe_allow_html=True)

# Sidebar configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # API Key input
    api_key = st.text_input(
        "Gemini API Key",
        type="password",
        value=settings.gemini_api_key or "",
        help="Get your free API key from https://makersuite.google.com/app/apikey"
    )
    
    # Model selection
    model = st.selectbox(
        "Model",
        ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-flash-latest"],
        index=0,
        help="Select the Gemini model to use"
    )
    
    # Batch size
    batch_size = st.slider(
        "Batch Size",
        min_value=10,
        max_value=100,
        value=50,
        step=10,
        help="Number of bookmarks per API call"
    )
    
    # Fetch metadata toggle
    fetch_metadata = st.checkbox(
        "Fetch Metadata",
        value=True,
        help="Fetch titles and descriptions from URLs"
    )
    
    st.divider()
    
    # Progress indicator
    st.subheader("📊 Progress")
    steps = ["Import", "Clean", "Categorize", "Export"]
    for i, step in enumerate(steps, 1):
        if i < st.session_state.current_step:
            st.success(f"✅ {step}")
        elif i == st.session_state.current_step:
            st.info(f"⏳ {step}")
        else:
            st.text(f"⏸️ {step}")

# Main content
tab1, tab2, tab3, tab4 = st.tabs(["📥 Import", "🧹 Clean", "🤖 Categorize", "📤 Export"])

# Tab 1: Import
with tab1:
    st.markdown('<div class="step-header">Step 1: Import Bookmarks</div>', unsafe_allow_html=True)
    
    st.info("Upload your Chrome bookmarks file (HTML or JSON format)")
    
    uploaded_file = st.file_uploader(
        "Choose a bookmarks file",
        type=["html", "json"],
        help="Export from Chrome: Bookmarks → Bookmark Manager → ⋮ → Export bookmarks"
    )
    
    if uploaded_file:
        with st.spinner("Loading bookmarks..."):
            try:
                # Detect file type
                is_html = (uploaded_file.type == "text/html" or 
                          uploaded_file.name.endswith('.html') or 
                          uploaded_file.name.endswith('.htm'))
                
                # Save uploaded file temporarily
                suffix = ".html" if is_html else ".json"
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    tmp_path = tmp_file.name
                
                # Load bookmarks using cached function
                bookmarks = load_bookmarks_cached(uploaded_file.getvalue(), is_html)
                
                st.session_state.bookmarks_raw = bookmarks
                st.session_state.uploaded_file_name = uploaded_file.name
                st.session_state.current_step = 2
                st.session_state.processing_status['import'] = True
                
                st.success(f"✅ Loaded {len(bookmarks)} bookmarks!")
                
                # Show preview
                st.subheader("Preview")
                df = pd.DataFrame(bookmarks[:10])
                st.dataframe(df[['title', 'url', 'parent']] if 'parent' in df.columns else df[['title', 'url']], use_container_width=True)
                
            except Exception as e:
                st.error(f"Error loading bookmarks: {str(e)}")

# Tab 2: Clean
with tab2:
    st.markdown('<div class="step-header">Step 2: Clean & Deduplicate</div>', unsafe_allow_html=True)
    
    if st.session_state.bookmarks_raw is None:
        st.warning("⚠️ Please import bookmarks first")
    else:
        st.info(f"Total bookmarks: {len(st.session_state.bookmarks_raw)}")
        
        if st.button("🧹 Clean Bookmarks", type="primary"):
            progress_bar = st.progress(0)
            progress_text = st.empty()
            
            try:
                # Phase 1: Normalize URLs (5%)
                progress_text.text("Normalizing URLs...")
                for i, bookmark in enumerate(st.session_state.bookmarks_raw):
                    bookmark['url'] = normalize_url(bookmark['url'])
                    progress_bar.progress((i + 1) / len(st.session_state.bookmarks_raw) * 0.05)
                
                # Phase 2: Deduplicate (10%)
                progress_text.text("Removing duplicates...")
                cleaned, removed = deduplicate_entries(st.session_state.bookmarks_raw)
                progress_bar.progress(0.10)
                
                st.session_state.bookmarks_cleaned = cleaned
                st.session_state.current_step = 3
                
                progress_bar.progress(1.0)
                progress_text.empty()
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Original", len(st.session_state.bookmarks_raw))
                with col2:
                    st.metric("Removed", len(removed))
                with col3:
                    st.metric("Unique", len(cleaned))
                
                st.success(f"✅ Bookmarks cleaned! Total: {len(cleaned)}, Duplicates removed: {len(removed)}")
                
                if removed:
                    with st.expander("View removed duplicates"):
                        df_removed = pd.DataFrame(removed)
                        st.dataframe(df_removed[['title', 'url']], use_container_width=True)
                
            except Exception as e:
                st.error(f"Error cleaning bookmarks: {str(e)}")

# Tab 3: Categorize
with tab3:
    st.markdown('<div class="step-header">Step 3: AI Categorization</div>', unsafe_allow_html=True)
    
    if st.session_state.bookmarks_cleaned is None:
        st.warning("⚠️ Please clean bookmarks first")
    else:
        st.info(f"Ready to categorize {len(st.session_state.bookmarks_cleaned)} bookmarks")
        
        if not api_key:
            st.error("❌ Please enter your Gemini API key in the sidebar")
        else:
            if st.button("🤖 Categorize with AI", type="primary"):
                progress_bar = st.progress(0)
                progress_text = st.empty()
                
                try:
                    bookmarks = st.session_state.bookmarks_cleaned.copy()
                    total_bookmarks = len(bookmarks)
                    
                    # Phase 1: Fetch metadata with live updates (10% → 40%)
                    if fetch_metadata:
                        progress_text.text("Phase 1/2: Fetching metadata from URLs...")
                        fetcher = MetadataFetcher(
                            concurrency=10,
                            timeout=30,
                            respect_robots=True
                        )
                        
                        # Metadata fetch with live progress tracking
                        async def fetch_metadata_with_progress(bookmarks, concurrency=10):
                            completed = 0
                            
                            async def track_fetch(bookmark):
                                nonlocal completed
                                metadata = await fetcher.fetch_single(bookmark['url'])
                                bookmark['fetched_title'] = metadata.get('title')
                                bookmark['description'] = metadata.get('description')
                                bookmark['keywords'] = metadata.get('keywords')
                                bookmark['content_snippet'] = metadata.get('content_preview')
                                
                                completed += 1
                                # Progress: 10% to 40% (30% range)
                                progress = 0.10 + (0.30 * completed / len(bookmarks))
                                progress_bar.progress(progress)
                                progress_text.text(f"Phase 1/2: Fetching metadata... {completed}/{len(bookmarks)}")
                                
                                return bookmark
                            
                            # Process with concurrency limit
                            tasks = [track_fetch(b) for b in bookmarks]
                            await asyncio.gather(*tasks)
                            return bookmarks
                        
                        bookmarks = asyncio.run(fetch_metadata_with_progress(bookmarks, concurrency=10))
                    else:
                        progress_bar.progress(0.10)
                    
                    # Phase 2: LLM categorization with batch logging (40% → 90%)
                    progress_text.text("Phase 2/2: AI categorization in progress...")
                    progress_bar.progress(0.40)
                    
                    llm_client = LLMClient(api_key=api_key, provider="gemini", model=model)
                    
                    # Calculate batches for progress tracking
                    num_batches = (total_bookmarks + batch_size - 1) // batch_size
                    
                    # Container for batch results logging
                    log_container = st.container()
                    
                    async def categorize_with_streamlit(bookmarks, llm_client, batch_size):
                        """Categorize with live batch logging"""
                        all_results = []
                        
                        for batch_idx in range(0, len(bookmarks), batch_size):
                            batch = bookmarks[batch_idx:batch_idx + batch_size]
                            batch_num = batch_idx // batch_size + 1
                            
                            progress_text.text(f"Phase 2/2: Categorizing batch {batch_num}/{num_batches}...")
                            
                            # Process batch with LLM
                            result = await llm_client.categorize_batch(batch)
                            
                            # Merge results with original data
                            batch_results = []
                            for llm_item in result:
                                original = next((e for e in batch if e.get("id") == llm_item["id"]), None)
                                if original:
                                    merged = {
                                        **original,
                                        "folder": llm_item.get("folder", "Unsorted"),
                                        "tags": llm_item.get("tags", []),
                                        "confidence": llm_item.get("confidence", 0.5)
                                    }
                                    batch_results.append(merged)
                                    all_results.append(merged)
                            
                            # Log batch results in expandable section
                            with log_container.expander(f"📦 Batch {batch_num}/{num_batches} - {len(batch_results)} bookmarks"):
                                for idx, entry in enumerate(batch_results[:5], 1):  # Show first 5
                                    folder = entry.get('folder', 'Unsorted')
                                    tags = ', '.join(entry.get('tags', [])[:3])
                                    title = entry.get('title', 'No title')[:50]
                                    st.write(f"{idx}. **{title}** → 📁 `{folder}` | 🏷️ {tags}")
                                
                                if len(batch_results) > 5:
                                    st.caption(f"... and {len(batch_results) - 5} more bookmarks")
                            
                            # Update progress: 40% to 90% (50% range)
                            progress = 0.40 + (0.50 * batch_num / num_batches)
                            progress_bar.progress(progress)
                        
                        return all_results
                    
                    categorized = asyncio.run(categorize_with_streamlit(bookmarks, llm_client, batch_size))
                    
                    st.session_state.bookmarks_categorized = categorized
                    st.session_state.current_step = 4
                    
                    # Complete
                    progress_bar.progress(1.0)
                    progress_text.text("✅ Categorization complete!")
                    st.success("✅ Categorization complete!")
                    
                    # Generate and display summary statistics
                    from bookmark_cli.preview import generate_preview
                    
                    st.subheader("📊 Summary Statistics")
                    
                    # Calculate folder distribution
                    folders = {}
                    tags_counter = {}
                    for bookmark in categorized:
                        folder = bookmark.get('folder', 'Unsorted')
                        folders[folder] = folders.get(folder, 0) + 1
                        
                        # Count tags
                        for tag in bookmark.get('tags', []):
                            tags_counter[tag] = tags_counter.get(tag, 0) + 1
                    
                    # Display metrics in columns
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Bookmarks", len(categorized))
                    with col2:
                        st.metric("Folders Created", len(folders))
                    with col3:
                        avg_conf = sum(b.get('confidence', 0) for b in categorized) / len(categorized)
                        st.metric("Avg Confidence", f"{avg_conf:.1%}")
                    
                    # Category distribution chart
                    st.subheader("📁 Category Distribution")
                    df_stats = pd.DataFrame(list(folders.items()), columns=['Folder', 'Count'])
                    df_stats = df_stats.sort_values('Count', ascending=False)
                    st.bar_chart(df_stats.set_index('Folder'))
                    
                    # Detailed stats in expandable sections
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        with st.expander("📂 View All Categories"):
                            st.dataframe(df_stats, use_container_width=True)
                    
                    with col2:
                        with st.expander("🏷️ Top Tags"):
                            top_tags = sorted(tags_counter.items(), key=lambda x: x[1], reverse=True)[:10]
                            df_tags = pd.DataFrame(top_tags, columns=['Tag', 'Count'])
                            st.dataframe(df_tags, use_container_width=True)
                    
                    # Full statistics JSON
                    with st.expander("📋 Detailed Statistics (JSON)"):
                        stats = {
                            "total_bookmarks": len(categorized),
                            "total_folders": len(folders),
                            "average_confidence": round(avg_conf, 3),
                            "folders": folders,
                            "top_tags": dict(top_tags[:10])
                        }
                        st.json(stats)
                    
                except Exception as e:
                    st.error(f"Error during categorization: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())

# Tab 4: Export
with tab4:
    st.markdown('<div class="step-header">Step 4: Export Results</div>', unsafe_allow_html=True)
    
    if st.session_state.bookmarks_categorized is None:
        st.warning("⚠️ Please categorize bookmarks first")
    else:
        st.info(f"Ready to export {len(st.session_state.bookmarks_categorized)} categorized bookmarks")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📥 Download HTML", type="primary"):
                try:
                    # Generate HTML
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.html', mode='w', encoding='utf-8') as tmp_file:
                        export_to_chrome_html(st.session_state.bookmarks_categorized, tmp_file.name)
                        tmp_file.flush()
                        
                        # Read the file
                        with open(tmp_file.name, 'r', encoding='utf-8') as f:
                            html_content = f.read()
                        
                        os.unlink(tmp_file.name)
                    
                    st.download_button(
                        label="💾 Download organized_bookmarks.html",
                        data=html_content,
                        file_name="organized_bookmarks.html",
                        mime="text/html"
                    )
                    
                    st.success("✅ HTML generated! Click the button above to download.")
                    
                except Exception as e:
                    st.error(f"Error exporting: {str(e)}")
        
        with col2:
            if st.button("📥 Download JSON"):
                try:
                    json_content = json.dumps(st.session_state.bookmarks_categorized, indent=2, ensure_ascii=False)
                    
                    st.download_button(
                        label="💾 Download bookmarks_categorized.json",
                        data=json_content,
                        file_name="bookmarks_categorized.json",
                        mime="application/json"
                    )
                    
                    st.success("✅ JSON generated! Click the button above to download.")
                    
                except Exception as e:
                    st.error(f"Error exporting JSON: {str(e)}")
        
        # Preview
        st.subheader("Preview")
        if st.session_state.bookmarks_categorized:
            df = pd.DataFrame(st.session_state.bookmarks_categorized)
            columns = ['title', 'folder', 'tags', 'url']
            display_cols = [col for col in columns if col in df.columns]
            st.dataframe(df[display_cols], use_container_width=True)

# Footer
st.divider()
st.markdown("""
    <div style='text-align: center; color: gray;'>
        <p>Built with ❤️ using Streamlit and Google Gemini AI</p>
        <p>Get your free API key at <a href='https://makersuite.google.com/app/apikey' target='_blank'>Google AI Studio</a></p>
    </div>
    """, unsafe_allow_html=True)
