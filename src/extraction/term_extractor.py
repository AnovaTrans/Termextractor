"""
Main TermExtractor orchestrator for TermExtractor-Pro
Orchestrates all components: API, extraction, lookup, derivatives, export
"""

from typing import Optional, Dict, Any, List
from pathlib import Path
import tempfile

from src.api import APIManager
from src.models import (
    Term, ExtractionResult, ExtractionConfig,
    BilinguialLookupStatistics, DerivativeStatistics
)
from src.extraction.bilingual_file_handler import BilingualFileHandler
from src.extraction.translation_lookup import TranslationLookup, TranslationLookupBuilder
from src.extraction.derivative_discovery import DerivativeDiscovery, DerivativeConfig
from src.io import FileParser, FormatExporter
from src.utils import chunk_text, normalize_language_code, clean_text, parse_model_json


class TermExtractor:
    """Main terminology extraction engine"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize TermExtractor.
        
        Args:
            api_key: Anthropic API key
        """
        self.api_manager = APIManager(api_key)
        self.file_parser = FileParser()
        self.exporter = FormatExporter()
        self.bilingual_handler = BilingualFileHandler()
        
        # Components
        self.translation_lookup: Optional[TranslationLookup] = None
        self.derivative_discovery: Optional[DerivativeDiscovery] = None
        
        # Configuration
        self.config: Optional[ExtractionConfig] = None
        
        # Statistics
        self.lookup_stats = BilinguialLookupStatistics()
        self.derivative_stats = DerivativeStatistics()
    
    def extract(
        self,
        file_path: str,
        source_lang: str = 'en',
        target_lang: Optional[str] = None,
        domain_path: Optional[str] = None,
        relevance_threshold: float = 70.0,
        # Bilingual lookup options
        enable_bilingual_lookup: bool = False,
        bilingual_file_path: Optional[str] = None,
        fuzzy_threshold: float = 70.0,
        # Derivative discovery options
        enable_derivative_discovery: bool = False,
        derivative_modes: Optional[List[str]] = None,
        # Model override (falls back to the configured extraction model)
        model: Optional[str] = None,
    ) -> ExtractionResult:
        """
        Extract terms from file.
        
        Args:
            file_path: Path to file to extract from
            source_lang: Source language code
            target_lang: Target language code (optional)
            domain_path: Domain hint (optional)
            relevance_threshold: Relevance score threshold (0-100)
            enable_bilingual_lookup: Enable bilingual lookup
            bilingual_file_path: Path to bilingual file
            fuzzy_threshold: Fuzzy match threshold (0-100)
            enable_derivative_discovery: Enable derivative discovery
            derivative_modes: Derivative search modes
            
        Returns:
            ExtractionResult with extracted terms
        """
        # Store config
        self.config = ExtractionConfig(
            source_language=normalize_language_code(source_lang),
            target_language=normalize_language_code(target_lang) if target_lang else None,
            domain_path=domain_path,
            relevance_threshold=relevance_threshold,
            enable_bilingual_lookup=enable_bilingual_lookup,
            bilingual_file_path=bilingual_file_path,
            fuzzy_match_threshold=fuzzy_threshold,
            enable_derivative_discovery=enable_derivative_discovery,
            derivative_modes=derivative_modes or ['prefix', 'suffix'],
        )
        
        # Initialize components
        self._initialize_components()
        
        # Parse file
        parsed = self.file_parser.parse(file_path)
        
        if parsed.get('metadata', {}).get('error'):
            return ExtractionResult(
                terms=[],
                metadata={'error': parsed['metadata']['error']}
            )
        
        text = parsed.get('text', '')
        if not text:
            return ExtractionResult(
                terms=[],
                metadata={'warning': 'File is empty or could not be parsed'}
            )
        
        # Extract terms
        result = self._extract_terms(
            text,
            self.config.source_language,
            self.config.target_language,
            self.config.domain_path,
            model=model,
        )
        
        # Enrich with bilingual lookup
        if self.config.enable_bilingual_lookup and self.translation_lookup:
            result = self._enrich_with_bilingual_lookup(result)
        
        # Enrich with derivative discovery
        if self.config.enable_derivative_discovery and self.derivative_discovery:
            result = self._enrich_with_derivatives(result, text)
        
        # Apply relevance threshold
        if self.config.relevance_threshold > 0:
            result = result.filter_by_relevance(self.config.relevance_threshold)
        
        # Add statistics
        result.lookup_statistics = self.lookup_stats.__dict__
        result.derivative_statistics = self.derivative_stats.__dict__
        
        return result
    
    def _initialize_components(self) -> None:
        """Initialize optional components based on config"""
        if not self.config:
            return
        
        # Bilingual lookup
        if self.config.enable_bilingual_lookup and self.config.bilingual_file_path:
            try:
                with open(self.config.bilingual_file_path, 'rb') as f:
                    bilingual_content = f.read()
                
                pairs = self.bilingual_handler.extract_translation_pairs(bilingual_content)
                exact_index = TranslationLookupBuilder.build_exact_index(pairs)
                
                self.translation_lookup = TranslationLookup(
                    exact_index=exact_index,
                    fuzzy_threshold=self.config.fuzzy_match_threshold,
                )
                
                self.lookup_stats.bilingual_file_name = Path(self.config.bilingual_file_path).name
                self.lookup_stats.bilingual_file_format = self.bilingual_handler.file_format or 'unknown'
            
            except Exception as e:
                print(f"⚠️  Error initializing bilingual lookup: {e}")
                self.translation_lookup = None
        
        # Derivative discovery
        if self.config.enable_derivative_discovery:
            deriv_config = DerivativeConfig(
                enabled=True,
                modes=self.config.derivative_modes,
            )
            self.derivative_discovery = DerivativeDiscovery(
                enabled=True,
                modes=self.config.derivative_modes,
            )
            self.derivative_stats.modes_used = self.config.derivative_modes
    
    def _extract_terms(
        self,
        text: str,
        source_lang: str,
        target_lang: Optional[str],
        domain_path: Optional[str],
        model: Optional[str] = None,
    ) -> ExtractionResult:
        """Extract terms from text using API"""
        if not text:
            return ExtractionResult()
        
        # Chunk text if needed
        chunks = chunk_text(text, self.config.chunk_size if self.config else 2000)
        
        all_terms = []
        domain_hierarchy = []
        parse_failures = 0

        # Fetch all chunks. A large file (thousands of segments) becomes dozens of
        # chunks; running them sequentially made a real memoQ file take many minutes
        # and the host timed the run out. A bounded thread pool overlaps the network
        # calls — each releases the API-manager lock before the request — so the run
        # finishes in a fraction of the time. Pool size comes from config
        # (performance.max_parallel_requests); the per-minute rate limit still caps
        # the real throughput.
        max_workers = int(self.api_manager.config.get('performance.max_parallel_requests', 3)) or 1
        max_workers = max(1, min(max_workers, len(chunks)))

        def _fetch(index_chunk):
            index, chunk = index_chunk
            context = f"Chunk {index + 1} of {len(chunks)}" if len(chunks) > 1 else None
            return index, self.api_manager.extract_terms(
                text=chunk, source_lang=source_lang, target_lang=target_lang,
                domain_path=domain_path, context=context, model=model,
            )

        responses: List[Optional[Dict[str, Any]]] = [None] * len(chunks)
        if max_workers == 1:
            for pair in enumerate(chunks):
                try:
                    idx, resp = _fetch(pair)
                    responses[idx] = resp
                except Exception as e:   # one bad chunk must not sink the run
                    parse_failures += 1
                    print(f"⚠️  Chunk {pair[0] + 1} failed: {e}")
        else:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {pool.submit(_fetch, pair): pair[0] for pair in enumerate(chunks)}
                for future in as_completed(futures):
                    idx = futures[future]
                    try:
                        _, resp = future.result()
                        responses[idx] = resp
                    except Exception as e:
                        parse_failures += 1
                        print(f"⚠️  Chunk {idx + 1} failed: {e}")

        # Parse the responses in chunk order. Parsing is local work, so keeping it
        # sequential costs nothing and makes the output deterministic. The model is
        # asked for bare JSON but often wraps it in a ```json fence or a sentence of
        # preamble; parse_model_json digs the JSON out of that.
        for response in responses:
            if not response:
                continue
            content = response.get('content', '') or ''
            data = parse_model_json(content, default=None)

            if not isinstance(data, dict):
                parse_failures += 1
                print(f"⚠️  Could not parse a JSON object from the model reply "
                      f"(first 120 chars): {content[:120]!r}")
                continue

            try:
                # Convert to Term objects
                for term_data in data.get('terms', []):
                    term = Term(
                        term=term_data.get('term', ''),
                        translation=term_data.get('translation'),
                        domain=term_data.get('domain', 'General'),
                        subdomain=term_data.get('subdomain'),
                        pos=term_data.get('pos', 'NOUN'),
                        definition=term_data.get('definition', ''),
                        context=term_data.get('context', ''),
                        relevance_score=float(term_data.get('relevance_score', 0)),
                        confidence_score=float(term_data.get('confidence_score', 0)),
                        frequency=int(term_data.get('frequency', 1)),
                        is_compound=bool(term_data.get('is_compound', False)),
                        is_abbreviation=bool(term_data.get('is_abbreviation', False)),
                        variants=term_data.get('variants', []),
                        related_terms=term_data.get('related_terms', []),
                    )
                    all_terms.append(term)
                
                # Get domain hierarchy
                if not domain_hierarchy:
                    domain_hierarchy = data.get('domain_hierarchy', ['General'])

            except (ValueError, TypeError, KeyError) as e:
                # A single malformed term field (e.g. a non-numeric score) must
                # not sink the whole chunk.
                parse_failures += 1
                print(f"⚠️  Skipped a malformed term entry: {e}")
                continue

        # Deduplicate terms
        unique_terms = self._deduplicate_terms(all_terms)

        result = ExtractionResult(
            terms=unique_terms,
            domain_hierarchy=domain_hierarchy,
            source_language=source_lang,
            target_language=target_lang,
            language_pair=f"{source_lang}-{target_lang or source_lang}",
        )

        # Surface a total parse failure instead of reporting "0 terms" as success.
        if not unique_terms and parse_failures and parse_failures >= len(chunks):
            result.metadata = {
                **(result.metadata or {}),
                'warning': ("The model replied but its output could not be read as "
                            "terms. Try again, or use a smaller document."),
                'parse_failures': parse_failures,
            }

        result.statistics = result._calculate_statistics(unique_terms)
        
        return result
    
    def _enrich_with_bilingual_lookup(self, result: ExtractionResult) -> ExtractionResult:
        """Enrich terms with bilingual lookup"""
        if not self.translation_lookup:
            return result
        
        enriched_terms = []
        
        for term in result.terms:
            self.lookup_stats.total_terms_processed += 1
            
            # Try lookup
            lookup_result = self.translation_lookup.lookup(
                term.term,
                use_fuzzy=True
            )
            
            if lookup_result:
                translation, source_type = lookup_result
                
                if source_type == 'EXACT_MATCH':
                    term.translation = translation
                    term.from_existing_translation = True
                    term.translation_source = 'EXACT_MATCH'
                    self.lookup_stats.exact_matches_found += 1
                
                elif source_type == 'FUZZY_REFERENCE':
                    fuzzy_match = self.translation_lookup.get_fuzzy_match(term.term)
                    if fuzzy_match:
                        ref_translation, similarity = fuzzy_match
                        term.fuzzy_reference_term = ref_translation
                        term.fuzzy_match_score = similarity
                        term.translation_source = 'FUZZY_REFERENCE'
                        self.lookup_stats.fuzzy_matches_found += 1
                        self.lookup_stats.fuzzy_matches_used += 1
            else:
                self.lookup_stats.api_generated += 1
            
            enriched_terms.append(term)
        
        # Calculate statistics
        if self.lookup_stats.total_terms_processed > 0:
            self.lookup_stats.lookup_rate = (
                (self.lookup_stats.exact_matches_found + self.lookup_stats.fuzzy_matches_used) /
                self.lookup_stats.total_terms_processed
            ) * 100
        
        result.terms = enriched_terms
        return result
    
    def _enrich_with_derivatives(self, result: ExtractionResult, text: str) -> ExtractionResult:
        """Enrich terms with derivative discovery"""
        if not self.derivative_discovery:
            return result
        
        enriched_terms = []
        
        for term in result.terms:
            enriched_term = self.derivative_discovery.enrich_term(
                term.to_dict(),
                text
            )
            
            # Convert back to Term object
            term.variants = enriched_term.get('variants', term.variants)
            term.discovered_derivatives = enriched_term.get('metadata', {}).get('discovered_derivatives')
            
            enriched_terms.append(term)
        
        # Update statistics
        deriv_stats = self.derivative_discovery.get_statistics()
        self.derivative_stats.terms_processed = deriv_stats.get('terms_processed', 0)
        self.derivative_stats.single_word_terms = deriv_stats.get('single_word_terms', 0)
        self.derivative_stats.derivatives_found = deriv_stats.get('derivatives_found', 0)
        self.derivative_stats.avg_derivatives_per_term = deriv_stats.get('avg_derivatives_per_term', 0.0)
        
        result.terms = enriched_terms
        return result
    
    @staticmethod
    def _deduplicate_terms(terms: List[Term]) -> List[Term]:
        """Deduplicate terms by normalizing"""
        seen = {}
        
        for term in terms:
            key = (term.term.lower(), (term.translation or '').lower())
            
            if key in seen:
                # Merge with existing
                existing = seen[key]
                existing.frequency += term.frequency
                existing.relevance_score = max(existing.relevance_score, term.relevance_score)
                existing.confidence_score = max(existing.confidence_score, term.confidence_score)
                existing.variants = list(set((existing.variants or []) + (term.variants or [])))
                existing.related_terms = list(set((existing.related_terms or []) + (term.related_terms or [])))
            else:
                seen[key] = term
        
        return list(seen.values())
    
    def export_result(
        self,
        result: ExtractionResult,
        output_format: str = 'xlsx',
    ) -> bytes:
        """
        Export extraction result.
        
        Args:
            result: ExtractionResult to export
            output_format: Format (xlsx, csv, tbx, json)
            
        Returns:
            Exported data as bytes
        """
        return self.exporter.export(result, output_format)
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get API usage statistics"""
        return self.api_manager.get_stats()
