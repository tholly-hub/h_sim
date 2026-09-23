# 産駒一覧修正・昇順統一・繋養年数＆ソート機能・タイム進化モデル調整 実装計画

ユーザーからのフィードバックに基づき、以下の4点の改修・機能追加を実施します。

1. **種牡馬・繁殖牝馬 産駒一覧ダイアログのエラー解消** (`No item with that key`)
2. **主要路線・重賞DB・表彰の年度・レース結果の昇順統一**（古い年 $\to$ 新しい年）
3. **種牡馬・繁殖牝馬リストの繋養期間（年数：○年目）表示＆多軸ソート機能追加**
4. **走破タイム・世代進化モデルの調整**（1F限界10.0秒、初期15.0秒から約50世代で到達するペースへ）

---

## 提案する変更内容

### 1. 産駒一覧ダイアログのエラー修正
#### [MODIFY] [progeny_dialog.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/views/progeny_dialog.py)
- `r["total_prize"]` を正しいカラム名 `r["prize_money"]` に修正。
- `sqlite3.Row` に対するアクセスを安全化し、欠損キーによる `IndexError` を防止。

---

### 2. 主要路線・重賞DB・表彰ビューの昇順統一
#### [MODIFY] [database_view.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/views/database_view.py)
- **主要レース路線タブ**:
  - 年度リスト取得クエリを `ORDER BY year ASC` に変更。
  - レース勝ち馬クエリを `ORDER BY rc.year ASC` に変更。
- **過去の重賞レースDBタブ**:
  - 重賞年度コンボボックスを昇順（古い年度 $\to$ 新しい年度）に並び替え。
  - レース結果クエリの並び順を `ORDER BY r.year ASC, r.week ASC, r.race_id ASC` に変更。

#### [MODIFY] [awards_view.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/views/awards_view.py)
- **年度代表馬・各部門賞タブ**:
  - 歴代推移一覧テーブル (`table_horse_awards_hist`) の並びを `sorted_years = sorted(years_map.keys(), reverse=False)`（昇順）に変更。
  - 年度コンボボックスを昇順に修正。
- **各種リーディング表彰タブ**:
  - 歴代リーディング推移一覧テーブル (`table_leading_hist`) の年度を昇順 (`ORDER BY year ASC`) に変更。
  - 年度コンボボックスを昇順に修正。
- **顕彰・殿堂・メモリアルタブ**:
  - 顕彰馬一覧 (`table_hall`) の並び順を選出年度（活動終了年）昇順 (`ORDER BY last_active_year ASC, h.g1_wins DESC, h.prize_money DESC`) に変更。

---

### 3. 種牡馬・繁殖牝馬リストの繋養期間表示 ＆ ソート機能
#### [MODIFY] [database_view.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/views/database_view.py)
- **種牡馬リスト**:
  - カラムに「繋養年数」（例: `5年目`）を追加。
  - ソートコンボボックスを設置（またはテーブルヘッダーソート対応）:
    - 馬名（50音順 / 昇順）
    - 繋養期間（降順）
    - 産駒頭数（降順）
    - 勝ち馬数（降順）
    - 勝ち上がり率（降順）
    - 重賞勝数（降順）
- **繁殖牝馬リスト**:
  - カラムに「繋養年数」（例: `3年目`）を追加。
  - ソートコンボボックスを設置:
    - 馬名（50音順 / 昇順）
    - 繋養期間（降順）
    - 産駒頭数（降順）
    - 勝ち馬数（降順）
    - 勝ち上がり率（降順）
- 繋養年数は `max(1, current_year - debut_year + 1)` または `age - 3` 等により正確に算出。

---

### 4. 走破タイム・世代進化モデルの調整
#### [MODIFY] [engine.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/race/engine.py)
- 急激なタイム短縮をもたらしていた過剰な非線形ボーナス（`top_tier_bonus`）を適正化。
- 1Fあたりの物理想定限界タイム（10.0秒/F: 例 1000m 50.0秒, 1600m 80.0秒, 2000m 100.0秒）をガードとして実装。
- 基礎能力値 50.0（初期世代）で 1F 15.0秒前後、能力値 100.0 で 1F 10.0秒へと漸近する安定したタイム算出ロジックを構成。

#### [MODIFY] [genetics.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/core/genetics.py)
- `calculate_polygenic_stat` の環境変異・ドリフトを調整し、初期世代（平均50.0）から約50世代（50年）かけてトップ層が 95〜100（1F 10.0秒相当）に到達する進化ペースにチューニング。

---

## 検証計画

### 自動テスト
- `python3 -m unittest discover tests` を実行し、全既存テストおよび新テストがパスすることを確認。
- `tests/test_database_view.py` や `tests/test_awards_view.py` を実行し、クエリやUI表示の整合性を検証。
- タイムシミュレーション検証スクリプトを実行し、初期世代（1F 15秒程度）から50世代での限界タイム推移を検証。

### 手動・動作確認
- GUI起動による各タブの昇順表示確認
- 種牡馬・繁殖牝馬リストでの「産駒一覧」ダイアログオープンと繋養年数・ソート機能の動作確認
