from src.core.llm_client import _extract_json


def test_extract_json_from_code_block():
    text = '```json\n{"key": "value"}\n```'
    assert _extract_json(text) == '{"key": "value"}'


def test_extract_json_plain():
    text = '{"key": "value"}'
    assert _extract_json(text) == '{"key": "value"}'


def test_extract_json_with_trailing_comma():
    text = '{"items": ["a", "b",]}'
    result = _extract_json(text)
    assert '"a"' in result


def test_extract_json_with_markdown_wrapper():
    text = 'Here is the result:\n```\n{"foo": 1}\n```\nDone.'
    assert _extract_json(text) == '{"foo": 1}'
