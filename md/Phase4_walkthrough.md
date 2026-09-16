# Phase 4 GUIデータ可視化＆レース再生システム および 馬名生成改修 完了ウォークスルー

## 1. 概要
本改修では、以下の2つの重要要求事項を完全に実装・検証しました：
1. **馬名生成規則および重複排除ルールの刷新**
   - 生まれる馬の名前を `[冠名] + [単語]`（単一単語・9文字超過許可）に変更。
   - **重賞（G1, G2, G3）勝利馬の名前は永久保護**（二度と命名不可）。
   - 現在活動中の現役競走馬・種牡馬・繁殖牝馬と同時代の重複を完全排除。
   - 過去の未勝利・平地条件戦止まりの馬名については世代交代後の再利用を許容（`horses.name` の UNIQUE 制約解除）。
2. **Phase 4 GUIデータ可視化＆レース再生システム（PyQt6）の実装**
   - クロスプラットフォーム対応のモダン・ダークテーマGUIを構築。
   - メインダッシュボード（シミュレーション進行・最新サマリ）。
   - 馬情報＆血統表ブラウザ（能力バー・5代血統表インタラクティブ閲覧）。
   - 5大リーディング＆生産牧場・馬主規模推移画面。
   - 1600m基準タイム時系列推移グラフ＆能力進化分析画面（matplotlib連携）。
   - レース結果一覧＆2Dトラック・レース展開アニメーション再生画面（0.1秒刻み）。
   - `python main.py --gui` 引数およびコンソールメニューからの起動に対応。

---

## 2. 変更・追加された主要コンポーネント

### 1) 馬名生成エンジン & 重複排除
- [`src/generators/name_generator.py`](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/generators/name_generator.py):
  - `_generate_compound_word()` による複数単語結合を廃止し、厳選されたテーマ別カタカナ単語から1語のみを組み合わせる形に変更。
  - `forbidden_names: set[str]` および `set_forbidden_names()` を実装し、禁止馬名を動的に登録・排除。
- [`src/core/breeding.py`](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/core/breeding.py):
  - `_sync_existing_names()` を改修。重賞勝ち馬（`g1_wins + g2_wins + g3_wins > 0`）を永久禁止セットへ格納。
  - 現役馬、種牡馬、繁殖牝馬の現存馬名も同時代重複禁止セットへ格納。
- [`src/db/schema.py`](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/db/schema.py):
  - `horses.name` の `UNIQUE` 制約を解除し、高速検索用の通常インデックス `idx_horses_name` を追加。

### 2) Phase 4 GUIシステム (`src/gui/`)
- [`src/gui/styles.py`](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/styles.py):
  - 洗練されたダークテーマ（#0f131a / #161b26 / #2563eb）のQSSスタイルシート。
- [`src/gui/widgets/pedigree_widget.py`](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/widgets/pedigree_widget.py):
  - 5代血統表（父・母・祖父母〜5代祖先）のグリッド表示。各祖先馬カードをクリックするとその馬の血統表へ即座にドリルダウン移動。
- [`src/gui/widgets/track_canvas.py`](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/widgets/track_canvas.py):
  - 2D楕円競馬場トラックの描画キャンバス。0.1秒ごとの馬番・馬体位置・スパート炎エフェクト・スタミナ残量バー・順位パネルをリアルタイムアニメーション描画。
- [`src/gui/widgets/mpl_canvas.py`](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/widgets/mpl_canvas.py):
  - Matplotlib QtAgg埋め込みキャンバス。ダークテーマ調の軸・グリッド、日本語フォント自動フォールバック対応。
- [`src/gui/views/dashboard_view.py`](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/views/dashboard_view.py):
  - シミュレーション進行コントローラー（「1週進行」「1ヶ月進行」「1年進行」）。UIをブロックしない `SimulationWorker` 非同期スレッド実行。
- [`src/gui/views/horse_browser_view.py`](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/views/horse_browser_view.py):
  - 馬名・性別・所属等のリアルタイム検索フィルタ、能力値（スピード・スタミナ・瞬発力・根性・気性）ビジュアルバー、5代血統表連動。
- [`src/gui/views/rankings_view.py`](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/views/rankings_view.py):
  - 騎手・調教師・馬主・生産牧場・種牡馬（AEI算出含む）の5大リーディングテーブルおよび生産牧場・馬主の規模階層（資金・収容数）一覧。
- [`src/gui/views/analytics_view.py`](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/views/analytics_view.py):
  - 世代ごとの1600m平均走破タイム推移折れ線グラフ、および各世代の平均スピード・スタミナ推移グラフ。
- [`src/gui/views/race_replay_view.py`](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/views/race_replay_view.py):
  - 開催済みレースの選択コンボボックス、着順・タイム・払戻・展開テーブル、再生コントローラー（再生/一時停止/巻き戻し/速度変更）。
- [`src/gui/app.py`](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/app.py):
  - メインウィンドウ `MainWindow`。サイドバーメニュー、タブ切り替え、ステータスバー。
- [`main.py`](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/main.py):
  - `--gui` コマンドライン引数および対話型メニュー `[22] GUIデータ可視化＆レース再生システムを起動` を追加。

---

## 3. テスト・検証結果

1. **馬名命名規則＆重複防止テスト**:
   - `tests/test_horse_name_uniqueness.py`
   - 単一単語構成（`[冠名]+[単語]`）、9文字超過許可、重賞勝利馬の永久命名禁止、現役馬・種牡馬・繁殖牝馬との同時代重複排除をすべて検証。
   - **結果: 全テスト通過（OK）**

2. **Phase 4 GUI単体テスト**:
   - `tests/test_phase4_gui.py`
   - メインウィンドウ初期化、馬情報ブラウザ、5大リーディング、時系列分析、レース再生、5代血統表クリックナビゲーションをオフスクリーン検証。
   - **結果: 全テスト通過（OK）**

3. **総合テストスイート**:
   - `python3 -m unittest discover -s tests`
   - 全44テストがすべてエラーなく正常通過（OK）。

4. **GUI起動確認**:
   - `python3 main.py --help` に `--gui` が正常に表示され、アプリケーション初期化および起動フローが正常に動作することを確認。

---

## 4. 起動方法
ターミナルから以下のコマンドでGUIを直接起動できます：
```bash
python3 main.py --gui
```
または対話型メニューからも起動可能です：
```bash
python3 main.py --menu
# メニュー番号 [22] を選択
```
