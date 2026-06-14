# オッズ取得のJSON API化 + 予想時オッズの採用 — 設計

- **日付:** 2026-06-14
- **対象:** `.claude/skills/netkeiba-scraper`, `.claude/skills/keiba-prediction`, `.claude/commands/keiba.md`, `CLAUDE.md`

## 背景・課題

`/keiba` の予想時およびバックテストで使うオッズが「毎回正しく取得できない」。

### 根本原因

`get_odds.py` は `https://race.netkeiba.com/odds/index.html` の**静的HTMLテーブル**をパースしている。しかし netkeiba はオッズを JavaScript / AJAX で描画するため、静的HTMLにはオッズ値が存在せず `---.-`（プレースホルダ）しか入っていない。「オッズが確定していないから取れない」のではなく、**HTML経由では暫定オッズすら取得できない**のが真因。

### 確認済みの事実（2026-06-14 検証）

netkeiba の JSON API は暫定オッズを完全な形で返す：

```
GET https://race.netkeiba.com/api/api_get_jra_odds.html?race_id=<id>&type=<n>&action=update
```

- `status`: `"middle"`（暫定/中間オッズ） / `"final"`（確定） / 発売前は別値
- `data.odds`: 馬券種ごとのオッズ辞書
- 1リクエストで該当馬券種の**全通り**が返る（現状の三連系「軸馬1〜18ループ」が不要になる）

`type` パラメータと `data.odds` のキー対応（検証済み: 1, 4, 7。残りは実装時に確認）：

| 馬券種 | api type | odds キー | エントリ形式 |
|--------|----------|-----------|--------------|
| 単勝 | 1 | `"1"` | `{馬番: ["オッズ", "", "人気"]}` |
| 複勝 | 1 | `"2"` | `{馬番: ["低", "高", "人気"]}` |
| 馬連 | 4 | `"4"` | `{"0102": ["オッズ", "", "人気"]}` |
| ワイド | 5 | `"5"` | `{"0102": ["低", "高", "人気"]}` |
| 馬単 | 6 | `"6"` | `{"0102": ["オッズ", "", "人気"]}` |
| 三連複 | 7 | `"7"` | `{"010203": ["オッズ", "", "人気"]}` |
| 三連単 | 8 | `"8"` | `{"010203": ["オッズ", "", "人気"]}` |

- 単勝・複勝は `type=1` の1リクエストで両方取得できる。
- 組み合わせキーは2桁ゼロ埋めの馬番連結（`"0102"`, `"010203"`）。
- **全6馬券種を `requests` で取得できることを 2026-06-14 に実地検証済み。** 件数は14頭出走で馬連91=C(14,2)、三連複364=C(14,3)、三連単2184=14×13×12 と理論値に完全一致。三連系も1リクエストで全通り返る。

### `status` の値（検証済み）

| status | 意味 | 場面 |
|--------|------|------|
| `middle` | 暫定/中間オッズ | 発売中（予想時） |
| `result` | 確定オッズ | レース確定後（過去レース） |
| `NG` | データ無し | 無効なレースID・発売前など |

- **堅牢性要件:** `status=="NG"` のとき `data` は dict ではなく**空文字列 `""`** を返す。パーサは `data`/`odds` が dict でない場合に空結果を返すようガードすること。
- `Referer` ヘッダは無くても取得できるが、保険として付与する。

## 採用方針（ユーザ確定事項）

1. **バックテストの払戻計算には「予想時点のオッズ」を採用する。** `/keiba` 実行時に取得した暫定オッズを `reports/<basename>.odds.json` として自動保存し、それをオッズ・オブ・レコードとする。
2. **発走直前の手動スナップ手順 (`snapshot_odds.py`) は任意の上書き用として残す。** API化して動くようにし、より直前のオッズで上書きしたい場合に手動実行できるCLIとして存続させる。

## アプローチ選定

- **(A) JSON API利用** ← 採用。完全な暫定オッズを取得でき、三連系も1リクエスト。
- (B) ヘッドレスブラウザでJS描画を待つ → 重く・遅く・壊れやすい。却下。
- (C) HTMLのまま別セレクタ探索 → HTMLにオッズ値が無いため不可能。却下。

## 設計

### 1. コア：`get_odds.py` の API 化

ネットワーク層とパース層を分離する。

- `_fetch_api_json(race_id, api_type) -> dict` — APIを叩いて JSON を dict で返す（ネットワーク、`requests`）。
  - リクエストヘッダに `Referer`（`https://race.netkeiba.com/odds/index.html?race_id=<id>`）を付与。
  - `status` と `data` を含むトップレベル dict を返す。
