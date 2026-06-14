# オッズ取得のJSON API化 + 予想時オッズの採用 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** netkeiba のオッズ取得を静的HTMLスクレイピングから JSON API (`api_get_jra_odds.html`) へ移行し、`/keiba` 予想時に取得した暫定オッズを `.odds.json` として自動保存してバックテストの払戻計算に採用する。

**Architecture:** `get_odds.py` をネットワーク層（`_fetch_api_json`）と純関数パーサ層（`parse_tansho_fukusho` / `parse_combined` / `parse_sanren` / `_assemble_snapshot`）に分離する。公開関数 `fetch_tansho_fukusho` / `fetch_combined_odds` / `fetch_sanren_odds` のシグネチャは維持し中身のみ差し替えるため、`snapshot_odds.py` と CLI は後方互換。`fetch_all_odds` を `get_odds.py` に移し `odds_status` を付与。予想フローと各ドキュメントを更新する。

**Tech Stack:** Python 3.12, `requests`, `pytest`。テストはネットワーク非依存の純関数のみ対象（フィクスチャは検証済みの実APIフォーマットを手書きの dict で再現）。

---

## File Structure

- `.claude/skills/netkeiba-scraper/scripts/get_odds.py` — **Modify**。HTMLパースをAPI化。パーサ純関数 + `_fetch_api_json` + `fetch_all_odds` + `_assemble_snapshot` を追加。公開関数名は維持。
- `.claude/skills/netkeiba-scraper/scripts/snapshot_odds.py` — **Modify**。`fetch_all_odds` を `get_odds` から import するよう変更（重複ロジック削除）。
- `tests/test_get_odds.py` — **Create**。パーサ純関数 + `_assemble_snapshot` の pytest。
- `.claude/skills/keiba-prediction/SKILL.md` — **Modify**。段階3・段階9・`predicted_odds` 注記を更新し、予想時 `.odds.json` 自動保存を明記。
- `.claude/commands/keiba.md` — **Modify**。予想時にオッズが自動保存される旨を追記。
- `.claude/skills/netkeiba-scraper/SKILL.md` — **Modify**。API化・`odds_status`・三連系1リクエストの注記。
- `CLAUDE.md` — **Modify**。フロー2段目「直前スナップ」を任意（上書き用）に格下げ。

### 検証済み API リファレンス（実装の前提）

```
GET https://race.netkeiba.com/api/api_get_jra_odds.html?race_id=<id>&type=<n>&action=update
```

- レスポンス: `{"status": "...", "data": {...} | "", ...}`
- `status`: `"middle"`（暫定）/ `"result"`（確定）/ `"NG"`（データ無し → `data` は空文字列 `""`）
- `data.odds`: `{ odds_key: { combo_key: [v0, v1, popularity] } }`
- `type` と `odds_key` の対応:

| 馬券種 | type | odds_key | v0 / v1 |
|--------|------|----------|---------|
| 単勝 | 1 | `"1"` | v0=オッズ, v1=`""` |
| 複勝 | 1 | `"2"` | v0=低, v1=高 |
| 馬連 | 4 | `"4"` | v0=オッズ, v1=`""` |
| ワイド | 5 | `"5"` | v0=低, v1=高 |
| 馬単 | 6 | `"6"` | v0=オッズ, v1=`""` |
| 三連複 | 7 | `"7"` | v0=オッズ, v1=`""` |
| 三連単 | 8 | `"8"` | v0=オッズ, v1=`""` |

- `combo_key` は2桁ゼロ埋め馬番連結（単複は馬番 `"01"`、馬連系 `"0102"`、三連系 `"010203"`）。
- `type=1` の1リクエストで単勝(`"1"`)・複勝(`"2"`)両方が返る。三連系も1リクエストで全通り。
- **後方互換方針:** ワイドは現行 `.odds.json` スキーマ（`odds_low`/`odds_high`）を保つが、現行のHTML実装と同じく **v0（低）を low/high 両方に採用**する（high は使わない）。これにより `compute_payout` と既存テストは不変。

