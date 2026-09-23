# ホープフルSおよびトライアル競走の2歳・牡牝混合（MIXED）対応 完了

## 1. 概要
- **ホープフルS（G1）**:
  - 年齢制限: 2歳限定（`AgeRestriction.TWO_YO`）
  - 性別制限: 牡馬・牝馬混合（`SexRestriction.MIXED`）
- **ホープフルSのトライアル・前哨戦**:
  - **東京スポーツ杯2歳S**（G2・芝1800m）: 2歳、MIXED、優先出走権1〜2着
  - **京都2歳S**（G3・芝2000m）: 2歳、MIXED、優先出走権1着
  - **芙蓉ステークス**（OP/L・芝2000m）: 2歳、MIXED、優先出走権1着
  - **アイビーステークス**（L・芝1800m）: 2歳、MIXED、優先出走権1着
  - **萩ステークス**（L・芝1800m）: 2歳、MIXED、優先出走権1着

---

## 2. 変更内容
1. **番組表定義の拡充・確認 ([`src/race/annual_program.py`](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/race/annual_program.py))**:
   - `ホープフルS`（第48週・中山・芝2000m・G1）が `AgeRestriction.TWO_YO` かつ `SexRestriction.MIXED` であることを確認。
   - `東京スポーツ杯2歳S`（第43週・東京・芝1800m・G2）、`京都2歳S`（第43週・京都・芝2000m・G3）がともに `AgeRestriction.TWO_YO` かつ `SexRestriction.MIXED`（ホープフルSトライアル）であることを確認。
   - ホープフルSに向けた実在の主要2歳芝中距離リステッド・オープン前哨戦（`芙蓉ステークス`・`アイビーステークス`・`萩ステークス`）を番組表（`LISTED_TITLES`）に追加（すべて2歳、MIXED）。
2. **出走判定・テストコードの追加 ([`tests/test_race_sex_restrictions.py`](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/tests/test_race_sex_restrictions.py))**:
   - ホープフルSおよびその全トライアルレースがすべて `AgeRestriction.TWO_YO` かつ `SexRestriction.MIXED` であることを自動検証するテスト `test_hopeful_stakes_and_trials_mixed_restriction` を追加。
   - 2歳の牡馬・牝馬双方が問題なく出走資格（`can_enter_race`）を満たして出走可能であることを検証。

---

## 3. 検証結果
- 全108件の単体テストがすべて正常にパスしました。
