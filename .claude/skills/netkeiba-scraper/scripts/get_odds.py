#!/usr/bin/env python3
"""
netkeibaからオッズを取得する。
使用例:
  python3 get_odds.py 202501010101                       # 単勝・複勝
  python3 get_odds.py 202501010101 --type umaren         # 馬連
  python3 get_odds.py 202501010101 --type sanrenpuku     # 3連複
  python3 get_odds.py 202501010101 --type all            # 全馬券種
"""

import sys
import argparse
import time
import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# 馬券種別とパラメータのマッピング
ODDS_TYPES = {
    "tansho":    {"label": "単勝",  "type_param": "b1"},
    "fukusho":   {"label": "複勝",  "type_param": "b1"},
    "umaren":    {"label": "馬連",  "type_param": "b4"},
    "wide":      {"label": "ワイド", "type_param": "b5"},
    "umatan":    {"label": "馬単",  "type_param": "b6"},
    "sanrenpuku":{"label": "3連複", "type_param": "b7"},
    "sanrentan": {"label": "3連単", "type_param": "b8"},
}


def _fetch_soup(race_id: str, type_param: str) -> BeautifulSoup:
    """オッズページのHTMLを取得してBeautifulSoupを返す"""
    url = f"https://race.netkeiba.com/odds/index.html?race_id={race_id}&type={type_param}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    resp.encoding = "EUC-JP"
    return BeautifulSoup(resp.text, "lxml")


def fetch_tansho_fukusho(race_id: str) -> dict:
    """単勝・複勝オッズをHTMLページから取得"""
    soup = _fetch_soup(race_id, "b1")
    data = {"tansho": [], "fukusho": []}

    # 単勝テーブル (#odds_tan_block内)
    tan_block = soup.select_one("#odds_tan_block table.RaceOdds_HorseList_Table")
    if tan_block:
        for row in tan_block.select("tr")[1:]:  # ヘッダー行をスキップ
            cells = row.find_all("td")
            if len(cells) >= 6:
                umaban = cells[1].get_text(strip=True)
                odds = cells[5].get_text(strip=True)
                if umaban:
                    data["tansho"].append({"num": umaban, "odds": odds})

    # 複勝テーブル (#odds_fuku_block内)
    fuku_block = soup.select_one("#odds_fuku_block table.RaceOdds_HorseList_Table")
    if fuku_block:
        for row in fuku_block.select("tr")[1:]:
            cells = row.find_all("td")
            if len(cells) >= 6:
                umaban = cells[1].get_text(strip=True)
                odds_text = cells[5].get_text(strip=True)
                if umaban:
                    # 複勝オッズは "1.2 - 3.4" の形式の場合がある
                    if "-" in odds_text and odds_text != "---.-":
                        parts = odds_text.split("-")
                        data["fukusho"].append({
                            "num": umaban,
                            "odds_low": parts[0].strip(),
                            "odds_high": parts[1].strip(),
                        })
                    else:
                        data["fukusho"].append({
                            "num": umaban,
                            "odds_low": odds_text,
                            "odds_high": odds_text,
                        })

    return data


def fetch_combined_odds(race_id: str, type_param: str) -> list[list]:
    """馬連・馬単・ワイドなどの組み合わせオッズをHTMLから取得

    三角行列テーブルをパースして [馬番1, 馬番2, オッズ] のリストを返す。
    """
    soup = _fetch_soup(race_id, type_param)
    rows = []

    for table in soup.select("table.Odds_Table"):
        tr_list = table.find_all("tr")
        if not tr_list:
            continue

        # 最初の行は軸馬番号
        first_cells = tr_list[0].find_all(["td", "th"])
        if not first_cells:
            continue
        axis_num = first_cells[0].get_text(strip=True)

        # 残りの行は相手馬番号とオッズ
        for tr in tr_list[1:]:
            cells = tr.find_all("td")
            if len(cells) >= 2:
                partner_num = cells[0].get_text(strip=True)
                odds_val = cells[1].get_text(strip=True)
                if axis_num and partner_num:
                    rows.append([axis_num, partner_num, odds_val])

    # オッズ順にソート（数値変換できないものは末尾へ）
    def odds_key(r):
        try:
            return float(r[-1])
        except (ValueError, IndexError):
            return 9999

    rows.sort(key=odds_key)
    return rows


