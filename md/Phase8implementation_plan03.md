# レース呼称変更・表彰項目整理・競走馬引退ルール改定の実装計画

以下の3つの要件について改定を行います。

1. **レース名呼称の変更**:
   - 「日本ダービー」 $\to$ 「東京優駿（日本ダービー）」
   - 「オークス」 $\to$ 「優駿牝馬（オークス）」
2. **表彰の整理**:
   - 表彰画面から「最多新人調教師」の表彰項目および歴代推移列を削除
3. **競走馬の引退タイミングの改定**:
   - 3歳末の重賞未勝利足切りを撤廃（3歳9月4週の未勝利引退は現状維持）
   - 4歳12月4週: 条件クラスの4歳馬は引退。オープン馬も成績推移・成長曲線に応じて引退判定
   - 5歳12月4週: 牝馬は全頭引退。牡馬は条件馬引退、オープン馬は成績推移・成長曲線に応じて引退判定
   - 6歳12月4週: 成績推移・成長曲線に応じて引退判定
   - 7歳12月4週: 全頭引退（7歳末で100%引退）

---

## 提案する変更内容

### 1. レース呼称変更

#### [MODIFY] [annual_program.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/race/annual_program.py)
- 本番G1の名称を `東京優駿（日本ダービー）`, `優駿牝馬（オークス）` に変更
- トライアル競走（青葉賞、京都新聞杯、プリンシパルS、フローラS、スイートピーS）の `target_g1_name` を新名称に変更

#### [MODIFY] [race_program.csv](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/data/race_program.csv)
- CSV内のレース名およびトライアル対象G1名を `東京優駿（日本ダービー）`, `優駿牝馬（オークス）` に更新

#### [MODIFY] [entry.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/race/entry.py)
- `G1_ALIAS_MAP` を新名称を正規化先として更新（「日本ダービー」「東京優駿」「オークス」「優駿牝馬」等の揺れを完全吸収）

#### [MODIFY] [database_view.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/views/database_view.py)
- `MAJOR_ROUTES` の 3歳牡馬3冠・3歳牝馬3冠定義および `ROUTE_RACE_ALIASES` を新名称に対応

#### [MODIFY] [initializer.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/generators/initializer.py)
- `MAJOR_G1_NAMES` の登録名称を更新

---

### 2. 表彰における「最多新人調教師」の削除

#### [MODIFY] [awards_view.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/gui/views/awards_view.py)
- 歴代各部門リーディングカードから「最多勝新人調教師」カードを削除（6枠 $\to$ 5枠レイアウトに調整）
- 歴代推移一覧テーブルの「最多勝新人調教師」カラムを削除（7列 $\to$ 6列）
- `_calc_annual_leaders` から新人調教師の算出処理を削除

---

### 3. 競走馬の引退タイミング改定

#### [MODIFY] [lifecycle.py](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/core/lifecycle.py)
- 年末（12月4週終了時）の引退判定ロジックを以下のように更新:
  - **4歳末**: 条件馬（重賞未勝利 かつ 収得賞金1600万円未満 / 3勝以下）は全頭引退。オープン馬もピークアウトや能力減退（`current_ability_rate`）に応じた確率的引退判定を実施。
  - **5歳末**: 牝馬は全頭引退（繁殖入り・定員調整へ）。牡馬は条件馬全頭引退、オープン馬は成績推移・成長曲線（ピークアウト・不振）に応じた引退判定。
  - **6歳末**: 成績推移・成長曲線（ピークアウト・近走不振・能力減衰）に応じた引退判定（引退確率を高めに設定）。
  - **7歳末**: 全頭引退（現役上限年齢として100%引退）。
  - ※3歳末の足切りは行わず、3歳9月4週で未勝利引退とならなかった馬（1勝以上）は4歳へ進出。

---

## 検証計画

### 自動テスト
- レース呼称変更のテスト:
  - `python3 -m unittest tests/test_database_view_routes.py`
  - `python3 -m unittest tests/test_phase6_trial_and_awards.py`
- 引退ロジックのテスト:
  - `tests/test_phase8_fixes.py` または新規テストにて、4歳条件馬引退、5歳牝馬引退、5〜6歳牡馬のピークアウト引退、7歳全頭引退を検証
- プロジェクト全体の全単体テスト実行:
  - `python3 -m unittest discover tests`

### 画面動作確認
- GUI画面で「主要レース路線」「表彰」の表示が崩れず正しく反映されていることを確認
