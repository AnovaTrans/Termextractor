"""Regression tests for parse_model_json.

The bug these lock down: term extraction returned zero terms with no error
whenever the model wrapped its JSON in a ```json fence or a sentence of
preamble — json.loads() raised and the exception was swallowed per chunk.
Run with: python -m pytest tests/test_model_json.py
"""
import json

from src.utils import parse_model_json

PAYLOAD = {"terms": [{"term": "photosynthesis", "relevance_score": 95}],
           "domain_hierarchy": ["Biology"]}
RAW = json.dumps(PAYLOAD)


def test_bare_json():
    assert parse_model_json(RAW) == PAYLOAD


def test_json_fence():
    assert parse_model_json("```json\n" + RAW + "\n```") == PAYLOAD


def test_bare_fence_without_language():
    assert parse_model_json("```\n" + RAW + "\n```") == PAYLOAD


def test_preamble_before_json():
    assert parse_model_json("Here are the terms:\n\n" + RAW) == PAYLOAD


def test_trailing_prose_after_json():
    assert parse_model_json(RAW + "\n\nHope that helps!") == PAYLOAD


def test_braces_inside_string_values_do_not_break_balance():
    obj = {"note": "use {curly} and [square] brackets", "n": 1}
    assert parse_model_json("prefix " + json.dumps(obj) + " suffix") == obj


def test_top_level_array():
    assert parse_model_json("```json\n[1, 2, 3]\n```") == [1, 2, 3]


def test_no_json_returns_default():
    assert parse_model_json("I could not help with that.", default=None) is None
    assert parse_model_json("", default={"x": 1}) == {"x": 1}
    assert parse_model_json(None, default={}) == {}


def test_fence_is_preferred_over_stray_braces_in_prose():
    text = "I think {maybe} this:\n```json\n" + RAW + "\n```"
    assert parse_model_json(text) == PAYLOAD
