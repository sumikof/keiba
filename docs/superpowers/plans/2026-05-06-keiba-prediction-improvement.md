# 競馬予想スキル改善 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 予想ロジックを 8 段階に整理し、馬券種・予算・スタイルをユーザ指定可能にし、対話／ワンライン両モードで動作する競馬予想スキルを構築する。

**Architecture:** `/keiba` コマンドが入口で引数解釈・対話分岐を行い、`netkeiba-scraper` で情報取得、`keiba-prediction` スキルで 8 段階の予想プロセスを実行、`strategies/<馬券種>.md` に馬券種ごとの構成ルールを分離する。

**Tech Stack:** Python 3 (requests, beautifulsoup4, lxml, pandas), pytest, Markdown スキルドキュメント。

**設計書:** `docs/superpowers/specs/2026-05-05-keiba-prediction-improvement-design.md`

---

## 重要な前提

このプロジェクトのスキルは **Markdown ドキュメント** が主体で、Claude が読み込んで実行する形式。Python スクリプトは `netkeiba-scraper` 配下のみが該当する。したがって:

- **TDD を厳密適用できるのは Task 1（スクレイパー拡張）と Task 11（予算配分計算ヘルパー）のみ。**
- ドキュメント主体のタスク（Task 2〜10、Task 12）は「**書く → セルフチェックリストで検証 → コミット**」のサイクル。
- 最終 Task で **実レースを 1 件流す end-to-end 動作確認** を行い、ドキュメントの実用性を検証する。

## File Structure

```
.claude/
├── commands/
│   └── keiba.md                            # 書き換え（Task 10）
└── skills/
    ├── netkeiba-scraper/
    │   ├── SKILL.md                        # 微更新（Task 1）
    │   └── scripts/
    │       ├── get_horse_info.py           # 拡張（Task 1）
    │       └── _prediction_helpers.py      # 新設（Task 11、予算配分）
    └── keiba-prediction/                   # 新設（Task 2）
        ├── SKILL.md                        # 新設（Task 2）
        └── strategies/                     # 新設
            ├── tansho.md                   # Task 3
            ├── fukusho.md                  # Task 4
            ├── wide.md                     # Task 5
            ├── umaren.md                   # Task 6
            ├── umatan.md                   # Task 7
            ├── sanrenpuku.md               # Task 8
            └── sanrentan.md                # Task 9

CLAUDE.md                                   # 書き換え（Task 12）
tests/                                      # 新設（Task 1, 11 用）
└── test_get_horse_info.py
└── test_prediction_helpers.py
```

各ファイルは責務が明確に分離されており、独立して理解・改修できる。

---

### Task 1: netkeiba-scraper の最小拡張（過去成績の通過順・上がり 3F・距離・馬場）

**目的:** `get_horse_info.py` の `get_horse_races()` を拡張し、予想ロジックで必要な「過去 5 走の通過順位・上がり 3F・距離・馬場（芝/ダ・状態）」を取得できるようにする。

**Files:**
- Create: `tests/test_get_horse_info.py`
- Modify: `.claude/skills/netkeiba-scraper/scripts/get_horse_info.py`
- Modify: `.claude/skills/netkeiba-scraper/SKILL.md`（出力項目の表を更新）

#### 背景

現状の `get_horse_races()` は以下のキーしか出力していない: `date, venue, weather, race_num, race_name, head_count, waku, umaban, odds, ninki, chakujun, jockey, kinryo, course, time, margin`。

netkeiba の `db.netkeiba.com/horse/result/<id>/` のテーブルには **通過順（道中位置）・上がり 3F・距離・馬場状態** のカラムが含まれているが、現状のコードはそれを抽出していない。

#### 実装方針

netkeiba の成績テーブルには以下のカラムが順序で含まれる（実装フェーズで実物 HTML を `requests` で取得し、ヘッダー文字列で位置を特定する）:
`日付, 開催, 天気, R, レース名, 映像, 頭数, 枠番, 馬番, オッズ, 人気, 着順, 騎手, 斤量, 距離, 馬場, タイム, 着差, 通過, ペース, 上り, 馬体重, 厩舎ｺﾒﾝﾄ, 備考, 勝ち馬(2着馬), 賞金`

カラム名でインデックスを引くロジックに変えて、追加項目を取得する。

- [ ] **Step 1: テストファイル作成（失敗するテストを書く）**

```python
# tests/test_get_horse_info.py
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".claude", "skills", "netkeiba-scraper", "scripts"))

from bs4 import BeautifulSoup
from get_horse_info import parse_race_row


def test_parse_race_row_extracts_passage_order():
    """過去レースの通過順を抽出できる"""
    headers = ["日付", "開催", "天気", "R", "レース名", "映像", "頭数",
               "枠番", "馬番", "オッズ", "人気", "着順", "騎手", "斤量",
               "距離", "馬場", "タイム", "着差", "通過", "ペース", "上り",
               "馬体重", "厩舎ｺﾒﾝﾄ", "備考", "勝ち馬(2着馬)", "賞金"]
    cells_text = ["2025/12/28", "中山4", "晴", "11", "有馬記念(G1)", "", "16",
                  "1", "1", "5.4", "3", "2", "ルメール", "57.0",
                  "芝2500", "良", "2:31.0", "0.1", "5-5-3-3", "60.4-35.6", "34.5",
                  "508(+2)", "", "", "ドウデュース", "70000"]
    row_html = "<tr>" + "".join(f"<td>{t}</td>" for t in cells_text) + "</tr>"
    row = BeautifulSoup(row_html, "lxml").find("tr")

    race = parse_race_row(row, headers)

    assert race["date"] == "2025/12/28"
    assert race["venue"] == "中山4"
    assert race["chakujun"] == "2"
    assert race["distance"] == "芝2500"
    assert race["baba"] == "良"
    assert race["passage"] == "5-5-3-3"
    assert race["agari"] == "34.5"
    assert race["pace"] == "60.4-35.6"


def test_parse_race_row_handles_missing_columns():
    """カラムが不足していても落ちず、空文字を入れる"""
    headers = ["日付", "開催", "着順"]
    cells_text = ["2025/12/28", "中山4", "2"]
    row_html = "<tr>" + "".join(f"<td>{t}</td>" for t in cells_text) + "</tr>"
    row = BeautifulSoup(row_html, "lxml").find("tr")

    race = parse_race_row(row, headers)

    assert race["date"] == "2025/12/28"
    assert race["passage"] == ""
    assert race["agari"] == ""
```

