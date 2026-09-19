"""Tests for the transcript reader of scripts/measure.py (no Claude call; synthetic .jsonl fixtures).

python -m pytest -q tests
"""

import io, json, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
from measure import parse_transcript  # noqa: E402  (import has no side effects: setup() runs only under __main__)


def write(tmp_path, lines):
    p = tmp_path / "t.jsonl"
    io.open(p, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    return str(p)


ATT = json.dumps(
    {
        "type": "attachment",
        "attachment": {"type": "deferred_tools_delta", "tools": ["mcp__a__x", "mcp__a__y", "mcp__b__z"]},
    }
)
USAGE = json.dumps(
    {
        "version": "2.1.266",
        "message": {
            "role": "assistant",
            "usage": {"input_tokens": 2, "cache_creation_input_tokens": 100, "cache_read_input_tokens": 50},
        },
    }
)


def test_reads_first_assistant_usage_and_mcp_names(tmp_path):
    t = parse_transcript(write(tmp_path, [ATT, USAGE, USAGE.replace("100", "999")]))
    assert t["usage"] == {
        "input_tokens": 2,
        "cache_creation_input_tokens": 100,
        "cache_read_input_tokens": 50,
    }  # first turn only
    assert t["version"] == "2.1.266"
    assert t["mcp_names"] == {"mcp__a__x", "mcp__a__y", "mcp__b__z"}
    assert t["attachment_chars"] == {
        "deferred_tools_delta": len(json.dumps(json.loads(ATT)["attachment"], ensure_ascii=False))
    }
    assert t["bad_lines"] == 0


def test_broken_line_is_counted_not_skipped(tmp_path):
    t = parse_transcript(write(tmp_path, [ATT, '{"type": "attachment", "attachment": {"type": "skill_listing"', USAGE]))
    assert t["bad_lines"] == 1
    assert t["usage"] is not None  # the rest is still read; the caller decides to fail


def test_no_usage_gives_none(tmp_path):
    t = parse_transcript(write(tmp_path, [ATT]))
    assert t["usage"] is None and t["bad_lines"] == 0


def test_blank_lines_are_not_errors(tmp_path):
    t = parse_transcript(write(tmp_path, ["", ATT, "", USAGE]))
    assert t["bad_lines"] == 0 and t["usage"]["cache_read_input_tokens"] == 50
