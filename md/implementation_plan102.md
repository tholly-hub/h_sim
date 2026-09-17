# 血統規制による距離・馬場適性遺伝 & ダッシュボード刷新・コースレコード・能力推移・段階進行 実装計画

## 概要
ユーザー様からのご要望に基づき、以下の包括的改修を実施します：
1. **血統表による距離適性・馬場特性の規制**:
   - 種牡馬・繁殖牝馬および5代血統表の特性から、子の距離適性レンジと馬場適性（芝・ダート・兼用）を厳格に規制。
   - 短距離特性馬（スプリンター）同士の交配から極端な長距離馬（ステイヤー）が出ないよう適性上限をクランプ。
2. **GUI画面体系の全面再編**:
   - メインタブから「レースタブ」「血統表タブ」を外し、ダッシュボード上の操作から**別ウィンドウ（ダイアログ）**として開く仕様に変更。
   - 従来のダッシュボード内容（週・月・年進行、統計、ログ）は新設の**「シミュレーション状況」タブ**へ移行。
   - 新生**「ダッシュボード」タブ**には、現在の年・月・週、今週のレース一覧、レース選択時の出馬表・オッズ、そして「レース閲覧（別ウィンドウ）」「レース結果（別ウィンドウ）」ボタンを配置。
   - 出馬表の各馬をクリックすると、**「競走馬詳細ダイアログ（別ウィンドウ）」**が開き、名前、厩舎、生産牧場、年齢、血統表、通算成績、重賞(G1/G2/G3/OP)1・2・3・着外数、距離別成績、芝ダート別成績、競馬場別成績、全出走履歴（着順・タイム・上がり3F等）を網羅して閲覧可能にする。
3. **各競馬場のコースレコード一覧タブの新設**:
   - 各競馬場（全12場）、馬場（芝・ダート）、距離別のコースレコードタイム、達成年週、達成馬名、騎手名、レース名を一覧表示する「⏱️ コースレコード」タブを新設。
4. **能力・タイム推移タブの拡張**:
   - 芝・ダート別、各距離（1000m〜3600m）ごとの走破タイム推移グラフをインタラクティブに切り替え表示。
5. **走破タイム・ダート差のリアル調整**:
   - 現代サラブレッドの走破タイム（芝1200m: 1分07〜08秒台、芝1600m: 1分32〜34秒台、芝2000m: 1分58秒〜2分00秒台、芝2400m: 2分23〜25秒台）に基準タイムを全面補正。
   - ダートタイムを「1000mあたり2.5秒（1000mで2〜3秒差）」芝より要するように調整。
6. **シミュレーション1〜3年目の段階的番組進行 & 厩舎・騎手引退ガード**:
   - 1年目：2歳レース開始月（6月＝第21週）から開始し、2歳戦のみ施行。
   - 2年目：2歳＋3歳レースのみ施行。
   - 3年目以降：古馬戦を含むフル番組表を施行。
   - 3年目終了までは厩舎（調教師）および騎手の引退を完全ガード（初期年齢調整 ＋ 3年目以内引退スキップ）。

---

## ユーザー確認事項（User Review Required）

> [!IMPORTANT]
> **タブ構成の変更について**
> - メインタブの構成が以下の4タブになります：
>   1. **📊 ダッシュボード**（週カレンダー・今週のレース一覧・出馬表 & オッズ・レース閲覧/結果ボタン）
>   2. **⚙️ シミュレーション状況**（従来の進行ボタン・進行ログ・全体統計サマリー）
>   3. **🏆 5大リーディング & 規模階層**
>   4. **📈 1600mタイム・能力推移**
> - 「レースリプレイ」および「競走馬・血統表」は独立した別ウィンドウ（モーダル/モードレスダイアログ）として起動します。

---

## 提案する変更内容

### 1. 遺伝・血統モデルの拡張（Core / Genetics）

