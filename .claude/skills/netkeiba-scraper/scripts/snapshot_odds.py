#!/usr/bin/env python3
"""
発走直前のオッズを取得し JSON ファイルに保存する。

使用例:
  python3 snapshot_odds.py 202608030411
  python3 snapshot_odds.py --basename 20260503_天皇賞春 202608030411

保存先:
  reports/<basename>.odds.json

basename が省略された場合は reports/ 内で同 race_id の予想 JSON を探し、
その basename を流用する。見つからない場合はエラー。
"""

import sys
import os
import json
import glob
import time
import argparse
from datetime import datetime, timezone, timedelta

import get_odds


JST = timezone(timedelta(hours=9))


def find_basename_from_reports(race_id: str, reports_dir: str) -> str | None:
    """reports/ 内の予想 JSON から同 race_id のものを探し basename を返す"""
    for path in glob.glob(os.path.join(reports_dir, "*.json")):
        if path.endswith(".odds.json"):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("race_id") == race_id:
                base = os.path.basename(path)
                return base[:-5]  # .json を除く
        except (json.JSONDecodeError, OSError):
            continue
    return None


def fetch_all_odds(race_id: str, head_count: int = 18) -> dict:
    """全馬券種のオッズを取得して 1 つの dict に集約する"""
    snapshot = {
        "race_id": race_id,
        "snapshot_at": datetime.now(JST).isoformat(),
    }

    # 単勝・複勝
    tf = get_odds.fetch_tansho_fukusho(race_id)
    snapshot["tansho"] = tf.get("tansho", [])
    snapshot["fukusho"] = tf.get("fukusho", [])
    time.sleep(0.5)

    # 馬連 (b4) / ワイド (b5) / 馬単 (b6)
    for bet_key, type_param in [("umaren", "b4"), ("wide", "b5"), ("umatan", "b6")]:
        rows = get_odds.fetch_combined_odds(race_id, type_param)
        if bet_key == "wide":
            snapshot[bet_key] = [
                {"combination": f"{r[0]}-{r[1]}", "odds_low": r[2], "odds_high": r[2]}
                for r in rows
            ]
        elif bet_key == "umatan":
            snapshot[bet_key] = [
                {"combination": f"{r[0]}→{r[1]}", "odds": r[2]}
                for r in rows
            ]
        else:  # umaren
            snapshot[bet_key] = [
                {"combination": f"{r[0]}-{r[1]}", "odds": r[2]}
                for r in rows
            ]
        time.sleep(0.5)

    # 三連複 (b7)
    rows = get_odds.fetch_sanren_odds(race_id, "b7", head_count)
    snapshot["sanrenpuku"] = [
        {"combination": f"{r[0]}-{r[1]}-{r[2]}", "odds": r[3]} for r in rows
    ]
    time.sleep(0.5)

    # 三連単 (b8)
    rows = get_odds.fetch_sanren_odds(race_id, "b8", head_count)
    snapshot["sanrentan"] = [
        {"combination": f"{r[0]}→{r[1]}→{r[2]}", "odds": r[3]} for r in rows
    ]

    return snapshot


def main():
    parser = argparse.ArgumentParser(description="オッズスナップショットを保存")
    parser.add_argument("race_id", help="レース ID (12 桁)")
    parser.add_argument("--basename", help="ファイル名のベース (例: 20260503_天皇賞春)")
    parser.add_argument("--reports-dir", default="reports", help="保存先ディレクトリ")
    parser.add_argument("--head-count", type=int, default=18,
                        help="出走頭数（3 連複・3 連単のスキャン上限）")
    args = parser.parse_args()

    if len(args.race_id) != 12 or not args.race_id.isdigit():
        print("エラー: レース ID は 12 桁の数字です")
        sys.exit(1)

    basename = args.basename
    if not basename:
        basename = find_basename_from_reports(args.race_id, args.reports_dir)
        if not basename:
            print(f"エラー: reports/ に race_id {args.race_id} の予想 JSON が見つかりません。")
            print("  --basename で明示的にファイル名を指定するか、先に /keiba で予想を立ててください。")
            sys.exit(1)
        print(f"basename を予想 JSON から取得: {basename}")

    print(f"オッズを取得中... (race_id: {args.race_id})")
    snapshot = fetch_all_odds(args.race_id, args.head_count)

    os.makedirs(args.reports_dir, exist_ok=True)
    out_path = os.path.join(args.reports_dir, f"{basename}.odds.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    counts = {k: len(v) for k, v in snapshot.items()
              if isinstance(v, list)}
    print(f"オッズ保存完了: {out_path}")
    print(f"  件数: {counts}")


if __name__ == "__main__":
    main()
