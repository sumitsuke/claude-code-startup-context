# N3 追加実験（企画設計 v2 §9・適応型）: 同じ依頼文で `claude -p` を条件ごとに 1 回ずつ走らせ、1 応答目の usage（総入力＝in+cc+cr）を比べる。
#   A1 現状 → B MEMORY.md を 1 行（退避→測→復元・SHA256 で確認・窓 1 分未満）→ A2 復元後 → C MCP 無し（--strict-mcp-config）→ A3 復元後
#   A1 は --system-prompt-snapshot on でシステムプロンプトを転写に記録し、構成要素（CLAUDE.md・MEMORY・道具名 …）の字数を直接数える。
#   ⚠ B の間に他のセッションが始まると最小の MEMORY を読む＝他のセッションが無い時間に。失敗しても finally で復元。
import subprocess, os, io, sys, json, glob, hashlib, time, datetime, shutil
sys.stdout.reconfigure(encoding="utf-8")
PROJ = os.environ["N3_PROJ"]                 # 例: <USERPROFILE>/.claude/projects/<project-dir>
MEM = os.path.join(PROJ, "memory", "MEMORY.md")
CWD = os.environ.get("N3_CWD", os.getcwd())  # 測りたいプロジェクトの作業フォルダ
PROMPT = "1+1 を数字だけで答えて"
CLAUDE = shutil.which("claude") or shutil.which("claude.cmd")
assert CLAUDE, "claude が PATH に無い"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, f"_実験_基礎の分解_結果_{datetime.date.today():%Y-%m-%d}.md")
def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
def newest():
    fs = sorted(glob.glob(os.path.join(PROJ, "*.jsonl")), key=os.path.getmtime); return fs[-1]
def run(label, extra=()):
    before = set(glob.glob(os.path.join(PROJ, "*.jsonl")))
    t0 = time.time()
    r = subprocess.run([CLAUDE, "-p", PROMPT, "--model", "claude-opus-5", *extra], cwd=CWD, capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=300)
    sec = round(time.time() - t0, 1)
    new = [f for f in glob.glob(os.path.join(PROJ, "*.jsonl")) if f not in before]
    f = new[0] if new else newest()
    first = None; ver = None; snap = None
    for line in io.open(f, encoding="utf-8", errors="replace"):
        try: d = json.loads(line)
        except Exception: continue
        ver = ver or d.get("version")
        if d.get("type") == "system_prompt_snapshot" or "system_prompt" in d and snap is None:
            snap = d
        m = d.get("message") or {}
        if first is None and m.get("role") == "assistant" and m.get("usage"):
            u = m["usage"]; first = (u["input_tokens"], u["cache_creation_input_tokens"], u["cache_read_input_tokens"])
    tot = sum(first) if first else None
    print(f"{label}: 合計 {tot:,} (in {first[0]} cc {first[1]:,} cr {first[2]:,}) ver {ver} {sec}s 応答「{r.stdout.strip()[:20]}」 転写 {os.path.basename(f)[:8]}")
    return {"label": label, "total": tot, "usage": first, "version": ver, "sec": sec, "transcript": os.path.basename(f), "answer": r.stdout.strip()[:40]}
rows = []
rows.append(run("A1 現状（snapshot）", ("--system-prompt-snapshot", "on")))
# ── B: MEMORY.md を 1 行に（退避→復元） ──
orig = open(MEM, "rb").read(); h0 = sha(MEM); bak = MEM + ".bak_N3"
shutil.copy2(MEM, bak)
try:
    io.open(MEM, "w", encoding="utf-8", newline="\n").write("# Memory Index\n")
    t_swap = time.time()
    rows.append(run("B MEMORY.md を 1 行"))
finally:
    open(MEM, "wb").write(orig)
    h1 = sha(MEM); print(f"  復元 sha256 一致={h0 == h1} 退避の窓 {round(time.time() - t_swap, 1)}s")
    if h0 == h1: os.remove(bak)
rows.append(run("A2 復元後"))
rows.append(run("C MCP 無し（--strict-mcp-config）", ("--strict-mcp-config",)))
rows.append(run("A3 再び現状"))
# ── 表 ──
base = rows[0]["total"]
lines = [f"# N3 追加実験の結果（{datetime.datetime.now():%Y-%m-%d %H:%M} JST・器＝`_実験_基礎の分解_2026-09-19.py`・依頼文「{PROMPT}」・claude -p）", "",
         "| 条件 | 総入力 | A1 との差 | in / cache_create / cache_read | CLI 版 | 秒 | 転写 |", "|---|---|---|---|---|---|---|"]
for r in rows:
    lines.append(f"| {r['label']} | {r['total']:,} | {r['total'] - base:+,} | {r['usage'][0]} / {r['usage'][1]:,} / {r['usage'][2]:,} | {r['version']} | {r['sec']} | {r['transcript'][:8]} |")
lines += ["", f"- MEMORY.md 原本: {len(orig):,} B・sha256 {h0[:16]}…・復元一致 {h0 == h1}",
          "- 読み方: B−A1 ≒ MEMORY.md（25KB 上限まで）の寄与／C−A1 ≒ MCP の道具名と MCP の指示文の寄与（負の値）／A2・A3 は再現の幅（同条件で ±どれだけ揺れるか）",
          "- ⚠ `claude -p`（CLI）はデスクトップアプリと基礎が別（アプリ固有の道具・指示が無い）。ここで測るのは**相対差**。絶対値はアプリの転写（87.8K）とは比べない"]
io.open(OUT, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
print("\n".join(lines[2:])); print("→", OUT)
