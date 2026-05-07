#!/usr/bin/env python3
"""
レース後に買い目と結果を照合し、損益を計算する。

使用例:
  python3 match_result.py 202608030411

処理:
  1. reports/ から該当 race_id の予想 JSON を探す
  2. オッズスナップショット (.odds.json) があれば読み込む
  3. get_race_result.py で結果を取得
  4. _backtest_helpers.compute_race_pnl で損益計算
  5. 該当 Markdown レポートに「## 実績」章を追記
  6. reports/_backtest_log.csv に 1 行追加
"""

import sys
import os
import json
import csv
import glob
import argparse
from datetime import datetime, timezone, timedelta

import get_race_result
import _backtest_helpers


JST = timezone(timedelta(hours=9))
BET_TYPE_LABELS = {
    "tansho": "単勝", "fukusho": "複勝", "wide": "ワイド",
    "umaren": "馬連", "umatan": "馬単",
    "sanrenpuku": "三連複", "sanrentan": "三連単",
}


def find_bets_json(race_id: str, reports_dir: str) -> tuple[str, dict] | None:
    """reports/ から race_id 一致の予想 JSON を探す"""
    for path in glob.glob(os.path.join(reports_dir, "*.json")):
        if path.endswith(".odds.json"):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("race_id") == race_id:
                return path, data
        except (json.JSONDecodeError, OSError):
            continue
    return None


def load_odds_json(bets_path: str) -> dict | None:
    """予想 JSON の隣にあるオッズスナップを読む"""
    odds_path = bets_path[:-5] + ".odds.json"
    if not os.path.exists(odds_path):
        return None
    try:
        with open(odds_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def format_winning_table(winners: list[dict]) -> str:
    if not winners:
        return "**的中なし**\n"
    lines = ["| 組合せ | 投資額 | 払戻 |", "|--------|--------|------|"]
    for w in winners:
        ratio = w["payout"] / max(w["amount"], 1)
        lines.append(f"| {w['combination']} | {w['amount']:,} 円 | {w['payout']:,} 円 ({ratio:.1f} 倍) |")
    return "\n".join(lines) + "\n"


def format_results_table(results: list[dict]) -> str:
    """着順テーブルを Markdown で整形（1-3 着のみ）"""
    lines = ["| 着 | 馬番 | 馬名 | 騎手 | タイム | 単勝 | 人気 |",
             "|----|------|------|------|--------|------|------|"]
    for r in results:
        try:
            chakujun = int(r["chakujun"])
        except (ValueError, KeyError):
            continue
        if chakujun > 3:
            continue
        lines.append(
            f"| {chakujun} | {r.get('umaban', '')} | {r.get('horse_name', '')} "
            f"| {r.get('jockey', '')} | {r.get('time', '')} "
            f"| {r.get('odds', '')} | {r.get('ninki', '')} |"
        )
    return "\n".join(lines) + "\n"


def build_results_section(pnl: dict, result: dict, bets: dict) -> str:
    losers_count = len(pnl["losing_bets"])
    losers_amount = sum(b["amount"] for b in pnl["losing_bets"])

    return (
        "\n## 実績\n\n"
        f"**結果照合実施**: {datetime.now(JST).strftime('%Y-%m-%d %H:%M')}\n\n"
        "### 着順\n\n"
        f"{format_results_table(result.get('results', []))}\n"
        "### 的中買い目\n\n"
        f"{format_winning_table(pnl['winning_bets'])}\n"
        f"**外れ買い目**: {losers_count} 点 / {losers_amount:,} 円\n\n"
        "### 収支\n\n"
        "| 項目 | 金額 |\n"
        "|------|------|\n"
        f"| 投資額 | {pnl['total_invested']:,} 円 |\n"
        f"| 払戻額 | {pnl['total_payout']:,} 円 |\n"
        f"| 収支 | **{'+' if pnl['profit'] >= 0 else '−'}{abs(pnl['profit']):,} 円** |\n"
        f"| 回収率 | **{pnl['roi'] * 100:.1f}%** |\n"
    )


def append_results_to_md(bets_path: str, section: str):
    md_path = bets_path[:-5] + ".md"
    if not os.path.exists(md_path):
        print(f"警告: Markdown レポート {md_path} が存在しません。CSV のみ更新します。")
        return
    with open(md_path, "a", encoding="utf-8") as f:
        f.write(section)


def append_to_csv(csv_path: str, bets: dict, pnl: dict):
    fields = ["race_id", "race_date", "race_name", "bet_type", "style",
              "budget", "total_invested", "total_payout", "profit", "roi"]
    new_file = not os.path.exists(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if new_file:
            writer.writeheader()
        writer.writerow({
            "race_id": bets["race_id"],
            "race_date": bets.get("race_date", ""),
            "race_name": bets.get("race_name", ""),
            "bet_type": bets["bet_type"],
            "style": bets.get("style", ""),
            "budget": bets.get("budget", ""),
            "total_invested": pnl["total_invested"],
            "total_payout": pnl["total_payout"],
            "profit": pnl["profit"],
            "roi": pnl["roi"],
        })


def main():
    parser = argparse.ArgumentParser(description="レース結果と買い目を照合し損益記録")
    parser.add_argument("race_id", help="レース ID (12 桁)")
    parser.add_argument("--reports-dir", default="reports")
    args = parser.parse_args()

    if len(args.race_id) != 12 or not args.race_id.isdigit():
        print("エラー: レース ID は 12 桁の数字です")
        sys.exit(1)

    found = find_bets_json(args.race_id, args.reports_dir)
    if not found:
        print(f"エラー: reports/ に race_id {args.race_id} の予想 JSON が見つかりません。")
        print("  先に /keiba で予想を立ててください。")
        sys.exit(1)
    bets_path, bets = found

    odds = load_odds_json(bets_path)
    if odds is None:
        print(f"警告: オッズスナップ {bets_path[:-5]}.odds.json が無いため、払戻金フォールバックで計算します。")

    print(f"レース結果を取得中... (race_id: {args.race_id})")
    result = get_race_result.get_race_result(args.race_id)
    if not result.get("results"):
        print("エラー: 結果がまだ確定していません。")
        sys.exit(1)

    try:
        pnl = _backtest_helpers.compute_race_pnl(bets, odds, result)
    except ValueError as e:
        print(f"エラー: 損益計算ができませんでした: {e}")
        sys.exit(1)

    section = build_results_section(pnl, result, bets)
    append_results_to_md(bets_path, section)

    csv_path = os.path.join(args.reports_dir, "_backtest_log.csv")
    append_to_csv(csv_path, bets, pnl)

    print(f"実績追記: {bets_path[:-5]}.md")
    print(f"CSV 追加: {csv_path}")
    print(f"  投資 {pnl['total_invested']:,} / 払戻 {pnl['total_payout']:,} / 収支 {pnl['profit']:+,} / 回収率 {pnl['roi'] * 100:.1f}%")


if __name__ == "__main__":
    main()
