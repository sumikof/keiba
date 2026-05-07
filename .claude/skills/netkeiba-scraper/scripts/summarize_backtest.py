#!/usr/bin/env python3
"""
reports/_backtest_log.csv から集計レポート (_backtest_summary.md) を再生成する。

使用例:
  python3 summarize_backtest.py
  python3 summarize_backtest.py --reports-dir reports
"""

import os
import csv
import argparse
from datetime import datetime, timezone, timedelta

import _backtest_helpers


JST = timezone(timedelta(hours=9))

BET_TYPE_JP = {
    "tansho": "単勝", "fukusho": "複勝", "wide": "ワイド",
    "umaren": "馬連", "umatan": "馬単",
    "sanrenpuku": "三連複", "sanrentan": "三連単",
}


def fmt_money(n: int) -> str:
    return f"{n:,}"


def fmt_signed(n: int) -> str:
    sign = "+" if n >= 0 else "−"
    return f"{sign}{abs(n):,}"


def fmt_pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def warn_if_small(n: int, value: str) -> str:
    """レース数 3 未満なら * を付与"""
    return f"{value}*" if n < 3 else value


def render_overall(s: dict) -> str:
    return (
        "## 全期間サマリ\n\n"
        "| 項目 | 値 |\n"
        "|------|----|\n"
        f"| 総レース数 | {s['races']} |\n"
        f"| 総投資額 | {fmt_money(s['invested'])} 円 |\n"
        f"| 総払戻額 | {fmt_money(s['payout'])} 円 |\n"
        f"| 収支 | **{fmt_signed(s['profit'])} 円** |\n"
        f"| 回収率 | **{fmt_pct(s['roi'])}** |\n"
        f"| 的中レース数 | {s['hit_races']} / {s['races']} ({fmt_pct(s['hit_rate'])}) |\n"
    )


def render_breakdown(title: str, group: dict, label_fn) -> str:
    if not group:
        return ""
    lines = [
        f"\n## {title}\n",
        "| 区分 | レース数 | 投資 | 払戻 | 収支 | 回収率 | 的中率 |",
        "|------|----------|------|------|------|--------|--------|",
    ]
    for key in sorted(group.keys()):
        s = group[key]
        n = s["races"]
        lines.append(
            f"| {label_fn(key)} | {n} "
            f"| {warn_if_small(n, fmt_money(s['invested']))} "
            f"| {warn_if_small(n, fmt_money(s['payout']))} "
            f"| {warn_if_small(n, fmt_signed(s['profit']))} "
            f"| {warn_if_small(n, fmt_pct(s['roi']))} "
            f"| {warn_if_small(n, fmt_pct(s['hit_rate']))} |"
        )
    return "\n".join(lines) + "\n"


def render_history(rows: list[dict]) -> str:
    sorted_rows = sorted(rows, key=lambda r: r.get("race_date", ""), reverse=True)
    lines = [
        "\n## レース別履歴\n",
        "| 日付 | レース | 馬券種 | スタイル | 投資 | 払戻 | 収支 | 回収率 |",
        "|------|--------|--------|---------|------|------|------|--------|",
    ]
    for r in sorted_rows:
        bt = BET_TYPE_JP.get(r.get("bet_type", ""), r.get("bet_type", ""))
        try:
            invested = int(r["total_invested"])
            payout = int(r["total_payout"])
            profit = int(r["profit"])
            roi = float(r["roi"])
        except (ValueError, KeyError):
            continue
        lines.append(
            f"| {r.get('race_date', '')} | {r.get('race_name', '')} | {bt} "
            f"| {r.get('style', '')} | {fmt_money(invested)} | {fmt_money(payout)} "
            f"| {fmt_signed(profit)} | {fmt_pct(roi)} |"
        )
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="バックテスト集計レポートを再生成")
    parser.add_argument("--reports-dir", default="reports")
    args = parser.parse_args()

    csv_path = os.path.join(args.reports_dir, "_backtest_log.csv")
    if not os.path.exists(csv_path):
        print(f"エラー: {csv_path} が存在しません。先にレースを照合してください。")
        return 1

    with open(csv_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    agg = _backtest_helpers.aggregate_log(rows)

    if rows:
        dates = [r.get("race_date", "") for r in rows if r.get("race_date")]
        period = f"{min(dates)} 〜 {max(dates)}" if dates else "—"
    else:
        period = "—"

    out = []
    out.append("# バックテスト集計レポート\n")
    out.append(f"**集計日時**: {datetime.now(JST).strftime('%Y-%m-%d %H:%M')}\n")
    out.append(f"**対象レース数**: {agg['overall']['races']}\n")
    out.append(f"**集計期間**: {period}\n\n")
    out.append(render_overall(agg["overall"]))
    out.append(render_breakdown("馬券種別", agg["by_bet_type"],
                                lambda k: BET_TYPE_JP.get(k, k)))
    out.append(render_breakdown("スタイル別", agg["by_style"], lambda k: k))
    out.append(render_history(rows))
    out.append("\n*: レース数 3 未満。標本数不足のため参考値。\n")

    out_path = os.path.join(args.reports_dir, "_backtest_summary.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("".join(out))

    print(f"集計レポート再生成: {out_path}")
    print(f"  対象 {agg['overall']['races']} レース、回収率 {fmt_pct(agg['overall']['roi'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
