"""The discard-and-re-run branch of measure.measured(): a run whose MCP tool-name count is not the expected one
is recorded in `discarded` and the condition is run again (max 3). Not exercised by the two real E2E runs (0 discards),
so it is exercised here with a stubbed run()."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import measure  # noqa: E402


def fake_runs(counts):
    it = iter(counts)

    def run(label, extra=()):
        n = next(it)
        return {
            "label": label,
            "total": 70000 + n,
            "mcp_tool_names": n,
            "input_tokens": 2,
            "cache_creation_input_tokens": 1,
            "cache_read_input_tokens": 1,
        }

    return run


def test_incomplete_run_is_discarded_and_rerun(monkeypatch):
    monkeypatch.setattr(measure, "run", fake_runs([221, 266]))
    measure.discarded.clear()
    r = measure.measured("A2 baseline", (), 266)
    assert r["mcp_tool_names"] == 266 and r["attempt"] == 2 and r["valid"] is True
    assert (
        len(measure.discarded) == 1
        and measure.discarded[0]["mcp_tool_names"] == 221
        and measure.discarded[0]["valid"] is False
    )


def test_three_incomplete_runs_fail_closed(monkeypatch):
    monkeypatch.setattr(measure, "run", fake_runs([221, 200, 100]))
    measure.discarded.clear()
    with pytest.raises(SystemExit):
        measure.measured("A3 baseline", (), 266)
    assert len(measure.discarded) == 3


def test_expected_zero_for_no_mcp(monkeypatch):
    monkeypatch.setattr(measure, "run", fake_runs([0]))
    measure.discarded.clear()
    assert measure.measured("C no MCP servers", (), 0)["attempt"] == 1
