#!/usr/bin/env python3
"""
netkeibaから指定日のJRAレース一覧を取得する。
使用例:
  python3 get_race_list.py                  # 今日
  python3 get_race_list.py 20250601         # 指定日
"""

import sys
import time
import argparse
from datetime import datetime

import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

VENUE_NAMES = {
    "01": "札幌", "02": "函館", "03": "福島", "04": "新潟",
    "05": "東京", "06": "中山", "07": "中京", "08": "京都",
    "09": "阪神", "10": "小倉",
}


def get_race_list(date_str: str) -> list[dict]:
    url = f"https://race.netkeiba.com/top/race_list_sub.html?kaisai_date={date_str}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    resp.encoding = "UTF-8"

    soup = BeautifulSoup(resp.text, "lxml")
    races = []

    for kai_block in soup.select(".RaceList_DataList"):
        # 競馬場名を取得
        venue_elem = kai_block.select_one(".RaceList_DataTitle")
        venue_name = venue_elem.get_text(strip=True) if venue_elem else "不明"

        for race_item in kai_block.select(".RaceList_DataItem"):
            link = race_item.select_one("a")
            if not link:
                continue

            href = link.get("href", "")
            race_id = ""
            if "race_id=" in href:
                race_id = href.split("race_id=")[1].split("&")[0].split("#")[0]

            # レース番号
            race_num_elem = race_item.select_one(".Race_Num, .RaceNum")
            race_num = race_num_elem.get_text(strip=True) if race_num_elem else "-"

            # レース名
            race_name_elem = race_item.select_one(".RaceName, .ItemTitle")
            race_name = race_name_elem.get_text(strip=True) if race_name_elem else link.get_text(strip=True)

            # 発走時刻
            time_elem = race_item.select_one(".RaceTime, .ItemTime")
            start_time = time_elem.get_text(strip=True) if time_elem else "-"

            # 出走頭数
            horses_elem = race_item.select_one(".ItemHeadCount, .Num")
            head_count = horses_elem.get_text(strip=True) if horses_elem else "-"

            races.append({
                "venue": venue_name,
                "race_num": race_num,
                "race_name": race_name,
                "start_time": start_time,
                "head_count": head_count,
                "race_id": race_id,
            })

    return races


def print_race_list(races: list[dict], date_str: str):
    if not races:
        print(f"[{date_str}] レース情報が見つかりませんでした。")
        print("  - JRA開催日でない可能性があります")
        print("  - ページ構造が変わった可能性があります")
        return

    # 競馬場ごとにグループ化して表示
    from itertools import groupby
    print(f"\n=== JRA レース一覧 [{date_str[:4]}/{date_str[4:6]}/{date_str[6:]}] ===\n")

    current_venue = None
    for r in races:
        if r["venue"] != current_venue:
            current_venue = r["venue"]
            print(f"【{current_venue}】")
            print(f"  {'R':<4} {'発走時刻':<8} {'レース名':<25} {'頭数':<5} レースID")
            print(f"  {'-'*65}")

        race_num = r["race_num"].replace("R", "").strip()
        print(
            f"  {race_num + 'R':<4} {r['start_time']:<8} {r['race_name']:<25} "
            f"{r['head_count']:<5} {r['race_id']}"
        )
    print()


def main():
    parser = argparse.ArgumentParser(description="netkeibaからJRAレース一覧を取得")
    parser.add_argument("date", nargs="?", help="日付 (YYYYMMDD形式、省略時は今日)")
    args = parser.parse_args()

    date_str = args.date if args.date else datetime.now().strftime("%Y%m%d")

    if len(date_str) != 8 or not date_str.isdigit():
        print(f"エラー: 日付は YYYYMMDD 形式で指定してください (例: 20250601)")
        sys.exit(1)

    print(f"netkeibaからレース情報を取得中... ({date_str})")
    try:
        races = get_race_list(date_str)
        print_race_list(races, date_str)
    except requests.RequestException as e:
        print(f"通信エラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