- [ ] **Step 2: テスト実行で失敗確認**

```bash
cd /workspace
source venv/bin/activate
pip install pytest 2>&1 | tail -5
pytest tests/test_get_horse_info.py -v
```

期待: `ImportError: cannot import name 'parse_race_row' from 'get_horse_info'` で失敗。

- [ ] **Step 3: `parse_race_row` を新設し、`get_horse_races` をリファクタ**

`.claude/skills/netkeiba-scraper/scripts/get_horse_info.py` の `get_horse_races` 関数を以下のように書き換える（`parse_race_row` を新設して切り出し）:

```python
def parse_race_row(row, headers: list[str]) -> dict:
    """成績テーブルの 1 行をヘッダー名ベースでパースする"""
    cells = row.find_all("td")
    if not cells:
        return {}

    def get_by_header(name: str) -> str:
        if name in headers:
            idx = headers.index(name)
            if idx < len(cells):
                return cells[idx].get_text(strip=True)
        return ""

    return {
        "date": get_by_header("日付"),
        "venue": get_by_header("開催"),
        "weather": get_by_header("天気"),
        "race_num": get_by_header("R"),
        "race_name": get_by_header("レース名"),
        "head_count": get_by_header("頭数"),
        "waku": get_by_header("枠番"),
        "umaban": get_by_header("馬番"),
        "odds": get_by_header("オッズ"),
        "ninki": get_by_header("人気"),
        "chakujun": get_by_header("着順"),
        "jockey": get_by_header("騎手"),
        "kinryo": get_by_header("斤量"),
        "distance": get_by_header("距離"),
        "baba": get_by_header("馬場"),
        "time": get_by_header("タイム"),
        "margin": get_by_header("着差"),
        "passage": get_by_header("通過"),
        "pace": get_by_header("ペース"),
        "agari": get_by_header("上り"),
        "weight": get_by_header("馬体重"),
    }


def get_horse_races(horse_id: str, max_races: int = 10) -> list[dict]:
    url = f"https://db.netkeiba.com/horse/result/{horse_id}/"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    resp.encoding = "EUC-JP"

    soup = BeautifulSoup(resp.text, "lxml")
    races = []

    race_table = soup.select_one("table.db_h_race_results, table.nk_tb_common")
    if not race_table:
        return races

    headers_row = race_table.select_one("tr")
    col_names = [th.get_text(strip=True) for th in headers_row.select("th")] if headers_row else []

    for row in race_table.select("tr")[1:]:
        race = parse_race_row(row, col_names)
        if race.get("date"):
            races.append(race)
        if len(races) >= max_races:
            break

    return races
```

- [ ] **Step 4: `print_horse_info` を更新して新項目を表示**

`print_horse_info` の近走成績テーブル出力部分を以下に置き換える:

```python
    if races:
        print(f"\n【近走成績（直近{len(races)}戦）】")
        print(f"  {'日付':<12} {'開催':<6} {'レース名':<20} {'頭数':<4} {'馬番':<4} "
              f"{'人気':<4} {'着順':<4} {'距離':<6} {'馬場':<4} "
              f"{'タイム':<8} {'着差':<6} {'通過':<10} {'上り':<5} {'ペース':<10}")
        print(f"  {'-'*130}")
        for r in races:
            print(
                f"  {r.get('date', ''):<12} {r.get('venue', ''):<6} "
                f"{r.get('race_name', ''):<20} {r.get('head_count', ''):<4} "
                f"{r.get('umaban', ''):<4} {r.get('ninki', ''):<4} "
                f"{r.get('chakujun', ''):<4} {r.get('distance', ''):<6} "
                f"{r.get('baba', ''):<4} {r.get('time', ''):<8} "
                f"{r.get('margin', ''):<6} {r.get('passage', ''):<10} "
                f"{r.get('agari', ''):<5} {r.get('pace', ''):<10}"
            )
    else:
        print("\n過去成績が取得できませんでした。")
```

- [ ] **Step 5: テスト実行で成功確認**

```bash
pytest tests/test_get_horse_info.py -v
```

期待: 2 件 PASS。

- [ ] **Step 6: ライブ動作確認（実 ID で取得）**

```bash
python3 .claude/skills/netkeiba-scraper/scripts/get_horse_info.py 2020104753 --races 5
```

期待: 出力に「通過」「上り」「距離」「馬場」のカラムが入っており、データが入っている（仮に空値があっても落ちない）。

- [ ] **Step 7: SKILL.md の機能選択テーブル下に追加情報を追記**

`.claude/skills/netkeiba-scraper/SKILL.md` の「出走馬情報（get_horse_info.py）」セクションの「出力」行を以下に置き換え:

```markdown
出力: 馬名、性別、毛色、生年月日、調教師、馬主、生産牧場、血統（父・母・母父）、通算成績、近走成績（**距離・馬場・通過順・上がり3F・ペース** を含む）
```

- [ ] **Step 8: コミット**

```bash
git add tests/test_get_horse_info.py \
        .claude/skills/netkeiba-scraper/scripts/get_horse_info.py \
        .claude/skills/netkeiba-scraper/SKILL.md
git commit -m "feat: extract passage/agari/distance/baba in horse race history"
```

---

### Task 2: keiba-prediction スキルの骨格作成（SKILL.md）

**目的:** 8 段階の予想プロセスを記述した `SKILL.md` を新設する。これが予想ロジックの中核。

**Files:**
- Create: `.claude/skills/keiba-prediction/SKILL.md`

- [ ] **Step 1: SKILL.md を新規作成**

`.claude/skills/keiba-prediction/SKILL.md` を以下の内容で作成:

````markdown
---
name: keiba-prediction
description: "中央競馬の予想を 8 段階のロジカルなプロセスで組み立てるスキル。レース条件分析・展開予想・全頭スコアリング・馬券種別買い目構成までを一貫して扱う。Use when: (1) 出走表・オッズ・全馬の過去成績がそろった状態で予想を立てる, (2) ユーザ指定の馬券種・予算・スタイルに合わせて買い目を組み立てる, (3) reports/ にレポートを出力する。Keywords: 競馬, 予想, 買い目, 馬券, 三連複, 三連単, 単勝, 複勝, 馬連, 馬単, ワイド, 展開, 脚質, 全頭評価. /keiba コマンドから呼び出される。"
---

# keiba-prediction

