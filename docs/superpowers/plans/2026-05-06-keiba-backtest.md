# 競馬バックテスト機能 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 予想 → 直前オッズスナップショット → 結果照合 → 集計 の 4 ステップを通じて、今後のレースで的中率・回収率をログ可能にする。

**Architecture:** バックテスト固有のロジックは `_backtest_helpers.py` の純関数に閉じ込め pytest でテスト。Markdown / JSON / CSV のファイル I/O とネットワーク取得は別スクリプト・コマンドが担当。データは `reports/` 配下の単一プレフィックス（`yyyymmdd_<レース名>`）で紐付ける。

**Tech Stack:** Python 3.12, requests, beautifulsoup4, lxml, pytest, json, csv（標準ライブラリ）

**設計書:** `docs/superpowers/specs/2026-05-06-keiba-backtest-design.md`

---

## 重要な前提

- **Python 環境**: venv の pip が壊れているため、すべての pytest 実行・スクリプト実行で以下を付与:
  ```
  PYTHONPATH=/workspace/venv/lib/python3.12/site-packages
  ```
- **conftest.py は既存**（`tests/conftest.py`）。`_backtest_helpers.py` は `.claude/skills/netkeiba-scraper/scripts/` に置くので import 可能。
- **ネットワークアクセスを伴うテストは書かない**。`_backtest_helpers.py` は純関数で固定データテストのみ。
- **TDD はヘルパーに適用**。コマンドファイル（Markdown）はドキュメントなので「書く → セルフチェック → コミット」のサイクル。
- **コミット粒度**: 1 タスク = 1 コミット（テストとコードを同コミットにまとめてよい）

## File Structure

```
.claude/
├── commands/
│   ├── keiba.md                            # 既存（Task 11 で参照を追記）
│   ├── keiba-result.md                     # 新設（Task 8）
│   └── keiba-backtest-summary.md           # 新設（Task 9）
└── skills/
    ├── netkeiba-scraper/
    │   └── scripts/
    │       ├── _backtest_helpers.py        # 新設（Task 1-5）
    │       ├── snapshot_odds.py            # 新設（Task 6）
    │       └── match_result.py             # 新設（Task 7）
    └── keiba-prediction/
        └── SKILL.md                        # 修正（Task 10：段階9にJSON出力追記）

CLAUDE.md                                   # 修正（Task 11）

tests/
└── test_backtest_helpers.py                # 新設（Task 1-5 で順次拡張）

reports/                                    # gitignored、新ファイルが生成される
├── yyyymmdd_<レース名>.md
├── yyyymmdd_<レース名>.json                # /keiba が出力
├── yyyymmdd_<レース名>.odds.json           # snapshot_odds.py が出力
├── _backtest_log.csv                       # match_result.py が追記
└── _backtest_summary.md                    # /keiba-backtest-summary が再生成
```

各ファイルの責務:
- `_backtest_helpers.py`: 純関数（パース・的中判定・払戻計算・集計）
- `snapshot_odds.py`: 既存の `get_odds.py` の関数を import してオッズを JSON 化
- `match_result.py`: 結果取得 + ヘルパー呼び出し + Markdown 追記 + CSV 追記
- `keiba-result.md`, `keiba-backtest-summary.md`: コマンド入口（Claude が読む手順書）

---

## Task 1: parse_combination — 馬券買い目文字列のパース

**目的:** 「1-3-5」「1→3→5」のような買い目文字列を馬番タプルに変換する純関数を実装する。

**Files:**
- Create: `tests/test_backtest_helpers.py`
- Create: `.claude/skills/netkeiba-scraper/scripts/_backtest_helpers.py`

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_backtest_helpers.py
import pytest
from _backtest_helpers import parse_combination


def test_parse_combination_sanrenpuku_unordered():
    """三連複は順不同・ソート済みタプルを返す"""
    assert parse_combination("1-3-5", "sanrenpuku") == (1, 3, 5)
    assert parse_combination("5-1-3", "sanrenpuku") == (1, 3, 5)


def test_parse_combination_sanrentan_ordered():
    """三連単は順序保持タプルを返す"""
    assert parse_combination("1→3→5", "sanrentan") == (1, 3, 5)
    assert parse_combination("5→1→3", "sanrentan") == (5, 1, 3)


def test_parse_combination_umaren_unordered():
    """馬連は順不同"""
    assert parse_combination("1-3", "umaren") == (1, 3)
    assert parse_combination("3-1", "umaren") == (1, 3)


def test_parse_combination_umatan_ordered():
    """馬単は順序保持"""
    assert parse_combination("1→3", "umatan") == (1, 3)
    assert parse_combination("3→1", "umatan") == (3, 1)


def test_parse_combination_wide_unordered():
    """ワイドは順不同（2 頭）"""
    assert parse_combination("1-3", "wide") == (1, 3)
    assert parse_combination("3-1", "wide") == (1, 3)


def test_parse_combination_tansho_single():
    """単勝は単一馬番"""
    assert parse_combination("7", "tansho") == (7,)


def test_parse_combination_fukusho_single():
    """複勝は単一馬番"""
    assert parse_combination("7", "fukusho") == (7,)


def test_parse_combination_invalid_raises():
    """不正な馬券種はエラー"""
    with pytest.raises(ValueError, match="不正な bet_type"):
        parse_combination("1-3-5", "invalid_type")
```

- [ ] **Step 2: テスト実行で失敗確認**

```bash
cd /workspace
PYTHONPATH=/workspace/venv/lib/python3.12/site-packages python3 -m pytest tests/test_backtest_helpers.py -v
```

期待: `ImportError: cannot import name 'parse_combination'` で失敗。

- [ ] **Step 3: 最小実装**

`.claude/skills/netkeiba-scraper/scripts/_backtest_helpers.py` を新規作成:

```python
"""
バックテスト用ヘルパー関数群（純関数）。
予想スキルや結果照合スクリプトから利用される。
ネットワーク I/O は持たないので pytest で完結する。
"""

from __future__ import annotations


_UNORDERED_TYPES = {"tansho", "fukusho", "wide", "umaren", "sanrenpuku"}
_ORDERED_TYPES = {"umatan", "sanrentan"}
_SINGLE_HORSE_TYPES = {"tansho", "fukusho"}


def parse_combination(combination: str, bet_type: str) -> tuple:
    """
    買い目文字列を馬番タプルに変換する。

    順不同馬券（馬連・三連複・ワイド）は昇順にソート。
    順序保持馬券（馬単・三連単）は元の順序を保つ。
    単勝・複勝は単一馬番。

    Args:
        combination: "1-3-5" または "1→3→5" 形式の文字列
        bet_type: 馬券種 (tansho / fukusho / wide / umaren / umatan / sanrenpuku / sanrentan)

    Returns:
        馬番のタプル

    Raises:
        ValueError: bet_type が未知の場合
    """
    if bet_type not in _UNORDERED_TYPES and bet_type not in _ORDERED_TYPES:
        raise ValueError(f"不正な bet_type: {bet_type}")

    if bet_type in _SINGLE_HORSE_TYPES:
        return (int(combination),)

    sep = "→" if "→" in combination else "-"
    nums = tuple(int(x) for x in combination.split(sep))

    if bet_type in _UNORDERED_TYPES:
        return tuple(sorted(nums))
    return nums
```

- [ ] **Step 4: テスト実行で成功確認**

```bash
PYTHONPATH=/workspace/venv/lib/python3.12/site-packages python3 -m pytest tests/test_backtest_helpers.py -v
```

期待: 8 件 PASS。

- [ ] **Step 5: コミット**

```bash
git add tests/test_backtest_helpers.py \
        .claude/skills/netkeiba-scraper/scripts/_backtest_helpers.py
git commit -m "feat: add parse_combination for bet ticket strings"
```

---

## Task 2: is_winning_bet — 各馬券種の的中判定

**目的:** 買い目と着順から的中・外れを判定する純関数を追加する。

**Files:**
- Modify: `tests/test_backtest_helpers.py`
- Modify: `.claude/skills/netkeiba-scraper/scripts/_backtest_helpers.py`

- [ ] **Step 1: 失敗するテストを追記**

`tests/test_backtest_helpers.py` の末尾に追加:

```python
from _backtest_helpers import is_winning_bet


# テスト用：1着=7, 2着=12, 3着=3
RESULT_7_12_3 = [7, 12, 3]


def test_is_winning_bet_tansho_hit():
    assert is_winning_bet("7", "tansho", RESULT_7_12_3) is True


def test_is_winning_bet_tansho_miss():
    assert is_winning_bet("3", "tansho", RESULT_7_12_3) is False


def test_is_winning_bet_fukusho_hit_in_third():
    assert is_winning_bet("3", "fukusho", RESULT_7_12_3) is True


