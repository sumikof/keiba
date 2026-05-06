# 競馬バックテスト機能 設計書

- 作成日: 2026-05-06
- 対象: `.claude/commands/`、`.claude/skills/netkeiba-scraper/scripts/`、`.claude/skills/keiba-prediction/SKILL.md`、`reports/`
- 目的: オッズスナップショット + 結果照合 + 集計の仕組みを追加し、今後のレースで予想の的中率・回収率を測定できるようにする

## 1. ゴールとスコープ

### 1.1 ゴール

1. `/keiba` 実行時に **買い目データを機械可読な JSON で並置出力** する
2. 発走直前に **全馬券種オッズの最終スナップショットを保存** できるようにする
3. レース後に **買い目と結果を照合し、損益を計算** して Markdown レポートに追記し、CSV ログに 1 行追加する
4. CSV から **馬券種別 / スタイル別の集計レポート** を再生成できるようにする
5. 損益計算は **純関数として pytest でテスト** する

### 1.2 スコープに含めるもの

- `/keiba` の段階 9 を拡張し JSON を並置出力
- 新コマンド `/keiba-result` `/keiba-backtest-summary`
- 新スクリプト `snapshot_odds.py` `match_result.py` `_backtest_helpers.py`
- 損益計算の単体テスト
- レポート Markdown への「実績」章追記、CSV ログ、集計 MD

### 1.3 スコープに含めないもの

- 過去レース（オッズが既に消失したレース）のバックテスト
- オッズの時系列変動分析（朝・昼・直前の複数スナップショット）
- グラフ可視化、期間絞り込み、競馬場別集計（YAGNI として後日対応）

## 2. 全体アーキテクチャ

### 2.1 ファイル構成

```
.claude/
├── commands/
│   ├── keiba.md                       # 既存（修正なし）
│   ├── keiba-result.md                # 新設：結果照合・損益記録
│   └── keiba-backtest-summary.md      # 新設：集計レポート出力
└── skills/
    ├── netkeiba-scraper/
    │   └── scripts/
    │       ├── snapshot_odds.py       # 新設：発走直前オッズを JSON 保存
    │       ├── match_result.py        # 新設：買い目と結果を照合し損益を計算
    │       └── _backtest_helpers.py   # 新設：集計・損益計算の純関数
    └── keiba-prediction/
        └── SKILL.md                   # 修正：段階 9 に「JSON 並置出力」を追記

reports/                                # 既存（gitignored）
├── yyyymmdd_<レース名>.md             # 既存：予想レポート
├── yyyymmdd_<レース名>.json           # 新設：買い目データ
├── yyyymmdd_<レース名>.odds.json      # 新設：発走直前オッズスナップ
├── _backtest_log.csv                  # 新設：レース別損益ログ（追記式）
└── _backtest_summary.md               # 新設：集計レポート（再生成式）

tests/
└── test_backtest_helpers.py           # 新設：損益計算のテスト
```

### 2.2 役割分担

- **`/keiba`**: 予想 + Markdown レポート + 買い目 JSON を出力
- **`snapshot_odds.py`**: 発走直前にユーザが手動実行。全馬券種オッズを `.odds.json` に保存
- **`/keiba-result <race_id>`**: レース後、買い目 JSON + オッズ JSON + 結果から損益を計算し、Markdown に「実績」章を追記、CSV に 1 行追加
- **`/keiba-backtest-summary`**: CSV を読んで `_backtest_summary.md` を再生成
- **`_backtest_helpers.py`**: 損益計算の純関数（pytest でテスト）

### 2.3 既存パターンへの整合

- `netkeiba-scraper` は引き続き「情報取得」の責務に集中（結果取得は元々スコープ内）
- `keiba-prediction` は「予想ロジック」の責務に集中（JSON 出力は段階 9 の出力形式の追加にとどまる）
- バックテスト固有のロジックはコマンドファイル + 純関数ヘルパーに閉じる

## 3. データフロー

### 3.1 タイムライン

```
[当日朝〜直前]                          [発走 5〜10 分前]                  [レース後]
       │                                       │                                │
       ▼                                       ▼                                ▼
 /keiba <レース名>                  python3 snapshot_odds.py             /keiba-result <race_id>
   --type sanrenpuku                 <race_id>
   --budget 10000                                                                │
       │                                       │                                │
       ▼                                       ▼                                ▼
 reports/yyyymmdd_<レース名>.md     reports/yyyymmdd_<レース名>.odds.json    実績を計算
 reports/yyyymmdd_<レース名>.json                                              ├─ Markdown レポートに「実績」章を追記
                                                                              └─ reports/_backtest_log.csv に 1 行追加
                                                                                    │
                                                                                    ▼
                                                                          /keiba-backtest-summary
                                                                                    │
                                                                                    ▼
                                                                          reports/_backtest_summary.md
                                                                          （集計を再生成）
```

