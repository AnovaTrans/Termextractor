"""Chunk extraction must run concurrently, aggregate every chunk, and survive a
single chunk failing. This is what turns a many-minute sequential run (which the
host timed out) into one that finishes.
Run with: python -m pytest tests/test_parallel_extraction.py
"""
import sys, types, json, tempfile, os, threading, time, itertools

# --- concurrency spy installed as a fake anthropic module ---------------------
_active = 0
_max_active = 0
_calls = 0
_lock = threading.Lock()
_counter = itertools.count()
_fail_on = {"text": None}


def _reset():
    global _active, _max_active, _calls
    _active = _max_active = _calls = 0


def _install_fake_anthropic():
    class Usage:
        input_tokens = 10
        output_tokens = 5

    class Msg:
        def __init__(self, text):
            self.content = [types.SimpleNamespace(type="text", text=text)]
            self.usage = Usage()

    class Messages:
        def create(self, **kw):
            global _active, _max_active, _calls
            user_text = kw["messages"][0]["content"]
            if _fail_on["text"] and _fail_on["text"] in user_text:
                raise RuntimeError("simulated chunk failure")
            with _lock:
                _active += 1
                _max_active = max(_max_active, _active)
                _calls += 1
                term_id = next(_counter)
            time.sleep(0.05)          # long enough for overlap to show
            with _lock:
                _active -= 1
            payload = {"terms": [{"term": f"term{term_id}", "relevance_score": 90}],
                       "domain_hierarchy": ["General"]}
            return Msg(json.dumps(payload))

    class Anthropic:
        def __init__(self, api_key=None):
            self.messages = Messages()

    for name in list(sys.modules):
        if name == "anthropic" or name.startswith("src"):
            del sys.modules[name]
    module = types.ModuleType("anthropic")
    module.Anthropic = Anthropic
    sys.modules["anthropic"] = module


def _run(num_segments=400, fail_text=None):
    _reset()
    _fail_on["text"] = fail_text
    _install_fake_anthropic()
    from src.extraction import TermExtractor
    os.environ["ANTHROPIC_API_KEY"] = "k"
    # Many short segments -> several 2000-char chunks.
    text = "\n\n".join(f"segment number {i} alpha beta" for i in range(num_segments))
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(text)
        path = f.name
    try:
        return TermExtractor(api_key="k").extract(file_path=path, source_lang="en",
                                                  relevance_threshold=0)
    finally:
        os.unlink(path)


def test_calls_actually_overlap():
    result = _run()
    assert _calls > 1, "expected multiple chunks"
    assert _max_active >= 2, f"calls did not overlap (max concurrent={_max_active})"


def test_every_chunk_is_aggregated():
    result = _run()
    # one unique term per chunk call, all collected
    assert len(result.terms) == _calls


def test_a_single_failing_chunk_does_not_sink_the_run():
    result = _run(fail_text="segment number 0 ")   # kills exactly the chunk holding seg 0
    # the run still completes and returns the terms from every other chunk
    assert len(result.terms) >= _calls - 1
    assert result.terms, "a single failed chunk wiped out the whole result"