def test_is_winning_bet_fukusho_miss():
    assert is_winning_bet("9", "fukusho", RESULT_7_12_3) is False


def test_is_winning_bet_wide_two_in_top3():
    assert is_winning_bet("7-12", "wide", RESULT_7_12_3) is True
    assert is_winning_bet("3-12", "wide", RESULT_7_12_3) is True
    assert is_winning_bet("7-3", "wide", RESULT_7_12_3) is True


def test_is_winning_bet_wide_miss():
    assert is_winning_bet("7-9", "wide", RESULT_7_12_3) is False


def test_is_winning_bet_umaren_hit():
    assert is_winning_bet("7-12", "umaren", RESULT_7_12_3) is True
    assert is_winning_bet("12-7", "umaren", RESULT_7_12_3) is True


def test_is_winning_bet_umaren_miss_third_place():
    """3 着とは当たらない"""
    assert is_winning_bet("7-3", "umaren", RESULT_7_12_3) is False


def test_is_winning_bet_umatan_order_matters():
    assert is_winning_bet("7→12", "umatan", RESULT_7_12_3) is True
    assert is_winning_bet("12→7", "umatan", RESULT_7_12_3) is False


def test_is_winning_bet_sanrenpuku_hit():
    assert is_winning_bet("7-12-3", "sanrenpuku", RESULT_7_12_3) is True
    assert is_winning_bet("3-7-12", "sanrenpuku", RESULT_7_12_3) is True


def test_is_winning_bet_sanrenpuku_miss():
    assert is_winning_bet("7-12-9", "sanrenpuku", RESULT_7_12_3) is False


def test_is_winning_bet_sanrentan_order_matters():
    assert is_winning_bet("7→12→3", "sanrentan", RESULT_7_12_3) is True
    assert is_winning_bet("3→12→7", "sanrentan", RESULT_7_12_3) is False
```

- [ ] **Step 2: テスト実行で失敗確認**

```bash
PYTHONPATH=/workspace/venv/lib/python3.12/site-packages python3 -m pytest tests/test_backtest_helpers.py -v
```

期待: 既存 8 件 PASS、新規 13 件 ImportError で失敗。

- [ ] **Step 3: 実装を追記**

`_backtest_helpers.py` の末尾に追加:

```python
def is_winning_bet(combination: str, bet_type: str, result: list[int]) -> bool:
    """
    買い目が当たりかを判定する。

    Args:
        combination: 買い目文字列
        bet_type: 馬券種
        result: 着順リスト [1着馬番, 2着馬番, 3着馬番]

    Returns:
        当たりなら True
    """
    parsed = parse_combination(combination, bet_type)
    first, second, third = result[0], result[1], result[2]

    if bet_type == "tansho":
        return parsed[0] == first

    if bet_type == "fukusho":
        return parsed[0] in (first, second, third)

    if bet_type == "wide":
        return set(parsed).issubset({first, second, third})

    if bet_type == "umaren":
        return set(parsed) == {first, second}

    if bet_type == "umatan":
        return parsed == (first, second)

    if bet_type == "sanrenpuku":
        return set(parsed) == {first, second, third}

    if bet_type == "sanrentan":
        return parsed == (first, second, third)

    return False
```

- [ ] **Step 4: テスト実行で成功確認**

```bash
PYTHONPATH=/workspace/venv/lib/python3.12/site-packages python3 -m pytest tests/test_backtest_helpers.py -v
```

期待: 21 件 PASS。

- [ ] **Step 5: コミット**

```bash
git add tests/test_backtest_helpers.py \
        .claude/skills/netkeiba-scraper/scripts/_backtest_helpers.py
git commit -m "feat: add is_winning_bet for hit/miss judgment"
```

---

## Task 3: compute_payout — 1 つの買い目の払戻計算

**目的:** 1 件の買い目に対して、オッズスナップ優先・払戻金フォールバックで払戻額を計算する純関数を追加する。

**Files:**
- Modify: `tests/test_backtest_helpers.py`
- Modify: `.claude/skills/netkeiba-scraper/scripts/_backtest_helpers.py`

- [ ] **Step 1: 失敗するテストを追記**

`tests/test_backtest_helpers.py` の末尾に追加:

```python
from _backtest_helpers import compute_payout


def test_compute_payout_miss_returns_zero():
    """外れなら 0 円"""
    bet = {"combination": "9", "amount": 1000, "bet_type": "tansho"}
    assert compute_payout(bet, None, [7, 12, 3], []) == 0


def test_compute_payout_uses_odds_snapshot_when_available():
    """オッズスナップがあれば amount × odds で計算"""
    bet = {"combination": "7", "amount": 1000, "bet_type": "tansho"}
    odds = {"tansho": [{"num": "7", "odds": "2.4"}]}
    # 1000 円 × 2.4 = 2400 円
    assert compute_payout(bet, odds, [7, 12, 3], []) == 2400


def test_compute_payout_uses_payoffs_when_no_odds():
    """オッズスナップなしなら払戻金（100 円当たり）をスケール"""
    bet = {"combination": "7", "amount": 600, "bet_type": "tansho"}
    payoffs = [{"ticket": "単勝", "nums": "7", "amount": 240}]
    # 600 円 × (240 / 100) = 1440 円
    assert compute_payout(bet, None, [7, 12, 3], payoffs) == 1440


def test_compute_payout_wide_uses_lower_bound():
    """ワイドの範囲オッズは下限を採用"""
    bet = {"combination": "7-12", "amount": 1000, "bet_type": "wide"}
    odds = {"wide": [{"combination": "7-12", "odds_low": "3.2", "odds_high": "4.5"}]}
    # 1000 円 × 3.2 = 3200 円
    assert compute_payout(bet, odds, [7, 12, 3], []) == 3200


def test_compute_payout_sanrenpuku_combination_normalized():
    """三連複オッズ検索時に combination を正規化（順不同で一致）"""
    bet = {"combination": "12-7-3", "amount": 600, "bet_type": "sanrenpuku"}
    odds = {"sanrenpuku": [{"combination": "3-7-12", "odds": "12.4"}]}
    # 600 円 × 12.4 = 7440 円
    assert compute_payout(bet, odds, [7, 12, 3], []) == 7440


def test_compute_payout_no_match_returns_zero_with_warning_data():
    """当たりなのにオッズも払戻もない場合は 0 円（データ不整合）"""
    bet = {"combination": "7", "amount": 1000, "bet_type": "tansho"}
    assert compute_payout(bet, {"tansho": []}, [7, 12, 3], []) == 0
```

- [ ] **Step 2: テスト実行で失敗確認**

```bash
PYTHONPATH=/workspace/venv/lib/python3.12/site-packages python3 -m pytest tests/test_backtest_helpers.py -v
```

期待: 既存 21 件 PASS、新規 6 件 ImportError で失敗。

- [ ] **Step 3: 実装を追記**

`_backtest_helpers.py` の末尾に追加:

```python
def _normalize_combination_for_lookup(combination: str, bet_type: str) -> str:
    """オッズ検索キーとして使える正規化文字列を返す。"""
    if bet_type in _SINGLE_HORSE_TYPES:
        return combination
    parsed = parse_combination(combination, bet_type)
    if bet_type in _ORDERED_TYPES:
        return "→".join(str(n) for n in parsed)
    return "-".join(str(n) for n in parsed)


def _payoff_ticket_label(bet_type: str) -> str:
    """payoffs テーブルでの日本語チケット名"""
    return {
        "tansho": "単勝",
        "fukusho": "複勝",
        "wide": "ワイド",
        "umaren": "馬連",
        "umatan": "馬単",
        "sanrenpuku": "3連複",
        "sanrentan": "3連単",
    }[bet_type]


def compute_payout(bet: dict, odds_snapshot: dict | None,
                   result: list[int], payoffs: list[dict]) -> int:
    """
    1 つの買い目の払戻額を計算する。

    優先順位:
      1. 当たりでなければ 0 円
      2. odds_snapshot に該当倍率があれば amount × 倍率
      3. なければ payoffs（100 円当たり）を用いて amount/100 × 払戻金

    Args:
        bet: {"combination", "amount", "bet_type"}
        odds_snapshot: snapshot_odds.py が保存した辞書、または None
        result: [1着, 2着, 3着] の馬番リスト
        payoffs: get_race_result.py の払戻金リスト

    Returns:
        払戻額（整数円）
    """
    bet_type = bet["bet_type"]
    combo = bet["combination"]
    amount = int(bet["amount"])

    if not is_winning_bet(combo, bet_type, result):
        return 0

    # オッズスナップから探す
    if odds_snapshot:
        normalized = _normalize_combination_for_lookup(combo, bet_type)
        for entry in odds_snapshot.get(bet_type, []):
            if bet_type in _SINGLE_HORSE_TYPES:
                key = entry.get("num", "")
            else:
                key = entry.get("combination", "")
            if key == normalized:
                odds_str = entry.get("odds_low") or entry.get("odds")
                try:
                    return int(amount * float(odds_str))
                except (TypeError, ValueError):
                    pass

    # 払戻金からフォールバック
    label = _payoff_ticket_label(bet_type)
    for p in payoffs:
        if p.get("ticket") != label:
            continue
        # nums は "7" や "7-3-12" など。combination と数値集合で照合
        try:
            payoff_combo = parse_combination(p["nums"], bet_type)
            bet_combo = parse_combination(combo, bet_type)
            if payoff_combo == bet_combo:
                payback = int(p["amount"])
                return amount * payback // 100
        except (ValueError, KeyError):
            continue

    return 0
