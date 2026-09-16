# 順位バー視点回転・バー幅縮小・騎手能力発揮連動・脚質別全力スパート 実装計画

ユーザー様からいただいた以下のご要望について、実装計画をご提案いたします。

1. **順位バーの180度視点回転効果**: 動画のように進行方向が変わる際に視点がクルッと180度回転するフリップ効果
2. **順位バーの横幅縮小**: 横幅をコンパクト（420px）に狭くし、見やすく凝縮
3. **騎手の能力による馬の能力発揮度連動**: 騎手のスキルや腕によって、馬のスピード・瞬発力・スタミナを引き出せる割合（88%〜106%）が変化する仕様
4. **脚質別の全力スパート発光演出**: 脚質ごとに異なる「真の勝負どころ（全力発揮ポイント）」でのみオーラが発光する演出

---

## 提案する改修内容

### 1. 騎手の能力による馬の能力発揮度合いの連動 ([engine.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/race/engine.py))
- **騎手能力抽出率（`jockey_extraction_rate`）の導入**:
  - 騎手の総合力（`skill * 0.45 + drive * 0.35 + experience * 0.20`）に基づき、能力発揮率を **88%〜106%** の範囲で動的算出。
  - **一流騎手（ルメール級・武豊級）**: 馬のスピード・瞬発力・スタミナを104%〜106%まで極限に引き出す。
  - **若手・見習い騎手**: 88%〜92%程度にとどまり、馬のポテンシャルを御しきれないリアルな騎手格差を表現。
  - フリー騎手ボーナスや調教師スキルとも自然にシナジー。

### 2. 脚質別の全力スパート区間 & 洗練された発光演出 ([engine.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/race/engine.py) / [track_canvas.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/widgets/track_canvas.py))
- 一律で直線全員が光る仕様を改め、各馬が脚質ごとに「全力を出す勝負どころ」でのみ発光するよう変更：
  - **逃げ (ESCAPE)**: スタート直後のハナ争い（0〜12%）、および直線入り口の二の脚突き放し（残り450m〜250m）
  - **先行 (LEADING)**: 4コーナー〜直線半ばの抜け出しスパート（残り400m〜150m）
  - **差し (BETWEEN)**: 直線勝負所の馬群突き抜け（残り350m〜50m）
  - **追込 (CLOSING)**: 4コーナー大外からのロングスパート（残り450m〜ゴール前）
- 発光オーラも、以前のどぎつい巨大な円から、馬体にフィットした洗練されたスタイリッシュなブーストエフェクトに改良。

### 3. 順位バーの180度視点回転（3Dフリップ）アニメーション ([track_canvas.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/widgets/track_canvas.py))
- 向正面（右向き）と直線（左向き）の切り替わり時に、約0.4秒間かけてバーが立体的にY軸周りに180度クルッと回転する視点トランジション効果を実装。
- 中継カメラが向正面からスタンド前に回り込んで視点が反転したことを、視聴者が直感的に理解できるようにします。

### 4. 順位バーの横幅縮小・コンパクト化 ([track_canvas.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/widgets/track_canvas.py))
- 現在700px近くと長すぎた中央隊列バーを **420px（コンパクトサイズ）** に縮小。
- 画面中央にすっきりと凝縮して配置し、全馬がギュッとまとまった見やすい隊列バーにします。

---

## 変更対象ファイル

### [MODIFY] [engine.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/race/engine.py)
- `calculate_finish_time`: 騎手能力発揮率（`jockey_extraction_rate`）の実装
- `generate_replay_data`: 脚質別スパート区間フラグ（`is_spurt`）の算出

### [MODIFY] [track_canvas.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/widgets/track_canvas.py)
- `_draw_jra_broadcast_hud`: バー幅の縮小（420px）、180度視点回転フリップ演出の実装
- `_draw_world_horses`: 脚質に応じた洗練されたスパート発光エフェクトの描画

---

## 検証計画
1. **騎手能力発揮率のテスト**: 一流騎手（skill=90）騎乗時と新人騎手（skill=30）騎乗時で、同一馬のタイムおよび能力引き出し率が期待通り差を生むことを検証。
2. **180度視点回転 & バー幅テスト**: 420px幅で全頭が表示され、進行方向反転時に滑らかに180度フリップすることを検証。
3. **脚質別スパート発光テスト**: 各脚質がそれぞれの勝負どころで正しく発光することを検証。
4. **ユニットテスト全件実行**: 既存テストの通過を確認。
