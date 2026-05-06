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
