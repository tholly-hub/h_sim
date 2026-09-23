# レース画面 UI・機能改善 ウォークスルー

レース画面（[RaceReplayView](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/views/race_replay_view.py) および [RaceViewDialog](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/views/race_dialogs.py)）について、ご指定いただいた要件に基づく改修を完了しました。

---

## 主な変更点

### 1. ウィンドウサイズ
- [RaceViewDialog](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/views/race_dialogs.py) 起動時に `setWindowState(Qt.WindowState.WindowMaximized)` を呼び出し、PC画面全体（最大化）で開くようにしました。

### 2. 1段目：コントロールボタン・レース選択バー
- **開催週表示**: 「レース」部分を「何月何週」（例: `5月3週`）のみのシンプル表示に変更。
- **レースプルダウン**: 青字スタイル（`#4fc3f7`）のプルダウンメニュー（`combo_races`）を配置し、同週のレース一覧から自由に選択・切り替え可能に。
- **詳細結果ボタン**: 「🏁 詳細結果」ボタンを新設し、いつでもダッシュボードと同じ詳細結果画面を開けるように配置。
- **レース速度初期値**: 4.0x を維持。

### 3. 2段目：レース画面 & 電光着順掲示板
- **電光着順掲示板の確定連動**:
  - レース走行中は「確定」ランプを消灯（ダーク）、着順のみリアルタイム追従、タイム `--:--.-`、着差非表示。
  - ゴール確定時に「確定」ランプが鮮やかな赤（`#ff1744`）に点灯し、勝馬走破タイム、コースレコード時の赤字「R」、上がり3Fタイム、1〜5着の馬番・着差が正しく表示されるように改善。
- **中央オーバーレイの非表示**:
  - レース画面中央を覆い隠していた大きなリザルトオーバーレイの自動ポップアップを廃止。
  - ゴール後は電光掲示板の確定点灯と連動し、ダッシュボードと同じ詳細レース結果ダイアログ（[RaceResultDialog](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/views/race_dialogs.py)）が自然に開くように連携。
- **レース画面の高さ確保**:
  - キャンバスと掲示板のストレッチ比率（`canvas: 8, board: 2`）を設定し、広いレーストラック描画領域を確保。

### 4. 3段目：HUD（情報オーバーレイ）
- **見やすい2段表示パネル**:
  - **上段**: レース名（14pt・太字・ゴールド `#ffd54f`）＋ 距離・周回・馬場（12pt・シアン `#80d8ff`）
  - **下段**: 先頭スピード表示（16pt・太字・オレンジ `#ffab40`）＋ 馬場勾配（15pt・太字）
- **先頭馬の位置に応じたリニア（滑らか）な勾配変化**:
  - コース起伏データ（中山の急坂、阪神の上り坂、東京のなだらかな起伏など）に基づき、先頭馬の走破距離 `leader_dist` に応じてリアルタイムかつ滑らかに勾配％（例: `+2.1% (急な上り坂)` / `0.0% (平坦)` / `-1.5% (下り坂)`）を補間計算・色分け表示（上りはレッド、下りはシアン、平坦はグリーン）。

---

## 検証結果

### 自動テスト
1. **表示仕様テスト**: `python3 -m unittest tests.test_display_fixes` -> **OK (3 tests passed)**
   - 出馬表の馬名幅（230px 確保）
   - レース結果ダイアログのオッズ・人気表記（`6.1倍 (3人気)`）
   - 電光着順掲示板の確定表示（馬番・タイムが正常に反映）
2. **全スイートテスト**: `python3 -m unittest discover tests` -> **OK (84 tests passed)**
   - 既存のレースロジック、血統、育成、馬場シミュレーション等、全機能との互換性を確認。
