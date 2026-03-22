#!/usr/bin/env python3
"""
netkeibaから出走馬のプロフィール・過去成績を取得する。
使用例:
  python3 get_horse_info.py 2020104753           # 馬IDで検索
  python3 get_horse_info.py --name "イクイノックス"  # 馬名で検索
  python3 get_horse_info.py 2020104753 --races 10  # 直近10戦を表示
"""

import sys
import re
import argparse
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def search_horse_by_name(name: str) -> str | None:
    """馬名でdb.netkeibaを検索して馬IDを返す"""
    url = f"https://db.netkeiba.com/horse/list/?word={quote(name)}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    resp.encoding = "EUC-JP"

    soup = BeautifulSoup(resp.text, "lxml")

    # 検索結果テーブル
    for link in soup.select("table.nk_tb_common a[href*='/horse/']"):
        href = link.get("href", "")
        match = re.search(r"/horse/(\d+)/", href)
        if match:
            horse_id = match.group(1)
            horse_name = link.get_text(strip=True)
            print(f"馬が見つかりました: {horse_name} (ID: {horse_id})")
            return horse_id

    return None


def get_horse_profile(horse_id: str) -> dict:
    """馬のプロフィール情報を取得"""
    url = f"https://db.netkeiba.com/horse/{horse_id}/"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    resp.encoding = "EUC-JP"

    soup = BeautifulSoup(resp.text, "lxml")
    profile = {"horse_id": horse_id}

    # 馬名
    title = soup.select_one("h1.horse_title, .horse_title")
    if not title:
        title = soup.select_one("h1")
    profile["name"] = title.get_text(strip=True) if title else "-"

    # プロフィールテーブル
    prof_table = soup.select_one("table.db_prof_table, .horse_data")
    if prof_table:
        for row in prof_table.select("tr"):
            th = row.select_one("th")
            td = row.select_one("td")
            if th and td:
                key = th.get_text(strip=True)
                val = td.get_text(" ", strip=True)
                if "生年月日" in key or "生年" in key:
                    profile["birthday"] = val
                elif "調教師" in key:
                    profile["trainer"] = val
                elif "馬主" in key:
                    profile["owner"] = val
                elif "生産者" in key or "生産牧場" in key:
                    profile["breeder"] = val
                elif "産地" in key:
                    profile["birthplace"] = val
                elif "毛色" in key:
                    profile["color"] = val
                elif "性別" in key or "性" == key:
                    profile["sex"] = val

    # 血統テーブル
    blood_table = soup.select_one("table.blood_table, .blood_pedigree")
    if blood_table:
        links = blood_table.find_all("a")
        if len(links) >= 1:
            profile["father"] = links[0].get_text(strip=True)
        if len(links) >= 2:
            profile["mother"] = links[1].get_text(strip=True)
        if len(links) >= 5:
            profile["mother_father"] = links[4].get_text(strip=True)

    # 通算成績
    result_block = soup.select_one(".db_h_race_results")
    if result_block:
        profile["total_record"] = result_block.get_text(" ", strip=True)

    return profile


def get_horse_races(horse_id: str, max_races: int = 10) -> list[dict]:
    """馬の過去レース成績を取得"""
    url = f"https://db.netkeiba.com/horse/result/{horse_id}/"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    resp.encoding = "EUC-JP"

    soup = BeautifulSoup(resp.text, "lxml")
    races = []

    # 成績テーブル
    race_table = soup.select_one("table.db_h_race_results, table.nk_tb_common")
    if not race_table:
        return races

    headers_row = race_table.select_one("tr")
    col_names = [th.get_text(strip=True) for th in headers_row.select("th")] if headers_row else []

    for row in race_table.select("tr.HorseRace, tr")[1:max_races + 1]:
        cells = row.find_all("td")
        if len(cells) < 5:
            continue

        race = {}
        # カラム名に基づいてマッピング（フォールバックは位置ベース）
        def get_cell(idx: int) -> str:
            return cells[idx].get_text(strip=True) if idx < len(cells) else ""

        race["date"] = get_cell(0)
        race["venue"] = get_cell(1)
        race["weather"] = get_cell(2)
        race["race_num"] = get_cell(3)
        race["race_name"] = get_cell(4)
        race["head_count"] = get_cell(6)
        race["waku"] = get_cell(7)
        race["umaban"] = get_cell(8)
        race["odds"] = get_cell(9)
        race["ninki"] = get_cell(10)
        race["chakujun"] = get_cell(11)
        race["jockey"] = get_cell(12)
        race["kinryo"] = get_cell(13)
        race["course"] = get_cell(14)
        race["time"] = get_cell(17) if len(cells) > 17 else get_cell(15)
        race["margin"] = get_cell(18) if len(cells) > 18 else get_cell(16)

        if race["date"]:
            races.append(race)

    return races[:max_races]


