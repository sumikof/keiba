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
from datetime import datetime, timezone, timedelta


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

JST = timezone(timedelta(hours=9))

# 馬券種 type_param（HTML時代の b1/b4...）→ JSON API の type 番号
_TYPE_PARAM_TO_API = {"b1": 1, "b4": 4, "b5": 5, "b6": 6, "b7": 7, "b8": 8}


def _fetch_api_json(race_id: str, api_type: int) -> dict:
    """netkeiba のオッズ JSON API を叩いて dict を返す。"""
    url = (
        "https://race.netkeiba.com/api/api_get_jra_odds.html"
        f"?race_id={race_id}&type={api_type}&action=update"
    )
    headers = dict(HEADERS)
    headers["Referer"] = (
        f"https://race.netkeiba.com/odds/index.html?race_id={race_id}"
    )
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, dict) else {}

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


def _odds_dict(api_json: dict, odds_key: str) -> dict:
    """data.odds[odds_key] を取り出す。NG/欠損時は空 dict。"""
    data = api_json.get("data")
    if not isinstance(data, dict):
        return {}
    odds = data.get("odds")
    if not isinstance(odds, dict):
        return {}
    block = odds.get(odds_key)
    return block if isinstance(block, dict) else {}


def _unpad(combo_key: str) -> list[str]:
    """'0102' -> ['1','2'] / '010203' -> ['1','2','3'] / '01' -> ['1']。"""
    return [str(int(combo_key[i:i + 2])) for i in range(0, len(combo_key), 2)]


def parse_tansho_fukusho(api_json: dict) -> dict:
    """type=1 のAPI JSONから単勝・複勝を抽出する純関数。"""
    tan_block = _odds_dict(api_json, "1")
    fuku_block = _odds_dict(api_json, "2")

    tansho = []
    for k, v in sorted(tan_block.items(), key=lambda kv: int(kv[0])):
        try:
            tansho.append({"num": _unpad(k)[0], "odds": v[0]})
        except (IndexError, ValueError):
            continue

    fukusho = []
    for k, v in sorted(fuku_block.items(), key=lambda kv: int(kv[0])):
        try:
            fukusho.append({"num": _unpad(k)[0], "odds_low": v[0], "odds_high": v[1]})
        except (IndexError, ValueError):
            continue

    return {"tansho": tansho, "fukusho": fukusho}


def _odds_sort_key(row: list) -> float:
    try:
        return float(row[-1])
    except (ValueError, IndexError):
        return 9999.0


def parse_combined(api_json: dict, odds_key: str) -> list[list]:
    """馬連(4)・ワイド(5)・馬単(6) のAPI JSONから [馬番1, 馬番2, オッズ] を抽出。

    ワイドは v0（低オッズ）を採用（現行スキーマ互換）。
    高オッズ側 vals[1] は intentionally dropped — downstream uses low value for both bounds.
    """
    block = _odds_dict(api_json, odds_key)
    rows = []
    for combo_key, vals in block.items():
        try:
            n1, n2 = _unpad(combo_key)
            rows.append([n1, n2, vals[0]])
        except (ValueError, IndexError):
            continue
    rows.sort(key=_odds_sort_key)
    return rows


def parse_sanren(api_json: dict, odds_key: str) -> list[list]:
    """三連複(7)・三連単(8) のAPI JSONから [馬番1, 馬番2, 馬番3, オッズ] を抽出。"""
    block = _odds_dict(api_json, odds_key)
    rows = []
    for combo_key, vals in block.items():
        try:
            n1, n2, n3 = _unpad(combo_key)
            rows.append([n1, n2, n3, vals[0]])
        except (ValueError, IndexError):
            continue
    rows.sort(key=_odds_sort_key)
    return rows


def fetch_tansho_fukusho(race_id: str) -> dict:
    """単勝・複勝オッズを JSON API から取得"""
    return parse_tansho_fukusho(_fetch_api_json(race_id, 1))


def fetch_combined_odds(race_id: str, type_param: str) -> list[list]:
    """馬連・馬単・ワイドの組み合わせオッズを JSON API から取得"""
    api_type = _TYPE_PARAM_TO_API[type_param]
    return parse_combined(_fetch_api_json(race_id, api_type), str(api_type))


def fetch_sanren_odds(race_id: str, type_param: str, head_count: int = 18) -> list[list]:
    """3連複・3連単オッズを JSON API から取得（1リクエストで全通り）"""
    api_type = _TYPE_PARAM_TO_API[type_param]
    return parse_sanren(_fetch_api_json(race_id, api_type), str(api_type))


def _assemble_snapshot(race_id, snapshot_at, odds_status, tf,
                       umaren_rows, wide_rows, umatan_rows,
                       sanrenpuku_rows, sanrentan_rows) -> dict:
    """各馬券種の行データを .odds.json スキーマの dict に集約する純関数。"""
    return {
        "race_id": race_id,
        "snapshot_at": snapshot_at,
        "odds_status": odds_status,
        "tansho": tf.get("tansho", []),
        "fukusho": tf.get("fukusho", []),
        "umaren": [
            {"combination": f"{r[0]}-{r[1]}", "odds": r[2]} for r in umaren_rows
        ],
        "wide": [
            {"combination": f"{r[0]}-{r[1]}", "odds_low": r[2], "odds_high": r[2]}
            for r in wide_rows
        ],
        "umatan": [
            {"combination": f"{r[0]}→{r[1]}", "odds": r[2]} for r in umatan_rows
        ],
        "sanrenpuku": [
            {"combination": f"{r[0]}-{r[1]}-{r[2]}", "odds": r[3]}
            for r in sanrenpuku_rows
        ],
        "sanrentan": [
            {"combination": f"{r[0]}→{r[1]}→{r[2]}", "odds": r[3]}
            for r in sanrentan_rows
        ],
    }


def fetch_all_odds(race_id: str, head_count: int = 18) -> dict:
    """全7馬券種のオッズを JSON API から取得し snapshot dict を返す。

    odds_status は単勝・複勝(type=1)レスポンスの status を採用する。
    head_count は後方互換のため残すが未使用。
    """
    tan_json = _fetch_api_json(race_id, 1)
    odds_status = tan_json.get("status", "")
    tf = parse_tansho_fukusho(tan_json)
    time.sleep(0.5)

    umaren_rows = fetch_combined_odds(race_id, "b4")
    time.sleep(0.5)
    wide_rows = fetch_combined_odds(race_id, "b5")
    time.sleep(0.5)
    umatan_rows = fetch_combined_odds(race_id, "b6")
    time.sleep(0.5)
    sanrenpuku_rows = fetch_sanren_odds(race_id, "b7")
    time.sleep(0.5)
    sanrentan_rows = fetch_sanren_odds(race_id, "b8")

    return _assemble_snapshot(
        race_id=race_id,
        snapshot_at=datetime.now(JST).isoformat(),
        odds_status=odds_status,
        tf=tf,
        umaren_rows=umaren_rows,
        wide_rows=wide_rows,
        umatan_rows=umatan_rows,
        sanrenpuku_rows=sanrenpuku_rows,
        sanrentan_rows=sanrentan_rows,
    )


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
