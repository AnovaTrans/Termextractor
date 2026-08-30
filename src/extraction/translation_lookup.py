"""
Translation Lookup for TermExtractor-Pro
Handles exact matching and fuzzy matching with similarity scoring
"""

import re
from typing import Dict, List, Tuple, Optional
from difflib import SequenceMatcher
from src.utils import calculate_similarity


class TranslationLookup:
    """Lookup translations in bilingual file"""
    
    def __init__(
        self,
        exact_index: Dict[str, str],
        fuzzy_index: Optional[Dict[str, Tuple[str, float]]] = None,
        fuzzy_threshold: float = 70.0,
    ):
        """
        Initialize translation lookup.
        
        Args:
            exact_index: Dictionary for exact matching
            fuzzy_index: Dictionary for fuzzy matching (optional)
            fuzzy_threshold: Minimum similarity % for fuzzy matches
        """
        self.exact_index = exact_index
        self.fuzzy_index = fuzzy_index or {}
        self.fuzzy_threshold = fuzzy_threshold
        
        # Statistics
        self.statistics = {
            'exact_matches': 0,
            'fuzzy_matches_above_threshold': 0,
            'fuzzy_matches_below_threshold': 0,
            'lookups_performed': 0,
        }
    
    def get_exact_match(self, term: str) -> Optional[str]:
        """
        Get exact match for term.
        
        Args:
            term: Term to look up
            
        Returns:
            Translation if found, None otherwise
        """
        self.statistics['lookups_performed'] += 1
        
        # Exact match (case-insensitive by default)
        normalized = term.strip().lower()
        
        for key, value in self.exact_index.items():
            if key.lower() == normalized:
                self.statistics['exact_matches'] += 1
                return value
        
        return None
    
    def get_fuzzy_match(self, term: str) -> Optional[Tuple[str, float]]:
        """
        Get fuzzy match for term.
        
        Args:
            term: Term to look up
            
        Returns:
            Tuple of (translation, similarity_score) or None
        """
        if not term:
            return None
        
        normalized_term = term.strip().lower()
        best_match = None
        best_score = 0.0
        
        # Search through exact index for fuzzy matches
        for key, value in self.exact_index.items():
            similarity = self._calculate_similarity(normalized_term, key.lower())
            
            if similarity > best_score:
                best_score = similarity
                best_match = (value, similarity)
        
        # Check if score meets threshold
        if best_match and best_score >= self.fuzzy_threshold:
            self.statistics['fuzzy_matches_above_threshold'] += 1
            return best_match
        elif best_match:
            self.statistics['fuzzy_matches_below_threshold'] += 1
            return None
        
        return None
    
    def find_containing_segments(self, term: str, k: int = 5) -> List[Tuple[str, str]]:
        """Return up to k (source, target) segment pairs whose SOURCE contains
        `term` as a whole word (case-insensitive). Used to pull a term's
        translation from inside the bilingual file when it isn't a standalone
        segment. `\\w` is Unicode-aware, so Turkish/accented letters bound
        correctly.
        """
        term = (term or "").strip()
        if not term:
            return []
        pattern = re.compile(r'(?<!\w)' + re.escape(term) + r'(?!\w)',
                             re.IGNORECASE | re.UNICODE)
        matches: List[Tuple[str, str]] = []
        for source, target in self.exact_index.items():
            if not target:
                continue
            if pattern.search(source):
                matches.append((source, target))
                if len(matches) >= k:
                    break
        return matches

    def lookup(self, term: str, use_fuzzy: bool = True) -> Optional[Tuple[str, str]]:
        """
        Look up term translation (exact first, then fuzzy).
        
        Args:
            term: Term to look up
            use_fuzzy: Whether to use fuzzy matching
            
        Returns:
            Tuple of (translation, source_type) where source_type is 'EXACT' or 'FUZZY'
                   or None if not found
        """
        # Try exact match first
        exact = self.get_exact_match(term)
        if exact:
            return (exact, 'EXACT_MATCH')
        
        # Try fuzzy match if enabled
        if use_fuzzy:
            fuzzy_result = self.get_fuzzy_match(term)
            if fuzzy_result:
                translation, similarity = fuzzy_result
                return (translation, 'FUZZY_REFERENCE')
        
        return None
    
    @staticmethod
    def _calculate_similarity(str1: str, str2: str) -> float:
        """
        Calculate similarity between two strings (0-100).
        
        Uses SequenceMatcher for better results than simple character matching.
        
        Args:
            str1: First string
            str2: Second string
            
        Returns:
            Similarity score (0-100)
        """
        if not str1 or not str2:
            return 0.0
        
        if str1 == str2:
            return 100.0
        
        # Use SequenceMatcher for ratio
        matcher = SequenceMatcher(None, str1, str2)
        ratio = matcher.ratio()
        
        return ratio * 100.0
    
    def get_statistics(self) -> Dict[str, any]:
        """Get lookup statistics"""
        return self.statistics.copy()
    
    def reset_statistics(self) -> None:
        """Reset statistics"""
        self.statistics = {
            'exact_matches': 0,
            'fuzzy_matches_above_threshold': 0,
            'fuzzy_matches_below_threshold': 0,
            'lookups_performed': 0,
        }


class TranslationLookupBuilder:
    """Build translation lookup indexes"""
    
    @staticmethod
    def build_exact_index(pairs: Dict[str, str]) -> Dict[str, str]:
        """
        Build exact match index.
        
        Args:
            pairs: Dictionary of source-target pairs
            
        Returns:
            Exact match index
        """
        index = {}
        
        for source, target in pairs.items():
            if source and target:
                # Store both original case and lowercase versions
                index[source.strip()] = target.strip()
        
        return index
    
    @staticmethod
    def build_fuzzy_index(pairs: Dict[str, str]) -> Dict[str, Tuple[str, float]]:
        """
        Build fuzzy match index.
        
        Args:
            pairs: Dictionary of source-target pairs
            
        Returns:
            Fuzzy match index (for reference during fuzzy lookup)
        """
        # For fuzzy, we use the exact index during lookup
        # This method is kept for API consistency
        return {}
