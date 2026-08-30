"""
Anthropic API client for TermExtractor-Pro
Cost-optimized model selection strategy
"""

import os
import threading
from typing import Optional, Dict, Any, List
import anthropic
from src.config import get_config


def _response_text(response) -> str:
    """Concatenate the text of every text block in a Messages response.

    Robust to responses whose first block is not text — e.g. when extended
    thinking is enabled the first block is a ThinkingBlock with no `.text`,
    so the old `response.content[0].text` would raise. This skips non-text
    blocks (thinking, tool_use) and joins the rest.
    """
    parts = []
    for block in (getattr(response, "content", None) or []):
        if getattr(block, "type", None) == "text":
            parts.append(getattr(block, "text", ""))
    return "".join(parts)


class AnthropicClient:
    """Anthropic API client with cost optimization"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Anthropic client.
        
        Args:
            api_key: Anthropic API key (uses ANTHROPIC_API_KEY env var if not provided)
        """
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        
        if not self.api_key:
            raise ValueError(
                "Anthropic API key not found. "
                "Set ANTHROPIC_API_KEY environment variable."
            )
        
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.config = get_config()

        # Guards usage_stats: extraction runs several requests concurrently and
        # dict increments are not atomic.
        self._stats_lock = threading.Lock()

        # Usage tracking
        self.usage_stats = {
            'total_requests': 0,
            'total_input_tokens': 0,
            'total_output_tokens': 0,
            'estimated_cost': 0.0,
        }
        
        # Pricing, USD per token (approximate; used only for the cost estimate).
        # Current-generation only — the UI never offers legacy models. Any live
        # model not listed here falls back to the Sonnet-tier estimate below.
        self.pricing = {
            'claude-haiku-4-5':  {'input': 1.00 / 1_000_000, 'output': 5.00 / 1_000_000},
            'claude-sonnet-5':   {'input': 3.00 / 1_000_000, 'output': 15.00 / 1_000_000},
            'claude-sonnet-4-6': {'input': 3.00 / 1_000_000, 'output': 15.00 / 1_000_000},
            'claude-opus-4-8':   {'input': 5.00 / 1_000_000, 'output': 25.00 / 1_000_000},
            'claude-opus-4-7':   {'input': 5.00 / 1_000_000, 'output': 25.00 / 1_000_000},
            'claude-opus-4-6':   {'input': 5.00 / 1_000_000, 'output': 25.00 / 1_000_000},
            'claude-fable-5':    {'input': 10.00 / 1_000_000, 'output': 50.00 / 1_000_000},
        }
        # Fallback when an unknown model id is priced.
        self._fallback_price = {'input': 3.00 / 1_000_000, 'output': 15.00 / 1_000_000}
    
    def _get_model_for_purpose(self, purpose: str = 'extraction') -> str:
        """
        Get best model for purpose based on cost-efficiency.
        
        Strategy:
        - extraction: Use Haiku (fast, cheap)
        - domain_classification: Use Haiku (simple task)
        - fuzzy_refinement: Use Sonnet (complex reasoning)
        
        Args:
            purpose: Task purpose
            
        Returns:
            Model name
        """
        return self.config.get_model(purpose)
    
    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate estimated cost for API call"""
        pricing = self.pricing.get(model, self._fallback_price)

        input_cost = input_tokens * pricing['input']
        output_cost = output_tokens * pricing['output']

        return input_cost + output_cost

    def _max_tokens(self) -> int:
        """Output-token ceiling per request, from config (default 8192)."""
        return int(self.config.get('api.max_tokens_per_request', 16000))
    
    def extract_terms(
        self,
        text: str,
        source_lang: str,
        target_lang: Optional[str] = None,
        domain_path: Optional[str] = None,
        context: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Extract terms from text.

        Args:
            text: Text to extract terms from
            source_lang: Source language code
            target_lang: Target language code (optional)
            domain_path: Domain hint
            context: Additional context
            model: Model id to use (falls back to the configured extraction model)
            max_tokens: Output-token ceiling (falls back to the configured value)

        Returns:
            API response with extracted terms
        """
        model = model or self._get_model_for_purpose('extraction')
        max_tokens = max_tokens or self._max_tokens()

        system_prompt = self._get_extraction_system_prompt()
        user_prompt = self._get_extraction_user_prompt(
            text, source_lang, target_lang, domain_path, context
        )

        response = self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )
        
        cost = self._calculate_cost(
            model,
            response.usage.input_tokens,
            response.usage.output_tokens
        )
        # Track usage (called from worker threads)
        with self._stats_lock:
            self.usage_stats['total_requests'] += 1
            self.usage_stats['total_input_tokens'] += response.usage.input_tokens
            self.usage_stats['total_output_tokens'] += response.usage.output_tokens
            self.usage_stats['estimated_cost'] += cost

        return {
            'content': _response_text(response),
            'model': model,
            'usage': {
                'input_tokens': response.usage.input_tokens,
                'output_tokens': response.usage.output_tokens,
                'cost': cost,
            }
        }
    
    def classify_domain(self, text: str) -> Dict[str, Any]:
        """
        Classify text into domain using Haiku (fast, cheap).
        
        Args:
            text: Text to classify
            
        Returns:
            Domain classification result
        """
        model = self._get_model_for_purpose('domain_classification')
        
        prompt = f"""Classify the following text into a domain hierarchy (max 3 levels).
        
Text: {text[:500]}

Return ONLY valid JSON:
{{
    "primary_domain": "string",
    "subdomain": "string or null",
    "confidence": number 0-100
}}"""
        
        response = self.client.messages.create(
            model=model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Track usage
        self.usage_stats['total_requests'] += 1
        self.usage_stats['total_input_tokens'] += response.usage.input_tokens
        self.usage_stats['total_output_tokens'] += response.usage.output_tokens
        
        return {
            'content': _response_text(response),
            'model': model,
        }
    
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
        Refine translation using Sonnet (better reasoning) with fuzzy reference.
        Used for higher-quality fuzzy match refinement.
        
        Args:
            term: Source term
            translation: API-generated translation
            reference_translation: Reference translation from fuzzy match
            similarity_score: Fuzzy match similarity (0-100)
            source_lang: Source language
            target_lang: Target language
            
        Returns:
            Refined translation result
        """
        model = self._get_model_for_purpose('fuzzy_refinement')
        
        prompt = f"""You are a terminology expert. Refine a translation using a fuzzy match reference.

SOURCE TERM ({source_lang}): "{term}"
API-GENERATED TRANSLATION ({target_lang}): "{translation}"
FUZZY MATCH REFERENCE ({target_lang}): "{reference_translation}"
FUZZY MATCH SIMILARITY: {similarity_score}%

Should the reference translation be used or the API translation?
Provide the best translation considering both options.

Return ONLY valid JSON:
{{
    "best_translation": "string",
    "rationale": "string",
    "source": "API" or "REFERENCE" or "HYBRID",
    "confidence": number 0-100
}}"""
        
        response = self.client.messages.create(
            model=model,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Track usage
        self.usage_stats['total_requests'] += 1
        self.usage_stats['total_input_tokens'] += response.usage.input_tokens
        self.usage_stats['total_output_tokens'] += response.usage.output_tokens
        cost = self._calculate_cost(
            model,
            response.usage.input_tokens,
            response.usage.output_tokens
        )
        self.usage_stats['estimated_cost'] += cost
        
        return {
            'content': _response_text(response),
            'model': model,
            'cost': cost,
        }
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics"""
        return self.usage_stats.copy()
    
    def reset_usage_stats(self) -> None:
        """Reset usage statistics"""
        self.usage_stats = {
            'total_requests': 0,
            'total_input_tokens': 0,
            'total_output_tokens': 0,
            'estimated_cost': 0.0,
        }
    
    @staticmethod
    def _get_extraction_system_prompt() -> str:
        """Get system prompt for term extraction"""
        return """You are an expert terminology extraction system specialized in identifying key terms, concepts, and domain-specific vocabulary from various texts. Your goal is to provide a comprehensive list suitable for creating glossaries or termbases.

Analyze the provided text carefully and extract terms with the following details:
1. term: The term/phrase exactly as appears or its base form
2. translation: The translation in target language (null if monolingual or not found)
3. domain: Primary domain (Medical, Technology, Legal, Education, etc.)
4. subdomain: More specific subdomain if identifiable (null if not applicable)
5. pos: Part of speech (NOUN, VERB, ADJ, PHRASE, etc.)
6. definition: Concise definition/explanation
7. context: Representative snippet from the text
8. relevance_score: 0-100 assessment of term importance to the text
9. confidence_score: 0-100 confidence in the extraction
10. frequency: How many times the term appears
11. is_compound: Boolean if term is a compound word
12. is_abbreviation: Boolean if term is an abbreviation/acronym
13. variants: List of morphological/spelling variations found
14. related_terms: List of semantically related terms found

Return ONLY valid JSON (no markdown, no preamble):
{
  "terms": [
    {
      "term": "string",
      "translation": "string or null",
      "domain": "string",
      "subdomain": "string or null",
      "pos": "string",
      "definition": "string",
      "context": "string",
      "relevance_score": number,
      "confidence_score": number,
      "frequency": number,
      "is_compound": boolean,
      "is_abbreviation": boolean,
      "variants": ["string"],
      "related_terms": ["string"]
    }
  ],
  "domain_hierarchy": ["string"],
  "statistics": {
    "total_terms": number,
    "high_relevance": number,
    "medium_relevance": number,
    "low_relevance": number
  }
}"""
    
    @staticmethod
    def _get_extraction_user_prompt(
        text: str,
        source_lang: str,
        target_lang: Optional[str] = None,
        domain_path: Optional[str] = None,
        context: Optional[str] = None,
    ) -> str:
        """Build user prompt for extraction"""
        parts = [
            f"Extract key terms, concepts, entities, and specialized vocabulary from the following text.",
            f"Source Language: {source_lang}",
        ]
        
        if target_lang:
            parts.append(f"Target Language: {target_lang}")
        else:
            parts.append("Target Language: None (monolingual extraction)")
        
        if domain_path:
            parts.append(f"Domain Hint: {domain_path}")
        else:
            parts.append("Domain Hint: None provided (determine from text)")
        
        if context:
            parts.append(f"Additional Context: {context}")
        
        parts.append(f"\nTEXT TO ANALYZE:\n{text}")
        
        return "\n".join(parts)