中央競馬の予想を 8 段階のロジカルなプロセスで組み立てる。情報取得は `netkeiba-scraper` スキルが担当し、本スキルは「取得済み情報を入力に予想を組み立てる」責務に集中する。

## 入力

- レース ID（または `/keiba` コマンドで特定済みのレース情報）
- 馬券種: `tansho` / `fukusho` / `wide` / `umaren` / `umatan` / `sanrenpuku` / `sanrentan`
- 予算: 整数（円）
- スタイル: `favorite` / `balanced` / `longshot`
- 軸馬指定（任意）: 馬番カンマ区切り

## 8 段階の予想プロセス

```
1. 入力受付       → 引数の確認・バリデーション
2. レース条件分析  → 競馬場・距離・馬場・ペース傾向の文章化
3. データ収集     → netkeiba-scraper で出走表・オッズ・全馬情報を取得
4. 展開・ペース予想 → 各馬の脚質分類とペース予測
5. 全頭スコアリング → 100 点満点で各馬を評価
6. 展開×評価補正  → 穴候補リストの作成・過大評価のフラグ立て
7. 軸・相手・穴選定 → スタイルに応じた 3 カテゴリの馬選び
8. 馬券構成       → strategies/<馬券種>.md に従って買い目を組む
```

最後に `reports/yyyymmdd_<レース名>.md` にレポートを出力する。

---

## 段階 1: 入力受付

- 馬券種が 7 種類のいずれかか確認
- 予算が 100 円単位の整数か確認（最低 100 円）
- スタイル省略時は `balanced`
- 軸馬指定が出走表に存在する馬番かを後段（段階 3 後）で確認

## 段階 2: レース条件分析

`netkeiba-scraper` の `get_race_entry.py` 出力から以下を整理し、**文章で考察を残す**:

- 競馬場・距離・コース（内回り / 外回り、芝 / ダート）
- 馬場状態・天候・クラス・賞金体系
- 「このコース・距離で有利な脚質」（一般論として）
- 「過去 5 年のペース傾向」（同レースの過去結果がある場合）

考察はそのままレポートの **第 2 章** にコピーする。

## 段階 3: データ収集

以下を `netkeiba-scraper` で取得する:

1. `get_race_entry.py <race_id>` — 出走表
2. `get_odds.py <race_id> --type tansho` — 単勝オッズ
3. `get_odds.py <race_id> --type fukusho` — 複勝オッズ
4. `get_odds.py <race_id> --type <user_type>` — ユーザ指定馬券種のオッズ
5. 各出走馬について `get_horse_info.py <horse_id> --races 10` — 過去 10 走

各馬の戦績は段階 4・5 で集計する。

## 段階 4: 展開・ペース予想

各馬の **過去 5 走の通過順** から脚質を推定する。

### 脚質分類ルール

過去 5 走の **第 1 コーナー通過順 / 出走頭数** の平均値で分類:

| 平均位置 | 脚質 |
|---------|------|
| 0.0〜0.2 | 逃げ |
| 0.2〜0.4 | 先行 |
| 0.4〜0.7 | 差し |
| 0.7〜1.0 | 追込 |

通過順データがない馬は「不明」として保留し、相応の不確実性を考察に含める。

### ペース予測

逃げ馬・先行馬の頭数で判定:

| 逃げ + 先行馬の数 | ペース予測 | 有利な脚質 |
|----------------|----------|----------|
| 5 頭以上 | Hi | 差し・追込 |
| 3〜4 頭 | Mid | バランス |
| 0〜2 頭 | Slow | 逃げ・先行 |

## 段階 5: 全頭スコアリング（100 点満点）

| 評価項目 | 配点 | 評価方法 |
|---------|------|---------|
| 同条件重賞実績 | 20 | 本番と同じ競馬場・距離での重賞着順（GI 1 着 = 20、GII 1 着 = 17、GIII 1 着 = 14、GI/II/III 2-3 着 = 10-15、GI/II/III 4-5 着 = 5-10、それ以外 0） |
| 競馬場別適性（コース連対率） | 15 | `(対象競馬場の 1 着 + 2 着) / 出走回数`、80% 以上 = +15、50-79% = +10、30-49% = +5、30% 未満 = −5、出走なし = −3 |
| 近走成績 | 15 | 直近 5 走の着順・タイム・着差。1-3 着 = +3 / 走、4-6 着 = +1 / 走、7 着以下 = 0、最大 15 |
| 前走凡走理由分析 | 10 | A〜D 分類で評価（下記） |
| 騎手・調教師 | 10 | リーディング上位騎手 = +5、当該コース実績 = +5、調教師 = +0〜5 |
| 血統・馬場適性 | 10 | 父・母父の傾向と当日馬場の合致度 |
| 脚質×展開適性 | 15 | 段階 4 の予想ペースで有利な脚質と各馬の脚質を照合（合致 = +15、半合致 = +8、不利 = +0、不明 = +5） |
| 人気との乖離 | 5 | 単勝オッズ上位 3 番人気 = +0、4-6 番人気 = +2、7 番人気以下 = +5 |

### 前走凡走理由分類（A〜D）

| 分類 | 定義 | 影響 |
|------|------|------|
| A. 能力的限界 | 格上挑戦で力不足 | −10〜0 |
| B. コース不適 | 得意でないコースでの凡走 | −3〜0（巻き返し可） |
| C. 展開不利 | ペースや位置取りが合わなかった | −5〜0 |
| D. 状態不良 | 馬体重急変・間隔詰め | −5〜0（条件付き） |

## 段階 6: 展開×評価の補正

段階 5 のスコアを段階 4 の展開予想と再度照合し、以下を作成する:

- **穴候補リスト**: 「展開不利で減点された馬の中で、本当は強い馬」「凡走理由が C（展開不利）と判定された馬」
- **過大評価フラグ**: 「展開有利で過大評価された馬」（人気上位だが今回は不利な脚質）

これは段階 7 と段階 8（穴選定）に直接使う。

## 段階 7: 軸・相手・穴の選定

スコアと展開を踏まえ、3 カテゴリに分ける:

- **軸馬**: スコア最上位 1〜2 頭 + ユーザ指定軸馬
- **相手**: 中位スコア + 展開がハマる馬
- **穴**: 段階 6 の穴候補リストから

スタイル別の比重:

| スタイル | 軸 | 相手 | 穴 |
|---------|----|------|----|
| favorite | スコア最上位、人気上位 | 上位 3〜4 頭 | 1 点だけ薄目 |
| balanced | スコア最上位（展開ハマる中位を許容） | 中位まで広げる | 必ず 1〜2 頭、予算 15-25% |
| longshot | 穴候補リストから選んでよい | 中位〜下位含む | 予算 40% 以上 |

