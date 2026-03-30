"""
TermExtractor-Pro - Main Streamlit Application
AI-powered terminology extraction with bilingual lookup and derivative discovery
"""

import streamlit as st
import os
from anova_brand_theme import apply_anova_theme, anova_header, anova_footer, anova_sidebar_logo

# Configure page
st.set_page_config(
    page_title="Anova Term Extractor Pro",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Apply Anova brand theme
apply_anova_theme()

# Initialize session state
if 'initialized' not in st.session_state:
    st.session_state.initialized = True
    st.session_state.extraction_result = None
    st.session_state.api_stats = {}


def main():
    """Main Streamlit app"""
    
    # Sidebar
    with st.sidebar:
        anova_sidebar_logo()

        st.subheader("⚙️ Configuration")

        # API Key
        api_key = st.text_input(
            "Anthropic API Key",
            type="password",
            value=os.getenv("ANTHROPIC_API_KEY", ""),
            help="Your Anthropic API key (https://console.anthropic.com)"
        )

        if api_key:
            os.environ["ANTHROPIC_API_KEY"] = api_key

    # Main content
    anova_header("Term Extractor Pro", "AI-powered terminology extraction with bilingual lookup and derivative discovery")
    
    # Tabs for different pages
    tab1, tab2, tab3 = st.tabs(["📝 Extract", "📊 Results", "⚙️ Settings"])
    
    with tab1:
        st.subheader("Term Extraction")
        st.write("Upload a document and extract terminology with AI.")
        
        # Show extraction page
        from pages.extraction import show_extraction_page
        show_extraction_page()
    
    with tab2:
        st.subheader("Extraction Results")
        
        if st.session_state.extraction_result:
            from pages.results import show_results_page
            show_results_page(st.session_state.extraction_result)
        else:
            st.info("👉 Extract terms first in the **Extract** tab to see results here.")
    
    with tab3:
        st.subheader("Settings & Configuration")
        from pages.settings import show_settings_page
        show_settings_page()

    anova_footer()


if __name__ == "__main__":
    # Check API key
    if not os.getenv("ANTHROPIC_API_KEY"):
        st.warning(
            "⚠️ **API Key Required**\n\n"
            "Please enter your Anthropic API key in the sidebar to get started.\n\n"
            "Get one at: https://console.anthropic.com"
        )
    
    main()
