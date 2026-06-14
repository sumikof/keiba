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