## 段階 8: 馬券構成

ユーザ指定の馬券種に対応する `strategies/<馬券種>.md` を読み込み、書かれた構成ルール・予算配分ルールに従って買い目を組み立てる。

予算が小さく点数が組めない場合のフォールバック:

- 三連単で予算不足 → 三連複への変更を提案
- 単勝・複勝で予算 100 円ちょうど → 軸 1 頭 1 点で組む
- バリデーションは段階 8 の入口で実施

## 段階 9: レポート生成

`reports/yyyymmdd_<レース名>.md` に以下の章立てで出力する:

1. レース概要（条件・天候・馬場）
2. レース条件分析の考察（段階 2 の文章）
3. 展開・ペース予想（段階 4 の文章、脚質マップ含む）
4. 全頭評価表（馬番・評価点・コメント、段階 5 + 6 の結果）
5. 軸・相手・穴の選定理由（段階 7 の文章）
6. 買い目（馬券種・スタイル・予算配分、点数と金額の表）
7. 注目穴馬の根拠（段階 6 の穴候補から選んだ理由）
8. シナリオ別収支見込み

`reports/` ディレクトリの過去レポート（`20260426_マイラーズC.md` など）を参考フォーマットとして利用してよい。

---

## 馬券種別の戦略ファイル

各馬券種の具体的な構成ルールは `strategies/` 配下のファイルを参照:

- 単勝: `strategies/tansho.md`
- 複勝: `strategies/fukusho.md`
- ワイド: `strategies/wide.md`
- 馬連: `strategies/umaren.md`
- 馬単: `strategies/umatan.md`
- 三連複: `strategies/sanrenpuku.md`
- 三連単: `strategies/sanrentan.md`
````

- [ ] **Step 2: セルフチェック**

以下を確認:
- [ ] フロントマター (`---name---`) が正しい形式
- [ ] 8 段階すべてが本文に存在する
- [ ] 7 つの戦略ファイルへのリンクが書かれている
- [ ] スコアリング表の合計が 100 点

- [ ] **Step 3: コミット**

```bash
git add .claude/skills/keiba-prediction/SKILL.md
git commit -m "feat: add keiba-prediction skill with 8-stage prediction process"
```

---

### Task 3: 単勝（tansho）戦略ファイル

**Files:**
- Create: `.claude/skills/keiba-prediction/strategies/tansho.md`

- [ ] **Step 1: ファイル作成**

```markdown
# 単勝（tansho）買い目戦略

## 概要

- **払戻条件:** 1 着の馬を当てる
- **最低購入単位:** 100 円
- **特徴:** シンプル。1 頭の評価が直接当たり外れに直結する。低予算でも成立しやすい。

## 入力

- 軸馬リスト / 穴リスト / 予算 / スタイル

## 構成ルール

### favorite スタイル

- **軸馬 1 頭にすべて投入**
- 候補: スコア最上位 1 頭

### balanced スタイル

- **軸馬 1 頭 + 穴馬 1 頭の 2 頭買い**
- 配分: 軸 70%、穴 30%
- 端数は 100 円単位に切り上げ / 切り捨て調整

### longshot スタイル

- **穴馬 1〜2 頭に厚め**
- 軸馬は薄目（10〜20%）
- 穴馬: 段階 6 の穴候補リストから単勝オッズ 10 倍以上の馬を 1〜2 頭選ぶ

## 予算配分

| スタイル | 軸 | 穴 |
|---------|---|---|
| favorite | 100% | 0% |
| balanced | 70% | 30% |
| longshot | 10〜20% | 80〜90% |

## バリデーション

- 予算 100 円未満 → エラー
- balanced で予算 100 円 → favorite に切り替え（穴に配分できない）
```

- [ ] **Step 2: セルフチェック**

- [ ] 共通フォーマット（概要・入力・構成ルール・予算配分・バリデーション）に沿っている
- [ ] 3 スタイルすべて記述されている

- [ ] **Step 3: コミット**

```bash
git add .claude/skills/keiba-prediction/strategies/tansho.md
git commit -m "feat: add tansho buying strategy"
```

---

### Task 4: 複勝（fukusho）戦略ファイル

**Files:**
- Create: `.claude/skills/keiba-prediction/strategies/fukusho.md`

- [ ] **Step 1: ファイル作成**

```markdown
# 複勝（fukusho）買い目戦略

## 概要

- **払戻条件:** 3 着以内（出走 8 頭以上の場合）または 2 着以内（5〜7 頭）に入ればよい
- **最低購入単位:** 100 円
- **特徴:** 単勝より的中しやすいがオッズは低め。安定志向の馬券種。

## 入力

- 軸馬リスト / 穴リスト / 予算 / スタイル

## 構成ルール

### favorite スタイル

- **軸馬 1 頭にすべて投入**
- 候補: スコア最上位 1 頭

### balanced スタイル

- **軸馬 1 頭 + 対抗 1 頭の 2 頭買い**
- 配分: 軸 60%、対抗 40%
- 対抗は段階 7 の相手リスト最上位

### longshot スタイル

- **穴馬 1〜2 頭に厚め**
- 軸馬は薄目（10〜20%）
- 穴馬: 段階 6 の穴候補リストから複勝オッズ 5 倍以上の馬を 1〜2 頭選ぶ

## 予算配分

| スタイル | 軸 | 対抗 | 穴 |
|---------|---|------|---|
| favorite | 100% | 0% | 0% |
| balanced | 60% | 40% | 0% |
| longshot | 10〜20% | 0% | 80〜90% |

## バリデーション

- 予算 100 円未満 → エラー
- balanced で予算 100 円 → favorite に切り替え
```

- [ ] **Step 2: セルフチェック・Step 3: コミット**

```bash
git add .claude/skills/keiba-prediction/strategies/fukusho.md
git commit -m "feat: add fukusho buying strategy"
```

---

### Task 5: ワイド（wide）戦略ファイル

**Files:**
- Create: `.claude/skills/keiba-prediction/strategies/wide.md`

- [ ] **Step 1: ファイル作成**

