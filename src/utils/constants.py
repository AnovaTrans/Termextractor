"""
Constants for TermExtractor-Pro
"""

# Models offered in the UI dropdown. Order = display order (recommended first).
# IDs are the current Anthropic aliases; they always resolve to the latest
# snapshot, so this list does not need a date bump every release.
AVAILABLE_MODELS = {
    "claude-haiku-4-5": "Claude Haiku 4.5 — fast & economical (recommended)",
    "claude-sonnet-5": "Claude Sonnet 5 — balanced quality",
    "claude-opus-4-8": "Claude Opus 4.8 — most capable",
    "claude-3-5-haiku-20241022": "Claude 3.5 Haiku — legacy, cheapest",
}

# Claude Models by purpose (ordered by cost-efficiency for our use case)
CLAUDE_MODELS = {
    "extraction": "claude-haiku-4-5",          # Fast, cheap for simple text extraction
    "complex_analysis": "claude-sonnet-5",     # Better for fuzzy reference refinement
    "domain_classification": "claude-haiku-4-5",  # Fast domain detection
}

# Default model (fallback / dropdown default)
DEFAULT_MODEL = "claude-haiku-4-5"

# Text processing
TEXT_CHUNK_SIZE = 2000  # Characters per chunk for large files
MIN_TERM_LENGTH = 2
MAX_TERM_LENGTH = 255

# Extraction defaults
DEFAULT_RELEVANCE_THRESHOLD = 70.0
DEFAULT_CONFIDENCE_THRESHOLD = 60.0

# Fuzzy matching
DEFAULT_FUZZY_THRESHOLD = 70.0
FUZZY_MATCH_MIN_SCORE = 50.0

# Derivative discovery
DERIVATIVE_WORD_CHARS = r"[A-Za-zÀ-ÖØ-öø-ÿßÜüÄäÖö0-9_]"
DEFAULT_DERIVATIVE_MODES = ["prefix", "suffix"]
DEFAULT_MAX_VARIANTS = 20
DEFAULT_MIN_VARIANT_LENGTH = 3

# Supported languages - EU, Other European, Turkish, Arabic, Russian, Simplified Chinese
SUPPORTED_LANGUAGES = {
    # EU Languages
    'bg': 'Bulgarian',
    'hr': 'Croatian',
    'cs': 'Czech',
    'da': 'Danish',
    'nl': 'Dutch',
    'en': 'English',
    'et': 'Estonian',
    'fi': 'Finnish',
    'fr': 'French',
    'de': 'German',
    'el': 'Greek',
    'hu': 'Hungarian',
    'ga': 'Irish',
    'it': 'Italian',
    'lv': 'Latvian',
    'lt': 'Lithuanian',
    'lb': 'Luxembourgish',
    'mt': 'Maltese',
    'pl': 'Polish',
    'pt': 'Portuguese',
    'ro': 'Romanian',
    'sk': 'Slovak',
    'sl': 'Slovenian',
    'es': 'Spanish',
    'sv': 'Swedish',
    'ca': 'Catalan',
    'cy': 'Welsh',
    # Other European Languages
    'sq': 'Albanian',
    'hy': 'Armenian',
    'az': 'Azerbaijani',
    'be': 'Belarusian',
    'bs': 'Bosnian',
    'ka': 'Georgian',
    'is': 'Icelandic',
    'mk': 'Macedonian',
    'no': 'Norwegian',
    'ru': 'Russian',
    'sr': 'Serbian',
    'uk': 'Ukrainian',
    # Special Requests
    'tr': 'Turkish',
    'ar': 'Arabic',
    'zh': 'Simplified Chinese',
}

# File formats
SUPPORTED_FILE_FORMATS = {
    'txt': 'Plain Text',
    'docx': 'Microsoft Word',
    'pdf': 'PDF',
    'html': 'HTML',
    'htm': 'HTML',
    'xliff': 'XLIFF',
    'sdlxliff': 'SDLXLIFF',
    'mqxliff': 'MQXLIFF',
    'xml': 'XML',
}

# Export formats
EXPORT_FORMATS = ['xlsx', 'csv', 'tbx', 'json']

# API rate limits
API_RATE_LIMIT_PER_MINUTE = 50
# Raised from 4096: at 4096 a term-dense chunk could exhaust the output budget,
# truncate the JSON mid-object, and — because the parser then failed — yield zero
# terms. 8192 clears any single ~2000-char chunk with headroom.
API_MAX_TOKENS_PER_REQUEST = 8192
API_TIMEOUT_SECONDS = 60

# Batch processing
BATCH_SIZE = 5
MAX_PARALLEL_REQUESTS = 3

# Statistics thresholds
HIGH_RELEVANCE_THRESHOLD = 80
MEDIUM_RELEVANCE_THRESHOLD = 60

# Export column names
EXPORT_COLUMNS = [
    'term',
    'translation',
    'from_existing_translation',
    'translation_source',
    'fuzzy_match_score',
    'discovered_derivatives',
    'domain',
    'subdomain',
    'pos',
    'definition',
    'context',
    'relevance_score',
    'confidence_score',
    'frequency',
    'is_compound',
    'is_abbreviation',
    'variants',
    'related_terms',
]

# Translation sources
TRANSLATION_SOURCE_API = "API"
TRANSLATION_SOURCE_EXACT = "EXACT_MATCH"
TRANSLATION_SOURCE_FUZZY = "FUZZY_REFERENCE"

# UI defaults
UI_THEME = "light"
UI_SIDEBAR_STATE = "expanded"
