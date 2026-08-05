"""The model dropdown and the raised token ceiling must actually reach the API.

We spy on messages.create and assert the model id and max_tokens it receives.
Run with: python -m pytest tests/test_model_selection.py
"""
import sys, types, json, tempfile, os

CALLS = []


def _install_fake_anthropic():
    payload = {"terms": [{"term": "x", "relevance_score": 90}], "domain_hierarchy": ["General"]}

    class Usage:
        input_tokens = 10
        output_tokens = 5

    class Msg:
        def __init__(self):
            self.content = [types.SimpleNamespace(type="text", text=json.dumps(payload))]
            self.usage = Usage()

    class Messages:
        def create(self, **kw):
            CALLS.append(kw)
            return Msg()

    class Anthropic:
        def __init__(self, api_key=None):
            self.messages = Messages()

    for name in list(sys.modules):
        if name == "anthropic" or name.startswith("src"):
            del sys.modules[name]
    module = types.ModuleType("anthropic")
    module.Anthropic = Anthropic
    sys.modules["anthropic"] = module


def _run(model):
    CALLS.clear()
    _install_fake_anthropic()
    from src.extraction import TermExtractor
    os.environ["ANTHROPIC_API_KEY"] = "test-key"
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("Some text to extract terms from.")
        path = f.name
    try:
        TermExtractor(api_key="test-key").extract(file_path=path, source_lang="en",
                                                  relevance_threshold=0, model=model)
    finally:
        os.unlink(path)
    assert CALLS, "the API was never called"
    return CALLS[0]


def test_selected_model_reaches_the_api():
    call = _run("claude-opus-4-8")
    assert call["model"] == "claude-opus-4-8"


def test_default_falls_back_to_configured_extraction_model():
    call = _run(None)
    assert call["model"] == "claude-haiku-4-5"   # from config.yaml model_selection


def test_max_tokens_is_raised_above_the_old_4096():
    call = _run("claude-haiku-4-5")
    assert call["max_tokens"] >= 8192


def test_available_models_are_current_ids():
    _install_fake_anthropic()
    from src.utils import AVAILABLE_MODELS, DEFAULT_MODEL
    assert DEFAULT_MODEL in AVAILABLE_MODELS
    assert "claude-haiku-4-5" in AVAILABLE_MODELS
    assert "claude-sonnet-5" in AVAILABLE_MODELS
    assert "claude-opus-4-8" in AVAILABLE_MODELS
    # no dated snapshot for the current aliases
    assert not any(mid.startswith("claude-opus-4-8-2") for mid in AVAILABLE_MODELS)
