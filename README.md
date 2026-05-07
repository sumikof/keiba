# keiba

中央競馬の予想・買い目検討・バックテストを Claude Code 上で行うプロジェクト。

## セットアップ

```bash
python3 -m venv venv
source venv/bin/activate
pip install requests beautifulsoup4 pandas lxml pytest
```

## 使い方

### 1. 予想

```
/keiba <レース名>
/keiba <レース名> --type <馬券種> --budget <金額>
/keiba <レース名> --type <馬券種> --budget <金額> --style <スタイル>
/keiba <レース名> --type <馬券種> --budget <金額> --axis <馬番,馬番>
```

馬券種: `tansho` / `fukusho` / `wide` / `umaren` / `umatan` / `sanrenpuku` / `sanrentan`
スタイル: `favorite`（堅め） / `balanced`（穴必須・既定） / `longshot`（高配当狙い）

`reports/yyyymmdd_<レース名>.md` (人間用) と `.json` (機械用) を出力。

### 2. 直前オッズスナップショット（バックテストに必須）

発走 5〜10 分前に実行:

```bash
python3 .claude/skills/netkeiba-scraper/scripts/snapshot_odds.py <race_id>
```

### 3. 結果照合

レース後:

```
/keiba-result <race_id>
```

該当レポートに「実績」章を追記、`reports/_backtest_log.csv` に 1 行追加。

### 4. 集計レポート

```
/keiba-backtest-summary
```

`reports/_backtest_summary.md` を再生成（馬券種別・スタイル別の回収率）。

## テスト

```bash
source venv/bin/activate
pytest tests/ -v
```

## 詳細ドキュメント

- 設計: [docs/superpowers/specs/](docs/superpowers/specs/)
- 実装計画: [docs/superpowers/plans/](docs/superpowers/plans/)
- Claude 向け運用指示: [CLAUDE.md](CLAUDE.md)
- 予想ロジック: [.claude/skills/keiba-prediction/SKILL.md](.claude/skills/keiba-prediction/SKILL.md)
- 馬券種別戦略: [.claude/skills/keiba-prediction/strategies/](.claude/skills/keiba-prediction/strategies/)
