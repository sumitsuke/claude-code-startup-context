#!/usr/bin/env python3
"""measure.py — decompose Claude Code's startup input by remove-and-restore.

Runs `claude -p "<fixed prompt>"` seven times in one working directory and records the
first-turn usage (total input = input + cache_creation + cache_read) of each run:

  A1 baseline -> B (auto memory index reduced to 1 line) -> A2 baseline
     -> C (no MCP servers) -> A3 baseline -> D (B and C at once) -> A4 baseline

Nothing of yours is modified:
  * B/D point *that run only* at a temporary auto-memory directory holding a 1-line
    MEMORY.md, via `--settings '{"autoMemoryDirectory": "<tmp>"}'` (official setting).
    Your real MEMORY.md is never read for writing, copied, or touched.
  * C/D pass `--strict-mcp-config --mcp-config <tmp>/mcp_empty.json` (`{"mcpServers": {}}`),
    i.e. "use only the MCP servers in this file, and this file lists none".
  * Every run gets its own `--session-id <uuid>`; the tool reads exactly that transcript,
    fails closed if the CLI exits non-zero, the transcript is missing, or no usage is found.
  * A run whose MCP tool-name count is not the expected one (the first turn went out before
    every MCP server had announced its tools) is recorded as discarded and re-run (max 3).

Environment:
  N3_PROJ   transcript directory of the project you measure  (~/.claude/projects/<project-dir>)
  N3_CWD    working directory to launch `claude` in           (default: current directory)
  N3_MODEL  model id                                          (default: claude-opus-5)

Output: results/measure_<date>_<time>.json (canonical) and .md (rendered from the JSON).
Cost: 7 CLI calls. Depending on how you authenticate, this consumes plan usage or API billing.
"""

import datetime, io, json, os, re, shutil, subprocess, sys, tempfile, time, uuid

sys.stdout.reconfigure(encoding="utf-8")
PROMPT = "1+1 を数字だけで答えて"  # fixed for every run; the number in a reply is irrelevant
MCP_NAME = re.compile(r"mcp__[A-Za-z0-9_-]+")
discarded = []


def setup():
    """Read the environment and create the temporary settings/MCP files. Module import has no side effects (tests import parse_transcript)."""
    global \
        PROJ, \
        CWD, \
        MODEL, \
        CLAUDE, \
        HERE, \
        OUT_DIR, \
        STAMP, \
        TMP, \
        MEM_DIR, \
        SETTINGS_MIN_MEMORY, \
        MCP_EMPTY, \
        FLAG_MIN_MEMORY, \
        FLAG_NO_MCP
    PROJ = os.environ.get("N3_PROJ", "")
    if not PROJ or not os.path.isdir(PROJ):
        sys.exit("N3_PROJ must point to the transcript directory (~/.claude/projects/<project-dir>)")
    CWD = os.environ.get("N3_CWD", os.getcwd())
    MODEL = os.environ.get("N3_MODEL", "claude-opus-5")
    CLAUDE = shutil.which("claude") or shutil.which("claude.cmd")
    if not CLAUDE:
        sys.exit("claude CLI not found in PATH")
    HERE = os.path.dirname(os.path.abspath(__file__))
    OUT_DIR = os.path.join(os.path.dirname(HERE), "results")
    os.makedirs(OUT_DIR, exist_ok=True)
    STAMP = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")

    TMP = tempfile.mkdtemp(prefix="claude_startup_measure_")
    MEM_DIR = os.path.join(TMP, "memory_min")
    os.makedirs(MEM_DIR)
    io.open(os.path.join(MEM_DIR, "MEMORY.md"), "w", encoding="utf-8", newline="\n").write("# Memory Index\n")
    SETTINGS_MIN_MEMORY = os.path.join(TMP, "settings_min_memory.json")
    io.open(SETTINGS_MIN_MEMORY, "w", encoding="utf-8").write(
        json.dumps({"autoMemoryDirectory": MEM_DIR.replace("\\", "/")})
    )
    MCP_EMPTY = os.path.join(TMP, "mcp_empty.json")
    io.open(MCP_EMPTY, "w", encoding="utf-8").write(json.dumps({"mcpServers": {}}))

    FLAG_MIN_MEMORY = ("--settings", SETTINGS_MIN_MEMORY)
    FLAG_NO_MCP = ("--strict-mcp-config", "--mcp-config", MCP_EMPTY)