### 3.2 各ステップの詳細

**1. 予想（`/keiba`）**
- 既存通りのフロー
- 段階 9 の出力で Markdown と並列に **JSON も書き出す**
- net keiba から取得した予想オッズ（参考値）も JSON に含める

**2. オッズスナップショット（`snapshot_odds.py`）**
- 引数: `<race_id>`、または `--latest` で `reports/` 内の未照合の最新レースを自動検出
- `get_odds.py` で取得した全馬券種オッズを `<race_id>` 単位で `.odds.json` に保存
- **発走後はオッズが消えるので、このタイミングが必須**
- スナップショット忘れ時は `/keiba-result` で警告（ただし結果照合は払戻金ベースで続行可能）

**3. 結果照合（`/keiba-result`）**
- 引数: `<race_id>`
- 必要ファイル: `<race>.json`（買い目）、`<race>.odds.json`（直前オッズ、任意）
- `get_race_result.py` で着順・払戻金を取得
- `_backtest_helpers.py` の関数で損益を計算
- Markdown レポートの末尾に「## 実績」章を追記
- `reports/_backtest_log.csv` に 1 行追加

**4. 集計（`/keiba-backtest-summary`）**
- CSV を読み込み、`_backtest_summary.md` を**再生成**（追記ではなく毎回上書き）
- 全期間 + 馬券種別 + スタイル別のテーブルを出力

### 3.3 エラーハンドリング

- `<race>.json` が存在しない → エラー「先に `/keiba <race>` で予想を立ててください」
- `<race>.odds.json` が存在しない → 警告 + 払戻金ベースで損益計算（精度落ちの旨を明示）
- レース未終了 → エラー「結果がまだ確定していません」

## 4. JSON / CSV スキーマ

### 4.1 買い目データ JSON: `reports/yyyymmdd_<レース名>.json`

```json
{
  "race_id": "202608030411",
  "race_name": "天皇賞(春)",
  "race_date": "2026-05-03",
  "venue": "京都",
  "course": "芝3200m",
  "bet_type": "sanrenpuku",
  "style": "balanced",
  "budget": 10000,
  "axis_horses": [7],
  "predicted_odds": {
    "tansho": [{"num": "1", "odds": "23.4"}],
    "sanrenpuku": [{"combination": "1-3-5", "odds": "45.6"}]
  },
  "bets": [
    {"combination": "7-3-12", "amount": 600, "category": "main"},
    {"combination": "7-3-1",  "amount": 400, "category": "dark_horse"}
  ],
  "total_amount": 10000,
  "generated_at": "2026-05-03T08:30:00+09:00"
}
```

`combination` は馬券種ごとの規約に従う:
- 単勝・複勝: `"7"` （単一馬番）
- ワイド・馬連・三連複: `"1-3-5"` （`-` で区切り、ソート済み馬番）
- 馬単・三連単: `"1→3→5"` （`→` で区切り、順序保持）

### 4.2 オッズスナップショット JSON: `reports/yyyymmdd_<レース名>.odds.json`

```json
{
  "race_id": "202608030411",
  "snapshot_at": "2026-05-03T15:35:00+09:00",
  "tansho":     [{"num": "1", "odds": "23.4"}],
  "fukusho":    [{"num": "1", "odds_low": "5.3", "odds_high": "8.1"}],
  "umaren":     [{"combination": "1-3", "odds": "12.4"}],
  "wide":       [{"combination": "1-3", "odds_low": "3.2", "odds_high": "4.5"}],
  "umatan":     [{"combination": "1→3", "odds": "25.6"}],
  "sanrenpuku": [{"combination": "1-3-5", "odds": "45.6"}],
  "sanrentan":  [{"combination": "1→3→5", "odds": "234.5"}]
}
```

### 4.3 損益ログ CSV: `reports/_backtest_log.csv`

ヘッダ:
```
race_id,race_date,race_name,bet_type,style,budget,total_invested,total_payout,profit,roi
```

例:
```csv
202608030411,2026-05-03,天皇賞(春),sanrenpuku,balanced,10000,10000,3200,-6800,0.32
202604010211,2026-05-03,越後S,umaren,longshot,3000,3000,4800,1800,1.60
```