```

- [ ] **Step 4: テスト実行で成功確認**

```bash
PYTHONPATH=/workspace/venv/lib/python3.12/site-packages python3 -m pytest tests/test_backtest_helpers.py -v
```

期待: 27 件 PASS。

- [ ] **Step 5: コミット**

```bash
git add tests/test_backtest_helpers.py \
        .claude/skills/netkeiba-scraper/scripts/_backtest_helpers.py
git commit -m "feat: add compute_payout with odds-snap and payoff fallback"
```

---

## Task 4: compute_race_pnl — 1 レースの損益集計

**目的:** 買い目 JSON・オッズ JSON・結果から 1 レースの損益を計算する関数を追加する。

**Files:**
- Modify: `tests/test_backtest_helpers.py`
- Modify: `.claude/skills/netkeiba-scraper/scripts/_backtest_helpers.py`

- [ ] **Step 1: 失敗するテストを追記**

```python
from _backtest_helpers import compute_race_pnl


def _make_bets_json(bet_type, bets):
    return {"race_id": "X", "bet_type": bet_type, "budget": 10000, "bets": bets}


def test_compute_race_pnl_all_miss():
    """全外れ"""
    bets = _make_bets_json("tansho", [
        {"combination": "9", "amount": 500},
        {"combination": "11", "amount": 500},
    ])
    result = {"results": [
        {"chakujun": "1", "umaban": "7"},
        {"chakujun": "2", "umaban": "12"},
        {"chakujun": "3", "umaban": "3"},
    ], "payoffs": []}
    pnl = compute_race_pnl(bets, None, result)
    assert pnl["total_invested"] == 1000
    assert pnl["total_payout"] == 0
    assert pnl["profit"] == -1000
    assert pnl["roi"] == 0.0
    assert len(pnl["winning_bets"]) == 0
    assert len(pnl["losing_bets"]) == 2


def test_compute_race_pnl_one_hit_with_odds():
    """1 点的中（オッズスナップ使用）"""
    bets = _make_bets_json("sanrenpuku", [
        {"combination": "7-12-3", "amount": 600},
        {"combination": "7-12-1", "amount": 400},
    ])
    odds = {"sanrenpuku": [{"combination": "3-7-12", "odds": "12.4"}]}
    result = {"results": [
        {"chakujun": "1", "umaban": "7"},
        {"chakujun": "2", "umaban": "12"},
        {"chakujun": "3", "umaban": "3"},
    ], "payoffs": []}
    pnl = compute_race_pnl(bets, odds, result)
    assert pnl["total_invested"] == 1000
    assert pnl["total_payout"] == 7440
    assert pnl["profit"] == 6440
    assert pnl["roi"] == 7.44
    assert len(pnl["winning_bets"]) == 1
    assert len(pnl["losing_bets"]) == 1


def test_compute_race_pnl_uses_payoffs_when_no_odds():
    """オッズ無 → 払戻金フォールバック"""
    bets = _make_bets_json("tansho", [{"combination": "7", "amount": 1000}])
    payoffs = [{"ticket": "単勝", "nums": "7", "amount": 240}]
    result = {"results": [
        {"chakujun": "1", "umaban": "7"},
        {"chakujun": "2", "umaban": "12"},
        {"chakujun": "3", "umaban": "3"},
    ], "payoffs": payoffs}
    pnl = compute_race_pnl(bets, None, result)
    assert pnl["total_invested"] == 1000
    assert pnl["total_payout"] == 2400
    assert pnl["profit"] == 1400
    assert pnl["roi"] == 2.4


def test_compute_race_pnl_skips_dead_heat():
    """同着で 1-3 着が 4 件以上 → ValueError"""
    bets = _make_bets_json("tansho", [{"combination": "7", "amount": 1000}])
    result = {"results": [
        {"chakujun": "1", "umaban": "7"},
        {"chakujun": "2", "umaban": "12"},
        {"chakujun": "2", "umaban": "5"},  # 2 着同着
        {"chakujun": "3", "umaban": "3"},
    ], "payoffs": []}
    import pytest
    with pytest.raises(ValueError, match="同着"):
        compute_race_pnl(bets, None, result)
```

- [ ] **Step 2: テスト実行で失敗確認**

```bash
PYTHONPATH=/workspace/venv/lib/python3.12/site-packages python3 -m pytest tests/test_backtest_helpers.py -v
```

期待: 既存 27 件 PASS、新規 4 件 ImportError で失敗。

- [ ] **Step 3: 実装を追記**

`_backtest_helpers.py` の末尾に追加:

```python
def _extract_top3(result: dict) -> list[int]:
    """着順テーブルから 1-3 着の馬番を取り出す（同着あれば ValueError）。"""
    top3 = []
    seen_chakujun = set()
    for r in result.get("results", []):
        try:
            chakujun = int(r["chakujun"])
        except (ValueError, KeyError):
            continue
        if chakujun > 3:
            continue
        if chakujun in seen_chakujun:
            raise ValueError(f"同着のため集計不可: {chakujun} 着")
        seen_chakujun.add(chakujun)
        try:
            top3.append((chakujun, int(r["umaban"])))
        except (ValueError, KeyError):
            continue
    if len(top3) < 3:
        raise ValueError("1-3 着の着順が揃っていません")
    top3.sort(key=lambda x: x[0])
    return [t[1] for t in top3]


def compute_race_pnl(bets_json: dict, odds_json: dict | None,
                     result: dict) -> dict:
    """
    1 レースの損益を計算する。

    Args:
        bets_json: 買い目 JSON の辞書（"bet_type", "bets" を含む）
        odds_json: オッズスナップの辞書、または None
        result: get_race_result.py の出力（"results", "payoffs"）

    Returns:
        {"total_invested", "total_payout", "profit", "roi",
         "winning_bets", "losing_bets"}

    Raises:
        ValueError: 同着で 1-3 着が判定できない場合
    """
    top3 = _extract_top3(result)
    bet_type = bets_json["bet_type"]
    payoffs = result.get("payoffs", [])

    total_invested = 0
    total_payout = 0
    winners: list[dict] = []
    losers: list[dict] = []

    for raw in bets_json.get("bets", []):
        bet = {"combination": raw["combination"],
               "amount": raw["amount"],
               "bet_type": bet_type}
        total_invested += int(raw["amount"])
        payout = compute_payout(bet, odds_json, top3, payoffs)
        total_payout += payout
        record = {**raw, "payout": payout}
        if payout > 0:
            winners.append(record)
        else:
            losers.append(record)

    roi = round(total_payout / total_invested, 2) if total_invested else 0.0
    profit = total_payout - total_invested

    return {
        "total_invested": total_invested,
        "total_payout": total_payout,
        "profit": profit,
        "roi": roi,
        "winning_bets": winners,
        "losing_bets": losers,
    }
```

- [ ] **Step 4: テスト実行で成功確認**

```bash
PYTHONPATH=/workspace/venv/lib/python3.12/site-packages python3 -m pytest tests/test_backtest_helpers.py -v
```

期待: 31 件 PASS。

- [ ] **Step 5: コミット**

```bash
git add tests/test_backtest_helpers.py \
        .claude/skills/netkeiba-scraper/scripts/_backtest_helpers.py
git commit -m "feat: add compute_race_pnl for race-level P&L"
```

---

## Task 5: aggregate_log — CSV ログから集計

**目的:** CSV ログ行から全期間 / 馬券種別 / スタイル別の集計を計算する関数を追加する。

**Files:**
- Modify: `tests/test_backtest_helpers.py`
- Modify: `.claude/skills/netkeiba-scraper/scripts/_backtest_helpers.py`

- [ ] **Step 1: 失敗するテストを追記**

```python
from _backtest_helpers import aggregate_log


def _make_log_row(**kwargs):
    base = {
        "race_id": "X", "race_date": "2026-04-01", "race_name": "テスト",
        "bet_type": "sanrenpuku", "style": "balanced", "budget": "10000",
        "total_invested": "10000", "total_payout": "5000",
        "profit": "-5000", "roi": "0.50",
    }
    base.update(kwargs)
    return base


