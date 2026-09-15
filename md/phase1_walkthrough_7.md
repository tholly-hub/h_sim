# Walkthrough - 厩舎システム・騎手システム・成績閲覧・血統表/系統図出力の実装

## 1. 概要

ご指示いただいた以下の全機能を実装し、単体テストおよび実機データベースにて正常動作を確認しました。

1. **厩舎システムの実装**
   - **美浦 25 厩舎、栗東 25 厩舎（合計 50 厩舎）** を生成。
   - 厩舎名は「苗字＋厩舎」（国枝厩舎、矢作厩舎など）。
   - 各厩舎に特徴・得意分野（芝得意、ダート得意、長距離得意、短距離得意、仕上り早、晩成育成、馬体ケア、万能）を設定。
   - 初期現役馬 1,250 頭を **全 50 厩舎に各 25 頭ずつ均等に入厩**。
   - 厩舎枠数は初期 30 頭、成績に応じて **最大 50 頭まで拡張可能**。
   - 新馬入厩で枠を超える場合は、成績下位の現役馬を他厩舎（同東西所属・空き枠優先）へ転厩。
   - 転厩によって所属馬が 0 頭にならないよう **最低 1 頭所属保証** を実装。

2. **騎手システムの実装**
   - **美浦 40 名、栗東 40 名（合計 80 名）** の騎手を生成。
   - キャリア 1〜30 年（年齢 20〜50 歳）を各世代均等に分散配置。
   - 能力値（操縦技術、直線推進力、スタートダッシュ、気性難折り合い）を付与。
   - **現役 30 年間定員維持サイクル**:
     - 毎年、キャリア 30 年超（または 50 歳超）となった騎手が定年引退。
     - 引退した人数と同数の新人騎手（20 歳、キャリア 1 年目）が自動誕生し、美浦 40 名・栗東 40 名（計 80 名）の定員規模を常に一定維持。
   - **有力馬への主戦騎手配分と乗り替わりロジック**:
     - 能力上位の馬に実力上位の騎手を主戦騎手として優先割り当て。
     - 同一レースに同じ騎手のお手馬が複数出走する場合、最も評価の高い馬に先約騎乗し、あぶれた馬には空き騎手から代打騎手を手配。
     - 代打騎手が好成績（1着〜2着連対）を挙げた場合、今後の主戦騎手として昇格・乗り替わり成立。

3. **成績閲覧および血統表・系統図出力**
   - **成績ランキング**:
     - 種牡馬、繁殖牝馬、競走馬、生産牧場、厩舎、騎手 の 6 カテゴリについて、通算（生涯）および当年成績のランキングを出力可能。
   - **3代血統表（Pedigree Tree）**:
     - 競走馬の父・母、父父・父母、母父・母母をアスキーアートツリー形式で出力。
   - **サイアーライン系統図（Sire Line Tree）**:
     - 初期種牡馬 60 頭を起点とする父系直系ツリーを出力。

---

## 2. 変更・追加されたファイル

- `src/db/schema.py`:
  - `trainers` テーブル、`jockeys` テーブルを追加。
  - `horses` テーブルに `trainer_id`, `jockey_id` を追加。
  - `results` テーブルに `trainer_id`, `jockey_id` を追加。
  - 関連インデックスを追加。
- `src/models/trainer.py` [新規]: `Trainer` データクラス、`TrainerSpecialty` Enum。
- `src/models/jockey.py` [新規]: `Jockey` データクラス、能力属性。
- `src/models/horse.py`: `Horse` データクラスに `trainer_id`, `jockey_id` を追加。
- `src/generators/name_generator.py`: 調教師苗字リスト、騎手氏名生成用 `PersonNameGenerator` を追加。
- `src/generators/initializer.py`: 50厩舎生成、80名騎手生成、現役馬各25頭均等入厩、上位騎手優先割り当て。
- `src/management/stable_manager.py` [新規]: 厩舎枠管理、新馬入厩、他厩舎転厩（同東西優先、0頭防止保護）。
- `src/management/jockey_manager.py` [新規]: 現役30年引退と新人補充（定員80名維持）、同一レースお手馬重複代打手配、連対時主戦昇格。
- `src/views/viewer.py`: `list_trainers`, `list_jockeys`, `show_pedigree`, `show_sire_line_tree`, `show_rankings` を追加、`show_horse_detail` に厩舎・主戦騎手を反映。
- `main.py`: `--trainers`, `--jockeys`, `--pedigree`, `--sire-tree`, `--stats` CLIオプション追加、対話型メニューの拡充。
- `tests/test_phase2_stable_jockey.py` [新規]: 包括的単体テストスイート。

---

## 3. テストと検証結果

### 1. 自動単体テスト
- `tests/test_phase2_stable_jockey.py` (5/5 テスト PASS)
  - `test_stable_initial_even_distribution`: 美浦25/栗東25厩舎、全厩舎初期枠30頭、各25頭均等入厩、全頭主戦騎手配分
  - `test_stable_capacity_expansion_and_transfer_safety`: 枠拡張（最大50頭）、残り1頭時の転厩拒否（0頭防止保護）
  - `test_jockey_quota_maintenance_and_retirement`: 30年現役引退、同数新人誕生による美浦40/栗東40定員維持
  - `test_jockey_race_assignment_and_substitute_promotion`: お手馬重複時の代打手配、2着入線による主戦昇格
  - `test_pedigree_and_sire_line_display`: 3代血統表、サイアーライン系統図、各種ランキングの表示確認
- `tests/test_transfer.py` (4/4 テスト PASS)
- `tests/test_phase1.py` (4/4 テスト PASS)
- **総計 13 テストすべて PASS**。

### 2. CLI 実機動作確認
- `$env:PYTHONIOENCODING="utf-8"; py -3 main.py --init`
  - 50牧場、100馬主、50厩舎（美浦25/栗東25）、80騎手（美浦40/栗東40）、1910頭（現役1250頭が入厩・主戦騎手付き）の初期化が成功。
- `$env:PYTHONIOENCODING="utf-8"; py -3 main.py --trainers`
  - 全50厩舎で管理頭数が 25 / 30頭、特徴（芝得意、ダート得意、長距離得意など）が綺麗に表示。
- `$env:PYTHONIOENCODING="utf-8"; py -3 main.py --jockeys`
  - 美浦40名・栗東40名、キャリア1〜30年、能力値、通算成績が表示。
- `$env:PYTHONIOENCODING="utf-8"; py -3 main.py --pedigree 700`
  - 3代血統表がツリー形式で出力。
- `$env:PYTHONIOENCODING="utf-8"; py -3 main.py --sire-tree`
  - 全60系統のサイアーライン系統図が出力。
- `$env:PYTHONIOENCODING="utf-8"; py -3 main.py --horse-id 1000`
  - 馬詳細情報に「厩舎 / 主戦: 高野厩舎 [栗東] / 主戦騎手: 角田 祐一 [美浦]」が正しく反映。
