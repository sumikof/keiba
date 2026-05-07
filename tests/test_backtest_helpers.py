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
    assert parse_combination("1-3", "umaren") == (1, 3)
    assert parse_combination("3-1", "umaren") == (1, 3)


def test_parse_combination_umatan_ordered():
    assert parse_combination("1→3", "umatan") == (1, 3)
    assert parse_combination("3→1", "umatan") == (3, 1)


def test_parse_combination_wide_unordered():
    assert parse_combination("1-3", "wide") == (1, 3)
    assert parse_combination("3-1", "wide") == (1, 3)


def test_parse_combination_tansho_single():
    assert parse_combination("7", "tansho") == (7,)


def test_parse_combination_fukusho_single():
    assert parse_combination("7", "fukusho") == (7,)


def test_parse_combination_invalid_raises():
    with pytest.raises(ValueError, match="不正な bet_type"):
        parse_combination("1-3-5", "invalid_type")


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


from _backtest_helpers import compute_payout


def test_compute_payout_miss_returns_zero():
    """外れなら 0 円"""
    bet = {"combination": "9", "amount": 1000, "bet_type": "tansho"}
    assert compute_payout(bet, None, [7, 12, 3], []) == 0


def test_compute_payout_uses_odds_snapshot_when_available():
    """オッズスナップがあれば amount × odds で計算"""
    bet = {"combination": "7", "amount": 1000, "bet_type": "tansho"}
    odds = {"tansho": [{"num": "7", "odds": "2.4"}]}
    assert compute_payout(bet, odds, [7, 12, 3], []) == 2400


def test_compute_payout_uses_payoffs_when_no_odds():
    """オッズスナップなしなら払戻金（100 円当たり）をスケール"""
    bet = {"combination": "7", "amount": 600, "bet_type": "tansho"}
    payoffs = [{"ticket": "単勝", "nums": "7", "amount": 240}]
    assert compute_payout(bet, None, [7, 12, 3], payoffs) == 1440


def test_compute_payout_wide_uses_lower_bound():
    """ワイドの範囲オッズは下限を採用"""
    bet = {"combination": "7-12", "amount": 1000, "bet_type": "wide"}
    odds = {"wide": [{"combination": "7-12", "odds_low": "3.2", "odds_high": "4.5"}]}
    assert compute_payout(bet, odds, [7, 12, 3], []) == 3200


def test_compute_payout_sanrenpuku_combination_normalized():
    """三連複オッズ検索時に combination を正規化（順不同で一致）"""
    bet = {"combination": "12-7-3", "amount": 600, "bet_type": "sanrenpuku"}
    odds = {"sanrenpuku": [{"combination": "3-7-12", "odds": "12.4"}]}
    assert compute_payout(bet, odds, [7, 12, 3], []) == 7440


def test_compute_payout_no_match_returns_zero_with_warning_data():
    """当たりなのにオッズも払戻もない場合は 0 円（データ不整合）"""
    bet = {"combination": "7", "amount": 1000, "bet_type": "tansho"}
    assert compute_payout(bet, {"tansho": []}, [7, 12, 3], []) == 0