カラム定義:
- `total_invested` = 実際に購入した合計額（通常 budget と同じ）
- `total_payout` = 払戻額（外れたら 0）
- `profit` = `total_payout - total_invested`
- `roi` = `total_payout / total_invested`（1.00 で収支トントン、小数 2 桁）

### 4.4 実績追記の Markdown 形式

`/keiba-result` が予想レポートの末尾に追記する章:

```markdown
## 実績

**結果照合実施**: 2026-05-04 10:00

### 着順

| 着 | 馬番 | 馬名 | 騎手 | タイム | 単勝 | 人気 |
|----|------|------|------|--------|------|------|
| 1  | 7    | クロワデュノール | 武豊 | 3:14.2 | 2.4 | 1 |
| 2  | 12   | ファントムサンダー | ルメール | 3:14.4 | 5.6 | 3 |
| 3  | 3    | サフィラ | 戸崎 | 3:14.6 | 8.9 | 4 |

### 的中買い目

| 組合せ | 投資額 | 配当倍率 | 払戻 |
|--------|--------|---------|------|
| 7-3-12 | 600 円 | 12.4 倍 | 7,440 円 |

**外れ買い目**: 19 点 / 9,400 円

### 収支

| 項目 | 金額 |
|------|------|
| 投資額 | 10,000 円 |
| 払戻額 | 7,440 円 |
| 収支 | **−2,560 円** |
| 回収率 | **74.4%** |
```

## 5. 損益計算ロジック

### 5.1 関数構成（`_backtest_helpers.py`）

```python
def parse_combination(combination: str, bet_type: str) -> tuple:
    """
    "1-3-5" → (1, 3, 5)  # 順不同（三連複）
    "1→3→5" → (1, 3, 5)  # 順序保持（三連単）
    """

def is_winning_bet(combination: str, bet_type: str, result: list[int]) -> bool:
    """
    買い目が当たりかを判定。
    result は 1-3 着の馬番リスト [1着, 2着, 3着]
    bet_type ごとに判定ルールが違う:
      - tansho: 1着のみ一致
      - fukusho: 3着以内（出走 8 頭以上の場合）
      - wide: 2 頭が 3 着以内
      - umaren: 1-2 着の組（順不同）
      - umatan: 1→2 着の順序一致
      - sanrenpuku: 1-3 着の組（順不同）
      - sanrentan: 1→2→3 着の順序一致
    """

def compute_payout(bet: dict, odds_snapshot: dict | None,
                   result: list[int], payoffs: list[dict]) -> int:
    """
    1 つの買い目の払戻額を計算。
    優先順位:
      1. 当たりでなければ 0 円を返す
      2. odds_snapshot に該当倍率があればそれを使う（amount × odds）
      3. なければ payoffs（実際の払戻金）を使う（100 円当たりの金額をスケール）
    """

def compute_race_pnl(bets_json: dict, odds_json: dict | None,
                     result: dict) -> dict:
    """
    1 レースの損益を計算。返り値:
      {
        "total_invested": int,
        "total_payout": int,
        "profit": int,
        "roi": float,  # 小数 2 桁
        "winning_bets": list[dict],
        "losing_bets": list[dict],
      }
    """

def aggregate_log(log_rows: list[dict]) -> dict:
    """
    CSV 行から集計。返り値:
      {
        "overall": {"races": N, "invested": ..., "payout": ..., "profit": ..., "roi": ..., "hit_races": ..., "hit_rate": ...},
        "by_bet_type": {"tansho": {...}, "sanrenpuku": {...}},
        "by_style": {"favorite": {...}, "balanced": {...}, "longshot": {...}}
      }
    """
```

### 5.2 払戻計算の優先順位

1. **オッズスナップショット優先** — 直前オッズが取れていれば `amount × odds` で精密に計算
2. **払戻金フォールバック** — オッズ無しなら netkeiba の払戻金（100 円当たり）を使い、`amount / 100 × 払戻` でスケール
3. 馬連・ワイドの「○○ - ○○」形式（範囲オッズ）は **下限値** を採用（保守的見積もり）

### 5.3 バリデーション

- `combination` が出走馬番に存在しない → エラー
- `result` の 3 着までが揃っていない（同着等のレアケース）→ 警告 + 該当レースをスキップ
- 不正な `bet_type` → エラー

### 5.4 テスト方針

`tests/test_backtest_helpers.py` で以下をテスト:

1. `parse_combination` — 三連複（順不同）、三連単（順序）、ワイド（順不同）など
2. `is_winning_bet` — 各馬券種の的中判定（当たり/外れ/同着シナリオ）
3. `compute_payout` — オッズあり / オッズなし、両ケース
4. `compute_race_pnl` — 全外れ / 1 点的中 / 複数的中 のシナリオ
5. `aggregate_log` — 1 レース / 複数レース / 馬券種別ブレイクダウン