---

## Task 1: 単勝・複勝パーサ `parse_tansho_fukusho`

**Files:**
- Modify: `.claude/skills/netkeiba-scraper/scripts/get_odds.py`
- Test: `tests/test_get_odds.py`

- [ ] **Step 1: Write the failing test**

`tests/test_get_odds.py` を新規作成:

```python
from get_odds import parse_tansho_fukusho


def test_parse_tansho_fukusho_splits_win_and_place():
    api = {
        "status": "middle",
        "data": {"odds": {
            "1": {"01": ["13.5", "", "6"], "02": ["4.0", "", "1"]},
            "2": {"01": ["3.5", "4.8", "8"], "02": ["1.5", "1.7", "1"]},
        }},
    }
    result = parse_tansho_fukusho(api)
    assert result["tansho"] == [
        {"num": "1", "odds": "13.5"},
        {"num": "2", "odds": "4.0"},
    ]
    assert result["fukusho"] == [
        {"num": "1", "odds_low": "3.5", "odds_high": "4.8"},
        {"num": "2", "odds_low": "1.5", "odds_high": "1.7"},
    ]


def test_parse_tansho_fukusho_handles_ng_status():
    api = {"status": "NG", "data": ""}
    result = parse_tansho_fukusho(api)
    assert result == {"tansho": [], "fukusho": []}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source venv/bin/activate && pytest tests/test_get_odds.py -v`
Expected: FAIL with `ImportError: cannot import name 'parse_tansho_fukusho'`

- [ ] **Step 3: Write minimal implementation**

`get_odds.py` のトップ付近（既存 `ODDS_TYPES` の下あたり）に追加:

```python
def _odds_dict(api_json: dict, odds_key: str) -> dict:
    """data.odds[odds_key] を取り出す。NG/欠損時は空 dict。"""
    data = api_json.get("data")
    if not isinstance(data, dict):
        return {}
    odds = data.get("odds")
    if not isinstance(odds, dict):
        return {}
    block = odds.get(odds_key)
    return block if isinstance(block, dict) else {}


def _unpad(combo_key: str) -> list[str]:
    """'0102' -> ['1','2'] / '010203' -> ['1','2','3'] / '01' -> ['1']。"""
    return [str(int(combo_key[i:i + 2])) for i in range(0, len(combo_key), 2)]


def parse_tansho_fukusho(api_json: dict) -> dict:
    """type=1 のAPI JSONから単勝・複勝を抽出する純関数。"""
    tan_block = _odds_dict(api_json, "1")
    fuku_block = _odds_dict(api_json, "2")

    tansho = [
        {"num": _unpad(k)[0], "odds": v[0]}
        for k, v in sorted(tan_block.items(), key=lambda kv: int(kv[0]))
    ]
    fukusho = [
        {"num": _unpad(k)[0], "odds_low": v[0], "odds_high": v[1]}
        for k, v in sorted(fuku_block.items(), key=lambda kv: int(kv[0]))
    ]
    return {"tansho": tansho, "fukusho": fukusho}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_get_odds.py -v`
Expected: PASS（2 件）

- [ ] **Step 5: Commit**

```bash
git add tests/test_get_odds.py .claude/skills/netkeiba-scraper/scripts/get_odds.py
git commit -m "feat: add parse_tansho_fukusho JSON parser"
```

---

## Task 2: 組み合わせパーサ `parse_combined`（馬連・ワイド・馬単）

**Files:**
- Modify: `.claude/skills/netkeiba-scraper/scripts/get_odds.py`
- Test: `tests/test_get_odds.py`

- [ ] **Step 1: Write the failing test**

`tests/test_get_odds.py` に追記:

