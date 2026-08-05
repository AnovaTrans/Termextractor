"""
Extraction page for TermExtractor-Pro
"""

import streamlit as st
import tempfile
from pathlib import Path
import os

from src.extraction import TermExtractor
from src.utils.constants import SUPPORTED_LANGUAGES, AVAILABLE_MODELS, DEFAULT_MODEL


def show_extraction_page():
    """Show extraction page"""
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.write("### Upload Document")
        
        uploaded_file = st.file_uploader(
            "Choose a file to extract terms from",
            type=["txt", "pdf", "docx", "html", "xml", "xliff", "sdlxliff", "mqxliff"],
            help="Supported formats: TXT, PDF, DOCX, HTML, XML, XLIFF"
        )
    
    with col2:
        st.write("### Basic Settings")
        
        source_lang = st.selectbox(
            "Source Language",
            options=list(SUPPORTED_LANGUAGES.keys()),
            format_func=lambda x: f"{x} - {SUPPORTED_LANGUAGES[x]}",
            index=list(SUPPORTED_LANGUAGES.keys()).index('en'),
            help="Language of the document"
        )
        
        target_lang = st.selectbox(
            "Target Language",
            options=["None"] + list(SUPPORTED_LANGUAGES.keys()),
            format_func=lambda x: f"{x} - {SUPPORTED_LANGUAGES[x]}" if x != "None" else "None",
            index=0,
            help="For bilingual extraction and translation"
        )
        
        if target_lang == "None":
            target_lang = None

    # AI model selection
    model_ids = list(AVAILABLE_MODELS.keys())
    default_index = model_ids.index(DEFAULT_MODEL) if DEFAULT_MODEL in model_ids else 0
    selected_model = st.selectbox(
        "🤖 AI Model",
        options=model_ids,
        format_func=lambda mid: AVAILABLE_MODELS[mid],
        index=default_index,
        help="Which Claude model to use for extraction. Faster models cost less; "
             "more capable models may find subtler terms.",
    )

    st.markdown("---")

    # Advanced settings
    with st.expander("🔧 Advanced Options", expanded=False):
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🌐 Bilingual Lookup")
            
            enable_bilingual = st.checkbox(
                "Enable Bilingual Lookup",
                value=False,
                help="Use existing translations from a bilingual file"
            )
            
            bilingual_file = None
            fuzzy_threshold = 70.0
            
            if enable_bilingual:
                bilingual_file = st.file_uploader(
                    "Upload existing translations (XLIFF/SDLXLIFF)",
                    type=["xliff", "sdlxliff", "mqxliff", "xml"],
                    key="bilingual_upload",
                    help="File containing source-target translation pairs"
                )
                
                fuzzy_threshold = st.slider(
                    "Fuzzy Match Threshold (%)",
                    min_value=0, max_value=100, value=70,
                    help="Minimum similarity to consider fuzzy match"
                )
        
        with col2:
            st.subheader("🔬 Derivative Discovery")
            
            enable_derivatives = st.checkbox(
                "Enable Derivative Discovery",
                value=False,
                help="Find morphological variants of single-word terms"
            )
            
            derivative_modes = ["prefix", "suffix"]
            
            if enable_derivatives:
                st.info(
                    "🔍 When enabled, finds morphological variants:\n"
                    "- **Prefix**: 'machine' → 'machines', 'machinery'\n"
                    "- **Suffix**: 'machine' → 'unmachine'\n"
                    "- **Any**: Finds variants anywhere"
                )
                
                modes_selected = st.multiselect(
                    "Search Patterns",
                    options=["prefix", "suffix", "any"],
                    default=["prefix", "suffix"],
                    help="Choose search patterns",
                )
                
                if modes_selected:
                    derivative_modes = modes_selected
    
    # Additional settings
    col1, col2, col3 = st.columns(3)
    
    with col1:
        domain_path = st.text_input(
            "Domain (optional)",
            value="",
            placeholder="e.g., Medical/Healthcare/Cardiology",
            help="Domain hint for better classification"
        )
    
    with col2:
        relevance_threshold = st.slider(
            "Relevance Threshold",
            min_value=0, max_value=100, value=70,
            help="Filter terms below this score"
        )
    
    with col3:
        export_format = st.selectbox(
            "Export Format",
            options=["xlsx", "csv", "json", "tbx"],
            index=0,
            help="Output format for results"
        )
    
    st.markdown("---")
    
    # Extract button
    col_extract, col_info = st.columns([2, 3])
    
    with col_extract:
        extract_button = st.button(
            "🚀 Extract Terms",
            use_container_width=True,
            type="primary"
        )
    
    with col_info:
        if uploaded_file:
            st.info(
                f"📄 **{uploaded_file.name}** ({uploaded_file.size / 1024:.1f} KB)\n\n"
                f"Language: **{source_lang}** → **{target_lang or 'Monolingual'}**"
            )
    
    # Perform extraction
    if extract_button:
        if not uploaded_file:
            st.error("❌ Please upload a file first")
            return
        
        if not os.getenv("ANTHROPIC_API_KEY"):
            st.error("❌ Anthropic API key not configured")
            return
        
        try:
            with st.spinner("🔄 Extracting terms..."):
                # Save uploaded file temporarily
                with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp:
                    tmp.write(uploaded_file.getbuffer())
                    tmp_path = tmp.name
                
                try:
                    # Initialize extractor
                    extractor = TermExtractor(api_key=os.getenv("ANTHROPIC_API_KEY"))
                    
                    # Prepare bilingual file path
                    bilingual_path = None
                    if enable_bilingual and bilingual_file:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(bilingual_file.name).suffix) as tmp_bi:
                            tmp_bi.write(bilingual_file.getbuffer())
                            bilingual_path = tmp_bi.name
                    
                    # Extract
                    result = extractor.extract(
                        file_path=tmp_path,
                        source_lang=source_lang,
                        target_lang=target_lang,
                        domain_path=domain_path if domain_path else None,
                        relevance_threshold=relevance_threshold,
                        enable_bilingual_lookup=enable_bilingual and bilingual_file is not None,
                        bilingual_file_path=bilingual_path,
                        fuzzy_threshold=fuzzy_threshold,
                        enable_derivative_discovery=enable_derivatives,
                        derivative_modes=derivative_modes,
                        model=selected_model,
                    )
                    
                    # Store in session state
                    st.session_state.extraction_result = result
                    st.session_state.api_stats = extractor.get_usage_stats()
                    st.session_state.export_format = export_format
                    
                    # Show success message
                    st.success(f"✅ Extracted {len(result.terms)} terms!")
                    
                    # Show quick stats
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Terms", len(result.terms))
                    with col2:
                        high_rel = len(result.get_high_relevance_terms(80))
                        st.metric("High Relevance", high_rel)
                    with col3:
                        if result.lookup_statistics:
                            st.metric("Bilingual Matches", result.lookup_statistics.get('exact_matches_found', 0))
                    with col4:
                        if result.derivative_statistics:
                            st.metric("Derivatives Found", result.derivative_statistics.get('derivatives_found', 0))
                    
                    # Show option to go to results
                    st.info("👉 View detailed results in the **Results** tab")
                
                finally:
                    # Cleanup
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                    if bilingual_path and os.path.exists(bilingual_path):
                        os.unlink(bilingual_path)
        
        except Exception as e:
            st.error(f"❌ Error during extraction: {str(e)}")
            st.write("Please check your API key and try again.")
