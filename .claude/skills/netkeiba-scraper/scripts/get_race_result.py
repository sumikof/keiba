#!/usr/bin/env python3
"""
netkeibaからレース結果・着順・払戻金を取得する。
使用例:
  python3 get_race_result.py 202501010101
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

TICKET_NAMES = {
    "単勝": "単勝", "複勝": "複勝", "枠連": "枠連",
    "馬連": "馬連", "ワイド": "ワイド", "馬単": "馬単",
    "3連複": "3連複", "3連単": "3連単",
}


def get_race_result(race_id: str) -> dict:
    url = f"https://race.netkeiba.com/race/result.html?race_id={race_id}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    resp.encoding = "EUC-JP"

    soup = BeautifulSoup(resp.text, "lxml")
    result = {"race_info": {}, "results": [], "payoffs": []}

    # レース情報
    title = soup.select_one(".RaceName, .RaceTitle")
    result["race_info"]["name"] = title.get_text(strip=True) if title else "-"

    data01 = soup.select_one(".RaceData01")
    result["race_info"]["detail"] = " ".join(data01.get_text(" ", strip=True).split()) if data01 else "-"

    data02 = soup.select_one(".RaceData02")
    result["race_info"]["meta"] = " ".join(data02.get_text(" ", strip=True).split()) if data02 else "-"

    # 着順テーブル
    result_table = soup.select_one(".RaceResultTable, table.nk_tb_common")
    if result_table:
        for row in result_table.select("tr.HorseList, tr")[1:]:
            cells = row.find_all("td")
            if len(cells) < 6:
                continue

            def gc(idx: int) -> str:
                return cells[idx].get_text(strip=True) if idx < len(cells) else ""

            horse = {
                "chakujun": gc(0),
                "waku": gc(1),
                "umaban": gc(2),
                "horse_name": gc(3),
                "seireii": gc(4),
                "kinryo": gc(5),
                "jockey": gc(6),
                "time": gc(7),
                "margin": gc(8),
                "ninki": gc(10) if len(cells) > 10 else "",
                "odds": gc(11) if len(cells) > 11 else "",
                "trainer": gc(13) if len(cells) > 13 else "",
                "weight": gc(14) if len(cells) > 14 else "",
            }
            # 着順が数字か「取」「除」「失」「中」などの場合のみ追加
            if horse["chakujun"] and (horse["chakujun"].isdigit() or horse["chakujun"] in ("取", "除", "失", "中")):
                result["results"].append(horse)

    # 払戻テーブル
    payoff_tables = soup.select(".PaybackList, .ResultPayment, table.pay_block")
    for table in payoff_tables:
        for row in table.select("tr"):
            ticket_elem = row.select_one("th, .Ticket")
            if not ticket_elem:
                continue
            ticket = ticket_elem.get_text(strip=True)
            if not ticket:
                continue

            nums_elem = row.select_one(".Num, .HorseNums")
            nums = nums_elem.get_text(strip=True) if nums_elem else ""

            payback_elem = row.select_one(".Odds, .Payback, td:nth-child(2)")
            payback = payback_elem.get_text(strip=True) if payback_elem else ""

            ninki_elem = row.select_one(".Ninki, .Favorite, td:nth-child(3)")
            ninki = ninki_elem.get_text(strip=True) if ninki_elem else ""

            if ticket and payback:
                result["payoffs"].append({
                    "ticket": ticket,
                    "nums": nums,
                    "payback": payback,
                    "ninki": ninki,
                })

    return result


def print_race_result(result: dict, race_id: str):
    info = result.get("race_info", {})
    results = result.get("results", [])
    payoffs = result.get("payoffs", [])

    print(f"\n=== レース結果 [{race_id}] ===")
    print(f"レース名  : {info.get('name', '-')}")
    print(f"レース詳細: {info.get('detail', '-')}")
    print(f"開催情報  : {info.get('meta', '-')}")
    print()

    if not results:
        print("レース結果が取得できませんでした。")
        print("  - レースがまだ終了していない可能性があります")
        print("  - レースIDを確認してください")
        return

    print("【着順】")
    print(f"  {'着':<4} {'枠':<3} {'馬番':<4} {'馬名':<18} {'性齢':<5} {'斤量':<5} {'騎手':<10} {'タイム':<10} {'着差':<8} {'人気':<4} オッズ")
    print(f"  {'-'*90}")
    for r in results:
        print(
            f"  {r.get('chakujun', ''):<4} {r.get('waku', ''):<3} {r.get('umaban', ''):<4} "
            f"{r.get('horse_name', ''):<18} {r.get('seireii', ''):<5} {r.get('kinryo', ''):<5} "
            f"{r.get('jockey', ''):<10} {r.get('time', ''):<10} {r.get('margin', ''):<8} "
            f"{r.get('ninki', ''):<4} {r.get('odds', '')}"
        )

    if payoffs:
        print("\n【払戻金】")
        print(f"  {'券種':<8} {'組み合わせ':<20} {'払戻金':<12} 人気")
        print(f"  {'-'*50}")
        for p in payoffs:
            print(
                f"  {p.get('ticket', ''):<8} {p.get('nums', ''):<20} "
                f"{p.get('payback', ''):<12} {p.get('ninki', '')}"
            )
    print()


def main():
    parser = argparse.ArgumentParser(description="netkeibaからレース結果を取得")
    parser.add_argument("race_id", help="レースID (12桁、例: 202501010101)")
    args = parser.parse_args()

    race_id = args.race_id.strip()
    if len(race_id) != 12 or not race_id.isdigit():
        print(f"エラー: レースIDは12桁の数字です (例: 202501010101)")
        sys.exit(1)

    print(f"レース結果を取得中... (race_id: {race_id})")
    try:
        result = get_race_result(race_id)
        print_race_result(result, race_id)
    except requests.RequestException as e:
        print(f"通信エラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