```markdown
# ワイド（wide）買い目戦略

## 概要

- **払戻条件:** 選んだ 2 頭がともに 3 着以内に入ればよい（順序不問）
- **最低購入単位:** 100 円 / 1 点
- **特徴:** 馬連より的中しやすい。穴馬を絡めても無理なく的中する穏やかな馬券種。

## 入力

- 軸馬リスト / 相手リスト / 穴リスト / 予算 / スタイル

## 構成ルール

### favorite スタイル

- **軸馬 1 頭 × 上位 3 頭の流し（3 点）**
- 配分: 各点に均等

### balanced スタイル

- **軸馬 1 頭 × (相手上位 3 頭 + 穴 1〜2 頭) の流し（4〜5 点）**
- 配分: 上位への点を厚め（60〜70%）、穴に 30〜40%

### longshot スタイル

- **穴 × 穴を含む組み合わせ**
- 軸馬を 1〜2 頭の穴に置き、相手を中位〜上位に流す
- 4〜6 点で構成し、穴 × 穴の点に予算の 40% を投入

## 予算配分

| スタイル | 軸/上位 | 穴 |
|---------|--------|---|
| favorite | 100% | 0% |
| balanced | 60〜70% | 30〜40% |
| longshot | 30〜40% | 60〜70% |

## バリデーション

- 予算 / 点数が 100 円を切る → 点数を減らすか warn
- 軸馬と相手が同一馬の場合エラー
```

- [ ] **Step 2-3: セルフチェック・コミット**

```bash
git add .claude/skills/keiba-prediction/strategies/wide.md
git commit -m "feat: add wide buying strategy"
```

---

### Task 6: 馬連（umaren）戦略ファイル

**Files:**
- Create: `.claude/skills/keiba-prediction/strategies/umaren.md`

- [ ] **Step 1: ファイル作成**

```markdown
# 馬連（umaren）買い目戦略

## 概要

- **払戻条件:** 選んだ 2 頭が 1-2 着（順序不問）
- **最低購入単位:** 100 円 / 1 点
- **特徴:** ワイドより的中条件が厳しいぶん配当は高い。軸流しが基本。

## 入力

- 軸馬リスト / 相手リスト / 穴リスト / 予算 / スタイル

## 構成ルール

### favorite スタイル

- **軸馬 1 頭 × 上位 3〜4 頭の流し（3〜4 点）**
- 配分: 各点に均等、ただし軸×最上位の組み合わせを 2 倍にしてよい

### balanced スタイル

- **軸馬 1 頭 × (相手上位 3 頭 + 穴 1〜2 頭) の流し（4〜5 点）**
- 配分: 上位への点を厚め（55〜70%）、穴に 25〜35%、波乱用に 10〜15% を残す

### longshot スタイル

- **軸を穴に置く / 穴 × 穴含む BOX**
- 4〜6 点。穴 × 穴の組み合わせに予算の 40〜50% を投入

## 予算配分

| スタイル | 軸/上位 | 中位 | 穴 |
|---------|--------|------|---|
| favorite | 80〜90% | 10〜20% | 0% |
| balanced | 55〜70% | 20〜30% | 15〜25% |
| longshot | 20〜30% | 30〜40% | 40〜50% |

## バリデーション

- 予算 / 点数が 100 円未満 → 点数を減らす
- BOX 時の点数: 3 頭 BOX = 3 点、4 頭 BOX = 6 点
```

- [ ] **Step 2-3: セルフチェック・コミット**

```bash
git add .claude/skills/keiba-prediction/strategies/umaren.md
git commit -m "feat: add umaren buying strategy"
```

---

### Task 7: 馬単（umatan）戦略ファイル

**Files:**
- Create: `.claude/skills/keiba-prediction/strategies/umatan.md`

- [ ] **Step 1: ファイル作成**

```markdown
# 馬単（umatan）買い目戦略

## 概要

- **払戻条件:** 1 着→2 着の組み合わせを順序通りに当てる
- **最低購入単位:** 100 円 / 1 点
- **特徴:** 順序を当てる必要があり馬連より配当が高い。点数が増えやすいので予算との兼ね合いが重要。

## 入力

- 軸馬リスト / 相手リスト / 穴リスト / 予算 / スタイル

## 構成ルール

### favorite スタイル

- **軸 1 着固定 → 上位 3 頭の流し（3 点）**
- 配分: 均等

### balanced スタイル

- **軸 1 着固定 → (上位 3 頭 + 穴 1〜2 頭) の流し（4〜5 点）**
- 補助として、対抗 1 着 → 軸 2 着の点を 1 つ加える（合計 5〜6 点）
- 配分: 軸 1 着パターンを厚め（70%）、対抗 1 着パターンを薄め（30%）

### longshot スタイル

- **穴 1 着 → 上位 / 中位流し + 上位 1 着 → 穴 2 着の双方向**
- 5〜8 点
- 配分: 穴 1 着パターンに予算の 50% 以上

## 予算配分

| スタイル | 軸 1 着パターン | 対抗 1 着 | 穴 1 着 |
|---------|----------------|----------|--------|
| favorite | 100% | 0% | 0% |
| balanced | 70% | 30% | 0% |
| longshot | 20% | 30% | 50% |

## バリデーション

- 予算 < 点数 × 100 → 点数縮小か警告
- 予算 1000 円未満 + longshot は組みづらいので「balanced への変更」または「予算増額」を提案
```

- [ ] **Step 2-3: セルフチェック・コミット**

```bash
git add .claude/skills/keiba-prediction/strategies/umatan.md
git commit -m "feat: add umatan buying strategy"
```

---

### Task 8: 三連複（sanrenpuku）戦略ファイル

**Files:**
- Create: `.claude/skills/keiba-prediction/strategies/sanrenpuku.md`

- [ ] **Step 1: ファイル作成**

