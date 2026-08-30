"""
Data models for TermExtractor-Pro
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum


class TranslationSourceType(Enum):
    """Enum for translation source types"""
    API = "API"
    EXACT_MATCH = "EXACT_MATCH"
    FILE_INSEGMENT = "FILE_INSEGMENT"  # term found inside a bilingual segment
    FUZZY_REFERENCE = "FUZZY_REFERENCE"


@dataclass
class Term:
    """Represents an extracted term with all metadata"""
    
    # Basic information
    term: str
    translation: Optional[str] = None
    domain: str = "General"
    subdomain: Optional[str] = None
    pos: str = "NOUN"  # Part of Speech
    
    # Content
    definition: str = ""
    context: str = ""
    
    # Scores (0-100)
    relevance_score: float = 0.0
    confidence_score: float = 0.0
    
    # Frequency and variants
    frequency: int = 1
    is_compound: bool = False
    is_abbreviation: bool = False
    variants: List[str] = field(default_factory=list)
    related_terms: List[str] = field(default_factory=list)
    
    # Bilingual lookup fields
    from_existing_translation: bool = False
    translation_source: str = "API"
    fuzzy_match_score: Optional[float] = None
    fuzzy_reference_term: Optional[str] = None
    source_file_info: Optional[str] = None
    
    # Derivative discovery fields
    discovered_derivatives: Optional[List[str]] = None
    derivative_discovery_enabled: bool = False
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert term to dictionary"""
        return {
            'term': self.term,
            'translation': self.translation,
            'domain': self.domain,
            'subdomain': self.subdomain,
            'pos': self.pos,
            'definition': self.definition,
            'context': self.context,
            'relevance_score': self.relevance_score,
            'confidence_score': self.confidence_score,
            'frequency': self.frequency,
            'is_compound': self.is_compound,
            'is_abbreviation': self.is_abbreviation,
            'variants': self.variants,
            'related_terms': self.related_terms,
            'from_existing_translation': self.from_existing_translation,
            'translation_source': self.translation_source,
            'fuzzy_match_score': self.fuzzy_match_score,
            'fuzzy_reference_term': self.fuzzy_reference_term,
            'discovered_derivatives': self.discovered_derivatives,
            'metadata': self.metadata,
        }
    
    def to_export_row(self) -> Dict[str, Any]:
        """Convert term to export row format"""
        return {
            'term': self.term,
            'translation': self.translation or '',
            'from_existing_translation': str(self.from_existing_translation),
            'translation_source': self.translation_source,
            'fuzzy_match_score': self.fuzzy_match_score or '',
            'discovered_derivatives': '; '.join(self.discovered_derivatives or []),
            'domain': self.domain,
            'subdomain': self.subdomain or '',
            'pos': self.pos,
            'definition': self.definition,
            'context': self.context,
            'relevance_score': round(self.relevance_score, 2),
            'confidence_score': round(self.confidence_score, 2),
            'frequency': self.frequency,
            'is_compound': str(self.is_compound),
            'is_abbreviation': str(self.is_abbreviation),
            'variants': '; '.join(self.variants or []),
            'related_terms': '; '.join(self.related_terms or []),
        }