各テストは固定データで検証（ネットワーク不要）。

## 6. 集計レポートの形式

`/keiba-backtest-summary` が `reports/_backtest_summary.md` を再生成する。

### 6.1 章立て

```markdown
# バックテスト集計レポート

**集計日時**: 2026-05-06 10:30
**対象レース数**: 12
**集計期間**: 2026-04-12 〜 2026-05-03

## 全期間サマリ

| 項目 | 値 |
|------|----|
| 総レース数 | 12 |
| 総投資額 | 96,000 円 |
| 総払戻額 | 78,400 円 |
| 収支 | **−17,600 円** |
| 回収率 | **81.7%** |
| 的中レース数 | 5 / 12 (41.7%) |

## 馬券種別

| 馬券種 | レース数 | 投資 | 払戻 | 収支 | 回収率 | 的中率 |
|--------|----------|------|------|------|--------|--------|
| 三連複 | 5 | 50,000 | 32,000 | −18,000 | 64.0% | 40.0% |
| 馬連 | 4 | 12,000 | 19,400 | +7,400 | 161.7% | 75.0% |

## スタイル別

| スタイル | レース数 | 投資 | 払戻 | 収支 | 回収率 | 的中率 |
|---------|----------|------|------|------|--------|--------|
| favorite | 3 | 12,000 | 8,000 | −4,000 | 66.7% | 33.3% |
| balanced | 7 | 70,000 | 55,400 | −14,600 | 79.1% | 42.9% |
| longshot | 2 | 14,000 | 15,000 | +1,000 | 107.1% | 50.0% |

## レース別履歴

| 日付 | レース | 馬券種 | スタイル | 投資 | 払戻 | 収支 | 回収率 |
|------|--------|--------|---------|------|------|------|--------|
| 2026-05-03 | 天皇賞(春) | 三連複 | balanced | 10,000 | 7,440 | −2,560 | 74.4% |
| 2026-05-03 | 越後S | 馬連 | longshot | 3,000 | 4,800 | +1,800 | 160.0% |
```

### 6.2 集計のルール

- **的中レース数** = `profit > 0` のレース数（収支プラス）
- **的中率** = 的中レース数 / レース数（馬券種・スタイルごとにも算出）
- **レース別履歴** = 日付降順（最新が上）
- **レース数が 3 未満のセル** には `*` を付与（標本数不足の注意喚起）
- 集計値の数値表記:
  - 金額はカンマ区切り
  - 回収率・的中率はパーセント表示（小数 1 桁）
  - 収支がマイナスなら `−` 接頭辞、プラスなら `+` 接頭辞

### 6.3 CSV から再生成

`_backtest_summary.md` は毎回 CSV から再生成（追記ではなく上書き）。CSV を編集すれば集計に反映される。新しいレースが照合されるたびに `/keiba-backtest-summary` を再実行する想定。

## 7. CLAUDE.md の更新範囲

`CLAUDE.md` の「作業フロー」セクションに以下を追記:

- 予想 → スナップショット → 結果照合 → 集計 の 4 ステップを明記
- バックテスト関連ファイルのパスを参照リスト（`関連スキル・ファイル`）に追加
- `_backtest_log.csv` と `_backtest_summary.md` の存在を明記

## 8. 将来の拡張余地（YAGNI として今回はスコープ外）

- 期間絞り込み（直近 1 ヶ月 / 全期間切り替え）
- グラフ可視化（matplotlib で回収率推移）
- 競馬場別 / 距離別の集計
- オッズ時系列分析（朝・昼・直前の複数スナップショット）

## 9. 確定事項（実装上の細部）

- **ファイル名規約**: 予想 JSON / オッズ JSON / Markdown レポートはすべて同じ `yyyymmdd_<レース名>` プレフィックスを使う。`snapshot_odds.py` は引数 `<race_id>` を受け取ったら、`reports/` 内の既存 `*.json` から `race_id` 一致のものを探し、その basename を取り出して `.odds.json` を組み立てる
- **タイムゾーン**: 全タイムスタンプを `+09:00`（JST）で固定
- **CSV ヘッダ自動付与**: ファイル不在時の初回作成時のみヘッダ書き込み
- **同着の扱い**: 着順テーブルの 1-3 着が 4 件以上ある場合（同着）は警告を出して当該レースをスキップ。集計には含めない
- **複勝・ワイドの範囲オッズ**: 下限を採用して保守的に計算（実払戻はそれ以上）
