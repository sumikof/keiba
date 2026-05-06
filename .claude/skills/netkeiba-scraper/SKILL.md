---
name: netkeiba-scraper
description: "netkeibaをスクレイピングして日本中央競馬(JRA)のレース情報を取得するスキル。Use when: (1) 競馬のレース一覧・開催情報を調べたい, (2) 出走表・枠順・出走馬を確認したい, (3) 単勝・複勝・馬連などのオッズを取得したい, (4) 出走馬のプロフィールや過去成績を調べたい, (5) レース結果・着順・払戻金を確認したい. Keywords: netkeiba, 競馬, 中央競馬, JRA, レース情報, race info, 出走表, 枠順, オッズ, odds, 馬券, horse racing, 出走馬, 成績, 払戻, 単勝, 複勝, 馬連, 馬単, 3連複, 3連単, レース結果, race result, horse profile, 血統, 騎手, 調教師, scraping, スクレイピング. このスキルはnetkeibaに関する競馬情報の取得が必要なときは必ず使うこと。"
---

# netkeiba-scraper

netkeibaをスクレイピングしてJRA（日本中央競馬）のレース情報・出走情報・オッズ・馬情報・レース結果を取得するスキル。

## 必須環境

```bash
pip install requests beautifulsoup4 pandas lxml
```

## ワークフロー

1. **タスク特定** → 下表から目的に合うスクリプトを選ぶ
2. **レースID特定** → レースIDが必要な場合は `get_race_list.py` で確認するか、ユーザに確認
3. **スクリプト実行** → `python scripts/<スクリプト名>.py <引数>`
4. **結果解釈** → 出力テーブルを読み取ってユーザに説明する

## 機能選択テーブル

| 目的 | スクリプト | 使用例 |
|------|-----------|--------|
| 開催レース一覧を取得 | `get_race_list.py` | `python ./scripts/get_race_list.py 20250101` |
| 出走表・枠順を取得 | `get_race_entry.py` | `python ./scripts/get_race_entry.py 202501010101` |
| オッズを取得 | `get_odds.py` | `python ./scripts/get_odds.py 202501010101` |
| 出走馬のプロフィール・成績 | `get_horse_info.py` | `python ./scripts/get_horse_info.py 2020104753` |
| レース結果・着順・払戻 | `get_race_result.py` | `python ./scripts/get_race_result.py 202501010101` |

## レースIDの形式

JRAのレースIDは12桁の数字：`YYYYCCKKDDNN`

| 部分 | 桁数 | 説明 | 例 |
|------|------|------|----|
| YYYY | 4 | 年 | 2025 |
| CC | 2 | 競馬場コード | 05=東京, 06=中山, 08=京都, 09=阪神 |
| KK | 2 | 開催回 | 01〜06 |
| DD | 2 | 開催日 | 01〜12 |
| NN | 2 | レース番号 | 01〜12 |

**競馬場コード一覧：**
`01=札幌, 02=函館, 03=福島, 04=新潟, 05=東京, 06=中山, 07=中京, 08=京都, 09=阪神, 10=小倉`

## 各スクリプトの詳細

### 開催レース一覧（get_race_list.py）

```bash
# 今日のレース一覧
python ./scripts/get_race_list.py

# 日付を指定（YYYYMMDD形式）
python ./scripts/get_race_list.py 20250601
```

出力: 競馬場名、レース番号、レース名、発走時刻、出走頭数、レースID

### 出走表・枠順（get_race_entry.py）

```bash
python ./scripts/get_race_entry.py 202501010101
```

出力: 枠番、馬番、馬名、性齢、斤量、騎手、調教師、馬体重、前走成績

### オッズ（get_odds.py）

```bash
# 単勝・複勝（デフォルト）
python ./scripts/get_odds.py 202501010101

# 馬連
python ./scripts/get_odds.py 202501010101 --type umaren

# 3連複
python ./scripts/get_odds.py 202501010101 --type sanrenpuku
```

対応馬券: `tansho`（単勝）, `fukusho`（複勝）, `umaren`（馬連）, `umatan`（馬単）, `wide`（ワイド）, `sanrenpuku`（3連複）, `sanrentan`（3連単）

### 出走馬情報（get_horse_info.py）

```bash
# 馬IDで検索（db.netkeiba.comのURL末尾の数字）
python ./scripts/get_horse_info.py 2020104753

# 馬名で検索（出走表から馬IDを取得して自動検索）
python ./scripts/get_horse_info.py --name "イクイノックス"
```

出力: 馬名、性別、毛色、生年月日、調教師、馬主、生産牧場、血統（父・母・母父）、通算成績、近走成績（**距離・馬場・通過順・上がり3F・ペース** を含む）

### レース結果（get_race_result.py）

```bash
python ./scripts/get_race_result.py 202501010101
```

出力: 着順、枠番、馬番、馬名、タイム、着差、騎手、斤量、人気、オッズ、払戻金情報

## 注意事項

- スクレイピングは節度をもって使用すること（連続リクエスト時は自動で1秒待機）
- netkeibaはログインなしでも基本情報は取得可能
- オッズはリアルタイムで変動するため、発走直前が最終オッズ
- 馬IDはdb.netkeiba.comの馬ページURLから確認できる（例: `https://db.netkeiba.com/horse/2020104753/`）
