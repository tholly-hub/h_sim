# レース出走体系の見直しおよび牝馬限定レース廃止 完了レポート

## 1. 概要
ユーザー様からのご要望に基づき、以下の2点の改修を実施しました。
1. **2歳・3歳主要G1レースおよび前哨戦・トライアルレースの牡牝分離（原則的にそれぞれのレースに出走）**:
   - **牡馬指定**: 朝日杯FS、皐月賞、日本ダービー、菊花賞、およびそれらのトライアル・前哨戦レース
   - **牝馬指定**: 阪神JF、桜花賞、オークス、秋華賞、およびそれらのトライアル・前哨戦レース
   - **古馬牝馬限定**: ヴィクトリアマイル、エリザベス女王杯、およびその前哨戦・トライアル・重賞レース
2. **新馬戦、未勝利戦、条件戦（1勝〜3勝クラス）の牝馬限定レースの廃止**:
   - これらのカテゴリーで走るレースをすべて牡馬・牝馬混合（`SexRestriction.MIXED`）に変更しました。

---

## 2. 変更内容の詳細

### ① 番組表定義の見直し ([annual_program.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/race/annual_program.py))
- **新馬・未勝利・条件戦の全レースを混合化**:
  - `3歳未勝利(牝馬限定・芝1800m)` → `3歳未勝利(芝1800m)` (`SexRestriction.MIXED`)
  - `1勝クラス(牝馬限定・芝...)` → `1勝クラス(芝...)` (`SexRestriction.MIXED`)
  - `2勝クラス(牝馬限定・芝1600m)` → `2勝クラス(芝1600m)` (`SexRestriction.MIXED`)
- **リステッドレースリスト (`LISTED_TITLES`) の性別制限拡張**:
  - `アネモネS(L)` [桜花賞TR] → `SexRestriction.FILLY_MARE`
  - `若葉ステークス(L)` [皐月賞TR] → `SexRestriction.COLT_HORSE`
  - `スイートピーS(L)` [オークスTR] → `SexRestriction.FILLY_MARE`
  - `プリンシパルS(L)` [日本ダービーTR] → `SexRestriction.COLT_HORSE`
  - `紅梅ステークス(L)` → `SexRestriction.FILLY_MARE`
- **重賞レース (`major_races`) の性別制限見直し**:
  - `京都新聞杯` (G2, ダービー前哨戦) → `SexRestriction.COLT_HORSE`
  - `京王杯2歳S` (G2, 朝日杯FSTR) → `SexRestriction.COLT_HORSE`
  - `デイリー杯2歳S` (G2, 朝日杯FSTR) → `SexRestriction.COLT_HORSE`
  - `アルテミスS` (G3, 阪神JF前哨戦) → 阪神JFトライアル設定 (`is_trial=1, target_g1_name='阪神ジュベナイルフィリーズ'`) かつ `SexRestriction.FILLY_MARE`

### ② 出走登録判定ロジックの強化 ([entry.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/race/entry.py))
- `can_enter_race()` において、Enum型およびDB格納文字列（`colt_horse`, `filly_mare` 等）、性別表記（`colt`, `horse`, `gelding`, `牡`, `騸` / `filly`, `mare`, `牝`）の両方に対して堅牢に判定するよう強化。

---

## 3. レース体系の確認

| 区分 | 対象G1 | 指定対象トライアル・前哨戦・関連重賞 | 性別制限 |
| :--- | :--- | :--- | :--- |
| **牡馬路線** | 朝日杯フューチュリティS | 京王杯2歳S, デイリー杯2歳S | `COLT_HORSE` |
| | 皐月賞 | 弥生賞ディープ記念, スプリングS, 若葉S(L) | `COLT_HORSE` |
| | 日本ダービー | 青葉賞, 京都新聞杯, プリンシパルS(L) | `COLT_HORSE` |
| | 菊花賞 | セントライト記念, 神戸新聞杯 | `COLT_HORSE` |
| **牝馬路線** | 阪神ジュベナイルフィリーズ | アルテミスS, ファンタジーS | `FILLY_MARE` |
| | 桜花賞 | チューリップ賞, フィリーズレビュー, アネモネS(L), フェアリーS, クイーンC, フラワーC, 紅梅S(L) | `FILLY_MARE` |
| | オークス | フローラS, スイートピーS(L) | `FILLY_MARE` |
| | 秋華賞 | 紫苑S, ローズS | `FILLY_MARE` |
| **古馬牝馬** | ヴィクトリアマイル | 阪神牝馬S, 中山牝馬S | `FILLY_MARE` |
| | エリザベス女王杯 | 府中牝馬S, マーメイドS, クイーンS, ターコイズS | `FILLY_MARE` |
| **下級条件** | 新馬戦・未勝利戦・1〜3勝クラス | 全レース混合（牝馬限定戦なし） | `MIXED` |

---

## 4. 検証結果

1. **新規単体テスト ([test_race_sex_restrictions.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/tests/test_race_sex_restrictions.py))**:
   - 新馬・未勝利・条件戦の全レースが `MIXED` であり、レース名に「牝馬限定」が含まれないことを確認。
   - 牡馬指定G1・トライアル全14レースが `COLT_HORSE` であることを確認。
   - 牝馬指定G1・トライアル全25レースが `FILLY_MARE` であることを確認。
   - `can_enter_race()` による牡牝の排他的出走判定が正常に機能することを確認。
   - **結果: 4/4 件 合格**

2. **全ユニットテストスイート**:
   - `python3 -m unittest discover tests`
   - **結果: 84/84 件 全テスト合格 (OK)**

3. **GUIヘッドレステスト**:
   - `python3 -m tests.test_gui_headless`
   - **結果: すべてのGUIコンポーネントが正常に起動・初期化完了**
