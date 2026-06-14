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
import argparse

import get_odds


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
    snapshot = get_odds.fetch_all_odds(args.race_id, args.head_count)

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
