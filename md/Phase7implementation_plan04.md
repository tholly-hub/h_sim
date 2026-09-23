# 直近のエラー修正 実装計画

## 概要
Phase8実装に入る前に、現時点で報告されている以下の2つの不具合を修正します。
1. **4年目1月第1週への移行時のクラッシュ (`AttributeError: 'sqlite3.Row' object has no attribute 'get'`)**
2. **3年目9月4週で3歳未勝利馬の引退リストが出力されない不具合**

---

## 原因分析

### 1. 4年目年進行時のクラッシュ
- **発生場所**: [lifecycle.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/core/lifecycle.py#L208)
- **原因**: 引退処理対象の馬リスト `retired_horses` 内のオブジェクト `h` は `sqlite3.Row` 型ですが、208行目と215行目で辞書型の `.get()` メソッドを呼び出しているため `AttributeError` が発生し、年進行処理が途中で停止していました。

### 2. 3年目9月4週の未勝利馬引退リスト非表示
- **発生場所1**: [dashboard_view.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/views/dashboard_view.py#L795)
  - 現状は `if next_w == 37:` (10月第1週への進行時) にダイアログを開く設定になっており、9月4週（第36週）実行時にはダイアログが開かれません。
- **発生場所2**: [annual_events_dialogs.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/views/annual_events_dialogs.py#L138-L148)
  - SQLクエリで `birth_year = self.year - 2` として抽出していましたが、初期生成データの生年オフセットにより3年目の3歳馬の生年と計算式が一致せず、0頭と判定されていました。
  - 第36週の未勝利引退処理（`calendar.py`）では `retired_year = ?` が更新されているため、`retired_year = self.year AND age = 3 AND career_wins = 0` で正確に抽出する必要があります。

---

## 変更内容

### [core]
#### [MODIFY] [lifecycle.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/core/lifecycle.py)
- 繁殖牝馬昇格判定およびログ出力において、`h.get("career_wins", 0)` や `h.get("career_starts", 0)` を `h["career_wins"]` / `h["career_starts"]` に修正します。

### [gui]
#### [MODIFY] [dashboard_view.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/views/dashboard_view.py)
- `_advance_to_next_week` 内で、未勝利引退ダイアログの表示条件を `if next_w == 36:`（9月4週のレース完了時）に変更します。

#### [MODIFY] [annual_events_dialogs.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/views/annual_events_dialogs.py)
- `UnvictoryRetirementDialog` のデータ取得SQLを `WHERE h.retired_year = ? AND h.age = 3 AND h.career_wins = 0` に変更し、確実にその年に引退した3歳未勝利馬を全頭取得・表示できるようにします。
- ダイアログタイトルやヘッダー文言を「9月第4週 3歳未勝利馬 引退発表一覧」に更新します。

---

## 検証手順

### 1. 単体テスト・自動検証
- スクリプトを作成し、テスト用DBにて3年目9月4週の未勝利馬引退処理とダイアログデータ抽出クエリを実行して、引退馬が正しく取得できることを確認。
- 3年度末から4年度1週への年進行処理（`advance_year`）を実行し、エラーなく完了することを確認。

### 2. 動作確認
- GUIまたはシミュレーション実行スクリプトにて、1年目〜4年目以降までスムーズに進行できることを確認。
