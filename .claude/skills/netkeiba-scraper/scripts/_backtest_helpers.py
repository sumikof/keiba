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
