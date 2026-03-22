#!/usr/bin/env python3
"""
netkeibaから出走表・枠順を取得する。
使用例:
  python3 get_race_entry.py 202501010101
"""

import sys
import argparse
import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

GATE_COLORS = {
    "1": "白", "2": "黒", "3": "赤", "4": "青",
    "5": "黄", "6": "緑", "7": "橙", "8": "桃",
}


def get_race_info(soup: BeautifulSoup) -> dict:
    info = {}

    # レース名
    title = soup.select_one(".RaceName, .RaceTitle")
    info["race_name"] = title.get_text(strip=True) if title else "-"

    # レース詳細（距離・コースなど）
    data11 = soup.select_one(".RaceData01")
    if data11:
        info["race_detail"] = " ".join(data11.get_text(" ", strip=True).split())
    else:
        info["race_detail"] = "-"

    # 日時・競馬場
    data02 = soup.select_one(".RaceData02")
    if data02:
        info["race_meta"] = " ".join(data02.get_text(" ", strip=True).split())
    else:
        info["race_meta"] = "-"

    return info


def get_race_entry(race_id: str) -> tuple[dict, list[dict]]:
    url = f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    resp.encoding = "EUC-JP"

    soup = BeautifulSoup(resp.text, "lxml")
    race_info = get_race_info(soup)

    horses = []
    table = soup.select_one(".ShutubaTable, #shutuba_table")
    if not table:
        # 別のセレクターを試す
        table = soup.find("table", class_=lambda x: x and "Shutuba" in x)

    if not table:
        return race_info, horses

    for row in table.select("tr.HorseList, tr[class*='HorseList']"):
        cells = row.find_all("td")
        if len(cells) < 5:
            continue

        horse = {}

        # 枠番
        waku = row.select_one(".Waku, [class*='Waku']")
        horse["waku"] = waku.get_text(strip=True) if waku else cells[0].get_text(strip=True)

        # 馬番
        umaban = row.select_one(".Umaban, [class*='Umaban']")
        horse["umaban"] = umaban.get_text(strip=True) if umaban else ""

        # 馬名・馬ID
        horse_name_elem = row.select_one(".HorseName a, .Horse_Name a")
        if horse_name_elem:
            horse["horse_name"] = horse_name_elem.get_text(strip=True)
            href = horse_name_elem.get("href", "")
            if "/horse/" in href:
                horse["horse_id"] = href.split("/horse/")[1].strip("/")
            else:
                horse["horse_id"] = ""
        else:
            horse["horse_name"] = ""
            horse["horse_id"] = ""

        # 性齢
        seireii = row.select_one(".Barei, .HorseSex")
        horse["seireii"] = seireii.get_text(strip=True) if seireii else ""

        # 斤量
        kinryo = row.select_one(".Jockey, .Kinryo")
        # 斤量と騎手が別セルにある場合
        kinryo_cell = None
        jockey_cell = None
        for i, cell in enumerate(cells):
            text = cell.get_text(strip=True)
            # 斤量は数値（例: 57.0, 55）
            try:
                val = float(text.replace("▲", "").replace("△", "").replace("☆", ""))
                if 48 <= val <= 62:
                    kinryo_cell = text
            except ValueError:
                pass

        horse["kinryo"] = kinryo_cell or ""

        # 騎手
        jockey_elem = row.select_one(".Jockey a, .RiderName a")
        horse["jockey"] = jockey_elem.get_text(strip=True) if jockey_elem else ""

        # 調教師
        trainer_elem = row.select_one(".Trainer a, .TrainerName a")
        horse["trainer"] = trainer_elem.get_text(strip=True) if trainer_elem else ""

        # 馬体重
        weight_elem = row.select_one(".Weight, .HorseWeight")
        horse["weight"] = weight_elem.get_text(strip=True) if weight_elem else ""

        if horse["horse_name"]:
            horses.append(horse)

    return race_info, horses


def print_entry(race_info: dict, horses: list[dict], race_id: str):
    print(f"\n=== 出走表 [{race_id}] ===")
    print(f"レース名  : {race_info.get('race_name', '-')}")
    print(f"レース詳細: {race_info.get('race_detail', '-')}")
    print(f"開催情報  : {race_info.get('race_meta', '-')}")
    print()

    if not horses:
        print("出走馬情報が取得できませんでした。")
        print("  - レースIDを確認してください")
        print("  - 出走表がまだ公開されていない可能性があります")
        return

    # ヘッダー
    print(f"{'枠':<3} {'馬番':<4} {'馬名':<18} {'性齢':<5} {'斤量':<5} {'騎手':<12} {'調教師':<12} {'馬体重':<10} 馬ID")
    print("-" * 90)

    for h in horses:
        gate_color = GATE_COLORS.get(h.get("waku", ""), "")
        waku_str = f"{h.get('waku', '')}({gate_color})" if gate_color else h.get("waku", "")
        print(
            f"{waku_str:<5} {h.get('umaban', ''):<4} {h.get('horse_name', ''):<18} "
            f"{h.get('seireii', ''):<5} {h.get('kinryo', ''):<5} {h.get('jockey', ''):<12} "
            f"{h.get('trainer', ''):<12} {h.get('weight', ''):<10} {h.get('horse_id', '')}"
        )
    print(f"\n出走頭数: {len(horses)}頭\n")


def main():
    parser = argparse.ArgumentParser(description="netkeibaから出走表を取得")
    parser.add_argument("race_id", help="レースID (12桁、例: 202501010101)")
    args = parser.parse_args()

    race_id = args.race_id.strip()
    if len(race_id) != 12 or not race_id.isdigit():
        print(f"エラー: レースIDは12桁の数字です (例: 202501010101)")
        sys.exit(1)

    print(f"出走表を取得中... (race_id: {race_id})")
    try:
        race_info, horses = get_race_entry(race_id)
        print_entry(race_info, horses, race_id)
    except requests.RequestException as e:
        print(f"通信エラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
