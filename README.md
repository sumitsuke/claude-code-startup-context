# claude-code-startup-context

**Measure what Claude Code puts into the context before you type anything — and which pieces of it are yours.**
A small remove-and-restore benchmark (`scripts/measure.py`, one file, standard library only) plus the data behind the Sumitsuke Lab article (2026-09-19).

Article: [Claude Code の開始時コンテキストを分解する——memory 11.7K・MCP 8.4K、翌日 6K 戻った](https://sumitsuke.jp/lab/startup-context-decomposition/) (Lab, Japanese) / Zenn version pending / part 1: [Claude Code の 1 依頼で消えたトークンはどこへ行くか](https://sumitsuke.jp/lab/where-tokens-go-claude-code/)

## In one paragraph

A Claude Code session has already sent 70–90K tokens of input by the time the first reply arrives. Over seven mornings started with the same routine request the first-turn input went 86.2K → 86.6K → 88.8K → 89.5K → **79.4K** (the morning after auto memory and skills were trimmed) → 85.8K → 88.0K (back). Removing one element at a time with `claude -p` (same prompt, baseline reproducible to ±3 tokens): **this project's `MEMORY.md` (15,340 chars, 134 lines) accounts for 11,722 tokens**, **the MCP connectors for 8,439**; removing both at once gives −20,308, which matches the sum (residual −147 vs. the first baseline, +7 vs. the baseline measured right after — the baseline itself drifted −154 because `git status` changed). The point of the article: what you trimmed comes back the next day from things that are not your documents, so measure again.

## Quick start (measure your own setup)

Requirements: Python 3.8+, `claude` on PATH, a project you normally work in.

```bash
# macOS / Linux
export N3_PROJ="$HOME/.claude/projects/<project-dir>"   # transcript dir of that project (ls ~/.claude/projects/)
export N3_CWD="/path/to/that/project"
python scripts/measure.py
```

```powershell
# Windows (PowerShell)
$env:N3_PROJ = "$HOME\.claude\projects\<project-dir>"
$env:N3_CWD  = "C:\path\to\that\project"
python scripts\measure.py
```

What it does: 7 runs of `claude -p "1+1 を数字だけで答えて"` — A1 baseline → B (auto-memory index reduced to one line) → A2 → C (no MCP servers) → A3 → D (B + C) → A4 — and writes `results/measure_<date>_<time>.json` (canonical) and `.md` (rendered from the JSON). Optional `N3_MODEL` (default `claude-opus-5`).

It does **not** touch your files:

- B and D point *that run only* at a temporary auto-memory directory holding a one-line `MEMORY.md`, through the official `autoMemoryDirectory` setting passed with `--settings`. Your real `MEMORY.md` is not read for writing, copied or renamed.
- C and D pass `--strict-mcp-config --mcp-config <tmp>/mcp_empty.json` (`{"mcpServers": {}}`) — "use only the servers listed in this file, which lists none".
- Every run gets its own `--session-id <uuid>` and the tool reads exactly that transcript. It stops (non-zero exit) if the CLI fails, the transcript is missing or has no usage — a failed call can never be recorded as a measurement.
- Cost: 7 CLI calls of roughly 55–75K input tokens each. Depending on how you authenticate they consume plan usage or API billing.

Reading the output: a run is valid only if its MCP tool-name count is the expected one (A1's count for A/B runs, 0 for C/D). `claude -p` sometimes sends the first turn before every MCP server has announced its tools (seen here: 221 of 266 names, total 1.2K lower, *same* `cache_read` as a complete run — so `cache_read` alone does not catch it). Such runs are recorded as discarded and re-run automatically (max 3). The `.md` also reports the baseline drift A4 − A1 and the additivity residual against both A1 and A4. ⚠ The discard-and-re-run branch has not yet been exercised by a real incomplete run (the two verification runs had 0 discards after the check was added).

## What is measured and what is not

| number | evidence level |
|---|---|
| MEMORY.md → 1 line: −11,722; no MCP: −8,439; both: −20,308 | measured (`data/RESULTS_2026-09-19.md`); re-measured with `measure.py` an hour later: −11,797 / −8,439 / −20,233 (`data/measure_2026-09-19.md`) |
| additivity: residual −147 vs. A1, +7 vs. A4 (baseline drift −154 = `session_context` only) | measured, both baselines in the table |
| `cache_read` 36,498 | measured value (constant within one prefix). "= system prompt + built-in tools" is an interpretation from the transcript structure |
| the remaining ≈17.5K (CLAUDE.md, skill listing, git status, prompt) | arithmetic residual, not measured per element; moves by hundreds with `git status` |
| a single connector (e.g. the mail connector) | not measured |
| `--system-prompt-snapshot` on vs. off | not measured — `on` is the CLI default; the 67,373 run in the data is a different-prefix run, not a snapshot-off run |

⚠ `claude -p` (CLI) has a different base than the desktop app (74K vs 88K here). Only differences are comparable across setups.
⚠ Measured with Claude Code 2.1.266; how MCP tools are listed can change between versions and move the 8.4K.

## Data

- `data/first_turn_usage_sessions_2026-09-12_19.json` — first-turn usage of 21 sessions of one project (prompt length only, no prompt text). `same_prompt_series` = the seven same-routine mornings (+1 branched duplicate).
- `data/RESULTS_2026-09-19.md` — the A1/B/A2/C/A3 and D/A4 tables, the discarded run P, the attachment-size decomposition, and the corrections made after review.
- `data/measure_2026-09-19.json` / `.md` — `scripts/measure.py` run end-to-end on the same project one hour later (15:10 JST), with the final code: memory −11,797 (the index had grown 219 bytes), MCP **−8,439** (identical), both −20,233, residual +3 (vs A1) / +5 (vs A4), baseline ±2, 0 runs discarded. `data/measure_2026-09-19_run1_incomplete_mcp_list.json` is the run just before it (15:08, earlier code without the validity check): its A2 came back at 72,987 with 221 of 266 MCP tool names **and the same `cache_read` as A1** — the observation that made the tool check tool-name counts instead of `cache_read`.
- `data/original_2026-09-19/` — the two scripts that actually produced those tables and their raw result file, kept verbatim (they hard-code that day's values and rewrite the real `MEMORY.md`: **historical evidence, do not run**). `SHA256_of_lab_copies.txt` there matches the copies published under `https://sumitsuke.jp/lab/startup-context-decomposition/evidence/`.
- `SHA256SUMS` (repository root) — checksums of the files as they are in this repository: `sha256sum -c SHA256SUMS`. Computed from the git index (LF), so it verifies on Linux/macOS/Windows alike; `.gitattributes` pins line endings.

## Checking the tool itself

- `python -m pytest -q tests` — the transcript reader on synthetic `.jsonl` fixtures (first-turn usage, MCP tool names, and that an unparseable line is **counted**, not skipped — `measure.py` stops if any line fails to parse).
- `python scripts/verify_results.py data/measure_2026-09-19.json` — recomputes every number of `summary` from the seven runs with separate arithmetic and checks the `.md` carries the same totals (`RESULT: ALL PASS`).
- `.github/workflows/verify.yml` runs both plus `sha256sum -c`, `compileall`, `ruff check` (bare `except`, pyflakes) and `ruff format --check` on every push. Data under `data/` is never formatted or linted.

## Not included (and why)

The transcripts themselves (`.jsonl`, they contain the prompts and the work), `MEMORY.md`, `CLAUDE.md` (internal operating documents). Only usage numbers and character counts are published.

## License

Code: MIT (`LICENSE`). Data, tables and figures: CC BY 4.0 (`DATA_LICENSE`) — please credit **Sumitsuke Lab** (https://sumitsuke.jp/lab/).