def test_aggregate_log_overall_two_races():
    rows = [
        _make_log_row(total_invested="10000", total_payout="7000",
                      profit="-3000", roi="0.70"),
        _make_log_row(total_invested="2000", total_payout="4000",
                      profit="2000", roi="2.00"),
    ]
    agg = aggregate_log(rows)
    assert agg["overall"]["races"] == 2
    assert agg["overall"]["invested"] == 12000
    assert agg["overall"]["payout"] == 11000
    assert agg["overall"]["profit"] == -1000
    assert agg["overall"]["roi"] == 0.92
    assert agg["overall"]["hit_races"] == 1
    assert agg["overall"]["hit_rate"] == 0.5


def test_aggregate_log_by_bet_type():
    rows = [
        _make_log_row(bet_type="sanrenpuku", total_invested="10000",
                      total_payout="7000", profit="-3000", roi="0.70"),
        _make_log_row(bet_type="umaren", total_invested="2000",
                      total_payout="4000", profit="2000", roi="2.00"),
        _make_log_row(bet_type="umaren", total_invested="3000",
                      total_payout="0", profit="-3000", roi="0.00"),
    ]
    agg = aggregate_log(rows)
    assert agg["by_bet_type"]["sanrenpuku"]["races"] == 1
    assert agg["by_bet_type"]["umaren"]["races"] == 2
    assert agg["by_bet_type"]["umaren"]["invested"] == 5000
    assert agg["by_bet_type"]["umaren"]["payout"] == 4000


def test_aggregate_log_by_style():
    rows = [
        _make_log_row(style="balanced", total_invested="10000",
                      total_payout="7000", profit="-3000", roi="0.70"),
        _make_log_row(style="longshot", total_invested="2000",
                      total_payout="4000", profit="2000", roi="2.00"),
    ]
    agg = aggregate_log(rows)
    assert agg["by_style"]["balanced"]["races"] == 1
    assert agg["by_style"]["longshot"]["races"] == 1
    assert agg["by_style"]["longshot"]["profit"] == 2000


def test_aggregate_log_empty():
    """空リストでも落ちない"""
    agg = aggregate_log([])
    assert agg["overall"]["races"] == 0
    assert agg["overall"]["invested"] == 0
    assert agg["overall"]["roi"] == 0.0
    assert agg["overall"]["hit_rate"] == 0.0
    assert agg["by_bet_type"] == {}
    assert agg["by_style"] == {}
```

- [ ] **Step 2: テスト実行で失敗確認**

```bash
PYTHONPATH=/workspace/venv/lib/python3.12/site-packages python3 -m pytest tests/test_backtest_helpers.py -v
```

期待: 既存 31 件 PASS、新規 4 件 ImportError で失敗。

- [ ] **Step 3: 実装を追記**

`_backtest_helpers.py` の末尾に追加:

```python
def _summarize(rows: list[dict]) -> dict:
    """1 グループの集計を返す。"""
    races = len(rows)
    invested = sum(int(r["total_invested"]) for r in rows)
    payout = sum(int(r["total_payout"]) for r in rows)
    profit = payout - invested
    roi = round(payout / invested, 2) if invested else 0.0
    hit_races = sum(1 for r in rows if int(r["profit"]) > 0)
    hit_rate = round(hit_races / races, 2) if races else 0.0
    return {
        "races": races,
        "invested": invested,
        "payout": payout,
        "profit": profit,
        "roi": roi,
        "hit_races": hit_races,
        "hit_rate": hit_rate,
    }


def aggregate_log(log_rows: list[dict]) -> dict:
    """
    CSV ログ行から集計を計算する。

    Args:
        log_rows: 各行が race_id / race_date / bet_type / style /
                  total_invested / total_payout / profit / roi 等のキーを持つ dict

    Returns:
        {"overall": {...}, "by_bet_type": {...}, "by_style": {...}}
    """
    by_bet_type: dict[str, list[dict]] = {}
    by_style: dict[str, list[dict]] = {}

    for row in log_rows:
        by_bet_type.setdefault(row["bet_type"], []).append(row)
        by_style.setdefault(row["style"], []).append(row)

    return {
        "overall": _summarize(log_rows),
        "by_bet_type": {k: _summarize(v) for k, v in by_bet_type.items()},
        "by_style": {k: _summarize(v) for k, v in by_style.items()},
    }
```

- [ ] **Step 4: テスト実行で成功確認**

```bash
PYTHONPATH=/workspace/venv/lib/python3.12/site-packages python3 -m pytest tests/test_backtest_helpers.py -v
```

期待: 35 件 PASS。

- [ ] **Step 5: コミット**

```bash
git add tests/test_backtest_helpers.py \
        .claude/skills/netkeiba-scraper/scripts/_backtest_helpers.py
git commit -m "feat: add aggregate_log for backtest summary stats"
```

---

## Task 6: snapshot_odds.py — オッズスナップショット保存

**目的:** 発走直前にオッズを取得し JSON で保存するスクリプトを作成する。

**Files:**
- Create: `.claude/skills/netkeiba-scraper/scripts/snapshot_odds.py`
- Modify: `.claude/skills/netkeiba-scraper/SKILL.md`（機能テーブルに追記）

- [ ] **Step 1: snapshot_odds.py を作成**

`.claude/skills/netkeiba-scraper/scripts/snapshot_odds.py`:

```python
#!/usr/bin/env python3
"""
発走直前のオッズを取得し JSON ファイルに保存する。

使用例:
  python3 snapshot_odds.py 202608030411
  python3 snapshot_odds.py --basename 20260503_天皇賞春 202608030411

保存先:
  reports/<basename>.odds.json

basename が省略された場合は reports/ 内で同 race_id の予想 JSON を探し、
その basename を流用する。見つからない場合はエラー。
"""

import sys
import os
import json
import glob
import time
import argparse
from datetime import datetime, timezone, timedelta

import get_odds


JST = timezone(timedelta(hours=9))


def find_basename_from_reports(race_id: str, reports_dir: str) -> str | None:
    """reports/ 内の予想 JSON から同 race_id のものを探し basename を返す"""
    for path in glob.glob(os.path.join(reports_dir, "*.json")):
        if path.endswith(".odds.json"):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("race_id") == race_id:
                base = os.path.basename(path)
                return base[:-5]  # .json を除く
        except (json.JSONDecodeError, OSError):
            continue
    return None


def fetch_all_odds(race_id: str, head_count: int = 18) -> dict:
    """全馬券種のオッズを取得して 1 つの dict に集約する"""
    snapshot = {
        "race_id": race_id,
        "snapshot_at": datetime.now(JST).isoformat(),
    }

    # 単勝・複勝
    tf = get_odds.fetch_tansho_fukusho(race_id)
    snapshot["tansho"] = tf.get("tansho", [])
    snapshot["fukusho"] = tf.get("fukusho", [])
    time.sleep(0.5)

    # 馬連 (b4) / ワイド (b5) / 馬単 (b6)
    for bet_key, type_param in [("umaren", "b4"), ("wide", "b5"), ("umatan", "b6")]:
        rows = get_odds.fetch_combined_odds(race_id, type_param)
        if bet_key == "wide":
            snapshot[bet_key] = [
                {"combination": f"{r[0]}-{r[1]}", "odds_low": r[2], "odds_high": r[2]}
                for r in rows
            ]
        elif bet_key == "umatan":
            snapshot[bet_key] = [
                {"combination": f"{r[0]}→{r[1]}", "odds": r[2]}
                for r in rows
            ]
        else:  # umaren
            snapshot[bet_key] = [
                {"combination": f"{r[0]}-{r[1]}", "odds": r[2]}
                for r in rows
            ]
        time.sleep(0.5)

    # 三連複 (b7)
    rows = get_odds.fetch_sanren_odds(race_id, "b7", head_count)
    snapshot["sanrenpuku"] = [
        {"combination": f"{r[0]}-{r[1]}-{r[2]}", "odds": r[3]} for r in rows
    ]
    time.sleep(0.5)

    # 三連単 (b8)
    rows = get_odds.fetch_sanren_odds(race_id, "b8", head_count)
    snapshot["sanrentan"] = [
        {"combination": f"{r[0]}→{r[1]}→{r[2]}", "odds": r[3]} for r in rows
    ]

    return snapshot


