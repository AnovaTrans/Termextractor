"""The XLIFF parser must return only translation segments, not memoQ metadata.

Regression for the real-file hang: a memoQ mqxliff carries a serialized LQA
model, tag definitions and commit history as text nodes. The old parser dumped
all of it, exploding the chunk count until the host timed the run out.
Run with: python -m pytest tests/test_xliff_parser.py
"""
import tempfile
from pathlib import Path

from src.io import FileParser

MQXLIFF = """\
<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2" xmlns:mq="MQXliff">
<file source-language="en-us" target-language="bg" datatype="x-memoq">
<header>
<mq:docinformation><mq:tagdefinition><XMLSerializedLQAModel>
<Name>SHOULD_NOT_APPEAR</Name><UseSeverityLevels>false</UseSeverityLevels>
</XMLSerializedLQAModel></mq:tagdefinition></mq:docinformation>
</header>
<body>
<trans-unit id="1"><source>River West OPEN</source><target>Ривър Уест</target>
<mq:commitinfo>COMMIT_NOISE</mq:commitinfo></trans-unit>
<trans-unit id="2"><source>Retail Sector</source><target></target></trans-unit>
<trans-unit id="3"><source>Control <g id="1">Panels</g></source><target></target></trans-unit>
</body>
</file>
</xliff>
"""


def _parse(text, suffix=".mqxliff"):
    with tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, encoding="utf-8") as f:
        f.write(text)
        path = f.name
    try:
        return FileParser().parse(path)
    finally:
        Path(path).unlink()


def test_only_source_segments_are_extracted():
    result = _parse(MQXLIFF)
    text = result["text"]
    assert text == "River West OPEN\n\nRetail Sector\n\nControl Panels"


def test_memoq_metadata_is_excluded():
    text = _parse(MQXLIFF)["text"]
    assert "SHOULD_NOT_APPEAR" not in text
    assert "XMLSerializedLQAModel" not in text
    assert "COMMIT_NOISE" not in text
    assert "false" not in text


def test_inline_tags_are_flattened_to_their_text():
    # <g id="1">Panels</g> inside a source becomes "Control Panels".
    text = _parse(MQXLIFF)["text"]
    assert "Control Panels" in text
    assert "<g" not in text


def test_segments_are_blank_line_separated_so_the_chunker_can_split():
    text = _parse(MQXLIFF)["text"]
    assert text.count("\n\n") == 2          # three segments, two separators


def test_metadata_reports_segment_count_and_bilingual():
    meta = _parse(MQXLIFF)["metadata"]
    assert meta["segment_count"] == 3
    assert meta["is_bilingual"] is True     # segment 1 has a target


def test_generic_xml_still_falls_back_to_all_text():
    result = _parse("<root><a>hello</a><b>world</b></root>", suffix=".xml")
    assert "hello" in result["text"] and "world" in result["text"]
