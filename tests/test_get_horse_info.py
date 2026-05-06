import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".claude", "skills", "netkeiba-scraper", "scripts"))

from bs4 import BeautifulSoup
from get_horse_info import parse_race_row


def test_parse_race_row_extracts_passage_order():
    """過去レースの通過順を抽出できる"""
    headers = ["日付", "開催", "天気", "R", "レース名", "映像", "頭数",
               "枠番", "馬番", "オッズ", "人気", "着順", "騎手", "斤量",
               "距離", "馬場", "タイム", "着差", "通過", "ペース", "上り",
               "馬体重", "厩舎ｺﾒﾝﾄ", "備考", "勝ち馬(2着馬)", "賞金"]
    cells_text = ["2025/12/28", "中山4", "晴", "11", "有馬記念(G1)", "", "16",
                  "1", "1", "5.4", "3", "2", "ルメール", "57.0",
                  "芝2500", "良", "2:31.0", "0.1", "5-5-3-3", "60.4-35.6", "34.5",
                  "508(+2)", "", "", "ドウデュース", "70000"]
    row_html = "<tr>" + "".join(f"<td>{t}</td>" for t in cells_text) + "</tr>"
    row = BeautifulSoup(row_html, "lxml").find("tr")

    race = parse_race_row(row, headers)

    assert race["date"] == "2025/12/28"
    assert race["venue"] == "中山4"
    assert race["chakujun"] == "2"
    assert race["distance"] == "芝2500"
    assert race["baba"] == "良"
    assert race["passage"] == "5-5-3-3"
    assert race["agari"] == "34.5"
    assert race["pace"] == "60.4-35.6"


def test_parse_race_row_handles_missing_columns():
    """カラムが不足していても落ちず、空文字を入れる"""
    headers = ["日付", "開催", "着順"]
    cells_text = ["2025/12/28", "中山4", "2"]
    row_html = "<tr>" + "".join(f"<td>{t}</td>" for t in cells_text) + "</tr>"
    row = BeautifulSoup(row_html, "lxml").find("tr")

    race = parse_race_row(row, headers)

    assert race["date"] == "2025/12/28"
    assert race["passage"] == ""
    assert race["agari"] == ""
