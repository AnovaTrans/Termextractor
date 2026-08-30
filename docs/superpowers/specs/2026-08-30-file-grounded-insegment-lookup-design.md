# File-grounded in-segment term translation + TMX reference

**Date:** 2026-08-30
**Status:** Approved (brainstorming)

## Problem

When Bilingual Lookup is on and the reference file is bilingual, a term that
appears **inside** sentences (not as its own segment) is not found by the
exact-segment index. It falls to the fuzzy path, whose AI refinement can
**invent** a translation that contradicts the file — e.g. the file's target
uses `şoför` for "driver" (17×), but the glossary shows `sürücü`.

Requirement: *if the term appears in the bilingual file, take its translation
from the file's existing target — not from a free AI translation.*

## Design

### New lookup tier

In `TermExtractor._enrich_with_bilingual_lookup`, insert a tier between the
existing EXACT and FUZZY paths:

1. **EXACT_MATCH** (unchanged) — term equals a whole source segment → use its target.
2. **FILE_INSEGMENT** (new) — term is not a standalone segment but occurs as a
   whole word in ≥1 source segment → collect up to **K=5** `(source, target)`
   pairs containing it → **one AI call** extracts the term's target rendering,
   in **base/dictionary form** (`şoför`, not `şoförün`), consistent across the
   examples → use it. `translation_source = "FILE_INSEGMENT"`,
   `from_existing_translation = True`.
3. **FUZZY_REFERENCE / API** (unchanged) — only if the term occurs nowhere in
   the file's source → free translation (fallback).

The AI call is **grounded**: the prompt gives the model the file's own target
segments and forbids inventing — "return only the target word/phrase as it
appears; base form; null if not clearly present." So it reads `şoför` out of
the file rather than translating "driver" afresh.

Consistency across the whole glossary is already handled by the existing
`_consolidate_by_source_term` (one translation per source term).

### TMX as a reference format

The lookup operates on `(source, target)` pairs, independent of the file
format. Add TMX alongside XLIFF/SDLXLIFF/MQXLIFF:

- `bilingual_file_handler.py`: accept `.tmx` in `is_bilingual_format`; detect
  `<tmx` in `detect_format`; add `_extract_from_tmx`.
- **TMX language matching:** TMX tags each `<tuv>` by `xml:lang` and a `<tu>`
  may hold >2 languages. Pick source = the tuv matching the header `srclang`
  (or the run's source language); target = the tuv matching the run's target
  language; fallback when neither resolves: first tuv = source, second = target.
- `pages/extraction.py` + `config.yaml`: add `tmx` to the bilingual uploader
  and `translation_lookup.supported_formats`.

## Components

| File | Change |
|---|---|
| `translation_lookup.py` | `find_containing_segments(term, k)` → up to K `(source,target)` pairs whose source contains the term as a whole word (case-insensitive). Needs the raw pairs, not just the whole-segment exact index. |
| `anthropic_client.py` | `extract_term_translation_from_segments(term, source_lang, target_lang, pairs)` → one grounded call; strict JSON `{ "translation": "<base form>" | null }`; `_response_text`-parsed. |
| `term_extractor.py` | New FILE_INSEGMENT tier in `_enrich_with_bilingual_lookup`; new stat `insegment_matches_found`; wire the containing-segment search + extraction; keep fuzzy/API fallback. |
| `bilingual_file_handler.py` | `_extract_from_tmx` + `.tmx` detection; expose the raw `(source,target)` pairs for the containing-segment search. |
| `pages/extraction.py`, `config.yaml` | `tmx` in uploader + supported_formats. |

## Error handling

- Extraction returns `null` / raises → fall back to the existing fuzzy/API path;
  never block the run. Client already retries.
- No containing segments → not a FILE_INSEGMENT case; fuzzy/API as today.

## Testing

- **Offline unit:** `find_containing_segments` (whole-word, case-insensitive,
  caps at K); `_extract_from_tmx` on a small TMX (language matching, fallback).
- **Offline with a mocked client:** the FILE_INSEGMENT tier calls the extractor
  and sets `translation_source=FILE_INSEGMENT` when the mock returns a value,
  falls back when it returns null.
- **End-to-end (needs API key, user-run):** the real XLIFF yields
  `driver → şoför` from the file.

## Cost

One extra small Haiku call per in-sentence, non-exact term. Tiny inputs/outputs;
well under a cent per run. Batching multiple terms per call is a possible future
optimization — not now (YAGNI).
