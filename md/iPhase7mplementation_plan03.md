# 2年目1月における未出走2歳馬の引退誤判定修正 Implementation Plan

2年目1月の年進行時において、未出走の2歳馬（3歳に加齢する馬）が引退扱いと誤認・誤表示されてしまう問題を修正し、「**2歳馬は引退せず、3歳9月4週（第36週）終了時点で未勝利（未出走含む0勝）だった馬が引退する**」というルールを正確に徹底します。

---

## ユーザー確認事項
- データベーススキーマに `retired_year` (INTEGER, デフォルト NULL) カラムを追加し、引退が確定した年度（3歳9月4週の未勝利引退、または年末の古馬引退）を明示的に記録・管理します。
- 既存のDBファイルがある場合でも、自動的に `ALTER TABLE horses ADD COLUMN retired_year INTEGER` が適用されるようマイグレーション処理を組み込みます。

---

## 提案する変更内容

### 1. データベース定義とマイグレーション
#### [MODIFY] [schema.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/db/schema.py)
- `horses` テーブル定義に `retired_year INTEGER DEFAULT NULL` を追加。
- `idx_horses_retired_year` インデックスを追加。
- 既存DB読み込み時のマイグレーション（カラム追加）ロジックを担保。

---

### 2. ライフサイクル＆引退管理ロジック
#### [MODIFY] [calendar.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/race/calendar.py)
- `_process_3yo_maiden_retirement`:
  - 3歳9月末（第36週）終了時点で、3歳かつ未勝利（`age = 3 AND career_wins = 0 AND is_active = 1`）の馬のみを引退させ、`is_active = 0, retired_year = year` を設定。
  - 2歳馬は絶対に引退させない。

#### [MODIFY] [lifecycle.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/core/lifecycle.py)
- `advance_year`:
  - 現役競走馬引退処理（ステップ3）の対象が `WHERE is_active = 1 AND age >= 4` であることを確認し、引退時に `is_active = 0, retired_year = current_year` を設定。
  - 2歳馬（年進行で3歳になる馬）および3歳馬（年進行で4歳になる勝ち馬）が誤って引退処理されないことを担保。

---

### 3. GUI表示およびダイアログ
#### [MODIFY] [annual_events_dialogs.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/views/annual_events_dialogs.py)
- `YearEndAwardsDialog`（年末表彰ダイアログ）:
  - 「本年引退競走馬一覧」タブのクエリを `WHERE h.retired_year = ? AND h.is_sire = 0 AND h.is_dam = 0` に修正。
  - これにより、未デビューの当歳・1歳馬や、年を越す現役2歳馬が引退馬一覧に混入する問題を根本解決。

#### [MODIFY] [horse_browser_view.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/views/horse_browser_view.py)
- 競走馬ブラウザの「引退馬」フィルタを `(h.retired_year IS NOT NULL OR h.career_starts > 0) AND h.is_active = 0 AND h.is_sire = 0 AND h.is_dam = 0` に修正し、未デビュー幼駒が引退馬に混ざらないよう適正化。

---

## 検証計画

### 自動テスト
- 新規テスト `tests/test_maiden_retirement.py` を追加:
  1. 1年目開始から1年目終了・年進行（2年目1月）までの実行:
     - 1年目未出走だった2歳馬が、2年目1月に `age = 3, is_active = 1, retired_year = None` として現役を維持していることを検証。
     - 2年目1月の年末表彰ダイアログ用クエリで、2歳・3歳の現役馬が引退馬一覧に含まれないことを検証。
  2. 2年目第36週（9月4週）までの実行:
     - 未出走および未勝利の3歳馬が第36週終了時に初めて `is_active = 0, retired_year = 2` として引退処理されることを検証。
     - 2歳馬（2年目の新馬）は第36週終了時にも引退せず現役を維持していることを検証。
  3. 既存の全単体テスト（116件）がすべてパスすることを確認。

### 手動検証
- GUIアプリを起動し、1年目から2年目へ週進行させた際、2年目1月のダイアログおよび名鑑において未出走2歳馬が正常に3歳現役馬として継続していることを確認。
