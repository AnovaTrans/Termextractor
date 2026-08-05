"""
Helper utilities for TermExtractor-Pro
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import hashlib
import json


def chunk_text(text: str, chunk_size: int = 2000, overlap: int = 100) -> List[str]:
    """
    Split text into chunks respecting paragraph boundaries.
    
    Args:
        text: Text to chunk
        chunk_size: Target chunk size in characters
        overlap: Overlap between chunks
        
    Returns:
        List of text chunks
    """
    if not text or len(text) <= chunk_size:
        return [text]
    
    chunks = []
    paragraphs = text.split('\n\n')
    current_chunk = ""
    
    for para in paragraphs:
        if len(current_chunk) + len(para) < chunk_size:
            current_chunk += para + '\n\n'
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = para + '\n\n'
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks if chunks else [text]


def normalize_language_code(lang_code: str) -> str:
    """
    Normalize language code to 2-letter format.
    
    Args:
        lang_code: Language code (e.g., 'en-US', 'en', 'eng')
        
    Returns:
        Normalized 2-letter code
    """
    if not lang_code:
        return 'en'
    
    code = lang_code.lower().strip()
    
    # Already 2-letter
    if len(code) == 2:
        return code
    
    # Language-Country format
    if '-' in code:
        return code.split('-')[0]
    
    # 3-letter code (ISO 639-2/3)
    three_letter_to_two = {
        'eng': 'en', 'deu': 'de', 'fra': 'fr', 'spa': 'es', 'ita': 'it',
        'por': 'pt', 'rus': 'ru', 'jpn': 'ja', 'kor': 'ko', 'zho': 'zh',
        'ara': 'ar', 'hin': 'hi', 'ben': 'bn', 'tur': 'tr', 'ron': 'ro',
        'bul': 'bg', 'hrv': 'hr', 'ces': 'cs', 'dan': 'da', 'nld': 'nl',
    }
    return three_letter_to_two.get(code, code[:2])


def is_single_word(term: str) -> bool:
    """
    Check if term is a single word (no spaces or hyphens).
    
    Args:
        term: Term to check
        
    Returns:
        True if single word, False otherwise
    """
    if not term or not term.strip():
        return False
    
    return not any(c in term for c in [' ', '-', '_'])


def clean_text(text: str) -> str:
    """
    Clean text by removing extra whitespace.
    
    Args:
        text: Text to clean
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Remove extra spaces
    text = re.sub(r'\s+', ' ', text)
    # Remove leading/trailing spaces
    text = text.strip()
    
    return text


def extract_domain_hierarchy(domain_path: str) -> List[str]:
    """
    Extract domain hierarchy from path string.
    
    Args:
        domain_path: Domain path (e.g., 'Medical/Healthcare/Cardiology')
        
    Returns:
        List of domain levels
    """
    if not domain_path:
        return ['General']
    
    path = domain_path.strip()
    levels = [level.strip() for level in path.split('/') if level.strip()]
    
    return levels if levels else ['General']


def parse_domain_path(domain_path: Optional[str]) -> str:
    """
    Parse and validate domain path.
    
    Args:
        domain_path: Domain path string
        
    Returns:
        Validated domain path
    """
    if not domain_path:
        return "General"
    
    path = domain_path.strip()
    if not path:
        return "General"
    
    return path


def calculate_similarity(str1: str, str2: str) -> float:
    """
    Calculate simple similarity between two strings (0-100).
    
    Args:
        str1: First string
        str2: Second string
        
    Returns:
        Similarity score (0-100)
    """
    if not str1 or not str2:
        return 0.0
    
    s1 = str1.lower().strip()
    s2 = str2.lower().strip()
    
    if s1 == s2:
        return 100.0
    
    # Jaccard similarity on character level
    set1 = set(s1)
    set2 = set(s2)
    
    if not set1 or not set2:
        return 0.0
    
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    
    return (intersection / union) * 100.0