@dataclass
class ExtractionResult:
    """Result of term extraction"""
    
    terms: List[Term] = field(default_factory=list)
    domain_hierarchy: List[str] = field(default_factory=lambda: ['General'])
    language_pair: str = "en"
    source_language: str = "en"
    target_language: Optional[str] = None
    
    # Statistics
    statistics: Dict[str, Any] = field(default_factory=dict)
    
    # Bilingual and derivative statistics
    lookup_statistics: Dict[str, Any] = field(default_factory=dict)
    derivative_statistics: Dict[str, Any] = field(default_factory=dict)
    
    # Processing metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate statistics after initialization if not provided"""
        if not self.statistics and self.terms:
            self.statistics = self._calculate_statistics(self.terms)
        elif not self.statistics:
            self.statistics = self._calculate_statistics([])
    
    def _calculate_statistics(self, terms: List[Term]) -> Dict[str, Any]:
        """Calculate statistics from terms"""
        if not terms:
            return {
                'total_terms': 0,
                'high_relevance': 0,
                'medium_relevance': 0,
                'low_relevance': 0,
                'avg_relevance_score': 0.0,
                'avg_confidence_score': 0.0,
                'unique_domains': 0,
            }
        
        high_rel = sum(1 for t in terms if t.relevance_score >= 80)
        medium_rel = sum(1 for t in terms if 60 <= t.relevance_score < 80)
        low_rel = sum(1 for t in terms if t.relevance_score < 60)
        
        avg_rel = sum(t.relevance_score for t in terms) / len(terms) if terms else 0
        avg_conf = sum(t.confidence_score for t in terms) / len(terms) if terms else 0
        
        unique_domains = len(set(t.domain for t in terms))
        
        return {
            'total_terms': len(terms),
            'high_relevance': high_rel,
            'medium_relevance': medium_rel,
            'low_relevance': low_rel,
            'avg_relevance_score': round(avg_rel, 2),
            'avg_confidence_score': round(avg_conf, 2),
            'unique_domains': unique_domains,
        }
    
    def filter_by_relevance(self, threshold: float) -> 'ExtractionResult':
        """Filter terms by relevance threshold"""
        filtered_terms = [t for t in self.terms if t.relevance_score >= threshold]
        
        result = ExtractionResult(
            terms=filtered_terms,
            domain_hierarchy=self.domain_hierarchy,
            language_pair=self.language_pair,
            source_language=self.source_language,
            target_language=self.target_language,
            metadata=self.metadata,
        )
        
        result.statistics = result._calculate_statistics(filtered_terms)
        result.lookup_statistics = self.lookup_statistics
        result.derivative_statistics = self.derivative_statistics
        
        return result
    
    def get_high_relevance_terms(self, threshold: float = 80) -> List[Term]:
        """Get high relevance terms"""
        return [t for t in self.terms if t.relevance_score >= threshold]


@dataclass
class BilinguialLookupStatistics:
    """Statistics for bilingual lookup"""
    
    total_terms_processed: int = 0
    exact_matches_found: int = 0
    insegment_matches_found: int = 0  # term translation pulled from inside a segment
    fuzzy_matches_found: int = 0
    fuzzy_matches_used: int = 0  # >= threshold
    fuzzy_matches_ignored: int = 0  # < threshold
    api_generated: int = 0
    lookup_rate: float = 0.0
    avg_fuzzy_score: float = 0.0
    bilingual_file_name: str = ""
    bilingual_file_format: str = ""


@dataclass
class DerivativeStatistics:
    """Statistics for derivative discovery"""
    
    terms_processed: int = 0
    single_word_terms: int = 0
    derivatives_found: int = 0
    avg_derivatives_per_term: float = 0.0
    modes_used: List[str] = field(default_factory=list)


@dataclass
class ExtractionConfig:
    """Configuration for extraction"""
    
    source_language: str = "en"
    target_language: Optional[str] = None
    domain_path: Optional[str] = None
    relevance_threshold: float = 70.0
    
    # Bilingual lookup settings
    enable_bilingual_lookup: bool = False
    bilingual_file_path: Optional[str] = None
    fuzzy_match_threshold: float = 70.0
    
    # Derivative discovery settings
    enable_derivative_discovery: bool = False
    derivative_modes: List[str] = field(default_factory=lambda: ["prefix", "suffix"])
    max_variants_per_term: int = 20
    
    # Processing settings
    chunk_size: int = 12000
    enable_caching: bool = False


@dataclass
class FileParseResult:
    """Result of file parsing"""
    
    text: str = ""
    file_format: str = ""
    language_pair: Optional[tuple] = None  # (source, target) for bilingual files
    is_bilingual: bool = False
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