- **純関数パーサ**（pytest 対象、ネットワーク非依存）：
  - `parse_tansho_fukusho(api_json) -> {"tansho": [...], "fukusho": [...]}`
    - tansho エントリ: `{"num", "odds"}`
    - fukusho エントリ: `{"num", "odds_low", "odds_high"}`
  - `parse_combined(api_json, odds_key) -> list[list]`
    - `"0102"` → `["1", "2", "オッズ"]`（ゼロ埋め解除）。ワイドは low を採用（現行 `fetch_combined_odds` 互換）。
  - `parse_sanren(api_json, odds_key) -> list[list]`
    - `"010203"` → `["1", "2", "3", "オッズ"]`。
  - オッズ順ソートは現行同様（数値変換不可は末尾）。
- **公開関数名を維持**し中身のみ差し替える（`snapshot_odds.py` を壊さない）：
  - `fetch_tansho_fukusho(race_id)` → `parse_tansho_fukusho(_fetch_api_json(race_id, 1))`
  - `fetch_combined_odds(race_id, type_param)` → API化。`type_param`（現行 `b4` 等）→ api type への変換マップを内部に持つ。
  - `fetch_sanren_odds(race_id, type_param, head_count=18)` → API化。`head_count` 引数は後方互換のため残すが**未使用**（1リクエストで全通り取得）。
- `status` の扱い: パーサは `data.odds` を見るが、`status` は呼び出し側（`fetch_all_odds`）で参照して `odds_status` として記録する。
- CLI (`main`) は現行のまま（`race_id`, `--type`）。出力フォーマットも維持。

### 2. 共有関数 `fetch_all_odds` の移設・拡張

現在 `snapshot_odds.py` にある「全7馬券種を集約して dict を返す」ロジックを `get_odds.py`（共有モジュール）へ移す。

- `fetch_all_odds(race_id, head_count=18) -> dict`
  - 既存の `.odds.json` スキーマ（`tansho` / `fukusho` / `umaren` / `wide` / `umatan` / `sanrenpuku` / `sanrentan`）を維持。`compute_payout` の期待形式を変えない。
  - `race_id`, `snapshot_at`（JST ISO）に加え `odds_status`（API `status`）を追加。
  - リクエスト間の `time.sleep` は節度ある間隔を維持。
- `snapshot_odds.py` は `get_odds.fetch_all_odds` を import して使う（重複ロジック削除）。

### 3. `/keiba` 予想フローの変更（中核要件）

- `keiba-prediction/SKILL.md` のデータ収集段に、予想時点の暫定オッズを `reports/<basename>.odds.json`（全7馬券種）として**自動保存**するステップを追加。
  - 実行コマンド: 予想JSON出力後に `snapshot_odds.py <race_id>`（basename 自動検出）を呼ぶ、または `get_odds.fetch_all_odds` を直接利用して保存する。本スペックでは **`snapshot_odds.py` を予想直後に自動実行**して `.odds.json` を生成する方式とする（経路を1つに統一）。
  - これがバックテストの払戻計算で使う「オッズ・オブ・レコード」になる。
- `predicted_odds`（参考値）は従来どおり予想JSONに残す。
- `keiba.md` コマンド本体にも同フローを反映。

### 4. `snapshot_odds.py` は任意の上書き用として存続

- API化（`fetch_all_odds` 経由）で動くようにする。
- `/keiba` が予想時に自動生成した `.odds.json` を、より直前のオッズで**上書き**したい場合に手動実行できる。
- `odds_status` を出力に含め、`final` か `middle` かが分かるようにする。

### 5. ドキュメント更新

- `netkeiba-scraper/SKILL.md` — JSON API 化の注記、`get_odds.py` がHTMLでなくAPIを使う旨、`odds_status` の説明、三連系が1リクエストになった旨。
- `keiba-prediction/SKILL.md` — 予想時オッズ自動保存ステップを明記。`predicted_odds` と `.odds.json` の役割の違い。
- `CLAUDE.md` — 作業フロー2段目「直前オッズスナップショット」を**任意（上書き用）** に格下げ。予想時に `.odds.json` が自動生成される旨を追記。

### 6. テスト（TDD）

- APIレスポンス（`type=1/4/5/6/7/8`）を保存した JSON フィクスチャを `tests/fixtures/`（または既存テスト構成に合わせた場所）に置く。
- `parse_tansho_fukusho` / `parse_combined` / `parse_sanren` の純関数を pytest で検証：
  - ゼロ埋めキーの解除（`"0102"` → `["1","2",...]`）
  - 単勝/複勝の分離と low/high
  - ソート順
  - 空オッズのハンドリング（`status=="NG"` で `data==""` の場合に空結果を返す）
- 既存の `_backtest_helpers` テストが壊れないこと（`.odds.json` スキーマ不変）を確認。

## 影響範囲・互換性

- `.odds.json` のスキーマは不変（`odds_status` 追加のみ）。`compute_payout` / `match_result.py` は変更不要。
- `get_odds.py` の公開関数シグネチャ維持 → `snapshot_odds.py` の既存呼び出しと後方互換。
- `fetch_sanren_odds` の `head_count` 引数は互換のため残すが無視される。

## 非対象（YAGNI）

- 枠連（wakuren）対応の新規追加。
- オッズの時系列・複数スナップ保持。
- ヘッドレスブラウザ導入。
