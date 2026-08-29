"""
Extraction page for TermExtractor-Pro
"""

import streamlit as st
import tempfile
from pathlib import Path
import os

from src.extraction import TermExtractor
from src.utils.constants import SUPPORTED_LANGUAGES
from src.utils.model_utils import (
    list_model_ids, default_model, display_name, FALLBACK_MODELS,
)


@st.cache_data(show_spinner=False)
def _cached_model_ids(api_key: str):
    """Live current-generation model ids, cached per key so we don't hit the
    Models API on every rerun."""
    return list_model_ids(api_key)


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

    # AI model selection — fetched live from the account so retired ids never
    # linger; legacy generations are filtered out in model_utils. Falls back to
    # the current-only static list when the API can't be reached.
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    live_ids = _cached_model_ids(api_key)
    model_ids = live_ids or FALLBACK_MODELS
    default_id = default_model(model_ids)
    default_index = model_ids.index(default_id) if default_id in model_ids else 0
    selected_model = st.selectbox(
        "🤖 AI Model",
        options=model_ids,
        format_func=display_name,
        index=default_index,
        help="Which Claude model to use for extraction. Faster models cost less; "
             "more capable models may find subtler terms. List is fetched live "
             "from your account (current-generation models only).",
    )
    if api_key and not live_ids:
        st.caption("⚠️ Couldn't fetch the live model list — showing current-generation defaults.")

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
    
    # Extract button. It is disabled while a run is in progress (so a second
    # click cannot restart the job) and until a file is chosen.
    running = st.session_state.get("extracting", False)

    col_extract, col_info = st.columns([2, 3])
    with col_extract:
        extract_button = st.button(
            "⏳ Extracting…" if running else "🚀 Extract Terms",
            use_container_width=True,
            type="primary",
            disabled=running or uploaded_file is None,
        )
    with col_info:
        if uploaded_file:
            st.info(
                f"📄 **{uploaded_file.name}** ({uploaded_file.size / 1024:.1f} KB)\n\n"
                f"Language: **{source_lang}** → **{target_lang or 'Monolingual'}**"
            )

    # First click only flips the flag and reruns, so the button re-renders
    # disabled BEFORE the blocking work starts (Streamlit runs top to bottom).
    if extract_button and not running:
        if not uploaded_file:
            st.error("❌ Please upload a file first")
            return
        if not os.getenv("ANTHROPIC_API_KEY"):
            st.error("❌ Anthropic API key not configured")
            return
        st.session_state.extracting = True
        st.session_state.pop("extraction_error", None)
        st.rerun()

    # The blocking work runs on the rerun where the button is already disabled.
    if running:
        progress_bar = st.progress(0.0, text="Preparing…")

        def on_progress(done, total):
            fraction = (done / total) if total else 0.0
            progress_bar.progress(
                min(fraction, 1.0),
                text=f"Extracting terms… {done}/{total} chunks ({fraction:.0%})",
            )

        tmp_path = None
        bilingual_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp:
                tmp.write(uploaded_file.getbuffer())
                tmp_path = tmp.name

            extractor = TermExtractor(api_key=os.getenv("ANTHROPIC_API_KEY"))

            if enable_bilingual and bilingual_file:
                with tempfile.NamedTemporaryFile(delete=False, suffix=Path(bilingual_file.name).suffix) as tmp_bi:
                    tmp_bi.write(bilingual_file.getbuffer())
                    bilingual_path = tmp_bi.name

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
                progress_cb=on_progress,
            )
            progress_bar.progress(1.0, text="Done")

            st.session_state.extraction_result = result
            st.session_state.api_stats = extractor.get_usage_stats()
            st.session_state.export_format = export_format
            st.session_state.last_extract_count = len(result.terms)
        except Exception as e:
            st.session_state.extraction_error = str(e)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
            if bilingual_path and os.path.exists(bilingual_path):
                os.unlink(bilingual_path)
            st.session_state.extracting = False
        # Rerun to re-enable the button and render the outcome below.
        st.rerun()

    # Outcome of the last run (persists across reruns / tab switches).
    if st.session_state.get("extraction_error"):
        st.error(f"❌ Error during extraction: {st.session_state.pop('extraction_error')}")
        st.write("Please check your API key and try again.")
    elif st.session_state.get("extraction_result") is not None and "last_extract_count" in st.session_state:
        result = st.session_state.extraction_result
        st.success(f"✅ Extracted {st.session_state.last_extract_count} terms!")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Terms", len(result.terms))
        with col2:
            st.metric("High Relevance", len(result.get_high_relevance_terms(80)))
        with col3:
            if result.lookup_statistics:
                st.metric("Bilingual Matches", result.lookup_statistics.get('exact_matches_found', 0))
        with col4:
            if result.derivative_statistics:
                st.metric("Derivatives Found", result.derivative_statistics.get('derivatives_found', 0))

        st.info("👉 View detailed results in the **Results** tab")