```markdown
# 三連複（sanrenpuku）買い目戦略

## 概要

- **払戻条件:** 1-3 着に入る 3 頭を順不同で当てる
- **最低購入単位:** 100 円 / 1 点
- **特徴:** 配当が大きく、フォーメーションで穴を絡められる。本プロジェクトのデフォルト馬券種。

## 入力

- 軸馬リスト / 相手リスト / 穴リスト / 予算 / スタイル

## 構成ルール

### favorite スタイル

- **1 頭軸フォーメーション**: 軸 1 頭 × 上位 4〜5 頭 × 上位 4〜5 頭
- 例: 軸 = 1 番、相手 1 列 = 2,3,4,5、相手 2 列 = 2,3,4,5 → 6 点
- 配分: 均等

### balanced スタイル（プロジェクトデフォルト）

- **メイン: 1 頭軸フォーメーション** 軸 1 頭 × 中位含む 4 頭 × 穴 1 頭含む 4 頭
- **サブ: 2 頭軸固定** 軸 + 対抗 2 頭固定 → 中位 3〜4 頭流し
- **大穴枠: 穴含む組み合わせ** 軸 × 穴 × 中位
- 配分: メイン 70〜80%、サブ 15% 以下、大穴 10〜15%

### longshot スタイル

- **2 頭軸フォーメーション + 穴を絡める**
- 軸 = 上位 1 + 穴 1、3 列目に中位〜下位を流す
- 配分: 穴絡みに予算の 40〜50%

## 予算配分

| スタイル | メイン（上位中心） | サブ（2 頭軸） | 大穴 |
|---------|------------------|--------------|------|
| favorite | 100% | 0% | 0% |
| balanced | 70〜80% | 10〜15% | 10〜15% |
| longshot | 30〜40% | 20〜30% | 40〜50% |

## 予算配分の決め方（balanced 1 万円の例）

```
予算 10,000 円
1 点 = 100 円
最大点数 = 100 点

メイン 1 頭軸フォーメ: 7,000 円 → 70 点
  軸 1 × 5 頭 × 5 頭 = 10 点 × 700 円 / 点 → 100 円単位に丸めて 700 円 × 10 点 = 7,000 円
サブ 2 頭軸固定: 1,500 円 → 15 点 (× 100 円)
大穴フォーメ: 1,500 円 → 15 点 (× 100 円)
```

## バリデーション

- 予算 < 600 円 → balanced の最小成立 (6 点) を割るので、favorite または点数縮小
- 軸馬・相手・穴で同一馬重複は不可
- フォーメーションの 3 列のうち 2 列以上で軸馬を含めると組み合わせが 0 点になるので注意
```

- [ ] **Step 2-3: セルフチェック・コミット**

```bash
git add .claude/skills/keiba-prediction/strategies/sanrenpuku.md
git commit -m "feat: add sanrenpuku buying strategy"
```

---

### Task 9: 三連単（sanrentan）戦略ファイル

**Files:**
- Create: `.claude/skills/keiba-prediction/strategies/sanrentan.md`

- [ ] **Step 1: ファイル作成**

```markdown
# 三連単（sanrentan）買い目戦略

## 概要

- **払戻条件:** 1-3 着の 3 頭を順序通りに当てる
- **最低購入単位:** 100 円 / 1 点
- **特徴:** 最高配当だが点数が爆発的に増える。フォーメーション必須。

## 入力

- 軸馬リスト / 相手リスト / 穴リスト / 予算 / スタイル

## 構成ルール

### favorite スタイル

- **1 着軸フォーメーション**: 軸 1 → 上位 3 → 上位 4
- 例: 1 → 2,3,4 → 2,3,4,5 → 各組み合わせを展開（軸を除いた重複なし）
- 配分: 軸 1 着の組み合わせを均等

### balanced スタイル

- **1 着軸フォーメ + 2 着の柔軟枠**:
  - メイン: 軸 1 → 上位 3 → 上位 + 穴 1
  - サブ: 上位 1 → 軸 → 上位（軸 2 着パターン）
- 配分: メイン 70%、サブ 30%

### longshot スタイル

- **穴 1 着フォーメも組み込む**:
  - メイン: 上位 1 → 軸 → 中位（軸 2 着）
  - 穴ブロック: 穴 → 上位 → 上位
- 配分: 穴ブロックに予算の 40% 以上

## 予算配分

| スタイル | 軸 1 着 | 軸 2 着 | 穴 1 着 |
|---------|--------|--------|--------|
| favorite | 100% | 0% | 0% |
| balanced | 70% | 30% | 0% |
| longshot | 20% | 30% | 50% |

## バリデーション

- **最低予算 3,000 円目安**: 三連単フォーメは点数が膨らむため、3,000 円未満では成立点数を組みづらい。
- 予算不足の場合、以下の優先順で提案:
  1. 点数縮小（軸 1 → 上位 2 → 上位 3）= 6 点
  2. 三連複への変更
- 軸馬・相手・穴で同一馬重複は不可
```

- [ ] **Step 2-3: セルフチェック・コミット**

```bash
git add .claude/skills/keiba-prediction/strategies/sanrentan.md
git commit -m "feat: add sanrentan buying strategy"
```

---

### Task 10: keiba コマンドの書き換え（引数仕様・対話/ワンライン）

**目的:** `.claude/commands/keiba.md` を書き換え、引数解釈・対話モードのフロー・即実行モードを定義する。

**Files:**
- Modify: `.claude/commands/keiba.md`

- [ ] **Step 1: コマンドファイルを書き換え**

`.claude/commands/keiba.md` の内容を以下に置き換え:

```markdown
# 競馬買い目検討（/keiba）

中央競馬の指定レースについて、`netkeiba-scraper` で情報を取得し、`keiba-prediction` スキルの 8 段階予想プロセスを実行して買い目レポートを `reports/` に作成する。

## 引数仕様

```bash
# 対話モード（不足分だけ聞く）
/keiba <レース名>

