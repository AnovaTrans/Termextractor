"""
Bilingual file handler for TermExtractor-Pro
Supports: XLIFF, SDLXLIFF, MQXLIFF, TMX formats
"""

import xml.etree.ElementTree as ET
import re
from typing import Dict, List, Tuple, Optional
from pathlib import Path


class BilingualFileHandler:
    """Handle bilingual file parsing and extraction"""
    
    XLIFF_NAMESPACES = {
        'xliff_1_2': 'urn:oasis:names:tc:xliff:document:1.2',
        'xliff_2_0': 'urn:oasis:names:tc:xliff:document:2.0',
        'xliff_2_1': 'urn:oasis:names:tc:xliff:document:2.1',
    }
    
    def __init__(self):
        """Initialize handler"""
        self.file_format = None
        self.source_lang = None
        self.target_lang = None
    
    def is_bilingual_format(self, file_path: str) -> bool:
        """
        Check if file is a bilingual format.
        
        Args:
            file_path: Path to file
            
        Returns:
            True if bilingual format
        """
        ext = Path(file_path).suffix.lower()
        return ext in ['.xliff', '.sdlxliff', '.mqxliff', '.xml', '.tmx']
    
    @staticmethod
    def _to_text(file_content: bytes) -> str:
        """Decode bytes to text, handling UTF-16 (MemoQ exports TMX as UTF-16).

        Plain utf-8 decoding of UTF-16 bytes leaves NUL characters between every
        letter, so a substring search like '<tmx' silently fails and the file is
        misrouted. Detect UTF-16 by BOM, else by a high NUL density in the head.
        """
        if file_content[:2] in (b'\xff\xfe', b'\xfe\xff'):
            return file_content.decode('utf-16', errors='ignore')
        if file_content[:2000].count(0) > 100:  # BOM-less UTF-16
            try:
                return file_content.decode('utf-16')
            except Exception:
                return file_content.decode('utf-16-le', errors='ignore')
        return file_content.decode('utf-8-sig', errors='ignore')

    def detect_format(self, file_content: bytes) -> str:
        """
        Detect bilingual file format.

        Args:
            file_content: File content as bytes

        Returns:
            Format type: 'xliff', 'sdlxliff', 'mqxliff', or 'unknown'
        """
        content_str = self._to_text(file_content)

        if '<tmx' in content_str:
            return 'tmx'
        elif 'sdl:' in content_str or 'http://sdl.com' in content_str:
            return 'sdlxliff'
        elif 'mq:' in content_str or 'MemoQ' in content_str:
            return 'mqxliff'
        elif '<xliff' in content_str:
            return 'xliff'

        return 'unknown'
    
    def detect_languages(self, file_content: bytes) -> Tuple[Optional[str], Optional[str]]:
        """
        Detect source and target languages from file.
        
        Args:
            file_content: File content as bytes
            
        Returns:
            Tuple of (source_lang, target_lang)
        """
        try:
            root = ET.fromstring(file_content)
            
            # Try to find language attributes
            for elem in root.iter():
                for attr_name, attr_value in elem.attrib.items():
                    attr_lower = attr_name.lower()
                    
                    if 'source' in attr_lower and 'lang' in attr_lower:
                        self.source_lang = self._normalize_lang(attr_value)
                    
                    if 'target' in attr_lower and 'lang' in attr_lower:
                        self.target_lang = self._normalize_lang(attr_value)
                
                if self.source_lang and self.target_lang:
                    break
        
        except:
            pass
        
        return self.source_lang, self.target_lang
    
    def extract_translation_pairs(self, file_content: bytes) -> Dict[str, str]:
        """
        Extract source-target translation pairs from bilingual file.
        
        Args:
            file_content: File content as bytes
            
        Returns:
            Dictionary of {source_term: target_term}
        """
        pairs = {}
        
        # Detect format
        fmt = self.detect_format(file_content)
        self.file_format = fmt
        
        # Detect languages
        self.detect_languages(file_content)
        
        # Parse based on format
        if fmt == 'tmx':
            pairs = self._extract_from_tmx(file_content)
        elif fmt == 'sdlxliff':
            pairs = self._extract_from_sdlxliff(file_content)
        elif fmt == 'mqxliff':
            pairs = self._extract_from_mqxliff(file_content)
        elif fmt == 'xliff' or fmt == 'unknown':
            pairs = self._extract_from_xliff(file_content)

        return pairs

    def _extract_from_tmx(self, file_content: bytes) -> Dict[str, str]:
        """Extract source->target pairs from a TMX translation memory.

        TMX tags each <tuv> by xml:lang and a <tu> may hold more than two
        languages. Source = the tuv matching the header `srclang` (fallback:
        first tuv); target = the tuv matching the already-detected target
        language, else the first tuv that isn't the source (fallback: second
        tuv). Good for the common 2-language TM; multi-language TMs use the
        fallback for the target side.
        """
        pairs: Dict[str, str] = {}
        XML_LANG = '{http://www.w3.org/XML/1998/namespace}lang'

        try:
            root = ET.fromstring(file_content)
        except Exception:
            return pairs

        def localname(tag: str) -> str:
            return tag.rsplit('}', 1)[-1]

        def lang_of(tuv) -> str:
            return tuv.attrib.get(XML_LANG) or tuv.attrib.get('lang') or ''

        def seg_text(tuv) -> str:
            for ch in tuv.iter():
                if localname(ch.tag) == 'seg':
                    return ''.join(ch.itertext()).strip()
            return ''

        # Source language from the header's srclang (unless it's "*all*").
        srclang = None
        for el in root.iter():
            if localname(el.tag) == 'header':
                srclang = el.attrib.get('srclang')
                break
        src_norm = (self._normalize_lang(srclang)
                    if srclang and srclang.lower() != '*all*' else None)
        tgt_norm = self.target_lang  # from detect_languages (often None for TMX)

        last_target_lang = None
        for tu in root.iter():
            if localname(tu.tag) != 'tu':
                continue
            tuvs = [c for c in tu if localname(c.tag) == 'tuv']
            if len(tuvs) < 2:
                continue

            source_tuv = target_tuv = None
            for tv in tuvs:
                l = self._normalize_lang(lang_of(tv))
                if src_norm and l == src_norm and source_tuv is None:
                    source_tuv = tv
                elif tgt_norm and l == tgt_norm and target_tuv is None:
                    target_tuv = tv
            if source_tuv is None:
                source_tuv = tuvs[0]
            if target_tuv is None:
                target_tuv = next((tv for tv in tuvs if tv is not source_tuv), None)
            if target_tuv is None:
                continue

            s, t = seg_text(source_tuv), seg_text(target_tuv)
            if s and t:
                pairs[s] = t
                last_target_lang = self._normalize_lang(lang_of(target_tuv))

        # Record detected languages so the run's metadata is populated.
        if src_norm and not self.source_lang:
            self.source_lang = src_norm
        if not self.target_lang and last_target_lang:
            self.target_lang = last_target_lang

        return pairs
    
    def _extract_from_xliff(self, file_content: bytes) -> Dict[str, str]:
        """Extract pairs from standard XLIFF format"""
        pairs = {}
        
        try:
            root = ET.fromstring(file_content)
            
            # Register namespaces
            for prefix, uri in self.XLIFF_NAMESPACES.items():
                ET.register_namespace(prefix.split('_')[0], uri)
            
            # Find all trans-unit elements
            for ns in [self.XLIFF_NAMESPACES['xliff_1_2'], None]:
                if ns:
                    trans_units = root.findall(f'{{{ns}}}file/{{{ns}}}body/{{{ns}}}trans-unit')
                    if not trans_units:
                        trans_units = root.findall(f'.//{{{ns}}}trans-unit')
                else:
                    trans_units = root.findall('.//trans-unit')
                
                if trans_units:
                    break
            
            # Extract source-target pairs
            for unit in trans_units:
                source_elem = unit.find(f'{{{self.XLIFF_NAMESPACES["xliff_1_2"]}}}source')
                target_elem = unit.find(f'{{{self.XLIFF_NAMESPACES["xliff_1_2"]}}}target')
                
                if source_elem is None:
                    source_elem = unit.find('source')
                if target_elem is None:
                    target_elem = unit.find('target')
                
                if source_elem is not None and target_elem is not None:
                    source_text = self._extract_text_from_element(source_elem)
                    target_text = self._extract_text_from_element(target_elem)
                    
                    if source_text and target_text:
                        pairs[source_text] = target_text
        
        except Exception as e:
            print(f"Error parsing XLIFF: {e}")
        
        return pairs
    
    def _extract_from_sdlxliff(self, file_content: bytes) -> Dict[str, str]:
        """Extract pairs from SDLXLIFF format"""
        pairs = {}
        
        try:
            root = ET.fromstring(file_content)
            
            # Find all trans-unit elements
            for unit in root.findall('.//trans-unit'):
                source_elem = unit.find('source')
                target_elem = unit.find('target')
                
                if source_elem is not None and target_elem is not None:
                    # For SDLXLIFF, extract text from mrk elements
                    source_text = self._extract_text_from_sdl_element(source_elem)
                    target_text = self._extract_text_from_sdl_element(target_elem)
                    
                    if source_text and target_text:
                        pairs[source_text] = target_text
        
        except Exception as e:
            print(f"Error parsing SDLXLIFF: {e}")
        
        return pairs
    
    def _extract_from_mqxliff(self, file_content: bytes) -> Dict[str, str]:
        """Extract pairs from MQXLIFF (MemoQ) format"""
        pairs = {}
        
        try:
            root = ET.fromstring(file_content)
            
            # Find all trans-unit elements
            for unit in root.findall('.//trans-unit'):
                source_elem = unit.find('source')
                target_elem = unit.find('target')
                
                if source_elem is not None and target_elem is not None:
                    # For MQXLIFF, extract text from mq:seg elements
                    source_text = self._extract_text_from_memoq_element(source_elem)
                    target_text = self._extract_text_from_memoq_element(target_elem)
                    
                    if source_text and target_text:
                        pairs[source_text] = target_text
        
        except Exception as e:
            print(f"Error parsing MQXLIFF: {e}")
        
        return pairs
    
    @staticmethod
    def _extract_text_from_element(elem) -> str:
        """Extract text from XML element (including child text)"""
        if elem is None:
            return ""
        
        text_parts = []
        if elem.text:
            text_parts.append(elem.text)
        
        for child in elem:
            if child.tail:
                text_parts.append(child.tail)
        
        return ''.join(text_parts).strip()
    
    @staticmethod
    def _extract_text_from_sdl_element(elem) -> str:
        """Extract text from SDL element (handle mrk tags)"""
        if elem is None:
            return ""
        
        text_parts = []
        
        # Find mrk elements (SDL specific)
        for mrk in elem.findall('.//mrk'):
            if mrk.text:
                text_parts.append(mrk.text)
            if mrk.tail:
                text_parts.append(mrk.tail)
        
        # If no mrk found, get all text
        if not text_parts:
            text_parts = [BilingualFileHandler._extract_text_from_element(elem)]
        
        return ''.join(text_parts).strip()
    
    @staticmethod
    def _extract_text_from_memoq_element(elem) -> str:
        """Extract text from MemoQ element (handle mq:seg tags)"""
        if elem is None:
            return ""
        
        text_parts = []
        
        # Find mq:seg elements (MemoQ specific)
        for seg in elem.findall('.//{http://www.memoq.com}seg'):
            if seg.text:
                text_parts.append(seg.text)
            if seg.tail:
                text_parts.append(seg.tail)
        
        # Fallback: try without namespace
        if not text_parts:
            for seg in elem.findall('.//seg'):
                if seg.text:
                    text_parts.append(seg.text)
                if seg.tail:
                    text_parts.append(seg.tail)
        
        # If still nothing, get all text
        if not text_parts:
            text_parts = [BilingualFileHandler._extract_text_from_element(elem)]
        
        return ''.join(text_parts).strip()
    
    @staticmethod
    def _normalize_lang(lang_code: str) -> str:
        """Normalize language code to 2-letter format"""
        if not lang_code:
            return None
        
        code = lang_code.lower().strip()
        
        # Already 2-letter
        if len(code) == 2:
            return code
        
        # Language-Country format
        if '-' in code:
            return code.split('-')[0]
        
        # 3-letter code
        if len(code) == 3:
            return code[:2]
        
        return code[:2]
