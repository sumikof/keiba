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