```python
from get_odds import parse_combined


def test_parse_combined_unpads_and_sorts_by_odds():
    api = {
        "status": "middle",
        "data": {"odds": {"4": {
            "0102": ["301.8", "", "65"],
            "0103": ["10.5", "", "2"],
        }}},
    }
    result = parse_combined(api, "4")
    assert result == [
        ["1", "3", "10.5"],
        ["1", "2", "301.8"],
    ]


def test_parse_combined_uses_low_value_for_wide():
    api = {
        "status": "middle",
        "data": {"odds": {"5": {"0102": ["57.7", "60.5", "60"]}}},
    }
    result = parse_combined(api, "5")
    assert result == [["1", "2", "57.7"]]


def test_parse_combined_handles_ng():
    assert parse_combined({"status": "NG", "data": ""}, "4") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_get_odds.py -k parse_combined -v`
Expected: FAIL with `ImportError: cannot import name 'parse_combined'`

- [ ] **Step 3: Write minimal implementation**

`get_odds.py` に追加:

```python
def _odds_sort_key(row: list) -> float:
    try:
        return float(row[-1])
    except (ValueError, IndexError):
        return 9999.0


def parse_combined(api_json: dict, odds_key: str) -> list[list]:
    """馬連(4)・ワイド(5)・馬単(6) のAPI JSONから [馬番1, 馬番2, オッズ] を抽出。

    ワイドは v0（低オッズ）を採用（現行スキーマ互換）。
    """
    block = _odds_dict(api_json, odds_key)
    rows = []
    for combo_key, vals in block.items():
        n1, n2 = _unpad(combo_key)
        rows.append([n1, n2, vals[0]])
    rows.sort(key=_odds_sort_key)
    return rows
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_get_odds.py -k parse_combined -v`
Expected: PASS（3 件）

- [ ] **Step 5: Commit**

```bash
git add tests/test_get_odds.py .claude/skills/netkeiba-scraper/scripts/get_odds.py
git commit -m "feat: add parse_combined JSON parser"
```

---

## Task 3: 三連系パーサ `parse_sanren`（三連複・三連単）

**Files:**
- Modify: `.claude/skills/netkeiba-scraper/scripts/get_odds.py`
- Test: `tests/test_get_odds.py`

- [ ] **Step 1: Write the failing test**

`tests/test_get_odds.py` に追記:

```python
from get_odds import parse_sanren


def test_parse_sanren_unpads_three_horses_and_sorts():
    api = {
        "status": "middle",
        "data": {"odds": {"7": {
            "010203": ["1260.4", "", "227"],
            "010204": ["88.8", "", "30"],
        }}},
    }
    result = parse_sanren(api, "7")
    assert result == [
        ["1", "2", "4", "88.8"],
        ["1", "2", "3", "1260.4"],
    ]


def test_parse_sanren_handles_ng():
    assert parse_sanren({"status": "NG", "data": ""}, "8") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_get_odds.py -k parse_sanren -v`
Expected: FAIL with `ImportError: cannot import name 'parse_sanren'`

- [ ] **Step 3: Write minimal implementation**

`get_odds.py` に追加:

```python
def parse_sanren(api_json: dict, odds_key: str) -> list[list]:
    """三連複(7)・三連単(8) のAPI JSONから [馬番1, 馬番2, 馬番3, オッズ] を抽出。"""
    block = _odds_dict(api_json, odds_key)
    rows = []
    for combo_key, vals in block.items():
        n1, n2, n3 = _unpad(combo_key)
        rows.append([n1, n2, n3, vals[0]])
    rows.sort(key=_odds_sort_key)
    return rows
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_get_odds.py -k parse_sanren -v`
Expected: PASS（2 件）

- [ ] **Step 5: Commit**

```bash
git add tests/test_get_odds.py .claude/skills/netkeiba-scraper/scripts/get_odds.py
git commit -m "feat: add parse_sanren JSON parser"
```

---

