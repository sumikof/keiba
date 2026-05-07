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
    with pytest.raises(ValueError, match="同着"):
        compute_race_pnl(bets, None, result)


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
