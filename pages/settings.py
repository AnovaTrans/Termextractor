"""
Settings page for TermExtractor-Pro
"""

import streamlit as st
from src.config import get_config


def show_settings_page():
    """Show settings and configuration page"""
    
    st.write("Configure TermExtractor-Pro settings and view system information.")
    
    st.markdown("---")
    
    # Configuration tabs
    tab_config, tab_info, tab_help = st.tabs(["⚙️ Configuration", "ℹ️ System Info", "❓ Help"])
    
    with tab_config:
        st.subheader("Application Configuration")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("#### Extraction Settings")
            
            extraction_config = get_config().get_extraction_config()
            
            st.write(f"- **Default Relevance Threshold**: {extraction_config.get('default_relevance_threshold', 70)}%")
            st.write(f"- **Chunk Size**: {extraction_config.get('chunk_size', 12000)} characters")
            st.write(f"- **Min Term Length**: {extraction_config.get('min_term_length', 2)}")
            st.write(f"- **Max Term Length**: {extraction_config.get('max_term_length', 255)}")
        
        with col2:
            st.write("#### API Configuration")
            
            api_config = get_config().get_api_config()
            
            st.write(f"- **Timeout**: {api_config.get('timeout_seconds', 60)}s")
            st.write(f"- **Rate Limit**: {api_config.get('rate_limit_per_minute', 50)} req/min")
            st.write(f"- **Max Tokens**: {api_config.get('max_tokens_per_request', 16000)}")
            st.write(f"- **Retry Attempts**: {api_config.get('retry_attempts', 3)}")
        
        st.markdown("---")
        
        st.write("#### Feature Configuration")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Bilingual Lookup**")
            
            lookup_config = get_config().get_translation_lookup_config()
            
            st.write(f"- **Enabled**: {lookup_config.get('enabled', False)}")
            st.write(f"- **Fuzzy Matching**: {lookup_config.get('fuzzy_matching_enabled', True)}")
            st.write(f"- **Fuzzy Threshold**: {lookup_config.get('fuzzy_threshold', 70)}%")
            st.write(f"- **Case Sensitive**: {lookup_config.get('exact_match_case_sensitive', False)}")
            
            supported = lookup_config.get('supported_formats', [])
            st.write(f"- **Supported Formats**: {', '.join(supported)}")
        
        with col2:
            st.write("**Derivative Discovery**")
            
            deriv_config = get_config().get_derivative_config()
            
            st.write(f"- **Enabled**: {deriv_config.get('enabled', False)}")
            
            modes = deriv_config.get('modes', [])
            st.write(f"- **Modes**: {', '.join(modes)}")
            
            st.write(f"- **Min Variant Length**: {deriv_config.get('min_variant_length', 3)}")
            st.write(f"- **Max Variants/Term**: {deriv_config.get('max_variants_per_term', 20)}")
            st.write(f"- **Case Sensitive**: {deriv_config.get('case_sensitive', False)}")
    
    with tab_info:
        st.subheader("System Information")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("#### Application")
            
            app_config = get_config().get_app_config()
            
            st.write(f"- **Name**: {app_config.get('name', 'TermExtractor-Pro')}")
            st.write(f"- **Version**: {app_config.get('version', '1.0.0')}")
            st.write(f"- **Description**: {app_config.get('description', 'N/A')}")
        
        with col2:
            st.write("#### Model Selection (Cost Optimized)")
            
            model_config = get_config().get_model_config()
            
            st.write(f"- **Extraction**: `{model_config.get('extraction_model', 'N/A')}`")
            st.write(f"- **Domain Classification**: `{model_config.get('domain_classification_model', 'N/A')}`")
            st.write(f"- **Fuzzy Refinement**: `{model_config.get('fuzzy_refinement_model', 'N/A')}`")
            st.write(f"- **Default**: `{model_config.get('default_model', 'N/A')}`")
        
        st.markdown("---")
        
        st.write("#### Language Support")
        
        lang_config = get_config().get_ui_config()
        supported_langs = ["en", "de", "fr", "es", "it", "pt", "bg", "ro", "tr", "ru", "ja", "zh", "ar", "hi"]
        
        st.write("**Supported Languages:**")
        
        cols = st.columns(7)
        for idx, lang in enumerate(supported_langs):
            with cols[idx % 7]:
                st.write(f"🌍 {lang.upper()}")
    
    with tab_help:
        st.subheader("Help & Documentation")
        
        st.write("### Getting Started")
        st.write("""
        1. **Upload Document**: Use the Extract tab to upload your document
        2. **Configure Settings**: Choose language pair and domain
        3. **Advanced Options**: Enable bilingual lookup and derivative discovery as needed
        4. **Extract**: Click the extract button to start processing
        5. **Review Results**: Check the Results tab for extracted terms
        6. **Export**: Download results in your preferred format
        """)
        
        st.markdown("---")
        
        st.write("### Feature Explanations")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("#### Bilingual Lookup")
            st.write("""
            **What it does:**
            - Checks if extracted terms already have translations in your bilingual file
            - Supports exact matching and fuzzy matching
            
            **When to use:**
            - When you have existing translations (XLIFF, SDLXLIFF files)
            - To maintain terminology consistency
            - To reduce AI API calls
            
            **Supported formats:**
            - XLIFF 1.2
            - SDLXLIFF
            - MQXLIFF
            """)
        
        with col2:
            st.write("#### Derivative Discovery")
            st.write("""
            **What it does:**
            - Finds morphological variants of extracted terms
            - Searches for prefix additions (e.g., 'machine' → 'machines')
            - Searches for suffix additions (e.g., 'machine' → 'machinery')
            
            **When to use:**
            - For comprehensive terminology coverage
            - In morphologically rich languages
            - When building terminology databases
            
            **Search patterns:**
            - Prefix: term + suffix
            - Suffix: prefix + term
            - Any: anywhere in compound
            """)
        
        st.markdown("---")
        
        st.write("### Export Formats")
        
        formats_info = {
            'XLSX': 'Spreadsheet with multiple sheets (terms, derivatives, statistics)',
            'CSV': 'Comma-separated values for spreadsheets and data processing',
            'JSON': 'Structured data format for APIs and programmatic use',
            'TBX': 'Terminology Exchange format for CAT tools (Trados, memoQ, etc.)',
        }
        
        for fmt, desc in formats_info.items():
            st.write(f"**{fmt}**: {desc}")
        
        st.markdown("---")
        
        st.write("### API Key Management")
        st.warning("""
        ⚠️ **Security Notice**
        
        - Your API key is sent securely to Anthropic servers
        - Never share your API key
        - Keep your API key confidential
        - You can rotate your key anytime in the Anthropic console
        
        **Get your API key:**
        - Go to https://console.anthropic.com
        - Create a new API key
        - Copy and paste it into the Configuration sidebar
        """)
