# 世代交代によるスピード能力・走破タイム進化システムの実装計画

## 概要
現在の走破タイム短縮が「年数の経過」による一律の遺伝ドリフトになっていた仕様を根本から見直し、**「世代の進展（競走馬引退による新種牡馬誕生）」をトリガーとし、「種牡馬の遺伝能力・繁殖牝馬の能力・配合相性（ニックス等）」によってスピード能力の向上・変動が決まる血統進化メカニズム** へ改修します。

---

## 世代（Generation）の厳密な定義
- **第1世代種牡馬（始祖種牡馬）**: 初期種牡馬 60頭 (`sires.generation = 1`)
- **第1世代繁殖牝馬（始祖牝馬）**: 初期繁殖牝馬 600頭 (`dams.generation = 1`)
- **第1世代競走馬**: 第1世代の種牡馬・繁殖牝馬から生まれた産駒 (`horses.generation = 1`)
- **第2世代種牡馬**: 第1世代の競走馬が引退し、新種牡馬となった馬 (`sires.generation = 2`)
- **第2世代競走馬**: 第2世代の種牡馬から生まれた産駒 (`horses.generation = 2`)
- **第3世代種牡馬**: 第2世代の競走馬が引退し、新種牡馬となった馬 (`sires.generation = 3`)
- （以降、第 $N$ 世代の種牡馬から生まれた馬が種牡馬になると第 $N+1$ 世代種牡馬となる）
- ※ 海外輸入種牡馬（[外]）は、現役稼働種牡馬の最新世代と同等を継承。

---

## Proposed Changes

### 1. データベース・スキーマ層
#### [MODIFY] [schema.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/db/schema.py)
- `horses` テーブルに `generation INTEGER NOT NULL DEFAULT 1` カラムを追加。
- `sires` テーブルに `generation INTEGER NOT NULL DEFAULT 1` カラムを追加。
- `dams` テーブルに `generation INTEGER NOT NULL DEFAULT 1` カラムを追加。

#### [MODIFY] [lifecycle.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/core/lifecycle.py)
- `_ensure_columns_exist` にて既存DBテーブルに対する `generation` カラムの存在チェックと自動ALTER TABLEを追加。

---

### 2. 初期化データ生成層
#### [MODIFY] [initializer.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/generators/initializer.py)
- 初期種牡馬（60頭）: `generation = 1`
- 初期繁殖牝馬（600頭）: `generation = 1`
- 初期現役馬・幼駒・当歳馬: `generation = 1`

---

### 3. 遺伝モデル・能力進化層
#### [MODIFY] [genetics.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/core/genetics.py)
- `calculate_polygenic_stat` から無条件の年ドリフト（+0.12）を撤廃し、平均 0.0 の正規分布（中立変異）に変更。
- **新関数 `calculate_offspring_speed` の実装**:
  - 基礎値: 両親のスピード相加平均 $\frac{\text{sire\_speed} + \text{dam\_speed}}{2.0}$
  - **世代進化ポテンシャル**: 種牡馬の世代（第2世代、第3世代...）に応じた潜在能力向上枠。
  - **繁殖牝馬の能力連動 (`dam_multiplier`)**:
    - 繁殖牝馬が高能力（スピード60以上、重賞勝ち、高底力）の場合は世代進化をフルに引き出しスピード向上。
    - 繁殖牝馬が低能力（スピード45未満、未勝利等）の場合は進化枠が発現せず、むしろスピードが低下。
  - **配合相性連動 (`compatibility_bonus`)**:
    - 黄金ニックス（+1.2〜2.5pt）、奇跡の血量（+2.0〜4.0pt）で大きく能力向上。
    - 危険な近交や相性不良ではペナルティ。
  - **遺伝的変異**: $\pm \sigma_e$ のランダム分散。

---

### 4. ライフサイクル・世代交代層
#### [MODIFY] [lifecycle.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/core/lifecycle.py)
- `_manage_sire_roster`:
  - 競走馬が新種牡馬に昇格する際、父馬の世代を取得し、`新種牡馬世代 = 父種牡馬世代 + 1` を設定。
  - 現役時代の競走成績（G1勝利数、重賞タイトル、勝率、獲得賞金）に基づき、新種牡馬の遺伝能力（スピード等の種牡馬ポテンシャル）を評価・確定。
  - 海外種牡馬導入時も現行の世代水準を反映。
- `_manage_broodmare_roster`:
  - 繁殖牝馬昇格時に母馬・父馬の世代から繁殖牝馬の `generation` を設定。

#### [MODIFY] [breeding.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/core/breeding.py)
- 当歳馬誕生時（`_perform_spring_foaling_impl`）:
  - 種牡馬の世代を取得し、産駒の `generation` を `sire_generation` として記録。
  - スピード能力の計算において新ロジック `GeneticsEngine.calculate_offspring_speed` を適用。

---

## Verification Plan

### Automated Tests
- **世代昇格・世代番号の継承テスト**:
  - 初期種牡馬（第1世代）の産駒が種牡馬入りした際に「第2世代種牡馬」となり、その産駒が種牡馬入りした際に「第3世代種牡馬」となることを検証。
- **スピード能力・走破タイムの世代依存テスト**:
  - 種牡馬が交代しないまま年数のみ経過したケースでは平均スピード能力がインフレしないことを確認。
  - 高能力繁殖牝馬×好相性新世代種牡馬の交配でスピード能力が向上することを確認。
  - 低能力繁殖牝馬との交配ではスピード能力が向上しない（下がる場合もある）ことを確認。
- **全単体テスト実行**:
  - `python3 -m unittest discover tests` で全テストが合格することを確認。

---

## User Review Required

> [!IMPORTANT]
> **世代進化のバランス設計について**:
> - 優秀な競走馬が引退して新世代種牡馬となり、優秀な繁殖牝馬と好相性で交配された場合にスピード能力が着実に向上します。
> - 一方で、能力の低い繁殖牝馬との交配や相性の悪い交配では能力が上がらない（または低下する）ため、プレイヤー（または牧場）の配合工夫が走破タイム短縮に直結する設計となります。
