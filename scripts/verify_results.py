#!/usr/bin/env python3
"""verify_results.py — recompute the summary of a measure.py result file from its runs, independently.

Does not import measure.py. Reads results/measure_*.json (or data/measure_*.json), rebuilds every number in
"summary" from the seven runs with its own arithmetic, and compares. Also checks that the .md next to it
carries the same totals. Exit 1 on any mismatch.

    python scripts/verify_results.py data/measure_2026-09-19.json
"""

import io, json, os, re, sys

sys.stdout.reconfigure(encoding="utf-8")
path = sys.argv[1] if len(sys.argv) > 1 else None
if not path or not os.path.isfile(path):
    sys.exit("usage: verify_results.py <measure_*.json>")
doc = json.load(io.open(path, encoding="utf-8"))
runs = doc["runs"]
labels = [r["label"].split()[0] for r in runs]
if labels != ["A1", "B", "A2", "C", "A3", "D", "A4"]:
    sys.exit(f"FAIL: run order {labels}")
tot = {}
ok = True


def check(name, got, want):
    global ok
    flag = got == want
    ok &= flag
    print(f"  [{'PASS' if flag else 'FAIL'}] {name}: file={got} independent={want}")


for r in runs:
    t = r["input_tokens"] + r["cache_creation_input_tokens"] + r["cache_read_input_tokens"]
    check(f"total of {r['label']}", r["total"], t)
    tot[r["label"].split()[0]] = t
A1, B, A2, C, A3, D, A4 = (tot[k] for k in ["A1", "B", "A2", "C", "A3", "D", "A4"])
s = doc["summary"]
check("memory_effect_B_minus_A1", s["memory_effect_B_minus_A1"], B - A1)
check("mcp_effect_C_minus_A1", s["mcp_effect_C_minus_A1"], C - A1)
check("both_effect_D_minus_A1", s["both_effect_D_minus_A1"], D - A1)
check("expected_additive_vs_A1", s["expected_additive_vs_A1"], B + C - A1)
check("residual_vs_A1", s["residual_vs_A1"], D - (B + C - A1))
check("baseline_drift_A4_minus_A1", s["baseline_drift_A4_minus_A1"], A4 - A1)
check("expected_additive_vs_A4", s["expected_additive_vs_A4"], A4 + (B - A1) + (C - A1))
check("residual_vs_A4", s["residual_vs_A4"], D - (A4 + (B - A1) + (C - A1)))
check("reproducibility_A2_A3_A4_minus_A1", s["reproducibility_A2_A3_A4_minus_A1"], [A2 - A1, A3 - A1, A4 - A1])
full = runs[0]["mcp_tool_names"]
check("mcp_tool_names_full", s.get("mcp_tool_names_full", full), full)
for r in runs:
    want = 0 if r["label"].split()[0] in ("C", "D") else full
    check(f"valid run {r['label'].split()[0]} (mcp names {r['mcp_tool_names']} == {want})", r["mcp_tool_names"], want)
md = path[:-5] + ".md"
if os.path.isfile(md):
    text = io.open(md, encoding="utf-8").read()
    for r in runs:
        check(
            f"md carries {r['label']} total",
            bool(re.search(rf"\| {re.escape(r['label'])} \| {r['total']:,} \|", text)),
            True,
        )
print("\nRESULT:", "ALL PASS" if ok else "MISMATCH FOUND")
sys.exit(0 if ok else 1)
