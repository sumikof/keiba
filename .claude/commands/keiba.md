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
