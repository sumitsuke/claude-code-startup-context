# claude-code-startup-context

**Claude Code の「開始時の入力」を、要素の除去→復元で分解する再現キット**（2026-09-19・Sumitsuke Lab）

記事: [Claude Code の開始時コンテキストを分解する——memory 11.7K・MCP 8.4K、翌日 6K 戻った](https://sumitsuke.jp/lab/startup-context-decomposition/)（Lab・本家）／技術版 Zenn（公開待ち）／前編 [Claude Code の 1 依頼で消えたトークンはどこへ行くか](https://sumitsuke.jp/lab/where-tokens-go-claude-code/)

## 一言でいうと

- Claude Code のセッションは、1 応答目の時点で 7〜9 万トークンを入力している。同じ定型作業で始めた 7 日間: 86.2K・86.6K・88.8K・89.5K → **79.4K**（auto memory と skills を削った翌朝）→ 85.8K → 88.0K（戻った）。
- 要素を 1 つずつ外して戻すと（`claude -p`・同一依頼文・再現 ±3）: **この MEMORY.md（15,340 字・134 行）をほぼ空にした差 −11,722**、**MCP コネクタ一式を外した差 −8,439**、両方同時 −20,308（加算の期待 −20,161・差 −147＝独立に足せる）。
- 削った翌日に測り直さないと「減ったまま」だと思い込む。土台は自分の文書だけでは決まらない。

## 何が測れて、何が測れないか

| 数字 | 証拠レベル |
|---|---|
| MEMORY.md をほぼ空にした差 −11,722／MCP を外した差 −8,439／同時 −20,308 | 実測（`scripts/`・`data/RESULTS_2026-09-19.md`） |
| `cache_read` 36,498 | 実測値（同一プレフィックス内で不変）。「＝システム指示＋組み込み道具」は構造からの解釈 |
| その他 17,574（CLAUDE.md・スキル一覧・git 状態・依頼文） | 算術残差・トークン未測 |
| コネクタ単体（Resend など） | 未測 |

⚠ `claude -p`（CLI）はデスクトップアプリと土台が別（当方: 74K vs 88K）。ここで比べられるのは**相対差**だけ。⚠ `-p` は MCP の道具一覧が揃う前に 1 応答目が走ることがある（当方の事前走: 道具名 221/266・`cache_read` 0）＝**`cache_read` が基準と違う走は同じプレフィックスではないので捨てる**。

## 4 手順（自分の環境で同じことをする）

1. 何が載っているかを見る＝`claude -p ... --system-prompt-snapshot on` の転写の添付（または対話で `/context`）
2. 総入力を固定する＝`usage.input_tokens + cache_creation_input_tokens + cache_read_input_tokens`
3. 要素を 1 つだけ外して測る（MEMORY.md を 1 行に／`--strict-mcp-config`）
4. 元に戻して基準が再現することを確かめる（当方 ±3）

## クイックスタート

```bash
# 前提: claude CLI が PATH に在る・測りたいプロジェクトの作業フォルダ・転写フォルダ（~/.claude/projects/<project-dir>）
export N3_PROJ="$HOME/.claude/projects/<project-dir>"   # Windows: set N3_PROJ=%USERPROFILE%\.claude\projects\<project-dir>
export N3_CWD="/path/to/your/project"
python scripts/experiment_startup_decomposition.py      # A1 → B(MEMORY 1 行) → A2 → C(MCP 無し) → A3。MEMORY.md は退避→復元（SHA256 で確認）
python scripts/experiment_D_additivity.py               # D(B＋C 同時) → A4
```

- 各走で `claude -p "1+1 を数字だけで答えて"` を 1 回呼ぶ（Opus 5・約 7 万トークンの入力＝費用はあなたのアカウントに掛かる）。
- ⚠ `MEMORY.md` を数秒だけ 1 行に差し替える。**他の Claude Code セッションが無い時間に**走らせる（失敗しても `finally` で復元）。
- 結果は `_実験_基礎の分解_結果_<日付>.md` に表で出る（当方の結果＝`data/RESULTS_2026-09-19.md`）。

## データ

- `data/first_turn_usage_sessions_2026-09-12_19.json` — 当方の 21 セッションの 1 応答目 usage（依頼文は字数だけ・本文は含まない）。`same_prompt_series` が同じ定型作業の 7 本（＋分岐の複製 1）。
- `data/RESULTS_2026-09-19.md` — A1/B/A2/C/A3・追試 D/A4・外れ値 P・添付の字数の内訳。
- `data/SHA256_of_lab_copies.txt` — Lab の `evidence/` に置いた写しの SHA256（同じ内容）。

## 置いていないもの（と理由）

転写 `.jsonl` そのもの（依頼文の本文・作業内容を含む）・`MEMORY.md`・`CLAUDE.md`（内部の運用文書）。usage の数字と字数だけを出している。

## License

Code: MIT (see `LICENSE`). Data, tables and figures: CC BY 4.0 (see `DATA_LICENSE`) — please credit **Sumitsuke Lab** (https://sumitsuke.jp/lab/).
