# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

日本中央競馬（JRA）の買い目を検討するプロジェクト。netkeibaからレース情報を取得し、資産最大化を目指した馬券購入戦略を立案する。

## 目標・制約

- 予算上限: **1万円**
- 中心馬券: **三連複フォーメーション買い**
- フォーメーションには必ず**穴馬（人気薄）を含める**

## 作業フロー

1. `netkeiba-scraper` スキルを使ってレース情報を取得
2. 対象レースの出走表・オッズを取得
3. 全出走馬の過去成績を `get_horse_info.py` で取得
4. **全頭評価**: 各馬に評価理由と点数（スコア）を付ける
5. 評価を基に三連複フォーメーションの買い目を組み立て、1万円以内に収める

## スクリプトの使い方

依存ライブラリのインストール:
```bash
pip install requests beautifulsoup4 pandas lxml
```

スクリプトはすべて `.claude/skills/netkeiba-scraper/scripts/` に置かれている:

```bash
# 今日のレース一覧
python3 .claude/skills/netkeiba-scraper/scripts/get_race_list.py

# 出走表取得（レースID12桁）
python3 .claude/skills/netkeiba-scraper/scripts/get_race_entry.py <RACE_ID>

# 三連複オッズ取得
python3 .claude/skills/netkeiba-scraper/scripts/get_odds.py <RACE_ID> --type sanrenpuku

# 馬の過去成績取得
python3 .claude/skills/netkeiba-scraper/scripts/get_horse_info.py <HORSE_ID>

# レース結果確認
python3 .claude/skills/netkeiba-scraper/scripts/get_race_result.py <RACE_ID>
```

## レースID形式

12桁: `YYYYCCKKDDNN`
- CC: 競馬場コード（05=東京, 06=中山, 07=中京, 08=京都, 09=阪神 など）
- KK: 開催回、DD: 開催日、NN: レース番号

## 全頭評価の方針

各馬を以下の観点で評価し、100点満点でスコアリングする:
- 近走成績（着順・タイム・上がり3F）
- 距離・コース適性
- 騎手・調教師
- 人気（オッズ）との乖離（穴馬候補の発掘）
- 血統・馬場状態適性

## 買い目戦略

- 軸馬（上位評価）+ 相手馬（中・低評価の穴馬含む）でフォーメーション構成
- 点数 × 最低購入金額（100円）が1万円以内に収まるよう調整
- 穴馬を1頭以上必ずフォーメーションに組み込む
