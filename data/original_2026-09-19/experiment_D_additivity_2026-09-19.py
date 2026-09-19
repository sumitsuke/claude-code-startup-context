# N3 追加実験 D（外部レビュー採用）: MEMORY.md 1 行 ＋ --strict-mcp-config を同時に外す＝B と C が加算できるか（期待 ≈ 54,072）。
# あわせて P（snapshot 無しの現状）＝A1 との差（事前走 73,093 と A1 74,233 の 1,140 の出所＝snapshot の有無か）。退避は try/finally・SHA256 で復元確認。
import subprocess, os, io, sys, json, glob, hashlib, time, datetime, shutil
sys.stdout.reconfigure(encoding="utf-8")
PROJ = os.environ["N3_PROJ"]                 # 例: <USERPROFILE>/.claude/projects/<project-dir>
MEM = os.path.join(PROJ, "memory", "MEMORY.md")
CWD = os.environ.get("N3_CWD", os.getcwd())  # 測りたいプロジェクトの作業フォルダ
PROMPT = "1+1 を数字だけで答えて"
CLAUDE = shutil.which("claude") or shutil.which("claude.cmd")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "_実験_基礎の分解_結果_2026-09-19.md")
def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
def run(label, extra=()):
    before = set(glob.glob(os.path.join(PROJ, "*.jsonl"))); t0 = time.time()
    r = subprocess.run([CLAUDE, "-p", PROMPT, "--model", "claude-opus-5", *extra], cwd=CWD, capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=300)
    sec = round(time.time() - t0, 1)
    new = [f for f in glob.glob(os.path.join(PROJ, "*.jsonl")) if f not in before]; f = new[0]
    first = None; ver = None
    for line in io.open(f, encoding="utf-8", errors="replace"):
        try: d = json.loads(line)
        except Exception: continue
        ver = ver or d.get("version"); m = d.get("message") or {}
        if first is None and m.get("role") == "assistant" and m.get("usage"):
            u = m["usage"]; first = (u["input_tokens"], u["cache_creation_input_tokens"], u["cache_read_input_tokens"])
    tot = sum(first)
    print(f"{label}: 合計 {tot:,} (in {first[0]} cc {first[1]:,} cr {first[2]:,}) ver {ver} {sec}s 応答「{r.stdout.strip()[:20]}」 転写 {os.path.basename(f)[:8]}")
    return (label, tot, first, ver, sec, os.path.basename(f)[:8])
rows = [run("P 現状（snapshot 無し）")]
orig = open(MEM, "rb").read(); h0 = sha(MEM)
try:
    io.open(MEM, "w", encoding="utf-8", newline="\n").write("# Memory Index\n"); t_swap = time.time()
    rows.append(run("D MEMORY.md 1 行＋MCP 無し", ("--strict-mcp-config",)))
finally:
    open(MEM, "wb").write(orig); h1 = sha(MEM); print(f"  復元 sha256 一致={h0 == h1} 退避の窓 {round(time.time() - t_swap, 1)}s")
rows.append(run("A4 復元後"))
A1 = 74233; B = 62511; C = 65794; expect = A1 - (A1 - B) - (A1 - C)
lines = ["", f"## 追試（{datetime.datetime.now():%Y-%m-%d %H:%M} JST・`_実験_D_2026-09-19.py`）: D＝同時に外す／P＝snapshot 無し", "",
         "| 条件 | 総入力 | in / cache_create / cache_read | CLI 版 | 秒 | 転写 |", "|---|---|---|---|---|---|"]
for label, tot, u, ver, sec, tr in rows:
    lines.append(f"| {label} | {tot:,} | {u[0]} / {u[1]:,} / {u[2]:,} | {ver} | {sec} | {tr} |")
D = rows[1][1]
lines += ["", f"- 加算の期待値＝A1 − (A1−B) − (A1−C) ＝ {expect:,}。D の実測 {D:,}＝差 **{D - expect:+,}**（±数十なら B と C は独立に加算できる＝分解図でよい。大きければ相互作用項）",
          f"- P（snapshot 無し・現状）{rows[0][1]:,} と A1（snapshot あり）74,233 の差 **{rows[0][1] - 74233:+,}**＝`--system-prompt-snapshot on` の有無の寄与（事前走 73,093 との差 1,140 の出所の切り分け）",
          f"- 復元 sha256 一致 {h0 == h1}"]
s = io.open(OUT, encoding="utf-8").read().rstrip("\n") + "\n" + "\n".join(lines) + "\n"
io.open(OUT, "w", encoding="utf-8", newline="\n").write(s); print("\n".join(lines[-3:]))