## Task 4: ネットワーク層 `_fetch_api_json` と公開 fetch 関数のAPI化

**Files:**
- Modify: `.claude/skills/netkeiba-scraper/scripts/get_odds.py`（`_fetch_soup` 削除、`fetch_tansho_fukusho` / `fetch_combined_odds` / `fetch_sanren_odds` を差し替え）

このタスクはネットワーク呼び出しのため単体テスト対象外。実装後にライブAPIで手動検証する。

- [ ] **Step 1: API type マップと `_fetch_api_json` を追加**

`get_odds.py` の `HEADERS` 直後に追加:

```python
# 馬券種 type_param（HTML時代の b1/b4...）→ JSON API の type 番号
_TYPE_PARAM_TO_API = {"b1": 1, "b4": 4, "b5": 5, "b6": 6, "b7": 7, "b8": 8}


def _fetch_api_json(race_id: str, api_type: int) -> dict:
    """netkeiba のオッズ JSON API を叩いて dict を返す。"""
    url = (
        "https://race.netkeiba.com/api/api_get_jra_odds.html"
        f"?race_id={race_id}&type={api_type}&action=update"
    )
    headers = dict(HEADERS)
    headers["Referer"] = (
        f"https://race.netkeiba.com/odds/index.html?race_id={race_id}"
    )
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, dict) else {}
```

- [ ] **Step 2: `_fetch_soup` を削除し公開 fetch 関数を差し替える**

旧 `_fetch_soup` 関数（`def _fetch_soup(...)` ブロック全体）を削除する。
`fetch_tansho_fukusho` の本体を以下に置換:

```python
def fetch_tansho_fukusho(race_id: str) -> dict:
    """単勝・複勝オッズを JSON API から取得"""
    return parse_tansho_fukusho(_fetch_api_json(race_id, 1))
```

`fetch_combined_odds` の本体を以下に置換:

```python
def fetch_combined_odds(race_id: str, type_param: str) -> list[list]:
    """馬連・馬単・ワイドの組み合わせオッズを JSON API から取得"""
    api_type = _TYPE_PARAM_TO_API[type_param]
    return parse_combined(_fetch_api_json(race_id, api_type), str(api_type))
```

`fetch_sanren_odds` の本体を以下に置換（`head_count` は後方互換のため残すが未使用）:

```python
def fetch_sanren_odds(race_id: str, type_param: str, head_count: int = 18) -> list[list]:
    """3連複・3連単オッズを JSON API から取得（1リクエストで全通り）"""
    api_type = _TYPE_PARAM_TO_API[type_param]
    return parse_sanren(_fetch_api_json(race_id, api_type), str(api_type))
```

- [ ] **Step 3: BeautifulSoup の未使用 import を削除**

`from bs4 import BeautifulSoup` 行を削除する（API化によりHTMLパース不要）。`import time` は Task 5 / `main` の `all` 分岐で使うため残す。

- [ ] **Step 4: 既存パーサテストが壊れていないことを確認**

Run: `pytest tests/test_get_odds.py -v`
Expected: PASS（Task 1-3 の全 7 件）

- [ ] **Step 5: ライブAPIで CLI を手動検証**

Run: `python3 .claude/skills/netkeiba-scraper/scripts/get_odds.py 202605030411 --type tansho`
Expected: `---.-` ではなく実数のオッズ（例: `1    13.x`）が単勝・複勝で表示される。

Run: `python3 .claude/skills/netkeiba-scraper/scripts/get_odds.py 202605030411 --type sanrenpuku`
Expected: 三連複オッズが上位20件表示され「他 N 通り」が出る。