def get_file_extension(file_path: str) -> str:
    """
    Get file extension.
    
    Args:
        file_path: File path
        
    Returns:
        File extension (lowercase, without dot)
    """
    path = Path(file_path)
    return path.suffix.lstrip('.').lower()


def is_bilingual_format(file_extension: str) -> bool:
    """
    Check if file format is bilingual (XLIFF, SDLXLIFF, etc).
    
    Args:
        file_extension: File extension
        
    Returns:
        True if bilingual format
    """
    bilingual_formats = ['xliff', 'sdlxliff', 'mqxliff', 'tmx', 'xml']
    return file_extension.lower() in bilingual_formats


def safe_json_dumps(obj: Any, default_str: str = "{}") -> str:
    """
    Safely convert object to JSON string.
    
    Args:
        obj: Object to convert
        default_str: Default string if conversion fails
        
    Returns:
        JSON string
    """
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2)
    except (TypeError, ValueError):
        return default_str


def safe_json_loads(json_str: str, default_dict: Optional[Dict] = None) -> Dict:
    """
    Safely parse JSON string.
    
    Args:
        json_str: JSON string
        default_dict: Default dict if parsing fails
        
    Returns:
        Parsed dictionary
    """
    if default_dict is None:
        default_dict = {}
    
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return default_dict


def _first_json_span(text: str) -> Optional[str]:
    """Return the first balanced {...} or [...] block in text, or None.

    Scans with a string-aware depth counter so braces inside JSON string values
    (and escaped quotes) do not throw the balance off.
    """
    for i, ch in enumerate(text):
        if ch not in "{[":
            continue
        close = "}" if ch == "{" else "]"
        depth = 0
        in_str = False
        escaped = False
        for j in range(i, len(text)):
            c = text[j]
            if in_str:
                if escaped:
                    escaped = False
                elif c == "\\":
                    escaped = True
                elif c == '"':
                    in_str = False
            elif c == '"':
                in_str = True
            elif c == ch:
                depth += 1
            elif c == close:
                depth -= 1
                if depth == 0:
                    return text[i:j + 1]
        break  # an opener with no matching close: nothing usable
    return None


def parse_model_json(text: str, default: Any = None) -> Any:
    """Parse JSON out of a language-model reply.

    Models are asked for bare JSON but routinely wrap it in a ```json ... ```
    fence or prepend a sentence ("Here are the terms: ..."). Raw json.loads()
    then raises and — where the caller swallows that — the whole extraction
    silently yields nothing. This strips a fence if present, and otherwise pulls
    the first balanced JSON block out of the surrounding prose.

    Returns `default` only when no JSON can be recovered at all.
    """
    if not text or not text.strip():
        return default

    candidate = text.strip()

    fence = re.search(r"```(?:json)?\s*(.*?)```", candidate, re.DOTALL | re.IGNORECASE)
    if fence:
        candidate = fence.group(1).strip()

    try:
        return json.loads(candidate)
    except (json.JSONDecodeError, TypeError):
        pass

    span = _first_json_span(candidate)
    if span is not None:
        try:
            return json.loads(span)
        except (json.JSONDecodeError, TypeError):
            pass

    return default


def hash_string(s: str) -> str:
    """
    Create SHA256 hash of string.
    
    Args:
        s: String to hash
        
    Returns:
        Hash hex string
    """
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def truncate_string(s: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate string to max length.
    
    Args:
        s: String to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated string
    """
    if len(s) <= max_length:
        return s
    
    return s[:max_length - len(suffix)] + suffix


def format_number(num: float, decimals: int = 2) -> str:
    """
    Format number to string with decimals.
    
    Args:
        num: Number to format
        decimals: Number of decimal places
        
    Returns:
        Formatted string
    """
    return f"{num:.{decimals}f}"


def get_memory_usage() -> str:
    """
    Get current memory usage (simplified).
    
    Returns:
        Memory usage string
    """
    try:
        import psutil
        process = psutil.Process()
        mb = process.memory_info().rss / 1024 / 1024
        return f"{mb:.1f} MB"
    except:
        return "N/A"
