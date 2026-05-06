from _prediction_helpers import allocate_budget, round_to_unit


def test_allocate_budget_balanced_three_groups():
    """3 グループ (main, sub, dark_horse) に 70/15/15 で配分する"""
    result = allocate_budget(10000, {"main": 0.70, "sub": 0.15, "dark_horse": 0.15})
    assert result == {"main": 7000, "sub": 1500, "dark_horse": 1500}


def test_allocate_budget_rounds_to_100():
    """端数は 100 円単位に丸める"""
    result = allocate_budget(10000, {"main": 0.71, "sub": 0.14, "dark_horse": 0.15})
    assert result["main"] % 100 == 0
    assert result["sub"] % 100 == 0
    assert result["dark_horse"] % 100 == 0
    assert sum(result.values()) <= 10000


def test_allocate_budget_total_does_not_exceed():
    """配分合計が予算を超えない"""
    result = allocate_budget(3000, {"main": 0.70, "sub": 0.15, "dark_horse": 0.15})
    assert sum(result.values()) <= 3000


def test_round_to_unit_basic():
    """100 円単位への切り捨て"""
    assert round_to_unit(7150, 100) == 7100
    assert round_to_unit(7100, 100) == 7100
    assert round_to_unit(99, 100) == 0


def test_allocate_budget_too_small_raises():
    """予算が 100 円未満ならエラー"""
    import pytest
    with pytest.raises(ValueError, match="予算は 100 円以上"):
        allocate_budget(50, {"main": 1.0})