# ワンラインモード
/keiba <レース名> --type <馬券種> --budget <金額>
/keiba <レース名> --type <馬券種> --budget <金額> --style <スタイル>
/keiba <レース名> --type <馬券種> --budget <金額> --axis <馬番,馬番>
```

## 引数定義

| 引数 | 必須 | 値 | 省略時 |
|------|------|----|----|
| `<レース名>` | 必須 | 文字列（部分一致） | エラー |
| `--type` | 任意 | `tansho` / `fukusho` / `wide` / `umaren` / `umatan` / `sanrenpuku` / `sanrentan` | 対話で確認 |
| `--budget` | 任意 | 整数（円、100 円単位） | 対話で確認 |
| `--style` | 任意 | `favorite` / `balanced` / `longshot` | `balanced` |
| `--axis` | 任意 | 馬番カンマ区切り（例: `5,7`） | 自動選定 |

## 作業手順

### 1. レース特定

引数のレース名（`$ARGUMENTS` の最初のトークン）から `netkeiba-scraper` の `get_race_list.py` で**直近の開催レース**を検索する。

```bash
python3 .claude/skills/netkeiba-scraper/scripts/get_race_list.py
```

複数候補がある場合のみ「どのレースですか？」とユーザに確認する。1 件に絞れたら、レース ID を以後の処理で使う。

### 2. 引数の解釈と対話モード分岐

- `--type` `--budget` `--style` `--axis` のうち**未指定のものを順に 1 問ずつ**ユーザに尋ねる:
  1. 馬券種（`tansho` / `fukusho` / `wide` / `umaren` / `umatan` / `sanrenpuku` / `sanrentan` の番号 1〜7）
  2. 予算（円単位）
  3. スタイル（`favorite` / `balanced` / `longshot`、デフォルト = `balanced`）
  4. 軸馬指定（自動 / 馬番）
- 全項目が揃っているワンラインモードでは確認をスキップする
- 最後に「`<馬券種>・<予算>円・<スタイル>・軸<指定>` で予想を組み立てます。よいですか？」と確認（対話モード時のみ）

### 3. バリデーション

- 予算が 100 円未満 → エラー
- 予算が極端に小さく該当馬券種で点数が組めない → 警告し、馬券種変更を提案（基準は各 `strategies/<馬券種>.md` のバリデーション節）
- 軸馬が出走表に存在しない → エラー

### 4. 予想スキルの起動

`keiba-prediction` スキルを起動し、以下を入力として渡す:

- レース ID
- 馬券種・予算・スタイル・軸馬指定

スキル側で 8 段階の予想プロセスが実行され、`reports/yyyymmdd_<レース名>.md` にレポートが出力される。

### 5. 出力確認

レポートが生成されたら、ファイルパスをユーザに伝える。
```

- [ ] **Step 2: セルフチェック**

- [ ] 全引数が引数定義表に含まれている
- [ ] 対話モードで聞く順序が定義されている
- [ ] バリデーション項目が網羅されている

- [ ] **Step 3: コミット**

```bash
git add .claude/commands/keiba.md
git commit -m "feat: rewrite /keiba command with type/budget/style/axis args"
```

---

### Task 11: 予算配分ヘルパー（`_prediction_helpers.py`）

**目的:** 予算配分計算をテスト可能な Python 関数に切り出す。スキルドキュメントから直接 import せず、Claude が計算を任せたいときに使える小さなユーティリティを用意する。

**Files:**
- Create: `tests/test_prediction_helpers.py`
- Create: `.claude/skills/netkeiba-scraper/scripts/_prediction_helpers.py`

#### 補足

このファイルは「Claude が予算配分計算で迷ったときに使える明示的なリファレンス実装」として配置する。スキルドキュメントから「迷ったらこれを使え」と参照される。

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/test_prediction_helpers.py
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".claude", "skills", "netkeiba-scraper", "scripts"))

from _prediction_helpers import allocate_budget, round_to_unit


def test_allocate_budget_balanced_three_groups():
    """3 グループ (main, sub, dark_horse) に 70/15/15 で配分する"""
    result = allocate_budget(10000, {"main": 0.70, "sub": 0.15, "dark_horse": 0.15})
    assert result == {"main": 7000, "sub": 1500, "dark_horse": 1500}


def test_allocate_budget_rounds_to_100():
    """端数は 100 円単位に丸める"""
    result = allocate_budget(10000, {"main": 0.71, "sub": 0.14, "dark_horse": 0.15})
    # 0.71 * 10000 = 7100 → 7100, 0.14 = 1400, 0.15 = 1500
    assert result["main"] % 100 == 0
    assert result["sub"] % 100 == 0
    assert result["dark_horse"] % 100 == 0
    assert sum(result.values()) <= 10000


def test_allocate_budget_total_does_not_exceed():
    """配分合計が予算を超えない"""
    result = allocate_budget(3000, {"main": 0.70, "sub": 0.15, "dark_horse": 0.15})
    assert sum(result.values()) <= 3000


def test_round_to_unit_basic():
    """100 円単位への切り捨て"""
    assert round_to_unit(7150, 100) == 7100
    assert round_to_unit(7100, 100) == 7100
    assert round_to_unit(99, 100) == 0


def test_allocate_budget_too_small_raises():
    """予算が 100 円未満ならエラー"""
    import pytest
    with pytest.raises(ValueError, match="予算は 100 円以上"):
        allocate_budget(50, {"main": 1.0})
```

- [ ] **Step 2: テスト実行で失敗確認**

```bash
pytest tests/test_prediction_helpers.py -v
```

期待: ImportError で失敗。

- [ ] **Step 3: 最小実装**

`.claude/skills/netkeiba-scraper/scripts/_prediction_helpers.py` を新規作成:

```python
"""
予想ロジックで利用される予算配分・端数処理のヘルパー関数。
keiba-prediction スキルから「迷ったらこれを使え」と参照される。
"""

from __future__ import annotations


