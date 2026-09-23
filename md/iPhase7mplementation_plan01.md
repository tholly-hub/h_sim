# Phase 7 実装計画書 (追加機能反映版)

ユーザー様からのご要請に基づき、以下の機能追加および修正を実施する計画を作成しました。

---

## ユーザー確認・検討事項

> [!IMPORTANT]
> - **競走馬成績リストヘッダーの拡充**:
>   - 成績リストのヘッダーに「競走成績（`#-#-#-#` 形式: 1着-2着-3着-着外）」、「クラス名（例: オープン、3勝クラス等）」、および「毛色」を表示します。
> - **馬の毛色システム (日本馬事協会 14種類規則 & 遺伝モデル)**:
>   - **14種類の毛色**: 栗毛、栃栗毛、鹿毛、黒鹿毛、青鹿毛、青毛、芦毛、白毛、月毛、河原毛、粕毛、薄墨毛、佐河毛、斑毛
>   - **遺伝モデル (メンデルの法則)**: Extension (E/e), Agouti (A/a), Gray (G/g), White (W/w), Cream (Cr/cr) の主要遺伝子座により交配時に両親から引き継がれ毛色が自動決定します。
>   - **2Dレースグラフィック反映**: レース画面（`TrackCanvas`）上の馬体カラーに実際の毛色が視覚的に美しく反映されます。
>   - **詳細ダイアログ**: 競走馬・種牡馬・繁殖牝馬の各詳細画面ヘッダーに毛色を記載します。
> - **ダイアログ表示のタイミング**:
>   - **9月4週（第36週）**: 「未勝利馬引退リスト」ダイアログが表示されます。
>   - **12月4週（第48週）**: 「年度末表彰・引退馬・新種牡馬/繁殖牝馬一覧」総合ダイアログが表示されます。

---

## 提案する変更内容

### 1. 毛色（Coat Color）システムと遺伝モデルの実装

#### [MODIFY] [horse.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/models/horse.py) & [schema.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/db/schema.py)
- `CoatColor` Enum（14種類: `CHESTNUT`, `DARK_CHESTNUT`, `BAY`, `DARK_BAY`, `BROWN`, `BLACK`, `GRAY`, `WHITE`, `PALOMINO`, `BUCKSHIN`, `ROAN`, `GRULLO`, `SORREL`, `PINTO`）を追加。
- `Horse` モデルに `coat_color` (毛色) および `coat_genotype` (毛色遺伝子文字列) プロパティを追加。
- データベーステーブル `horses` に `coat_color`, `coat_genotype` カラムを追加（マイグレーション対応）。

#### [MODIFY] [genetics.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/core/genetics.py) & [breeding.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/core/breeding.py)
- 毛色決定用遺伝子座（E/e, A/a, G/g, W/w, Cr/cr）の交配遺伝ロジックを実装。
- 両親の毛色遺伝子座を受け継ぎ、メンデルの法則に従って産駒の毛色を決定。

#### [MODIFY] [track_canvas.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/widgets/track_canvas.py)
- 14種類の毛色に対応するRGB描画カラーマップ（栗毛: 明るい茶, 鹿毛: 赤茶+黒たてがみ, 芦毛: 灰色, 白毛: 白, 青毛: 漆黒...など）を設定。
- 2Dレースシミュレーションアニメーション内で各馬の毛色がグラフィックに反映されるように更新。

#### [MODIFY] [horse_detail_dialog.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/views/horse_detail_dialog.py), [sire_progeny_dialog.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/views/sire_progeny_dialog.py)
- ダイアログヘッダーに「競走成績（`1-2-3-着外`）」「現在のクラス名（オープン/3勝クラス/2勝クラス/1勝クラス/未勝利/新馬）」「毛色」を明記。

---

### 2. カレンダー進行イベントダイアログ (9月4週・12月4週)

#### [NEW] [annual_events_dialogs.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/views/annual_events_dialogs.py)
- **`UnvictoryRetirementDialog` (9月4週 未勝利引退馬発表ダイアログ)**:
  - 未勝利引退馬一覧（馬名, 性別, 父, 母, 毛色, 成績 `#-#-#-#`）。
  - 馬名クリックで [`HorseDetailDialog`](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/views/horse_detail_dialog.py) を開く。
- **`YearEndAwardsDialog` (12月4週 年度末発表・表彰ダイアログ)**:
  - 4つのタブ構成 (1. 表彰関係, 2. 引退馬, 3. 種牡馬, 4. 繁殖牝馬)。
  - **表彰馬・功労馬・顕彰馬の馬名クリックで競走馬詳細ダイアログを表示**。
  - 特別功労 (騎手500勝+G1 20勝 / 調教師250勝+G1 10勝)
  - 殿堂 (騎手1000勝+G1 30勝 / 調教師500勝+G1 15勝)
  - 新種牡馬・新繁殖牝馬・引退馬一覧で毛色やサイアーライン・成績・重賞実績を表示。

#### [MODIFY] [calendar.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/race/calendar.py), [dashboard_view.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/views/dashboard_view.py), [app.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/app.py)
- 9月4週および12月4週進行完了時に自動ポップアップ表示。

---

### 3. 競馬データベース画面の修正

#### [MODIFY] [database_view.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/views/database_view.py)
- 競走馬リーディング & 世代・クラス別名鑑のテーブル末尾に「主な重賞成績」列を追加。
- 年度代表馬・各部門賞カードの上段スクロールなし一括閲覧レイアウト（グリッド表示）調整。
- 重賞レースDBに「グレード別」「競馬場別」「レース別（年次履歴史系列）」フィルターを追加。

#### [MODIFY] [records_view.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/views/records_view.py)
- 先頭に **「総合」タブ**（全競馬場の距離別ベストレコード一覧）を追加。
- 行クリックで **「レコード推移ダイアログ (`RecordHistoryDialog`)」**（時系列リスト + Matplotlibグラフ: 縦軸タイム[分:秒], 横軸時間軸）を表示。

---

### 4. 各種リーディング画面の修正

#### [MODIFY] [rankings_view.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/views/rankings_view.py) & [rankings.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/race/rankings.py)
- 名称を **「各種リーディング」** に変更。
- 順位基準を「勝利数」最優先（同数は2着数、3着数）に変更。
- 各テーブルに「持ち馬数」と「勝ち馬数」列を追加。

#### [MODIFY] [ranking_history_dialog.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/views/ranking_history_dialog.py)
- グラフ描画基準を勝利数・勝利数ベースの年度別順位推移に修正。

---

## 検証計画

### 自動テスト (Automated Tests)
- `python3 -m unittest discover -s tests` を実行し、毛色決定交配遺伝ロジック、14種類毛色判定、9月4週未勝利馬抽出、12月4週表彰集計、特別功労・殿堂選定、各種リーディング順位基準などのテストが全て成功することを確認。

### 手動検証 (Manual Verification)
- 2Dレース画面上で馬の毛色がグラフィックに正しく反映されることを確認。
- 競走馬詳細画面ヘッダーに成績（`#-#-#-#`）、クラス名、毛色が表示されることを確認。
- シミュレーション進行時に9月4週および12月4週ダイアログが表示され、馬名クリックで詳細が開くことを確認。
- データベースタブで総合コースレコードおよび推移グラフを表示確認。
