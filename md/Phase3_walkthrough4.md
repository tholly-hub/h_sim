# 馬名命名規則改修 ウォークスルー

## 改修内容の概要

生まれた馬の名前について、以下の2点のご要望に対応いたしました。
1. **名前の形式**: `[冠名] + [単語] + [単語]`（2単語合成）となっていたものを **`[冠名] + [単語]`**（1単語のみ）に変更。
2. **重複防止ルール**: **重賞(G1, G2, G3)を勝利した馬の名前は二度とつけない（永久欠番）**ルールを導入。あわせて、現在活動中の馬（現役馬、供用中種牡馬、供用中繁殖牝馬）とも同時代重複しないよう管理。

---

## 変更されたファイルと主な実装内容

| 対象ファイル | 変更内容 |
| :--- | :--- |
| [name_generator.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/%E3%83%9E%E3%82%A4%E3%83%88%E3%82%99%E3%83%A9%E3%82%A4%E3%83%95%E3%82%99/h_sim/src/generators/name_generator.py) | 2単語合成（`_generate_compound_word`）を廃止し、必ず `[冠名] + [単語]`（1単語）で生成。禁止馬名セットを一括設定する `set_forbidden_names` を追加。 |
| [breeding.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/%E3%83%9E%E3%82%A4%E3%83%88%E3%82%99%E3%83%A9%E3%82%A4%E3%83%95%E3%82%99/h_sim/src/core/breeding.py) | 交配・出産時の `_sync_existing_names` において、**重賞(G1/G2/G3)勝利馬（過去の引退馬含む全世代）** および **現在活動中（現役・種牡馬・繁殖牝馬）の馬** を抽出し、命名禁止馬名としてジェネレータへ設定。 |
| [schema.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/%E3%83%9E%E3%82%A4%E3%83%88%E3%82%99%E3%83%A9%E3%82%A4%E3%83%95%E3%82%99/h_sim/src/db/schema.py) | 重賞未勝利で引退した馬の名前の再利用を可能にするため、`horses` テーブルの `name` 列の `UNIQUE` 制約を解除し、検索用インデックス `idx_horses_name` を配置。 |
| [test_horse_name_uniqueness.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/%E3%83%9E%E3%82%A4%E3%83%88%E3%82%99%E3%83%A9%E3%82%A4%E3%83%95%E3%82%99/h_sim/tests/test_horse_name_uniqueness.py) | 生成される馬名がすべて `[冠名] + [単語]` であること、重賞勝ち馬の名前が再利用されないこと、重賞未勝利引退馬の名前は除外されることのユニットテストを追加。 |

---

## 検証結果

### 1. ユニットテスト
`python3 -m unittest discover tests` を実行し、全テスト（54件）がすべてパスすることを確認しました。

### 2. 当歳馬命名の実機シミュレーション検証
新規データベースを作成し、初期化後に年度交配・出産処理（500頭誕生）を実行して検証しました：
- **形式検証**: 誕生した500頭すべてが `[冠名] + [単語]`（1単語のみ）で命名されていることを確認（アサーション通過）。
- **重複排除検証**:
  - 過去の重賞(G1, G2, G3)勝利馬（40頭）と同名の当歳馬は **0頭（完全重複なし）**。
  - 同年度誕生馬500頭同士の重複も **0頭**。

#### 誕生した当歳馬のサンプル例:
1. `ハタノコロナ`（ハタノ ＋ コロナ）
2. `ライデンカトリーヌ`（ライデン ＋ カトリーヌ）
3. `スエヒロタンザナイト`（スエヒロ ＋ タンザナイト）
4. `カガミインダス`（カガミ ＋ インダス）
5. `キララキウイ`（キララ ＋ キウイ）
6. `マキハラエレーナ`（マキハラ ＋ エレーナ）
7. `ヒビキチューリップ`（ヒビキ ＋ チューリップ）
8. `スワノツツジ`（スワノ ＋ ツツジ）
9. `クワハラルベライト`（クワハラ ＋ ルベライト）
10. `ハタノオパール`（ハタノ ＋ オパール）
