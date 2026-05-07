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
        try:
            payoff_combo = parse_combination(p["nums"], bet_type)
            bet_combo = parse_combination(combo, bet_type)
            if payoff_combo == bet_combo:
                payback = int(p["amount"])
                return amount * payback // 100
        except (ValueError, KeyError):
            continue

    return 0
