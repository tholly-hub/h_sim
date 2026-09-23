# レース出走条件改定および番組表調整 完了報告

ユーザー様からご指定いただいたレース出走条件の改定と番組表の調整を実装し、全テストおよび実シミュレーションでの検証を完了いたしました。

---

## 🛠️ 主な修正内容

### 1. レース間隔ルールの改定 ([`entry.py`](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/race/entry.py))
- **一般馬（1勝以上）**: 最低でも **中4週**（前走から差5週以上）の間隔が必要となります。
- **未勝利馬（0勝馬）**: 特例として従来通り **中3週**（前走から差4週以上）で出走可能です。

```python
# レース間隔制限
if last_run is not None:
    last_y, last_w = last_run
    diff_weeks = (race.year - last_y) * 48 + (race.week - last_w)
    min_interval = 4 if horse.career_wins == 0 else 5
    if diff_weeks < min_interval:
        return False
```

### 2. G1勝利馬のG3・リステッド出走制限 ([`entry.py`](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/race/entry.py))
- 過去にG1で1勝以上している競走馬（`g1_wins > 0`）は、**G3競走およびリステッド競走に出走できない**ように制限しました。
- ただし、対象レースが**トライアル競走（`is_trial = 1`）の場合は出走可能**としています。

```python
# G1勝利馬の出走制限（G3・リステッド競走は原則出走不可、ただしトライアル競走は出走可能）
if getattr(horse, "g1_wins", 0) > 0 and race.grade in (RaceGrade.G3, RaceGrade.L):
    if not race.is_trial:
        return False
```

### 3. 番組表のトライアル開催週調整 ([`annual_program.py`](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/src/race/annual_program.py))
- 中4週ルール（5週以上間隔）が適用されても、トライアル競走で権利を獲得した馬が本番G1に出走できるよう、**全53レースのトライアル競走の開催週を対象G1の5週以上前（中4週以上）に前倒し調整**しました。
- 開催週の移動に伴い、各週の競馬場ローテーション（`weekly_tracks`）も調整し、1年48週すべてにおいて「2〜3場開催、各競馬場4レース以上」のバランスを維持しています。

---

## 🧪 検証結果

1. **自動テストスイート ([`tests/test_race_entry_rules.py`](file:///Users/takashihorimatsu/Library/CloudStorage/GoogleDrive-thorimatsu@gmail.com/マイドライブ/h_sim/tests/test_race_entry_rules.py))**:
   - 未勝利馬の中3週出走可能 / 中2週出走不可の検証: **PASS**
   - 既勝利馬の中4週出走可能 / 中3週出走不可の検証（年跨ぎ含む）: **PASS**
   - G1馬の通常G3/L出走不可 & トライアルG3/L出走可能の検証: **PASS**
   - 全53トライアル競走と対象G1の週差がすべて5週以上（`diff >= 5`）であることの検証: **PASS**
   - 全95件のテストスイート: **ALL PASSED**

2. **2年間実シミュレーション検証**:
   - G1勝ち馬の通常G3/リステッド出走違反: **0件**
   - G1勝ち馬のトライアル競走への出走: **正常に許可**
   - 年間進行および表彰・昇級等への悪影響なし