def main():
    parser = argparse.ArgumentParser(description="オッズスナップショットを保存")
    parser.add_argument("race_id", help="レース ID (12 桁)")
    parser.add_argument("--basename", help="ファイル名のベース (例: 20260503_天皇賞春)")
    parser.add_argument("--reports-dir", default="reports", help="保存先ディレクトリ")
    parser.add_argument("--head-count", type=int, default=18,
                        help="出走頭数（3 連複・3 連単のスキャン上限）")
    args = parser.parse_args()

    if len(args.race_id) != 12 or not args.race_id.isdigit():
        print("エラー: レース ID は 12 桁の数字です")
        sys.exit(1)

    basename = args.basename
    if not basename:
        basename = find_basename_from_reports(args.race_id, args.reports_dir)
        if not basename:
            print(f"エラー: reports/ に race_id {args.race_id} の予想 JSON が見つかりません。")
            print("  --basename で明示的にファイル名を指定するか、先に /keiba で予想を立ててください。")
            sys.exit(1)
        print(f"basename を予想 JSON から取得: {basename}")

    print(f"オッズを取得中... (race_id: {args.race_id})")
    snapshot = fetch_all_odds(args.race_id, args.head_count)

    os.makedirs(args.reports_dir, exist_ok=True)
    out_path = os.path.join(args.reports_dir, f"{basename}.odds.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    counts = {k: len(v) for k, v in snapshot.items()
              if isinstance(v, list)}
    print(f"オッズ保存完了: {out_path}")
    print(f"  件数: {counts}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 動作確認（実行可能性のスモークテスト）**

```bash
cd /workspace
PYTHONPATH=/workspace/venv/lib/python3.12/site-packages python3 .claude/skills/netkeiba-scraper/scripts/snapshot_odds.py --help
```

期待: argparse のヘルプメッセージが表示される。

注意: 実レースでの取得テストは Task 12 の end-to-end フェーズで行う（過去レースはオッズが消失しているため）。

- [ ] **Step 3: SKILL.md の機能テーブルに追記**

`.claude/skills/netkeiba-scraper/SKILL.md` の機能選択テーブルに行を追加。既存テーブルの最終行（レース結果）の下に挿入:

```markdown
| 発走直前オッズのスナップショット保存 | `snapshot_odds.py` | `python ./scripts/snapshot_odds.py 202608030411` |
```

そのテーブル下に新セクションを追加:

```markdown
### オッズスナップショット保存（snapshot_odds.py）

\`\`\`bash
# race_id を指定（reports/ 内の予想 JSON から basename 自動検出）
python3 ./scripts/snapshot_odds.py 202608030411

# basename を明示
python3 ./scripts/snapshot_odds.py --basename 20260503_天皇賞春 202608030411
\`\`\`

出力: `reports/<basename>.odds.json`（全 7 馬券種のオッズを含む）

発走後はオッズが消えるため、**発走 5〜10 分前** にスナップ保存することがバックテストの精度に直結する。
```

注: `\`\`\`` は通常のバッククォート 3 つで書くこと。

- [ ] **Step 4: コミット**

```bash
git add .claude/skills/netkeiba-scraper/scripts/snapshot_odds.py \
        .claude/skills/netkeiba-scraper/SKILL.md
git commit -m "feat: add snapshot_odds.py to save pre-race odds as JSON"
```

---

## Task 7: match_result.py — 結果照合・損益記録スクリプト

**目的:** 買い目 JSON + オッズスナップ（任意）+ レース結果から損益を計算し、Markdown レポートに「実績」章を追記、CSV に 1 行追加する。

**Files:**
- Create: `.claude/skills/netkeiba-scraper/scripts/match_result.py`

- [ ] **Step 1: スクリプトを作成**

`.claude/skills/netkeiba-scraper/scripts/match_result.py`:

```python
#!/usr/bin/env python3
"""
レース後に買い目と結果を照合し、損益を計算する。

使用例:
  python3 match_result.py 202608030411

処理:
  1. reports/ から該当 race_id の予想 JSON を探す
  2. オッズスナップショット (.odds.json) があれば読み込む
  3. get_race_result.py で結果を取得
  4. _backtest_helpers.compute_race_pnl で損益計算
  5. 該当 Markdown レポートに「## 実績」章を追記
  6. reports/_backtest_log.csv に 1 行追加
"""

import sys
import os
import json
import csv
import glob
import argparse
from datetime import datetime, timezone, timedelta

import get_race_result
import _backtest_helpers


JST = timezone(timedelta(hours=9))
BET_TYPE_LABELS = {
    "tansho": "単勝", "fukusho": "複勝", "wide": "ワイド",
    "umaren": "馬連", "umatan": "馬単",
    "sanrenpuku": "三連複", "sanrentan": "三連単",
}


def find_bets_json(race_id: str, reports_dir: str) -> tuple[str, dict] | None:
    """reports/ から race_id 一致の予想 JSON を探す"""
    for path in glob.glob(os.path.join(reports_dir, "*.json")):
        if path.endswith(".odds.json"):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("race_id") == race_id:
                return path, data
        except (json.JSONDecodeError, OSError):
            continue
    return None


def load_odds_json(bets_path: str) -> dict | None:
    """予想 JSON の隣にあるオッズスナップを読む"""
    odds_path = bets_path[:-5] + ".odds.json"
    if not os.path.exists(odds_path):
        return None
    try:
        with open(odds_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def format_winning_table(winners: list[dict]) -> str:
    if not winners:
        return "**的中なし**\n"
    lines = ["| 組合せ | 投資額 | 払戻 |", "|--------|--------|------|"]
    for w in winners:
        ratio = w["payout"] / max(w["amount"], 1)
        lines.append(f"| {w['combination']} | {w['amount']:,} 円 | {w['payout']:,} 円 ({ratio:.1f} 倍) |")
    return "\n".join(lines) + "\n"


def format_results_table(results: list[dict]) -> str:
    """着順テーブルを Markdown で整形（1-3 着のみ）"""
    lines = ["| 着 | 馬番 | 馬名 | 騎手 | タイム | 単勝 | 人気 |",
             "|----|------|------|------|--------|------|------|"]
    for r in results:
        try:
            chakujun = int(r["chakujun"])
        except (ValueError, KeyError):
            continue
        if chakujun > 3:
            continue
        lines.append(
            f"| {chakujun} | {r.get('umaban', '')} | {r.get('horse_name', '')} "
            f"| {r.get('jockey', '')} | {r.get('time', '')} "
            f"| {r.get('odds', '')} | {r.get('ninki', '')} |"
        )
    return "\n".join(lines) + "\n"


def build_results_section(pnl: dict, result: dict, bets: dict) -> str:
    losers_count = len(pnl["losing_bets"])
    losers_amount = sum(b["amount"] for b in pnl["losing_bets"])

    return (
        "\n## 実績\n\n"
        f"**結果照合実施**: {datetime.now(JST).strftime('%Y-%m-%d %H:%M')}\n\n"
        "### 着順\n\n"
        f"{format_results_table(result.get('results', []))}\n"
        "### 的中買い目\n\n"
        f"{format_winning_table(pnl['winning_bets'])}\n"
        f"**外れ買い目**: {losers_count} 点 / {losers_amount:,} 円\n\n"
        "### 収支\n\n"
        "| 項目 | 金額 |\n"
        "|------|------|\n"
        f"| 投資額 | {pnl['total_invested']:,} 円 |\n"
        f"| 払戻額 | {pnl['total_payout']:,} 円 |\n"
        f"| 収支 | **{'+' if pnl['profit'] >= 0 else '−'}{abs(pnl['profit']):,} 円** |\n"
        f"| 回収率 | **{pnl['roi'] * 100:.1f}%** |\n"
    )


def append_results_to_md(bets_path: str, section: str):
    md_path = bets_path[:-5] + ".md"
    if not os.path.exists(md_path):
        print(f"警告: Markdown レポート {md_path} が存在しません。CSV のみ更新します。")
        return
    with open(md_path, "a", encoding="utf-8") as f:
        f.write(section)


def append_to_csv(csv_path: str, bets: dict, pnl: dict):
    fields = ["race_id", "race_date", "race_name", "bet_type", "style",
              "budget", "total_invested", "total_payout", "profit", "roi"]
    new_file = not os.path.exists(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if new_file:
            writer.writeheader()
        writer.writerow({
            "race_id": bets["race_id"],
            "race_date": bets.get("race_date", ""),
            "race_name": bets.get("race_name", ""),
            "bet_type": bets["bet_type"],
            "style": bets.get("style", ""),
            "budget": bets.get("budget", ""),
            "total_invested": pnl["total_invested"],
            "total_payout": pnl["total_payout"],
            "profit": pnl["profit"],
            "roi": pnl["roi"],
        })


def main():
    parser = argparse.ArgumentParser(description="レース結果と買い目を照合し損益記録")
    parser.add_argument("race_id", help="レース ID (12 桁)")
    parser.add_argument("--reports-dir", default="reports")
    args = parser.parse_args()

    if len(args.race_id) != 12 or not args.race_id.isdigit():
        print("エラー: レース ID は 12 桁の数字です")
        sys.exit(1)

    found = find_bets_json(args.race_id, args.reports_dir)
    if not found:
        print(f"エラー: reports/ に race_id {args.race_id} の予想 JSON が見つかりません。")
        print("  先に /keiba で予想を立ててください。")
        sys.exit(1)
    bets_path, bets = found

    odds = load_odds_json(bets_path)
    if odds is None:
        print(f"警告: オッズスナップ {bets_path[:-5]}.odds.json が無いため、払戻金フォールバックで計算します。")

    print(f"レース結果を取得中... (race_id: {args.race_id})")
    result = get_race_result.get_race_result(args.race_id)
    if not result.get("results"):
        print("エラー: 結果がまだ確定していません。")
        sys.exit(1)

    try:
        pnl = _backtest_helpers.compute_race_pnl(bets, odds, result)
    except ValueError as e:
        print(f"エラー: 損益計算ができませんでした: {e}")
        sys.exit(1)

    section = build_results_section(pnl, result, bets)
    append_results_to_md(bets_path, section)

    csv_path = os.path.join(args.reports_dir, "_backtest_log.csv")
    append_to_csv(csv_path, bets, pnl)

    print(f"実績追記: {bets_path[:-5]}.md")
    print(f"CSV 追加: {csv_path}")
    print(f"  投資 {pnl['total_invested']:,} / 払戻 {pnl['total_payout']:,} / 収支 {pnl['profit']:+,} / 回収率 {pnl['roi'] * 100:.1f}%")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 動作確認（ヘルプ表示）**

```bash
cd /workspace
PYTHONPATH=/workspace/venv/lib/python3.12/site-packages python3 .claude/skills/netkeiba-scraper/scripts/match_result.py --help
```

期待: argparse のヘルプメッセージが表示される。

- [ ] **Step 3: コミット**

```bash
git add .claude/skills/netkeiba-scraper/scripts/match_result.py
git commit -m "feat: add match_result.py for race result matching"
```

---

## Task 8: /keiba-result コマンドファイル

**目的:** Claude が `/keiba-result <race_id>` で起動できるよう、コマンド手順書を作る。

**Files:**
- Create: `.claude/commands/keiba-result.md`

- [ ] **Step 1: コマンドファイルを作成**

`.claude/commands/keiba-result.md`:

```markdown
# 結果照合・損益記録（/keiba-result）

レース後、`/keiba` で生成した予想と実際のレース結果を突き合わせ、損益を計算して該当レポートに「実績」章を追記し、CSV ログに 1 行追加する。

## 引数

\`\`\`bash
/keiba-result <race_id>
\`\`\`

| 引数 | 必須 | 値 |
|------|------|----|
| `<race_id>` | 必須 | 12 桁のレース ID |

## 作業手順

### 1. 引数バリデーション

`<race_id>` が 12 桁の数字であることを確認。違えばエラー終了。

### 2. スクリプト実行

\`\`\`bash
python3 .claude/skills/netkeiba-scraper/scripts/match_result.py <race_id>
\`\`\`

このスクリプトが以下を自動で行う:

- `reports/` 内から `race_id` 一致の予想 JSON を検索
- 隣接するオッズ JSON があれば読み込む（無ければ警告）
- `get_race_result.py` で着順・払戻金を取得
- `_backtest_helpers.compute_race_pnl` で損益計算
- 該当 Markdown レポートの末尾に「## 実績」章を追記
- `reports/_backtest_log.csv` に 1 行追加

### 3. 実行結果のユーザへの報告

スクリプトの標準出力（投資額・払戻額・収支・回収率）をそのままユーザに伝え、追記先のファイルパスも併せて報告する。

### 4. エラー時の対処

スクリプトが exit code 非 0 で終了した場合、ユーザにエラーメッセージを伝え、考えられる原因を以下から提示:

- 予想 JSON が無い → `/keiba <レース名>` で先に予想を立てる
- 結果が確定していない → レース未終了または結果ページ未公開
- 同着で 1-3 着が判定できない → このレースはスキップせざるを得ない

## 関連

- 集計レポートを更新するには `/keiba-backtest-summary` を実行
```

- [ ] **Step 2: セルフチェック**

ファイルを開き直して以下を確認:

- 引数の説明があるか
- スクリプトのフルパスが正しいか
- エラーケース対応が網羅されているか

- [ ] **Step 3: コミット**

```bash
git add .claude/commands/keiba-result.md
git commit -m "feat: add /keiba-result command for result matching"
```

---

## Task 9: /keiba-backtest-summary コマンドファイル + 集計実装

**目的:** CSV ログを読んで `_backtest_summary.md` を再生成するコマンドと、Markdown 出力を担う Python スクリプトを作る。

集計ロジックは Task 5 の `aggregate_log` を再利用するため、Markdown 整形のみを担う薄いスクリプト `summarize_backtest.py` を追加する。

**Files:**
- Create: `.claude/skills/netkeiba-scraper/scripts/summarize_backtest.py`
- Create: `.claude/commands/keiba-backtest-summary.md`

- [ ] **Step 1: summarize_backtest.py を作成**

`.claude/skills/netkeiba-scraper/scripts/summarize_backtest.py`:

```python
#!/usr/bin/env python3
"""
reports/_backtest_log.csv から集計レポート (_backtest_summary.md) を再生成する。

使用例:
  python3 summarize_backtest.py
  python3 summarize_backtest.py --reports-dir reports
"""

import os
import csv
import argparse
from datetime import datetime, timezone, timedelta

import _backtest_helpers


JST = timezone(timedelta(hours=9))

BET_TYPE_JP = {
    "tansho": "単勝", "fukusho": "複勝", "wide": "ワイド",
    "umaren": "馬連", "umatan": "馬単",
    "sanrenpuku": "三連複", "sanrentan": "三連単",
}


def fmt_money(n: int) -> str:
    return f"{n:,}"


def fmt_signed(n: int) -> str:
    sign = "+" if n >= 0 else "−"
    return f"{sign}{abs(n):,}"


def fmt_pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def warn_if_small(n: int, value: str) -> str:
    """レース数 3 未満なら * を付与"""
    return f"{value}*" if n < 3 else value


def render_overall(s: dict) -> str:
    return (
        "## 全期間サマリ\n\n"
        "| 項目 | 値 |\n"
        "|------|----|\n"
        f"| 総レース数 | {s['races']} |\n"
        f"| 総投資額 | {fmt_money(s['invested'])} 円 |\n"
        f"| 総払戻額 | {fmt_money(s['payout'])} 円 |\n"
        f"| 収支 | **{fmt_signed(s['profit'])} 円** |\n"
        f"| 回収率 | **{fmt_pct(s['roi'])}** |\n"
        f"| 的中レース数 | {s['hit_races']} / {s['races']} ({fmt_pct(s['hit_rate'])}) |\n"
    )


def render_breakdown(title: str, group: dict, label_fn) -> str:
    if not group:
        return ""
    lines = [
        f"\n## {title}\n",
        "| 区分 | レース数 | 投資 | 払戻 | 収支 | 回収率 | 的中率 |",
        "|------|----------|------|------|------|--------|--------|",
    ]
    for key in sorted(group.keys()):
        s = group[key]
        n = s["races"]
        lines.append(
            f"| {label_fn(key)} | {n} "
            f"| {warn_if_small(n, fmt_money(s['invested']))} "
            f"| {warn_if_small(n, fmt_money(s['payout']))} "
            f"| {warn_if_small(n, fmt_signed(s['profit']))} "
            f"| {warn_if_small(n, fmt_pct(s['roi']))} "
            f"| {warn_if_small(n, fmt_pct(s['hit_rate']))} |"
        )
    return "\n".join(lines) + "\n"


def render_history(rows: list[dict]) -> str:
    sorted_rows = sorted(rows, key=lambda r: r.get("race_date", ""), reverse=True)
    lines = [
        "\n## レース別履歴\n",
        "| 日付 | レース | 馬券種 | スタイル | 投資 | 払戻 | 収支 | 回収率 |",
        "|------|--------|--------|---------|------|------|------|--------|",
    ]
    for r in sorted_rows:
        bt = BET_TYPE_JP.get(r.get("bet_type", ""), r.get("bet_type", ""))
        try:
            invested = int(r["total_invested"])
            payout = int(r["total_payout"])
            profit = int(r["profit"])
            roi = float(r["roi"])
        except (ValueError, KeyError):
            continue
        lines.append(
            f"| {r.get('race_date', '')} | {r.get('race_name', '')} | {bt} "
            f"| {r.get('style', '')} | {fmt_money(invested)} | {fmt_money(payout)} "
            f"| {fmt_signed(profit)} | {fmt_pct(roi)} |"
        )
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="バックテスト集計レポートを再生成")
    parser.add_argument("--reports-dir", default="reports")
    args = parser.parse_args()

    csv_path = os.path.join(args.reports_dir, "_backtest_log.csv")
    if not os.path.exists(csv_path):
        print(f"エラー: {csv_path} が存在しません。先にレースを照合してください。")
        return 1

    with open(csv_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    agg = _backtest_helpers.aggregate_log(rows)

    if rows:
        dates = [r.get("race_date", "") for r in rows if r.get("race_date")]
        period = f"{min(dates)} 〜 {max(dates)}" if dates else "—"
    else:
        period = "—"

    out = []
    out.append("# バックテスト集計レポート\n")
    out.append(f"**集計日時**: {datetime.now(JST).strftime('%Y-%m-%d %H:%M')}\n")
    out.append(f"**対象レース数**: {agg['overall']['races']}\n")
    out.append(f"**集計期間**: {period}\n\n")
    out.append(render_overall(agg["overall"]))
    out.append(render_breakdown("馬券種別", agg["by_bet_type"],
                                lambda k: BET_TYPE_JP.get(k, k)))
    out.append(render_breakdown("スタイル別", agg["by_style"], lambda k: k))
    out.append(render_history(rows))
    out.append("\n*: レース数 3 未満。標本数不足のため参考値。\n")

    out_path = os.path.join(args.reports_dir, "_backtest_summary.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("".join(out))

    print(f"集計レポート再生成: {out_path}")
    print(f"  対象 {agg['overall']['races']} レース、回収率 {fmt_pct(agg['overall']['roi'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: コマンドファイルを作成**

`.claude/commands/keiba-backtest-summary.md`:

```markdown
# バックテスト集計レポート再生成（/keiba-backtest-summary）

`reports/_backtest_log.csv` を読み込み、集計レポート `reports/_backtest_summary.md` を再生成する。

## 引数

なし。

## 作業手順

### 1. スクリプト実行

\`\`\`bash
python3 .claude/skills/netkeiba-scraper/scripts/summarize_backtest.py
\`\`\`

スクリプトが以下を実施する:

- `reports/_backtest_log.csv` を読む
- `_backtest_helpers.aggregate_log` で全期間 / 馬券種別 / スタイル別の集計を計算
- `reports/_backtest_summary.md` を **再生成**（追記ではなく上書き）

### 2. 実行結果のユーザへの報告

スクリプトの標準出力（対象レース数・回収率）をユーザに伝え、出力ファイルパスを示す。

### 3. エラー時の対処

`_backtest_log.csv` が無い場合: ユーザに「先に `/keiba-result` で 1 レース以上を照合してください」と案内する。
```

- [ ] **Step 3: 動作確認**

```bash
cd /workspace
PYTHONPATH=/workspace/venv/lib/python3.12/site-packages python3 .claude/skills/netkeiba-scraper/scripts/summarize_backtest.py --help
```

期待: ヘルプ表示。

- [ ] **Step 4: コミット**

```bash
git add .claude/skills/netkeiba-scraper/scripts/summarize_backtest.py \
        .claude/commands/keiba-backtest-summary.md
git commit -m "feat: add /keiba-backtest-summary command and renderer"
```

---

## Task 10: keiba-prediction SKILL.md に JSON 出力を追加

**目的:** `/keiba` 実行時に、Markdown レポートと並列で買い目データを JSON として出力するよう、`keiba-prediction/SKILL.md` の段階 9 を拡張する。

**Files:**
- Modify: `.claude/skills/keiba-prediction/SKILL.md`

- [ ] **Step 1: 段階 9 セクションを編集**

`.claude/skills/keiba-prediction/SKILL.md` の `## 段階 9: レポート生成` セクションを以下に置き換える。

OLD（現行）:
```markdown
## 段階 9: レポート生成

`reports/yyyymmdd_<レース名>.md` に以下の章立てで出力する:

1. レース概要（条件・天候・馬場）
2. レース条件分析の考察（段階 2 の文章）
3. 展開・ペース予想（段階 4 の文章、脚質マップ含む）
4. 全頭評価表（馬番・評価点・コメント、段階 5 + 6 の結果）
5. 軸・相手・穴の選定理由（段階 7 の文章）
6. 買い目（馬券種・スタイル・予算配分、点数と金額の表）
7. 注目穴馬の根拠（段階 6 の穴候補から選んだ理由）
8. シナリオ別収支見込み

`reports/` ディレクトリに過去レポートが存在する場合、それを参考フォーマットとして利用してよい。
```

NEW:
```markdown
## 段階 9: レポート生成

`reports/yyyymmdd_<レース名>.md` に以下の章立てで出力する:

1. レース概要（条件・天候・馬場）
2. レース条件分析の考察（段階 2 の文章）
3. 展開・ペース予想（段階 4 の文章、脚質マップ含む）
4. 全頭評価表（馬番・評価点・コメント、段階 5 + 6 の結果）
5. 軸・相手・穴の選定理由（段階 7 の文章）
6. 買い目（馬券種・スタイル・予算配分、点数と金額の表）
7. 注目穴馬の根拠（段階 6 の穴候補から選んだ理由）
8. シナリオ別収支見込み

`reports/` ディレクトリに過去レポートが存在する場合、それを参考フォーマットとして利用してよい。

### バックテスト用 JSON の並置出力（必須）

Markdown と同時に `reports/yyyymmdd_<レース名>.json` に **機械可読な買い目データ** を必ず出力する。後続の `/keiba-result` `/keiba-backtest-summary` がこの JSON を入力として使う。

JSON のスキーマ:

\`\`\`json
{
  "race_id": "202608030411",
  "race_name": "天皇賞(春)",
  "race_date": "2026-05-03",
  "venue": "京都",
  "course": "芝3200m",
  "bet_type": "sanrenpuku",
  "style": "balanced",
  "budget": 10000,
  "axis_horses": [7],
  "predicted_odds": {
    "tansho": [{"num": "1", "odds": "23.4"}],
    "sanrenpuku": [{"combination": "1-3-5", "odds": "45.6"}]
  },
  "bets": [
    {"combination": "7-3-12", "amount": 600, "category": "main"},
    {"combination": "7-3-1",  "amount": 400, "category": "dark_horse"}
  ],
  "total_amount": 10000,
  "generated_at": "2026-05-03T08:30:00+09:00"
}
\`\`\`

`combination` の規約:
- 単勝・複勝: `"7"`（単一馬番）
- ワイド・馬連・三連複: `"1-3-5"` （`-` 区切り、ソート済み馬番）
- 馬単・三連単: `"1→3→5"` （`→` 区切り、順序保持）

`category` は `main` / `sub` / `dark_horse`（戦略ファイルで定義された比重ブロック）。

`predicted_odds` には予想時点で取得できたオッズを入れる（参考値）。確定オッズは別途 `snapshot_odds.py` で取得する。

`generated_at` は JST タイムゾーン (`+09:00`) で出力する。
```

- [ ] **Step 2: セルフチェック**

ファイルを Read して以下を確認:
- バックティック 3 つで囲まれた JSON 例が正しく書かれている
- 段階 9 の章立て番号（1-8）が崩れていない
- `combination` の規約が正しく書かれている

- [ ] **Step 3: コミット**

```bash
git add .claude/skills/keiba-prediction/SKILL.md
git commit -m "feat: add backtest JSON output to keiba-prediction stage 9"
```

---

## Task 11: CLAUDE.md にバックテストフローを追記

**目的:** バックテスト関連ファイル・コマンド・運用フローを CLAUDE.md に明記する。

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: 「作業フロー」セクションを更新**

CLAUDE.md の `## 作業フロー` セクションを以下に置き換える:

OLD:
```markdown
## 作業フロー

1. ユーザは `/keiba <レース名> [--type ...] [--budget ...] [--style ...] [--axis ...]` で起動する
2. `/keiba` コマンドが引数解釈・対話分岐し、不足分はユーザに 1 問ずつ確認する
3. `keiba-prediction` スキルが 8 段階の予想プロセスを実行する:
   1. 入力受付 / 2. レース条件分析 / 3. データ収集 / 4. 展開・ペース予想
   5. 全頭スコアリング / 6. 展開×評価補正 / 7. 軸・相手・穴選定 / 8. 馬券構成
4. レポートを `reports/yyyymmdd_<レース名>.md` に出力する
```

NEW:
```markdown
## 作業フロー

### 予想 → 結果照合 → 集計の 4 ステップ

1. **予想**: ユーザは `/keiba <レース名> [--type ...] [--budget ...] [--style ...] [--axis ...]` で起動する
   - `/keiba` が 8 段階の予想プロセスを実行
   - `reports/yyyymmdd_<レース名>.md` (人間用) と `.json` (機械用) を並置出力
2. **直前オッズスナップショット**: 発走 5〜10 分前に `python3 .claude/skills/netkeiba-scraper/scripts/snapshot_odds.py <race_id>` を実行
   - 全 7 馬券種の確定オッズを `reports/yyyymmdd_<レース名>.odds.json` に保存
   - **発走後はオッズが消えるためこのタイミングが必須**
3. **結果照合**: レース後 `/keiba-result <race_id>` を実行
   - 着順・払戻金を取得し損益を計算
   - 該当 Markdown に「## 実績」章を追記
   - `reports/_backtest_log.csv` に 1 行追加
4. **集計レポート再生成**: `/keiba-backtest-summary` を実行
   - 全期間 / 馬券種別 / スタイル別の回収率を `reports/_backtest_summary.md` に出力（毎回再生成）
```

- [ ] **Step 2: 「関連スキル・ファイル」セクションを更新**

該当セクションに以下のコマンド・ファイルを追記:

OLD:
```markdown
## 関連スキル・ファイル

- `.claude/commands/keiba.md` — `/keiba` コマンド本体
- `.claude/skills/keiba-prediction/SKILL.md` — 8 段階予想プロセス
- `.claude/skills/keiba-prediction/strategies/<馬券種>.md` — 馬券種ごとの構成ルール
- `.claude/skills/netkeiba-scraper/SKILL.md` — 情報取得スキル

評価方法・スコアリング詳細・前走凡走分類などは `keiba-prediction/SKILL.md` を参照。
```

NEW:
```markdown
## 関連スキル・ファイル

### 予想
- `.claude/commands/keiba.md` — `/keiba` コマンド本体
- `.claude/skills/keiba-prediction/SKILL.md` — 8 段階予想プロセス
- `.claude/skills/keiba-prediction/strategies/<馬券種>.md` — 馬券種ごとの構成ルール
- `.claude/skills/netkeiba-scraper/SKILL.md` — 情報取得スキル

### バックテスト
- `.claude/commands/keiba-result.md` — 結果照合・損益記録
- `.claude/commands/keiba-backtest-summary.md` — 集計レポート再生成
- `.claude/skills/netkeiba-scraper/scripts/snapshot_odds.py` — 直前オッズスナップ保存
- `.claude/skills/netkeiba-scraper/scripts/match_result.py` — 結果照合スクリプト
- `.claude/skills/netkeiba-scraper/scripts/summarize_backtest.py` — 集計レポート生成
- `.claude/skills/netkeiba-scraper/scripts/_backtest_helpers.py` — 損益計算純関数（pytest テスト対象）

### データ
- `reports/yyyymmdd_<レース名>.md` — 予想レポート（人間用）
- `reports/yyyymmdd_<レース名>.json` — 買い目データ（機械用）
- `reports/yyyymmdd_<レース名>.odds.json` — 直前オッズスナップ
- `reports/_backtest_log.csv` — レース別損益ログ（追記式）
- `reports/_backtest_summary.md` — 集計レポート（再生成式）

評価方法・スコアリング詳細・前走凡走分類などは `keiba-prediction/SKILL.md` を参照。
```

- [ ] **Step 3: コミット**

```bash
git add CLAUDE.md
git commit -m "docs: add backtest workflow and file references to CLAUDE.md"
```

---

## Task 12: end-to-end スモークテスト

**目的:** 既存レポート（`reports/20260503_天皇賞春.md` など Task 13 で生成済み）に手動で結果照合を流して、`/keiba-result` 相当の動作を確認する。

**Files:**
- 既存ファイルの存在確認のみ（テストデータ生成）

注: 過去レースのオッズスナップは取得不可（オッズ消失済み）のため、払戻金フォールバックを使った照合となる。

- [ ] **Step 1: 既存予想 JSON があるか確認**

```bash
ls reports/*.json 2>/dev/null
```

期待:
- もし存在すれば該当レースで Step 2 へ
- 存在しなければ Task 13 のレポート（天皇賞春）の予想を JSON 化したダミーを 1 件作って Step 2 へ。具体例:

```bash
cat > reports/20260503_天皇賞春.json <<'EOF'
{
  "race_id": "202608030411",
  "race_name": "天皇賞(春)",
  "race_date": "2026-05-03",
  "venue": "京都",
  "course": "芝3200m",
  "bet_type": "sanrenpuku",
  "style": "balanced",
  "budget": 10000,
  "axis_horses": [7],
  "predicted_odds": {},
  "bets": [
    {"combination": "7-12-3", "amount": 600, "category": "main"},
    {"combination": "7-3-1",  "amount": 400, "category": "dark_horse"}
  ],
  "total_amount": 1000,
  "generated_at": "2026-05-03T08:30:00+09:00"
}
EOF
```

注: ファイル不存在のときだけ作る。実在の予想 JSON があればそれを使う。

- [ ] **Step 2: match_result.py を実行**

```bash
cd /workspace
PYTHONPATH=/workspace/venv/lib/python3.12/site-packages python3 .claude/skills/netkeiba-scraper/scripts/match_result.py 202608030411
```

期待される動作:
- オッズスナップ無しの警告
- レース結果取得
- 損益計算（払戻金フォールバック）
- Markdown に「## 実績」追記（あれば）
- `reports/_backtest_log.csv` に 1 行追加
- 投資 / 払戻 / 収支 / 回収率の標準出力

- [ ] **Step 3: CSV を確認**

```bash
cat reports/_backtest_log.csv
```

期待: ヘッダ + 1 行のデータ。

- [ ] **Step 4: summarize_backtest.py を実行**

```bash
PYTHONPATH=/workspace/venv/lib/python3.12/site-packages python3 .claude/skills/netkeiba-scraper/scripts/summarize_backtest.py
```

期待: `reports/_backtest_summary.md` が生成される。

- [ ] **Step 5: 集計レポートの内容確認**

```bash
cat reports/_backtest_summary.md
```

期待: 「全期間サマリ」「馬券種別」「スタイル別」「レース別履歴」のセクション。レース 1 件分のデータが反映されている。レース数 1 < 3 なので各セルに `*` 付与。

- [ ] **Step 6: 全テスト再実行で回帰確認**

```bash
PYTHONPATH=/workspace/venv/lib/python3.12/site-packages python3 -m pytest tests/ -v
```

期待: 全テスト PASS（既存 7 件 + 新規 35 件 = 42 件）。

- [ ] **Step 7: 動作確認サマリ**

reports/ にあるファイルを git ls しつつ動作確認結果をレポート（reports は gitignored なのでコミットなし）:

```bash
ls -la reports/
```

問題なければ end-to-end 動作確認完了。

---

## Self-Review

### 1. Spec coverage

- 1.1 ゴール: 4 つ全て対応 — JSON 並置 (Task 10), スナップショット (Task 6), 結果照合+CSV (Task 7+8), 集計再生成 (Task 9), pytest テスト (Task 1-5)
- 1.2 スコープ: すべての項目に対応するタスクがある
- 1.3 スコープ外: グラフ・期間絞り込み・複数スナップ等は計画に含めていない（OK）
- 2. 全体アーキテクチャ: ファイル構成・役割分担とも計画通り
- 3. データフロー: タイムライン・各ステップ・エラーハンドリングとも実装に反映
- 4. JSON / CSV スキーマ: Task 7 (CSV), Task 10 (予想 JSON), Task 6 (オッズ JSON), Task 7 (Markdown 実績章) で対応
- 5. 損益計算ロジック: 関数構成・優先順位・バリデーション・テスト方針とも Task 1-5 で対応
- 6. 集計レポート: 章立て・集計ルール・再生成方式とも Task 9 で対応
- 7. CLAUDE.md 更新: Task 11
- 9. 確定事項: ファイル名規約 (Task 6 で実装), JST 固定 (Task 6,7,9 で実装), CSV ヘッダ自動 (Task 7), 同着 ValueError (Task 4), ワイド下限 (Task 3)

### 2. Placeholder scan

- 「TBD」「TODO」「省略」検索: なし
- 各 Task に具体的なコード・コマンド・期待値が記載されている
- 戦略の取捨選択（YAGNI 範囲）は Section 8 で明示し、Task に含めていない（OK）

### 3. Type consistency

- `bet_type` の値（tansho / fukusho / wide / umaren / umatan / sanrenpuku / sanrentan）: 全 Task で統一
- `combination` の表記規約（`-` 区切り / `→` 区切り）: Task 1, 6, 7, 10 で一致
- `result` の構造（`{"results": [{"chakujun", "umaban", ...}], "payoffs": [...]}`）: Task 4, 7 で一致
- `aggregate_log` の戻り値キー（`overall` / `by_bet_type` / `by_style`）: Task 5, 9 で一致
- `compute_race_pnl` の戻り値キー（`total_invested`, `total_payout`, `profit`, `roi`, `winning_bets`, `losing_bets`）: Task 4, 7 で一致
- 関数名: `parse_combination`, `is_winning_bet`, `compute_payout`, `compute_race_pnl`, `aggregate_log` — 全 Task で一貫

問題なし。