def fetch_sanren_odds(race_id: str, type_param: str, head_count: int = 18) -> list[list]:
    """3連複・3連単オッズをHTMLから取得

    軸馬ごとにページを取得し、三角行列を展開して
    [馬番1, 馬番2, 馬番3, オッズ] のリストを返す。
    """
    all_rows = []
    seen = set()

    for jiku in range(1, head_count + 1):
        url = (
            f"https://race.netkeiba.com/odds/index.html"
            f"?race_id={race_id}&type={type_param}&jiku={jiku}"
        )
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            resp.encoding = "EUC-JP"
        except requests.RequestException:
            continue

        soup = BeautifulSoup(resp.text, "lxml")
        tables = soup.select("table.Odds_Table")
        if not tables:
            break  # この軸馬は出走していない → これ以上の軸馬もなし

        for table in tables:
            tr_list = table.find_all("tr")
            if not tr_list:
                continue

            first_cells = tr_list[0].find_all(["td", "th"])
            if not first_cells:
                continue
            second_num = first_cells[0].get_text(strip=True)

            for tr in tr_list[1:]:
                cells = tr.find_all("td")
                if len(cells) >= 2:
                    third_num = cells[0].get_text(strip=True)
                    odds_val = cells[1].get_text(strip=True)

                    if type_param == "b7":
                        # 3連複: 順番不問なのでソートして重複排除
                        combo = tuple(sorted([str(jiku), second_num, third_num]))
                    else:
                        # 3連単: 順番が意味を持つ
                        combo = (str(jiku), second_num, third_num)

                    if combo not in seen:
                        seen.add(combo)
                        all_rows.append(list(combo) + [odds_val])

        time.sleep(0.3)

    def odds_key(r):
        try:
            return float(r[-1])
        except (ValueError, IndexError):
            return 9999

    all_rows.sort(key=odds_key)
    return all_rows


def print_tansho_fukusho(race_id: str):
    data = fetch_tansho_fukusho(race_id)

    print(f"\n=== 単勝・複勝オッズ [{race_id}] ===\n")

    tansho = sorted(data.get("tansho", []), key=lambda x: int(x.get("num", 99)))
    fukusho = sorted(data.get("fukusho", []), key=lambda x: int(x.get("num", 99)))

    if tansho or fukusho:
        max_len = max(len(tansho), len(fukusho))
        print(f"{'馬番':<4} {'単勝オッズ':<12}  {'馬番':<4} {'複勝オッズ（低-高）'}")
        print("-" * 45)
        for i in range(max_len):
            t = tansho[i] if i < len(tansho) else {}
            f = fukusho[i] if i < len(fukusho) else {}
            t_str = f"{t.get('num', ''):<4} {t.get('odds', '-'):<12}" if t else " " * 16
            f_str = f"{f.get('num', ''):<4} {f.get('odds_low', '-')}〜{f.get('odds_high', '-')}" if f else ""
            print(f"{t_str}  {f_str}")
    else:
        print("オッズ情報が取得できませんでした。")

    print()


def print_combined(race_id: str, odds_type: str):
    config = ODDS_TYPES[odds_type]

    if odds_type in ("sanrenpuku", "sanrentan"):
        rows = fetch_sanren_odds(race_id, config["type_param"])
    else:
        rows = fetch_combined_odds(race_id, config["type_param"])

    print(f"\n=== {config['label']}オッズ [{race_id}] ===\n")

    if not rows:
        print("オッズ情報が取得できませんでした。")
        print()
        return

    # 上位20件を表示
    display_rows = rows[:20]

    if odds_type in ("umaren", "wide", "umatan"):
        print(f"{'1頭目':<6} {'2頭目':<6} オッズ")
        print("-" * 25)
        for r in display_rows:
            if len(r) >= 3:
                print(f"{r[0]:<6} {r[1]:<6} {r[2]}")
    elif odds_type in ("sanrenpuku", "sanrentan"):
        print(f"{'1頭目':<6} {'2頭目':<6} {'3頭目':<6} オッズ")
        print("-" * 30)
        for r in display_rows:
            if len(r) >= 4:
                print(f"{r[0]:<6} {r[1]:<6} {r[2]:<6} {r[3]}")

    if len(rows) > 20:
        print(f"  ... 他 {len(rows) - 20} 通り (オッズ上位20件を表示)")
    print()


def main():
    parser = argparse.ArgumentParser(description="netkeibaからオッズを取得")
    parser.add_argument("race_id", help="レースID (12桁、例: 202501010101)")
    parser.add_argument(
        "--type",
        default="tansho",
        choices=list(ODDS_TYPES.keys()) + ["all"],
        help="馬券種別 (デフォルト: tansho 単勝・複勝も同時表示)"
    )
    args = parser.parse_args()

    race_id = args.race_id.strip()
    if len(race_id) != 12 or not race_id.isdigit():
        print(f"エラー: レースIDは12桁の数字です (例: 202501010101)")
        sys.exit(1)

    print(f"オッズを取得中... (race_id: {race_id})")

    try:
        if args.type in ("tansho", "fukusho"):
            print_tansho_fukusho(race_id)
        elif args.type == "all":
            print_tansho_fukusho(race_id)
            for t in ["umaren", "wide", "umatan", "sanrenpuku"]:
                time.sleep(1)
                print_combined(race_id, t)
        else:
            print_combined(race_id, args.type)

    except requests.RequestException as e:
        print(f"通信エラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
