"""
予想ロジックで利用される予算配分・端数処理のヘルパー関数。
keiba-prediction スキルから「迷ったらこれを使え」と参照される。
"""

from __future__ import annotations


def round_to_unit(amount: int, unit: int = 100) -> int:
    """amount を unit 単位で切り捨てる"""
    return (amount // unit) * unit


def allocate_budget(total: int, ratios: dict[str, float], unit: int = 100) -> dict[str, int]:
    """
    予算 total を ratios の比率で配分し、各値を unit 単位に丸める。
    合計が total を超えないように切り捨てで処理。

    Args:
        total: 総予算（円）
        ratios: グループ名 → 比率 のマッピング（合計が 1.0 でなくても許容）
        unit: 丸め単位（デフォルト 100 円）

    Returns:
        グループ名 → 配分額 のマッピング

    Raises:
        ValueError: total が unit 未満の場合
    """
    if total < unit:
        raise ValueError(f"予算は {unit} 円以上必要です（指定: {total}）")

    return {
        name: round_to_unit(int(total * ratio), unit)
        for name, ratio in ratios.items()
    }
