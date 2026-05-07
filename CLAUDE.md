# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

日本中央競馬（JRA）の買い目を検討するプロジェクト。netkeibaからレース情報を取得し、ユーザの希望（馬券種・予算・スタイル）に合わせてロジカルに買い目を組み立てる。

## 目標・制約

- **デフォルト予算:** 1 万円（ユーザ指定で変更可）
- **デフォルト馬券種:** 三連複フォーメーション（ユーザ指定で変更可）
- **デフォルトスタイル:** balanced（穴馬を必ず含める。`favorite` / `longshot` でも可）
- 対応馬券種: 単勝 / 複勝 / ワイド / 馬連 / 馬単 / 三連複 / 三連単
- 対応スタイル: `favorite`（堅め） / `balanced`（バランス、穴必須） / `longshot`（高配当狙い）

## 作業フロー

### 予想 → 結果照合 → 集計の 4 ステップ

1. **予想**: ユーザは `/keiba <レース名> [--type ...] [--budget ...] [--style ...] [--axis ...]` で起動する
   - `/keiba` が 8 段階の予想プロセスを実行
   - `reports/yyyymmdd_<レース名>.md` (人間用) と `.json` (機械用) を並置出力
2. **直前オッズスナップショット**: 発走 5〜10 分前に `python3 .claude/skills/netkeiba-scraper/scripts/snapshot_odds.py <race_id>` を実行
   - 全 7 馬券種の確定オッズを `reports/yyyymmdd_<レース名>.odds.json` に保存
   - **発走後はオッズが消えるためこのタイミングが必須**
3. **結果照合**: レース後 `/keiba-result <race_id>` を実行
   - 着順・払戻金を取得し損益を計算
   - 該当 Markdown に「## 実績」章を追記
   - `reports/_backtest_log.csv` に 1 行追加
4. **集計レポート再生成**: `/keiba-backtest-summary` を実行
   - 全期間 / 馬券種別 / スタイル別の回収率を `reports/_backtest_summary.md` に出力（毎回再生成）

## 関連スキル・ファイル

### 予想
- `.claude/commands/keiba.md` — `/keiba` コマンド本体
- `.claude/skills/keiba-prediction/SKILL.md` — 8 段階予想プロセス
- `.claude/skills/keiba-prediction/strategies/<馬券種>.md` — 馬券種ごとの構成ルール
- `.claude/skills/netkeiba-scraper/SKILL.md` — 情報取得スキル

### バックテスト
- `.claude/commands/keiba-result.md` — 結果照合・損益記録
- `.claude/commands/keiba-backtest-summary.md` — 集計レポート再生成
- `.claude/skills/netkeiba-scraper/scripts/snapshot_odds.py` — 直前オッズスナップ保存
- `.claude/skills/netkeiba-scraper/scripts/match_result.py` — 結果照合スクリプト
- `.claude/skills/netkeiba-scraper/scripts/summarize_backtest.py` — 集計レポート生成
- `.claude/skills/netkeiba-scraper/scripts/_backtest_helpers.py` — 損益計算純関数（pytest テスト対象）

### データ
- `reports/yyyymmdd_<レース名>.md` — 予想レポート（人間用）
- `reports/yyyymmdd_<レース名>.json` — 買い目データ（機械用）
- `reports/yyyymmdd_<レース名>.odds.json` — 直前オッズスナップ
- `reports/_backtest_log.csv` — レース別損益ログ（追記式）
- `reports/_backtest_summary.md` — 集計レポート（再生成式）

評価方法・スコアリング詳細・前走凡走分類などは `keiba-prediction/SKILL.md` を参照。

## 環境構築

```bash
python3 -m venv venv
source venv/bin/activate
pip install requests beautifulsoup4 pandas lxml pytest
```

## テスト実行

```bash
source venv/bin/activate
pytest tests/ -v
```
