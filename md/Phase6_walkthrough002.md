# レース出走体系の見直しおよび新馬・未勝利・条件戦の牝馬限定レース廃止 計画書

## 目的・概要
ユーザー様からのご要望に基づき、以下の2点を改修します。
1. **2歳・3歳G1レースおよび前哨戦・トライアルレースの牡牝分離（原則的にそれぞれのレースに出馬）**:
   - 牡馬出走指定: 朝日杯FS、皐月賞、日本ダービー、菊花賞、およびそれらのトライアル・前哨戦レース
   - 牝馬出走指定: 阪神JF、桜花賞、オークス、秋華賞、およびそれらのトライアル・前哨戦レース
   - 古馬牝馬限定レース: ヴィクトリアマイル、エリザベス女王杯、およびそのトライアル・前哨戦レース（阪神牝馬S、府中牝馬S等）は牝馬限定
2. **新馬戦、未勝利戦、条件戦（1勝〜3勝クラス）の牝馬限定レースの廃止**:
   - これらのカテゴリーで走るレースはすべて牡馬・牝馬混合（`SexRestriction.MIXED`）に変更する。

---

## 提案する変更内容

### 1. 番組表定義の見直し ([annual_program.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/race/annual_program.py))

#### ① 新馬・未勝利・条件戦の牝馬限定廃止
- **3歳未勝利戦**:
  - 現在: `3歳未勝利(牝馬限定・芝1800m)` (`SexRestriction.FILLY_MARE`)
  - 変更後: `3歳未勝利(芝1800m)` (`SexRestriction.MIXED`)
- **1勝クラス**:
  - 現在: `1勝クラス(牝馬限定・芝1600/1800m)` (`SexRestriction.FILLY_MARE`)
  - 変更後: `1勝クラス(芝1600/1800m)` (`SexRestriction.MIXED`)
- **2勝クラス**:
  - 現在: `2勝クラス(牝馬限定・芝1600m)` (`SexRestriction.FILLY_MARE`)
  - 変更後: `2勝クラス(芝1600m)` (`SexRestriction.MIXED`)
- ※新馬戦および3勝クラスには元々牝馬限定戦は存在しないため、上記変更により下級条件・条件戦の全レースが牡馬・牝馬混合になります。

#### ② 2歳・3歳主要G1およびトライアル・前哨戦の性別制限設定
- **牡馬指定 (`SexRestriction.COLT_HORSE`)**:
  - 朝日杯フューチュリティS (G1)
  - 皐月賞 (G1)
  - 日本ダービー (G1)
  - 菊花賞 (G1)
  - トライアル / 前哨戦:
    - 弥生賞ディープ記念 (G2)
    - スプリングS (G2)
    - 若葉ステークス (L)
    - 青葉賞 (G2)
    - 京都新聞杯 (G2) ← *`MIXED` から `COLT_HORSE` に更新*
    - プリンシパルS (L) ← *`MIXED` から `COLT_HORSE` に更新*
    - セントライト記念 (G2)
    - 神戸新聞杯 (G2)
    - 京王杯2歳S (G2) ← *`MIXED` から `COLT_HORSE` に更新*
    - デイリー杯2歳S (G2) ← *`MIXED` から `COLT_HORSE` に更新*

- **牝馬指定 (`SexRestriction.FILLY_MARE`)**:
  - 阪神ジュベナイルフィリーズ (G1)
  - 桜花賞 (G1)
  - オークス (G1)
  - 秋華賞 (G1)
  - トライアル / 前哨戦 / 牝馬重賞:
    - チューリップ賞 (G2)
    - フィリーズレビュー (G2)
    - アネモネS (L) ← *`MIXED` から `FILLY_MARE` に更新*
    - フローラS (G2)
    - スイートピーS (L) ← *`MIXED` から `FILLY_MARE` に更新*
    - 紫苑S (G2)
    - ローズS (G2)
    - ファンタジーS (G3)
    - アルテミスS (G3) ← *阪神JFトライアル設定 (`is_trial=1, target_g1_name='阪神ジュベナイルフィリーズ'`) かつ `FILLY_MARE`*
    - 紅梅ステークス (L) ← *`FILLY_MARE` に設定*
    - フェアリーS (G3), クイーンC (G3), フラワーC (G3)

- **古馬牝馬限定 (`SexRestriction.FILLY_MARE`)**:
  - ヴィクトリアマイル (G1)
  - エリザベス女王杯 (G1)
  - 阪神牝馬S (G2), 府中牝馬S (G2), 中山牝馬S (G3), マーメイドS (G3), クイーンS (G3), ターコイズS (G3)

- **リステッドレースリスト定義 (`LISTED_TITLES`) の拡張**:
  - 各レースのタプルに性別制限フィールドを追加し、アネモネS・スイートピーS・紅梅Sは `FILLY_MARE`、若葉S・プリンシパルSは `COLT_HORSE`、それ以外は `MIXED` として正確に生成。

### 2. 出走登録判定の堅牢化 ([entry.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/race/entry.py))
- `can_enter_race()` 内の性別判定ロジックにおいて、Enum型とDB格納文字列型の双方に完全対応:
  ```python
  sex_res_val = race.sex_restriction.value if hasattr(race.sex_restriction, 'value') else str(race.sex_restriction).lower()
  if sex_res_val in ('filly_mare', 'filly') and not is_female:
      return False
  if sex_res_val in ('colt_horse', 'colt') and not is_male:
      return False
  ```
  これにより、牡馬指定レースに牝馬が誤って登録されたり、牝馬指定レースに牡馬が登録されることが100%防止されます。

---

## 検証計画

### 1. 単体テスト & プログラム検証
- `tests/test_race_sex_restrictions.py`（新規）を作成:
  - 新馬・未勝利・条件戦（1勝〜3勝クラス）の全レースにおいて `sex_restriction == SexRestriction.MIXED` であることを検証。
  - 朝日杯FS、皐月賞、日本ダービー、菊花賞、およびその前哨戦（弥生賞、スプリングS、若葉S、青葉賞、京都新聞杯、プリンシパルS、神戸新聞杯、セントライト記念、京王杯2歳S、デイリー杯2歳S）が `SexRestriction.COLT_HORSE` であることを検証。
  - 阪神JF、桜花賞、オークス、秋華賞、およびその前哨戦（チューリップ賞、フィリーズレビュー、アネモネS、フローラS、スイートピーS、紫苑S、ローズS、アルテミスS、ファンタジーS）が `SexRestriction.FILLY_MARE` であることを検証。
  - 出走登録処理で牡馬・牝馬がそれぞれの指定レース以外には登録されないことを検証。

### 2. 既存テストスイートのパス確認
- `python3 -m unittest discover tests` を実行し、既存80件のテストがすべて合格することを確認。
- `python3 -m tests.test_gui_headless` を実行し、GUI/シミュレーション全体が正常に動作することを確認。