> 注: 過去レースのため `status` は `result`（確定）で返る場合がある。実数オッズが出れば成功。

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/netkeiba-scraper/scripts/get_odds.py
git commit -m "feat: switch get_odds fetchers from HTML scraping to JSON API"
```

---

## Task 5: `fetch_all_odds` / `_assemble_snapshot` を get_odds.py へ移設し odds_status を付与

**Files:**
- Modify: `.claude/skills/netkeiba-scraper/scripts/get_odds.py`（`_assemble_snapshot` + `fetch_all_odds` を追加）
- Modify: `.claude/skills/netkeiba-scraper/scripts/snapshot_odds.py`（自前の `fetch_all_odds` を削除し import）
- Test: `tests/test_get_odds.py`

- [ ] **Step 1: `_assemble_snapshot` のテストを書く**

`tests/test_get_odds.py` に追記:

```python
from get_odds import _assemble_snapshot


def test_assemble_snapshot_builds_full_schema():
    tf = {
        "tansho": [{"num": "1", "odds": "13.5"}],
        "fukusho": [{"num": "1", "odds_low": "3.5", "odds_high": "4.8"}],
    }
    snap = _assemble_snapshot(
        race_id="202605030411",
        snapshot_at="2026-06-14T12:25:00+09:00",
        odds_status="middle",
        tf=tf,
        umaren_rows=[["1", "2", "301.8"]],
        wide_rows=[["1", "2", "57.7"]],
        umatan_rows=[["1", "2", "389.2"]],
        sanrenpuku_rows=[["1", "2", "3", "1260.4"]],
        sanrentan_rows=[["1", "2", "3", "4651.8"]],
    )
    assert snap["race_id"] == "202605030411"
    assert snap["snapshot_at"] == "2026-06-14T12:25:00+09:00"
    assert snap["odds_status"] == "middle"
    assert snap["tansho"] == [{"num": "1", "odds": "13.5"}]
    assert snap["fukusho"] == [{"num": "1", "odds_low": "3.5", "odds_high": "4.8"}]
    assert snap["umaren"] == [{"combination": "1-2", "odds": "301.8"}]
    assert snap["wide"] == [{"combination": "1-2", "odds_low": "57.7", "odds_high": "57.7"}]
    assert snap["umatan"] == [{"combination": "1→2", "odds": "389.2"}]
    assert snap["sanrenpuku"] == [{"combination": "1-2-3", "odds": "1260.4"}]
    assert snap["sanrentan"] == [{"combination": "1→2→3", "odds": "4651.8"}]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_get_odds.py -k assemble -v`
Expected: FAIL with `ImportError: cannot import name '_assemble_snapshot'`

- [ ] **Step 3: `_assemble_snapshot` と `fetch_all_odds` を get_odds.py に実装**

`get_odds.py` の先頭付近の import に追加:

```python
from datetime import datetime, timezone, timedelta
```

`JST` 定数を追加（`HEADERS` 付近）:

```python
JST = timezone(timedelta(hours=9))
```

`get_odds.py` に関数を追加（`fetch_sanren_odds` の下あたり）:

```python
def _assemble_snapshot(race_id, snapshot_at, odds_status, tf,
                       umaren_rows, wide_rows, umatan_rows,
                       sanrenpuku_rows, sanrentan_rows) -> dict:
    """各馬券種の行データを .odds.json スキーマの dict に集約する純関数。"""
    return {
        "race_id": race_id,
        "snapshot_at": snapshot_at,
        "odds_status": odds_status,
        "tansho": tf.get("tansho", []),
        "fukusho": tf.get("fukusho", []),
        "umaren": [
            {"combination": f"{r[0]}-{r[1]}", "odds": r[2]} for r in umaren_rows
        ],
        "wide": [
            {"combination": f"{r[0]}-{r[1]}", "odds_low": r[2], "odds_high": r[2]}
            for r in wide_rows
        ],
        "umatan": [
            {"combination": f"{r[0]}→{r[1]}", "odds": r[2]} for r in umatan_rows
        ],
        "sanrenpuku": [
            {"combination": f"{r[0]}-{r[1]}-{r[2]}", "odds": r[3]}
            for r in sanrenpuku_rows
        ],
        "sanrentan": [
            {"combination": f"{r[0]}→{r[1]}→{r[2]}", "odds": r[3]}
            for r in sanrentan_rows
        ],
    }