def print_horse_info(profile: dict, races: list[dict]):
    print(f"\n=== 馬情報: {profile.get('name', '不明')} (ID: {profile.get('horse_id', '-')}) ===\n")

    print("【プロフィール】")
    fields = [
        ("生年月日", "birthday"), ("性別", "sex"), ("毛色", "color"),
        ("調教師", "trainer"), ("馬主", "owner"), ("生産者", "breeder"),
        ("産地", "birthplace"),
    ]
    for label, key in fields:
        val = profile.get(key, "")
        if val:
            print(f"  {label:<8}: {val}")

    print("\n【血統】")
    if "father" in profile:
        print(f"  父     : {profile.get('father', '-')}")
    if "mother" in profile:
        print(f"  母     : {profile.get('mother', '-')}")
    if "mother_father" in profile:
        print(f"  母父   : {profile.get('mother_father', '-')}")

    if "total_record" in profile:
        print(f"\n【通算成績】\n  {profile['total_record']}")

    if races:
        print(f"\n【近走成績（直近{len(races)}戦）】")
        print(f"  {'日付':<12} {'競馬場':<6} {'レース名':<22} {'頭数':<4} {'枠':<3} {'馬番':<4} {'着順':<4} {'騎手':<10} {'斤量':<5} {'タイム':<10} {'着差':<6} {'人気':<4} オッズ")
        print(f"  {'-'*100}")
        for r in races:
            print(
                f"  {r.get('date', ''):<12} {r.get('venue', ''):<6} {r.get('race_name', ''):<22} "
                f"{r.get('head_count', ''):<4} {r.get('waku', ''):<3} {r.get('umaban', ''):<4} "
                f"{r.get('chakujun', ''):<4} {r.get('jockey', ''):<10} {r.get('kinryo', ''):<5} "
                f"{r.get('time', ''):<10} {r.get('margin', ''):<6} {r.get('ninki', ''):<4} "
                f"{r.get('odds', '')}"
            )
    else:
        print("\n過去成績が取得できませんでした。")

    print()


def main():
    parser = argparse.ArgumentParser(description="netkeibaから出走馬情報を取得")
    parser.add_argument("horse_id", nargs="?", help="馬ID (db.netkeibaのURL末尾の数字)")
    parser.add_argument("--name", help="馬名で検索")
    parser.add_argument("--races", type=int, default=10, help="表示する過去レース数 (デフォルト: 10)")
    args = parser.parse_args()

    horse_id = args.horse_id

    if args.name:
        print(f"馬名「{args.name}」で検索中...")
        horse_id = search_horse_by_name(args.name)
        if not horse_id:
            print(f"「{args.name}」が見つかりませんでした。")
            print("  ヒント: 馬名の表記を確認するか、db.netkeiba.comで直接検索してください")
            sys.exit(1)
        time.sleep(0.5)
    elif not horse_id:
        print("エラー: 馬ID または --name オプションが必要です")
        sys.exit(1)

    print(f"馬情報を取得中... (horse_id: {horse_id})")
    try:
        profile = get_horse_profile(horse_id)
        races = get_horse_races(horse_id, args.races)
        print_horse_info(profile, races)
    except requests.RequestException as e:
        print(f"通信エラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
