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
