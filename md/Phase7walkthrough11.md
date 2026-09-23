# 2年目1月における未出走2歳馬の引退誤判定修正 Walkthrough

## 実施した変更内容

### 1. データベーススキーマおよびマイグレーションの改修
- [`src/db/schema.py`](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/db/schema.py):
  - `horses` テーブルに `retired_year INTEGER`（引退年度）カラムを追加。
  - `idx_horses_retired_year` インデックスを追加。
- [`src/db/database.py`](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/db/database.py):
  - 既存のDBファイル読み込み時にも自動的に `retired_year` カラムとインデックスを補完・作成するマイグレーションロジックを追加。

### 2. 引退判定ロジックとルールの厳格化
- [`src/race/calendar.py`](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/race/calendar.py) (`_process_3yo_maiden_retirement`):
  - **3歳9月4週（第36週）終了時**に、3歳未勝利馬（0勝・未出走馬）を引退させ、`retired_year = year, trainer_id = NULL, jockey_id = NULL` を記録。
  - **2歳馬は第36週時点でも絶対に引退させない**ことを保証。
- [`src/core/lifecycle.py`](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/core/lifecycle.py) (`advance_year`):
  - 年末進行時の現役馬引退処理において、4歳〜8歳以上の古馬のみを対象とし、引退時に `retired_year = current_year, trainer_id = NULL, jockey_id = NULL` を記録。
  - **2歳馬（年進行で3歳になる馬）は年末進行で引退させず、3歳現役馬として継続**することを保証。

### 3. 年末表彰ダイアログおよび馬ブラウザの引退馬抽出クエリ修正
- [`src/gui/views/annual_events_dialogs.py`](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/views/annual_events_dialogs.py) (`YearEndAwardsDialog`):
  - 「本年引退競走馬一覧」タブのクエリを `WHERE h.retired_year = ? AND h.is_sire = 0 AND h.is_dam = 0` に修正。
  - これにより、未出走の幼駒や年越し現役馬が誤って「引退馬」として表示される不具合を根本解消。
- [`src/gui/views/horse_browser_view.py`](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/views/horse_browser_view.py):
  - 「引退馬」および「当歳・1歳」のフィルタ条件を `retired_year` を用いて適正化。

### 4. データベースロック競合の解消
- [`src/views/pedigree_builder.py`](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/views/pedigree_builder.py), [`src/core/breeding.py`](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/core/breeding.py):
  - 繁殖・種付けイベント実行時の `get_ancestors_tree` でトランザクションの `conn` を引き回すように修正し、SQLiteのテーブルロック競合（`database table is locked`）を解消。

---

## 検証結果

### 自動単体テスト
- 新規追加テスト [`tests/test_maiden_retirement.py`](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/tests/test_maiden_retirement.py):
  1. `test_2yo_not_retired_on_new_year`: 1年目終了・年進行（2年目1月）時に2歳馬が引退せず3歳現役馬として存続すること、1年目の年末引退馬一覧に2歳・3歳馬が含まれないことを確認。
  2. `test_3yo_maiden_retired_at_week_36`: 2年目第36週（9月4週）終了時に3歳未勝利馬（0勝・未出走馬）が引退（`retired_year = 2`）し、2歳馬および3歳勝ち馬は現役を維持することを確認。
- 全体テスト実行: 全118件の単体テストがすべて **OK (PASS)**。