#### [MODIFY] [genetics.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/core/genetics.py)
- `calculate_pedigree_aptitude(sire_id, dam_id, db)` メソッドを追加。
- 5代血統表の全祖先馬（最大62頭）から、芝/ダート特性および距離特性（MSTN型・平均距離）の血統影響度（遺伝的寄与度: 父母50%, 祖父母25%, 曽祖父母12.5%...）を集計。
- 短距離血統規制：
  - 両親が短距離適性（C/C等）、または祖先の短距離シェアが高い場合、スタミナ遺伝値および最大適性距離の上限を厳格にクランプ（例: 最大1600m以下に制限、極端な長距離馬の出現を完全抑止）。
- 馬場適性規制：
  - 祖先馬のダートシェア・芝シェアから、子の馬場適性確率（芝特化・ダート特化・兼用）を決定論的に導出。

#### [MODIFY] [breeding.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/core/breeding.py)
- 当歳馬の誕生時、血統表集計に基づく距離適性制限と馬場適性を付与してDBへ登録。

#### [MODIFY] [horse.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/models/horse.py)
- `Horse` クラスの距離適性レンジ算出において、血統親和性・親の特性を優先し、短距離血統からの長距離逸脱を抑止。

---

### 2. GUI画面の再構築（GUI）

#### [NEW] [simulation_status_view.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/views/simulation_status_view.py)
- 従来の `DashboardView` の中身（シミュレーション進行ボタン、1週/1ヶ月/1年進行ワーカー、コンソールログ表示、主要統計カード）を独立したビューとして切り出し、「シミュレーション状況」タブとして提供。

#### [MODIFY] [dashboard_view.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/views/dashboard_view.py)
- 完全刷新：
  - **上部**: 現在の「○年目 / ○月○週（第○週）」カレンダー表示 ＋ 「1週進める」ショートカットボタン。
  - **左ペイン**: 「今週のレース一覧」テーブル（発走時刻/場・レース名・グレード・芝/ダ・距離・出走頭数）。
  - **右ペイン**: 選択されたレースの「出馬表 & オッズ」テーブル。
    - 枠番・馬番・馬名（クリック可能）・性齢・騎手・斤量・単勝オッズ・脚質などを表示。
    - 出馬表の上部に「🎬 レース閲覧」ボタン と 「📋 レース結果」ボタンを配置。
    - 「レース閲覧」クリック $\to$ 2Dアニメーションレースリプレイを別ウィンドウで起動。
    - 「レース結果」クリック $\to$ 確定着順・タイム・払戻/着差結果を別ウィンドウで起動。
    - 出馬表の馬名クリック $\to$ 該当馬の「競走馬詳細ダイアログ」を別ウィンドウで起動。

#### [NEW] [horse_detail_dialog.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/views/horse_detail_dialog.py)
- 出馬表の馬名をクリックした際に表示される総合馬情報ウィンドウ：
  - **基本ヘッダー**: 馬名、年齢、性別、厩舎名、生産牧場名、馬主名、父・母名、適性（芝/ダ/兼用、適性距離レンジ、脚質）。
  - **成績サマリー**:
    - 通算成績（○戦○勝）
    - 重賞成績: G1 (1着-2着-3着-着外)、G2、G3、リステッド/OPの内訳
    - 距離別成績: 〜1400m、1600m、1800〜2200m、2400m〜
    - 馬場別成績: 芝 (○-○-○-○)、ダート (○-○-○-○)
    - 競馬場別成績: 東京、中山、阪神、京都等の全場内訳
  - **タブ1: 過去の出走レース結果履歴**:
    - 全出走レースのテーブル（開催年週、競馬場、レース名、グレード、馬場距離、頭数/枠番、人気/オッズ、着順、タイム、着差、通過順/脚質、上り3Fタイム、騎手）。
  - **タブ2: 5代血統表**:
    - 既存の `PedigreeWidget` を組み込み、祖先馬のクリックジャンプにも対応。

