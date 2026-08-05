"""
API Manager for TermExtractor-Pro
Handles rate limiting, caching, and request orchestration
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import time
import threading
from src.api.anthropic_client import AnthropicClient
from src.config import get_config


class APIManager:
    """Manages API requests with rate limiting and caching"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize API manager.
        
        Args:
            api_key: Anthropic API key
        """
        self.client = AnthropicClient(api_key)
        self.config = get_config()
        
        # Rate limiting
        self.rate_limit_per_minute = self.config.get('api.rate_limit_per_minute', 50)
        self.request_times: List[datetime] = []

        # Simple in-memory cache
        self.cache: Dict[str, Any] = {}
        self.cache_ttl = timedelta(hours=24)
        self.cache_timestamps: Dict[str, datetime] = {}

        # Chunks are extracted from a thread pool (see TermExtractor). This lock
        # guards the shared bookkeeping — cache, request_times, stats — while the
        # network call itself runs OUTSIDE the lock so requests overlap.
        self._lock = threading.Lock()
        
        # Processing stats
        self.stats = {
            'total_requests': 0,
            'cached_hits': 0,
            'rate_limited_waits': 0,
        }
    
    def _cleanup_cache(self) -> None:
        """Remove expired cache entries"""
        now = datetime.now()
        expired_keys = [
            key for key, timestamp in self.cache_timestamps.items()
            if now - timestamp > self.cache_ttl
        ]
        
        for key in expired_keys:
            del self.cache[key]
            del self.cache_timestamps[key]
    
    def _get_cache_key(self, *args) -> str:
        """Generate cache key from arguments"""
        return str(hash(tuple(args)))
    
    def _check_rate_limit(self) -> None:
        """Enforce the per-minute request cap. Thread-safe; sleeps outside the lock."""
        sleep_needed = 0.0
        with self._lock:
            now = datetime.now()
            cutoff = now - timedelta(minutes=1)
            self.request_times = [t for t in self.request_times if t > cutoff]

            if len(self.request_times) >= self.rate_limit_per_minute:
                oldest_request = min(self.request_times)
                wait_time = (oldest_request + timedelta(minutes=1) - now).total_seconds()
                if wait_time > 0:
                    self.stats['rate_limited_waits'] += 1
                    sleep_needed = wait_time + 0.1

            self.request_times.append(now)

        # Was asyncio.sleep() in synchronous code — never awaited, so it slept for
        # nothing. Sleep here, outside the lock, so other threads are not blocked.
        if sleep_needed:
            time.sleep(sleep_needed)
    
    def extract_terms(
        self,
        text: str,
        source_lang: str,
        target_lang: Optional[str] = None,
        domain_path: Optional[str] = None,
        context: Optional[str] = None,
        use_cache: bool = True,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Extract terms with caching and rate limiting.

        Args:
            text: Text to extract from
            source_lang: Source language
            target_lang: Target language (optional)
            domain_path: Domain hint (optional)
            context: Additional context (optional)
            use_cache: Use cache if available
            model: Model id override (optional)
            max_tokens: Output-token ceiling override (optional)

        Returns:
            Extraction result
        """
        # Cache key includes the model: the same text on a different model is a
        # different result and must not be served from a stale entry.
        cache_key = self._get_cache_key('extract', text[:100], source_lang, target_lang,
                                        domain_path, model)

        if use_cache:
            with self._lock:
                if cache_key in self.cache:
                    self.stats['cached_hits'] += 1
                    return self.cache[cache_key]

        # Rate limiting (thread-safe, may sleep)
        self._check_rate_limit()

        with self._lock:
            self.stats['total_requests'] += 1

        # The network call runs OUTSIDE the lock so concurrent chunks overlap.
        result = self.client.extract_terms(
            text, source_lang, target_lang, domain_path, context,
            model=model, max_tokens=max_tokens,
        )

        if use_cache:
            with self._lock:
                self.cache[cache_key] = result
                self.cache_timestamps[cache_key] = datetime.now()

        return result
    
    def classify_domain(self, text: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        Classify domain with caching.
        
        Args:
            text: Text to classify
            use_cache: Use cache if available
            
        Returns:
            Domain classification
        """
        # Check cache first
        cache_key = self._get_cache_key('domain', text[:100])
        
        if use_cache and cache_key in self.cache:
            self.stats['cached_hits'] += 1
            return self.cache[cache_key]
        
        # Rate limiting
        self._check_rate_limit()
        
        # Call API
        self.stats['total_requests'] += 1
        result = self.client.classify_domain(text)
        
        # Cache result
        if use_cache:
            self.cache[cache_key] = result
            self.cache_timestamps[cache_key] = datetime.now()
        
        return result
    
    def refine_with_fuzzy_reference(
        self,
        term: str,
        translation: str,
        reference_translation: str,
        similarity_score: float,
        source_lang: str,
        target_lang: str,
    ) -> Dict[str, Any]:
        """
        Refine translation using fuzzy reference.
        (No caching for this as context matters)
        
        Args:
            term: Source term
            translation: API translation
            reference_translation: Reference from fuzzy match
            similarity_score: Fuzzy similarity
            source_lang: Source language
            target_lang: Target language
            
        Returns:
            Refined translation
        """
        # Rate limiting
        self._check_rate_limit()
        
        # Call API
        self.stats['total_requests'] += 1
        result = self.client.refine_with_fuzzy_reference(
            term, translation, reference_translation, similarity_score,
            source_lang, target_lang
        )
        
        return result
    
    def get_stats(self) -> Dict[str, Any]:
        """Get API manager statistics"""
        client_stats = self.client.get_usage_stats()
        
        return {
            'manager_stats': self.stats,
            'client_stats': client_stats,
            'cache_size': len(self.cache),
        }
    
    def clear_cache(self) -> None:
        """Clear all cache"""
        self.cache.clear()
        self.cache_timestamps.clear()
    
    def reset_stats(self) -> None:
        """Reset statistics"""
        self.stats = {
            'total_requests': 0,
            'cached_hits': 0,
            'rate_limited_waits': 0,
        }
        self.client.reset_usage_stats()
