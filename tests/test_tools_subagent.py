import json

from gptme.tools.subagent import _extract_json


def test_extract_json_block():
    s = """
Here is a result:
```json
{ "status": "ok" }
```
"""
    assert _extract_json(s) == '{ "status": "ok" }'


def test_extract_json_raw():
    s = """
{
  "result": "The 49th Fibonacci number is 7778742049.",
  "status": "success"
}
"""
    assert json.loads(_extract_json(s)) == json.loads(s)


def test_extract_json_empty():
    s = ""
    assert _extract_json(s) == ""