def parse_transcript(path):
    """Read one transcript (.jsonl) up to the first assistant turn.
    Returns usage (3 fields), CLI version, attachment sizes (chars of JSON per type), the set of MCP tool names,
    and bad_lines = lines that are not JSON. A line that fails to parse is counted, never skipped silently
    (a truncated or U+2028-split line would otherwise make a wrong number look like a measurement)."""
    usage = None
    version = None
    attachments = {}
    mcp_names = set()
    bad = 0
    for line in io.open(path, encoding="utf-8", errors="replace"):
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            bad += 1
            continue
        version = version or d.get("version")
        if d.get("type") == "attachment" and usage is None:
            a = d.get("attachment") or {}
            raw = json.dumps(a, ensure_ascii=False)
            attachments[a.get("type", "?")] = attachments.get(a.get("type", "?"), 0) + len(raw)
            mcp_names.update(MCP_NAME.findall(raw))
        m = d.get("message") or {}
        if usage is None and m.get("role") == "assistant" and m.get("usage"):
            u = m["usage"]
            usage = {k: u.get(k, 0) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")}
    return {
        "usage": usage,
        "version": version,
        "attachment_chars": attachments,
        "mcp_names": mcp_names,
        "bad_lines": bad,
    }


def run(label, extra=()):
    sid = str(uuid.uuid4())
    transcript = os.path.join(PROJ, sid + ".jsonl")
    cmd = [CLAUDE, "-p", PROMPT, "--model", MODEL, "--session-id", sid, "--system-prompt-snapshot", "on", *extra]
    t0 = time.time()
    r = subprocess.run(
        cmd,
        cwd=CWD,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdin=subprocess.DEVNULL,
        timeout=300,
    )
    sec = round(time.time() - t0, 1)
    if r.returncode != 0:
        sys.exit(f"FAIL {label}: claude exited {r.returncode}\n{r.stderr[-2000:]}")
    if not os.path.isfile(transcript):
        sys.exit(f"FAIL {label}: transcript {sid}.jsonl not found under N3_PROJ")
    t = parse_transcript(transcript)
    usage, version, attachments, mcp_names = t["usage"], t["version"], t["attachment_chars"], t["mcp_names"]
    if t["bad_lines"]:
        sys.exit(f"FAIL {label}: {t['bad_lines']} unparseable line(s) in {sid}.jsonl - nothing is skipped silently")
    if not usage:
        sys.exit(f"FAIL {label}: no assistant usage in {sid}.jsonl")
    total = sum(usage.values())
    print(
        f"{label}: total {total:,}  (in {usage['input_tokens']}  cache_create {usage['cache_creation_input_tokens']:,}  "
        f"cache_read {usage['cache_read_input_tokens']:,})  v{version}  {sec}s  mcp tool names {len(mcp_names)}"
    )
    return {
        "label": label,
        "session_id": sid,
        "total": total,
        **usage,
        "claude_code_version": version,
        "seconds": sec,
        "mcp_tool_names": len(mcp_names),
        "attachment_chars": attachments,
    }


# `claude -p` sometimes sends the first turn before every MCP server has announced its tools (observed: 221 of 266
# names, with the same cache_read as a complete run — so cache_read alone does not detect it). A run is valid only if
# its MCP tool-name count is what its condition expects: A1's count for A/B runs, 0 for C/D. Invalid runs are kept in
# the output as "discarded" and the condition is re-run (up to 3 attempts).


def measured(label, extra=(), expect_mcp=None):
    for attempt in range(1, 4):
        r = run(label, extra)
        r["attempt"] = attempt
        if expect_mcp is None or r["mcp_tool_names"] == expect_mcp:
            r["valid"] = True
            return r
        print(
            f"  discarded: MCP tool names {r['mcp_tool_names']} != {expect_mcp} (tool list incomplete when the first turn was sent) - re-running"
        )
        r["valid"] = False
        r["discard_reason"] = f"mcp_tool_names {r['mcp_tool_names']} != {expect_mcp}"
        discarded.append(r)
    sys.exit(f"FAIL {label}: 3 attempts, MCP tool list never complete")


def main():
    try:
        runs = [measured("A1 baseline")]
        full = runs[0]["mcp_tool_names"]
        runs.append(measured("B memory index 1 line", FLAG_MIN_MEMORY, full))
        runs.append(measured("A2 baseline", (), full))
        runs.append(measured("C no MCP servers", FLAG_NO_MCP, 0))
        runs.append(measured("A3 baseline", (), full))
        runs.append(measured("D memory 1 line + no MCP", (*FLAG_MIN_MEMORY, *FLAG_NO_MCP), 0))
        runs.append(measured("A4 baseline", (), full))
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    if any(r["mcp_tool_names"] > full for r in runs + discarded):
        sys.exit(f"FAIL: A1 saw {full} MCP tool names but a later run saw more - A1 itself was incomplete; run again")

    A1, B, A2, C, A3, D, A4 = (r["total"] for r in runs)
    summary = {
        "memory_effect_B_minus_A1": B - A1,
        "mcp_effect_C_minus_A1": C - A1,
        "both_effect_D_minus_A1": D - A1,
        "expected_additive_vs_A1": A1 + (B - A1) + (C - A1),
        "residual_vs_A1": D - (A1 + (B - A1) + (C - A1)),
        "baseline_drift_A4_minus_A1": A4 - A1,
        "expected_additive_vs_A4": A4 + (B - A1) + (C - A1),
        "residual_vs_A4": D - (A4 + (B - A1) + (C - A1)),
        "reproducibility_A2_A3_A4_minus_A1": [A2 - A1, A3 - A1, A4 - A1],
        "mcp_tool_names_full": full,
        "discarded_runs": len(discarded),
    }
    doc = {
        "tool": "claude-code-startup-context/scripts/measure.py",
        "schema": 1,
        "measured_at": datetime.datetime.now().astimezone().isoformat(timespec="minutes"),
        "claude_code_version": runs[0]["claude_code_version"],
        "model": MODEL,
        "prompt": PROMPT,
        "total_input_definition": "input_tokens + cache_creation_input_tokens + cache_read_input_tokens (first assistant turn)",
        "runs": runs,
        "discarded_runs": discarded,
        "summary": summary,
    }
    jp = os.path.join(OUT_DIR, f"measure_{STAMP}.json")
    io.open(jp, "w", encoding="utf-8", newline="\n").write(json.dumps(doc, ensure_ascii=False, indent=2) + "\n")

    s = summary
    md = [
        f"# Claude Code startup input — remove-and-restore ({doc['measured_at']}, Claude Code {doc['claude_code_version']}, {MODEL})",
        "",
        "| run | total input | vs A1 | input / cache_create / cache_read | mcp tool names | s | attempt |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in runs:
        md.append(
            f"| {r['label']} | {r['total']:,} | {r['total'] - A1:+,} | {r['input_tokens']} / {r['cache_creation_input_tokens']:,} / "
            f"{r['cache_read_input_tokens']:,} | {r['mcp_tool_names']} | {r['seconds']} | {r['attempt']} |"
        )
    for r in discarded:
        md.append(
            f"| ~~{r['label']}~~ discarded ({r['discard_reason']}) | {r['total']:,} | {r['total'] - A1:+,} | {r['input_tokens']} / {r['cache_creation_input_tokens']:,} / "
            f"{r['cache_read_input_tokens']:,} | {r['mcp_tool_names']} | {r['seconds']} | {r['attempt']} |"
        )
    md += [
        "",
        f"- memory index -> 1 line: **{s['memory_effect_B_minus_A1']:+,}**; no MCP servers: **{s['mcp_effect_C_minus_A1']:+,}**; both at once: {s['both_effect_D_minus_A1']:+,}",
        f"- additivity vs A1: expected {s['expected_additive_vs_A1']:,}, measured {D:,}, residual {s['residual_vs_A1']:+,}",
        f"- baseline drift during the series (A4 - A1): {s['baseline_drift_A4_minus_A1']:+,}  -> additivity vs A4: expected {s['expected_additive_vs_A4']:,}, residual {s['residual_vs_A4']:+,}",
        f"- reproducibility of the baseline (A2, A3, A4 vs A1): {s['reproducibility_A2_A3_A4_minus_A1']}",
        f"- validity: a run counts only if its MCP tool-name count is the expected one ({full} for A/B, 0 for C/D); {len(discarded)} run(s) discarded and re-run. cache_read is reported, not used as the test (an incomplete run can share A1's cache_read)",
        "- B/D use --settings (temporary autoMemoryDirectory), which can shorten the shared prefix (lower cache_read) without changing what the total measures",
        "- A1 attachment sizes (chars of JSON, from the transcript): "
        + ", ".join(f"{k} {v:,}" for k, v in runs[0]["attachment_chars"].items()),
        "- `claude -p` (CLI) has a different base than the desktop app; only the *differences* above are comparable across setups",
        "",
    ]
    mp = jp[:-5] + ".md"
    io.open(mp, "w", encoding="utf-8", newline="\n").write("\n".join(md))
    print("\n".join(md[-8:]))
    print("->", jp)
    print("->", mp)


if __name__ == "__main__":
    setup()
    main()