def fetch_all_odds(race_id: str, head_count: int = 18) -> dict:
    """全7馬券種のオッズを JSON API から取得し snapshot dict を返す。

    odds_status は単勝・複勝(type=1)レスポンスの status を採用する。
    head_count は後方互換のため残すが未使用。
    """
    tan_json = _fetch_api_json(race_id, 1)
    odds_status = tan_json.get("status", "")
    tf = parse_tansho_fukusho(tan_json)
    time.sleep(0.5)

    umaren_rows = fetch_combined_odds(race_id, "b4")
    time.sleep(0.5)
    wide_rows = fetch_combined_odds(race_id, "b5")
    time.sleep(0.5)
    umatan_rows = fetch_combined_odds(race_id, "b6")
    time.sleep(0.5)
    sanrenpuku_rows = fetch_sanren_odds(race_id, "b7")
    time.sleep(0.5)
    sanrentan_rows = fetch_sanren_odds(race_id, "b8")

    return _assemble_snapshot(
        race_id=race_id,
        snapshot_at=datetime.now(JST).isoformat(),
        odds_status=odds_status,
        tf=tf,
        umaren_rows=umaren_rows,
        wide_rows=wide_rows,
        umatan_rows=umatan_rows,
        sanrenpuku_rows=sanrenpuku_rows,
        sanrentan_rows=sanrentan_rows,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_get_odds.py -k assemble -v`
Expected: PASS（1 件）

- [ ] **Step 5: snapshot_odds.py を get_odds.fetch_all_odds に委譲**

`snapshot_odds.py` の自前 `fetch_all_odds` 関数（`def fetch_all_odds(...)` ブロック全体）を削除し、`main` 内の呼び出しを差し替える。
`import get_odds` は既にある。`main` の該当行:

```python
    print(f"オッズを取得中... (race_id: {args.race_id})")
    snapshot = fetch_all_odds(args.race_id, args.head_count)
```

を以下に変更:

```python
    print(f"オッズを取得中... (race_id: {args.race_id})")
    snapshot = get_odds.fetch_all_odds(args.race_id, args.head_count)
```

不要になった import（`time`, `datetime/timezone/timedelta`, `JST` 定数）が snapshot_odds.py 内で他に使われていなければ削除する。`json`, `os`, `glob`, `sys`, `argparse` は残す。

- [ ] **Step 6: snapshot_odds.py をライブ検証**

Run: `python3 .claude/skills/netkeiba-scraper/scripts/snapshot_odds.py --basename _tmp_verify 202605030411 --reports-dir /tmp`
Expected: `/tmp/_tmp_verify.odds.json` が生成され、`件数:` に各馬券種の非ゼロ件数が出る。

確認: `python3 -c "import json; d=json.load(open('/tmp/_tmp_verify.odds.json')); print(d['odds_status'], {k:len(v) for k,v in d.items() if isinstance(v,list)})"`
Expected: `odds_status` が表示され、tansho/umaren/sanrenpuku 等が非ゼロ。確認後 `/tmp/_tmp_verify.odds.json` は削除してよい。

- [ ] **Step 7: 全テスト実行**

Run: `pytest tests/ -v`
Expected: 既存 + 新規すべて PASS。

- [ ] **Step 8: Commit**

```bash
git add tests/test_get_odds.py .claude/skills/netkeiba-scraper/scripts/get_odds.py .claude/skills/netkeiba-scraper/scripts/snapshot_odds.py
git commit -m "feat: move fetch_all_odds into get_odds with odds_status"
```

---

## Task 6: `/keiba` 予想フローに `.odds.json` 自動保存を追加（keiba-prediction SKILL.md）

**Files:**
- Modify: `.claude/skills/keiba-prediction/SKILL.md`

ドキュメント変更のためテストなし。

- [ ] **Step 1: 段階3のオッズ取得記述を更新**

`.claude/skills/keiba-prediction/SKILL.md` の段階3（52-62行付近）の以下の箇所:

```
2. `get_odds.py <race_id> --type tansho` — 単勝オッズ
3. `get_odds.py <race_id> --type fukusho` — 複勝オッズ
4. `get_odds.py <race_id> --type <user_type>` — ユーザ指定馬券種のオッズ
```

の直後（番号 5 の前）に注記を追加:

```
> オッズは netkeiba の JSON API から取得され、発売中は暫定オッズ（status: middle）が返る。`---.-` にはならない。
```

- [ ] **Step 2: 段階9に `.odds.json` 自動保存ステップを追加**

`.claude/skills/keiba-prediction/SKILL.md` の「### バックテスト用 JSON の並置出力（必須）」セクション末尾（`generated_at` の行の後）に新セクションを追加:

```markdown
### 予想時オッズの自動保存（必須）

予想 JSON を出力したら、続けて予想時点の暫定オッズを全馬券種分 `.odds.json` として保存する:

\```bash
python3 .claude/skills/netkeiba-scraper/scripts/snapshot_odds.py <race_id>
\```

これにより `reports/yyyymmdd_<レース名>.odds.json` が生成され、バックテスト（`/keiba-result`）の払戻計算で使う「オッズ・オブ・レコード」になる。予想 JSON が先に出力されていれば basename は自動検出される。
```

（`\`` は実ファイルではバッククォート3つに置き換える）

- [ ] **Step 3: predicted_odds の注記を更新**

`.claude/skills/keiba-prediction/SKILL.md` の以下の行:

```
`predicted_odds` には予想時点で取得できたオッズを入れる（参考値）。確定オッズは別途 `snapshot_odds.py` で取得する。
```

を以下に置換:

```
`predicted_odds` には予想時点で取得できたオッズを入れる（レポート表示用の参考値）。バックテストの払戻計算には、上記「予想時オッズの自動保存」で生成した `.odds.json`（全馬券種）を使う。
```

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/keiba-prediction/SKILL.md
git commit -m "docs: capture prediction-time odds snapshot in keiba prediction flow"
```

---

## Task 7: `/keiba` コマンド本体に自動保存を追記（keiba.md）

**Files:**
- Modify: `.claude/commands/keiba.md`

- [ ] **Step 1: 出力に関する記述を更新**

`.claude/commands/keiba.md` の62行目付近:

```
スキル側で 8 段階の予想プロセスが実行され、`reports/yyyymmdd_<レース名>.md` にレポートが出力される。
```

を以下に置換:

```
スキル側で 8 段階の予想プロセスが実行され、`reports/yyyymmdd_<レース名>.md`（レポート）・`.json`（買い目）・`.odds.json`（予想時点の全馬券種オッズ）が `reports/` に出力される。`.odds.json` はバックテストの払戻計算に使われる。
```

- [ ] **Step 2: Commit**

```bash
git add .claude/commands/keiba.md
git commit -m "docs: note odds.json auto-save in keiba command"
```

---

## Task 8: netkeiba-scraper SKILL.md をAPI化に合わせて更新

**Files:**
- Modify: `.claude/skills/netkeiba-scraper/SKILL.md`

- [ ] **Step 1: オッズ取得セクションに API 注記を追加**

`.claude/skills/netkeiba-scraper/SKILL.md` の「### オッズ（get_odds.py）」セクション末尾（対応馬券の行の後）に追加:

```markdown
オッズは netkeiba の JSON API（`api_get_jra_odds.html`）から取得する。発売中は暫定オッズ（`status: middle`）、確定後は `status: result` が返り、いずれも実数で取得できる。三連複・三連単も 1 リクエストで全通り取得する。
```

- [ ] **Step 2: 注意事項の「確定が最終」記述を更新**

`.claude/skills/netkeiba-scraper/SKILL.md` の注意事項にある:

```
- オッズはリアルタイムで変動するため、発走直前が最終オッズ
```

を以下に置換:

```
- オッズはリアルタイムで変動する。`get_odds.py` / `snapshot_odds.py` の出力 `odds_status` で `middle`（暫定）か `result`（確定）かを判別できる
```

- [ ] **Step 3: snapshot_odds.py セクションの表現を調整**

`.claude/skills/netkeiba-scraper/SKILL.md` の snapshot_odds.py セクション末尾:

```
発走後はオッズが消えるため、**発走 5〜10 分前** にスナップ保存することがバックテストの精度に直結する。
```

を以下に置換:

```
`/keiba` 予想時に予想時点オッズが自動保存されるため、通常このスクリプトを手動実行する必要はない。より発走に近いオッズで `.odds.json` を上書きしたい場合の任意手段として使う。出力 `.odds.json` には `odds_status` が含まれる。
```

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/netkeiba-scraper/SKILL.md
git commit -m "docs: update netkeiba-scraper SKILL for JSON API odds"
```

---

## Task 9: CLAUDE.md の作業フローを更新

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: 作業フローの段階を更新**

`CLAUDE.md` の「### 予想 → 結果照合 → 集計の 4 ステップ」の項目1に、`.odds.json` 自動生成を追記する。項目1の既存サブ箇条書き:

```
   - `reports/yyyymmdd_<レース名>.md` (人間用) と `.json` (機械用) を並置出力
```

を以下に置換:

```
   - `reports/yyyymmdd_<レース名>.md` (人間用)・`.json` (機械用)・`.odds.json` (予想時点の全馬券種オッズ) を並置出力
```

- [ ] **Step 2: 項目2を「任意」に格下げ**

`CLAUDE.md` の項目2全体:

```
2. **直前オッズスナップショット**: 発走 5〜10 分前に `python3 .claude/skills/netkeiba-scraper/scripts/snapshot_odds.py <race_id>` を実行
   - 全 7 馬券種の確定オッズを `reports/yyyymmdd_<レース名>.odds.json` に保存
   - **発走後はオッズが消えるためこのタイミングが必須**
```

を以下に置換:

```
2. **（任意）直前オッズで上書き**: `/keiba` 予想時に `.odds.json` が自動生成されるため通常は不要。より発走に近いオッズで上書きしたい場合のみ `python3 .claude/skills/netkeiba-scraper/scripts/snapshot_odds.py <race_id>` を実行
   - 全 7 馬券種のオッズ（`odds_status` 付き）を `reports/yyyymmdd_<レース名>.odds.json` に保存
```

- [ ] **Step 3: バックテストの払戻計算の前提を確認**

`CLAUDE.md` の項目3（結果照合）の記述はそのままで整合する（払戻計算は `.odds.json` 優先・払戻金フォールバック）。変更不要であることを確認する。

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: demote pre-post odds snapshot to optional in workflow"
```

---

## Task 10: 最終確認

- [ ] **Step 1: 全テスト実行**

Run: `source venv/bin/activate && pytest tests/ -v`
Expected: 全 PASS（既存 + `test_get_odds.py` の 8 件）。

- [ ] **Step 2: エンドツーエンドのオッズ取得を確認**

Run: `python3 .claude/skills/netkeiba-scraper/scripts/get_odds.py 202605030411 --type all 2>&1 | head -30`
Expected: 単勝・複勝・馬連・ワイド・馬単・三連複すべてで `---.-` でなく実数オッズが表示される。

- [ ] **Step 3: 差分レビュー**

Run: `git log --oneline main..HEAD` と `git diff main --stat`
Expected: Task 1-9 のコミットが並び、変更ファイルが File Structure の一覧と一致する。
