# ウォークスルー: 出馬表表示の修正および競走馬詳細ダイアログにおける今走結果非表示

## 実装概要

ユーザーのご要望に基づき、以下の2点を実装・改修いたしました：
1. **出馬表が表示されない問題の修正**:
   - 初期起動時や週切り替え時、未発走レース選択時において、自動でその週の出走登録・レース実行を行い、常に確実に第1レースの出馬表（枠番、馬番、馬名、性齢、適性、騎手、厩舎、オッズ）が表示されるよう堅牢化。
2. **競走馬詳細における「今回のレース結果」非表示（ネタバレ防止）**:
   - 出馬表の馬名クリックで表示される競走馬詳細（`HorseDetailDialog`）において、**今回選択中のレース結果（着順・走破タイム・獲得賞金）を除外**し、レース発走前の**「過去の戦績・過去の出走履歴・生涯獲得賞金・成績集計」**のみを表示するように改修。

---

## 変更内容詳細

### 1. 競走馬詳細ダイアログ (`src/gui/views/horse_detail_dialog.py`)
- `HorseDetailDialog.__init__` に `exclude_race_id: Optional[int] = None` を追加。
- `_load_horse_data` において：
  - レース履歴取得時に `WHERE res.horse_id = ? AND res.race_id != ?` で該当レースを除外。
  - プロフィールカードの「生涯獲得賞金」から該当レースの `prize_awarded` を減算して表示。
  - 成績集計タブ（通算戦績、重賞内訳、馬場別・距離別・競馬場別）も今走を除外した正確な過去戦績で集計・表示。

### 2. ダッシュボードビュー (`src/gui/views/dashboard_view.py`)
- `refresh_dashboard()` で常に `_ensure_initial_week_run()` を呼び出し、DB初期化後や別画面からの復帰時でも確実に今週のレース出走データがロードされるよう強化。
- `_load_race_entry()` において、選択レースが未実行だった場合に自動実行して即時出馬表を生成するフォールバックを追加。
- `_on_horse_cell_clicked()` で馬名をクリックした際、`HorseDetailDialog(self.db, horse_id, exclude_race_id=self.current_selected_race_id, parent=self)` を渡すよう改修。

---

## 検証結果

### 1. ユニットテスト (`tests/test_horse_detail_exclude.py`)
- `test_exclude_race_id`:
  - `exclude_race_id=None` の場合: 全出走履歴および全額賞金を表示。
  - `exclude_race_id=target_race_id` の場合: 直近レースの履歴が1件除外され、賞金も直近レース分を差し引いた金額が表示されることを確認（**PASS**）。

### 2. ダッシュボードテスト (`tests/test_dashboard_view.py`)
- `test_dashboard_initial_load`:
  - `DashboardView` 初期化時にレース一覧および出馬表が即座に読み込まれることを確認（**PASS**）。
  - レース切り替え時にも該当レースの出馬表が正しく更新されることを確認（**PASS**）。

### 3. コマンド実行結果
```text
Ran 6 tests in 3.258s
OK
PASS: test_exclude_race_id passed successfully!
PASS: Dashboard loaded 2 races and 8 entries.
PASS: Switched to race 1, loaded 8 entries.
```