def round_to_unit(amount: int, unit: int = 100) -> int:
    """amount を unit 単位で切り捨てる"""
    return (amount // unit) * unit


def allocate_budget(total: int, ratios: dict[str, float], unit: int = 100) -> dict[str, int]:
    """
    予算 total を ratios の比率で配分し、各値を unit 単位に丸める。
    合計が total を超えないように切り捨てで処理。

    Args:
        total: 総予算（円）
        ratios: グループ名 → 比率 のマッピング（合計が 1.0 でなくても許容）
        unit: 丸め単位（デフォルト 100 円）

    Returns:
        グループ名 → 配分額 のマッピング

    Raises:
        ValueError: total が unit 未満の場合
    """
    if total < unit:
        raise ValueError(f"予算は {unit} 円以上必要です（指定: {total}）")

    return {
        name: round_to_unit(int(total * ratio), unit)
        for name, ratio in ratios.items()
    }
```

- [ ] **Step 4: テスト実行で成功確認**

```bash
pytest tests/test_prediction_helpers.py -v
```

期待: 5 件 PASS。

- [ ] **Step 5: keiba-prediction/SKILL.md に参照を追記**

`.claude/skills/keiba-prediction/SKILL.md` の段階 8 末尾に以下を追記:

```markdown

### 予算配分の計算ヘルパー

予算配分の計算で迷った場合は `.claude/skills/netkeiba-scraper/scripts/_prediction_helpers.py` の `allocate_budget(total, ratios)` を利用してよい。

例:

\`\`\`python
from _prediction_helpers import allocate_budget
allocate_budget(10000, {"main": 0.70, "sub": 0.15, "dark_horse": 0.15})
# {"main": 7000, "sub": 1500, "dark_horse": 1500}
\`\`\`
```

- [ ] **Step 6: コミット**

```bash
git add tests/test_prediction_helpers.py \
        .claude/skills/netkeiba-scraper/scripts/_prediction_helpers.py \
        .claude/skills/keiba-prediction/SKILL.md
git commit -m "feat: add budget allocation helpers with tests"
```

---

### Task 12: CLAUDE.md の更新

**目的:** プロジェクト指針を新方針（予算柔軟・馬券種 7 種・スタイル 3 種）に合わせる。

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: CLAUDE.md を以下に書き換え**

```markdown
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

1. ユーザは `/keiba <レース名> [--type ...] [--budget ...] [--style ...] [--axis ...]` で起動する
2. `/keiba` コマンドが引数解釈・対話分岐し、不足分はユーザに 1 問ずつ確認する
3. `keiba-prediction` スキルが 8 段階の予想プロセスを実行する:
   1. 入力受付 / 2. レース条件分析 / 3. データ収集 / 4. 展開・ペース予想
   5. 全頭スコアリング / 6. 展開×評価補正 / 7. 軸・相手・穴選定 / 8. 馬券構成
4. レポートを `reports/yyyymmdd_<レース名>.md` に出力する

## 関連スキル・ファイル

- `.claude/commands/keiba.md` — `/keiba` コマンド本体
- `.claude/skills/keiba-prediction/SKILL.md` — 8 段階予想プロセス
- `.claude/skills/keiba-prediction/strategies/<馬券種>.md` — 馬券種ごとの構成ルール
- `.claude/skills/netkeiba-scraper/SKILL.md` — 情報取得スキル

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
```

- [ ] **Step 2: セルフチェック**

- [ ] 既存の評価表・凡走分類・コース別適性表が `keiba-prediction/SKILL.md` に移動済みで、CLAUDE.md からは概要参照のみになっている
- [ ] 個人情報（メール等）が含まれていない

- [ ] **Step 3: コミット**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for flexible budget/type/style"
```

---

### Task 13: end-to-end 動作確認（実レース 1 件）

**目的:** 直近の実レース 1 件で `/keiba` を実行し、レポートが期待通り生成されることを確認する。

**Files:**
- Output: `reports/<yyyymmdd>_<レース名>.md`

#### 注意

このタスクは Claude が実際に `/keiba` 相当の処理を手動で実行する。`/keiba` コマンドはチャットスラッシュコマンドなので、本タスクではコマンド本文（`.claude/commands/keiba.md`）の手順に従って各ステップを手動で実行する。

- [ ] **Step 1: 直近のレース 1 件を選定**

```bash
source venv/bin/activate
python3 .claude/skills/netkeiba-scraper/scripts/get_race_list.py
```

期待: 直近の開催日のレース一覧が出力される。**当日または直近の重賞 1 件**を選び、レース ID をメモする。

- [ ] **Step 2: ワンラインモードでの実行**

例（実 ID に置き換え）:

```
仮想テスト: /keiba 〇〇〇 --type sanrenpuku --budget 10000 --style balanced
```

実際は Claude が内部的に以下を順に実行:

1. `get_race_list.py` でレース ID を確定
2. `get_race_entry.py <race_id>` で出走表
3. `get_odds.py <race_id> --type tansho`
4. `get_odds.py <race_id> --type sanrenpuku`
5. 各馬の `get_horse_info.py <horse_id> --races 10`
6. `keiba-prediction/SKILL.md` の 8 段階を順に実行
7. `strategies/sanrenpuku.md` の balanced ルールで買い目構成
8. `reports/<yyyymmdd>_<レース名>.md` に出力

- [ ] **Step 3: レポート内容の検証**

生成されたレポートに以下が含まれているかチェック:

- [ ] レース概要（条件・天候・馬場）
- [ ] レース条件分析の考察（段階 2 の文章）
- [ ] 展開・ペース予想（段階 4 の脚質マップ含む）
- [ ] 全頭評価表（段階 5 + 6 の結果、評価点とコメント）
- [ ] 軸・相手・穴の選定理由
- [ ] 買い目（馬券種・スタイル・予算配分、点数と金額の表）
- [ ] 注目穴馬の根拠
- [ ] シナリオ別収支見込み
- [ ] 合計金額が予算（10,000 円）以内に収まっている
- [ ] 穴馬が 1 頭以上含まれている（balanced スタイルなので必須）

- [ ] **Step 4: 対話モードでも 1 件確認**

別レースまたは同一レースで `/keiba <レース名>` のみで起動し、対話で馬券種・予算・スタイルを尋ねられることを確認。

- [ ] **Step 5: コミット**

```bash
git add reports/
git commit -m "test: verify end-to-end keiba prediction flow with real race"
```

- [ ] **Step 6: 動作確認サマリ**

end-to-end で動作したことを確認できれば実装完了。問題があれば該当 Task に戻って修正する。

---

## Self-Review

**1. Spec coverage チェック**

設計書 (`docs/superpowers/specs/2026-05-05-keiba-prediction-improvement-design.md`) の各セクションが計画でカバーされているか:

- 1. ゴールとスコープ → 計画全体で実装
- 2. 全体アーキテクチャ → ファイル構成が計画通り、Task 2-9 で構築
- 3. コマンドインターフェース仕様 → Task 10
- 4. 情報収集の拡張 → Task 1
- 5. 予想ロジック → Task 2（SKILL.md）+ Task 11（予算ヘルパー）
- 6. 馬券種別戦略 → Task 3-9
- 7. CLAUDE.md の更新 → Task 12
- 8. レポート出力の方針 → Task 2 の段階 9 + Task 13 で検証
- 9. 実装フェーズで判断する事項 → Task 1（通過順・上がり 3F の取得確認）、Task 13（最小予算検証）

**2. Placeholder scan**

「TBD」「TODO」「実装後に決める」「省略」を検索:
- 各 Task に必要なコード・ファイル内容が記載されている
- 戦略ファイル 7 つ全てに具体的な配分比とバリデーションが記載されている
- 段階 5 のスコアリングルールに具体的な点数計算式が記載されている

**3. Type consistency**

- スタイル名: `favorite` / `balanced` / `longshot` で全 Task 統一
- 馬券種名: `tansho` / `fukusho` / `wide` / `umaren` / `umatan` / `sanrenpuku` / `sanrentan` で全 Task 統一
- `parse_race_row` の戻り値キー（`distance`, `baba`, `passage`, `agari`, `pace`）が Task 1 内で一貫している
- `allocate_budget(total, ratios)` の引数名が Task 11 と SKILL.md 参照で一致

問題なし。
