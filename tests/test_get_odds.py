from get_odds import parse_tansho_fukusho
from get_odds import parse_combined
from get_odds import parse_sanren
from get_odds import _unpad, _odds_sort_key


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


def test_parse_tansho_fukusho_skips_short_value_lists():
    api = {"status": "middle", "data": {"odds": {
        "1": {"01": ["13.5", "", "6"], "02": []},
        "2": {"01": ["3.5", "4.8", "8"], "03": ["1.5"]},
    }}}
    result = parse_tansho_fukusho(api)
    assert result["tansho"] == [{"num": "1", "odds": "13.5"}]
    assert result["fukusho"] == [{"num": "1", "odds_low": "3.5", "odds_high": "4.8"}]


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


def test_parse_combined_skips_malformed_rows():
    api = {"status": "middle", "data": {"odds": {"4": {
        "0102": ["10.5", "", "2"],
        "01": ["99.9", "", "9"],   # malformed: only one horse
        "0304": [],                 # malformed: no odds
    }}}}
    assert parse_combined(api, "4") == [["1", "2", "10.5"]]


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


def test_parse_sanren_skips_malformed_rows():
    api = {"status": "middle", "data": {"odds": {"7": {
        "010203": ["88.8", "", "30"],
        "0102": ["5.0", "", "1"],   # malformed: only two horses
    }}}}
    assert parse_sanren(api, "7") == [["1", "2", "3", "88.8"]]


def test_unpad_handles_single_pair_and_triple():
    assert _unpad("01") == ["1"]
    assert _unpad("0102") == ["1", "2"]
    assert _unpad("010203") == ["1", "2", "3"]


def test_odds_sort_key_fallback_for_nonnumeric():
    assert _odds_sort_key(["1", "2", "12.3"]) == 12.3
    assert _odds_sort_key(["1", "2", "---"]) == 9999.0
    assert _odds_sort_key([]) == 9999.0