#### [NEW] [records_view.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/views/records_view.py)
- **コースレコード閲覧画面 (`RecordsView`)**:
  - 全12競馬場、芝・ダート、距離別の最速走破タイム・達成年週・達成馬名・騎手名・レース名を表示する一覧テーブル。
  - 競馬場・馬場・距離フィルター完備。

#### [MODIFY] [analytics_view.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/views/analytics_view.py)
- 芝・ダート選択コンボボックス、距離（1000m〜3600m）選択コンボボックスを追加。
- 選択されたコース条件における走破タイム・能力推移グラフを動的描画。

#### [MODIFY] [engine.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/race/engine.py)
- `BASE_TIMES` を現代サラブレッドのリアル水準（1200m: 1分08秒5, 1600m: 1分33秒5, 2000m: 1分59秒5, 2400m: 2分25秒0等）へ全面改定。
- ダートタイム補正を「1000mあたり2.5秒加算（1000mで2〜3秒差）」に更新。

#### [MODIFY] [calendar.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/race/calendar.py) / [program.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/race/program.py)
- 1年目は第21週（6月）から開始し、2歳戦のみ登録・施行。
- 2年目は第1週から開始し、2歳戦＋3歳戦のみ登録・施行。
- 3年目以降は全年齢（古馬含むフル番組表）を施行。

#### [MODIFY] [initializer.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/generators/initializer.py) / [lifecycle.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/core/lifecycle.py)
- 調教師の初期年齢を40〜65歳、騎手の初期年齢を18〜43歳に設定。
- 3年目終了時（year <= 3）は調教師・騎手の引退処理を完全スキップ（3年間全員現役維持）。

#### [MODIFY] [app.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/app.py)
- タブ構成の整理：
  - タブ1: `DashboardView`（新ダッシュボード：カレンダー・今週のレース一覧・出馬表オッズ・レース閲覧/結果ボタン）
  - タブ2: `SimulationStatusView`（シミュレーション状況：週進行ボタン・ログ・全体統計）
  - タブ3: `RecordsView`（⏱️ 各競馬場のコースレコード一覧）
  - タブ4: `RankingsView`（🏆 5大リーディング & 規模階層）
  - タブ5: `AnalyticsView`（📈 芝ダート別・各距離別タイム・能力推移）
  - ※旧 `RaceReplayView` と `HorseBrowserView` はメインタブから除外（ダイアログ呼び出しに変更）。

---

## 検証計画

### 自動テスト & スクリプト検証
1. **血統規制テスト (`scratch/verify_pedigree_aptitude.py`)**:
   - 短距離血統（スプリンター×スプリンター）から長距離馬が出ないことを確認（全頭が1600m以下に収まることを検証）。
   - ダート血統・芝血統からの馬場適性の継承確率を検証。
2. **タイム補正・ダート差テスト (`scratch/verify_times.py`)**:
   - 芝1200m、1600m、2000m、2400mの走破タイムが現代水準（1分07〜08秒台、1分32〜34秒台、1分58秒〜2分00秒台、2分23〜25秒台）になることを確認。
   - ダートタイムが芝より1000mあたり2〜3秒遅いことを確認。
3. **年次別段階進行 & 引退ガードテスト (`scratch/verify_phased_sim.py`)**:
   - 1年目が第21週から開始し2歳戦のみであること、2年目が2〜3歳戦のみであること、3年目からフル番組になることを検証。
   - 1〜3年目に調教師・騎手の引退が0件であることを検証。
4. **GUI動作確認テスト (`scratch/test_gui_headless.py`)**:
   - `QApplication` 環境下で、`MainWindow`、`DashboardView`、`SimulationStatusView`、`RecordsView`、`AnalyticsView`、`HorseDetailDialog`、`RaceReplayDialog`、`RaceResultDialog` が正常に初期化・インスタンス化でき、シグナルやデータバインドにエラーがないことを検証。
