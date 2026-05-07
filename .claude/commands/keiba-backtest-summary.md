# バックテスト集計レポート再生成（/keiba-backtest-summary）

`reports/_backtest_log.csv` を読み込み、集計レポート `reports/_backtest_summary.md` を再生成する。

## 引数

なし。

## 作業手順

### 1. スクリプト実行

```bash
python3 .claude/skills/netkeiba-scraper/scripts/summarize_backtest.py
```

スクリプトが以下を実施する:

- `reports/_backtest_log.csv` を読む
- `_backtest_helpers.aggregate_log` で全期間 / 馬券種別 / スタイル別の集計を計算
- `reports/_backtest_summary.md` を **再生成**（追記ではなく上書き）

### 2. 実行結果のユーザへの報告

スクリプトの標準出力（対象レース数・回収率）をユーザに伝え、出力ファイルパスを示す。

### 3. エラー時の対処

`_backtest_log.csv` が無い場合: ユーザに「先に `/keiba-result` で 1 レース以上を照合してください」と案内する。
