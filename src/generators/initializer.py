"""
初期データ生成モジュール
- 50生産牧場の生成
- 100馬主の生成（固有冠名付与）
- 初期繁殖群（種牡馬60頭、繁殖牝馬600頭）の生成
- 初期現役競走馬群（約1,250頭）の生成
- 能力パラメータ（平均50.0、MSTN遺伝子型、成長型、脚質）の付与
"""

from __future__ import annotations

import math
import random
from typing import List, Tuple

from src.db.database import Database
from src.generators.name_generator import (
    DEFAULT_OWNER_PREFIXES,
    DEFAULT_OWNER_PROFILES,
    HorseNameGenerator,
    PersonNameGenerator,
)
from src.models.breeder import Breeder
from src.models.horse import GenotypeMSTN, GrowthType, Horse, RunningStyle
from src.models.owner import Owner
from src.models.trainer import TrainerSpecialty

# 全9地方（北海道、東北、関東、中部、北陸、近畿、中国、四国、九州）の代表的地名に基づく50牧場定義: (地方名, 牧場名)
DEFAULT_BREEDER_PROFILES: list[Tuple[str, str]] = [
    # 1. 北海道 (18場: 馬産地の中核・名門拠点)
    ("北海道", "日高ファーム"),
    ("北海道", "静内ファーム"),
    ("北海道", "浦河牧場"),
    ("北海道", "門別ファーム"),
    ("北海道", "早来ファーム"),
    ("北海道", "白老牧場"),
    ("北海道", "追分ファーム"),
    ("北海道", "新冠ファーム"),
    ("北海道", "三石牧場"),
    ("北海道", "様似ファーム"),
    ("北海道", "平取ファーム"),
    ("北海道", "鵡川ファーム"),
    ("北海道", "十勝ファーム"),
    ("北海道", "富良野牧場"),
    ("北海道", "洞爺ファーム"),
    ("北海道", "釧路ファーム"),
    ("北海道", "大雪ファーム"),
    ("北海道", "登別牧場"),

    # 2. 東北地方 (6場: 青森・岩手・宮城・山形・福島の馬産・名峰)
    ("東北", "八戸牧場"),        # 青森 (南部馬・歴史的馬産地)
    ("東北", "七戸ファーム"),      # 青森 (ダービー馬輩出名産地)
    ("東北", "遠野牧場"),        # 岩手 (遠野郷・馬の里)
    ("東北", "岩手山ファーム"),    # 岩手 (名峰岩手山)
    ("東北", "蔵王高原ファーム"),  # 山形/宮城 (蔵王高原)
    ("東北", "会津牧場"),        # 福島 (会津盆地)

    # 3. 関東地方 (5場: 栃木・千葉・埼玉・茨城・群馬)
    ("関東", "那須高原ファーム"),  # 栃木 (那須野ヶ原)
    ("関東", "下総牧場"),        # 千葉 (下総御料牧場ゆかり)
    ("関東", "秩父ファーム"),      # 埼玉 (秩父山麓)
    ("関東", "常陸ファーム"),      # 茨城 (常陸大地)
    ("関東", "浅間ファーム"),      # 群馬 (浅間山麓)

    # 4. 中部地方 (5場: 静岡・長野・岐阜・山梨・三重)
    ("中部", "富士山麓ファーム"),  # 静岡/山梨 (富士山麓草地)
    ("中部", "木曽ファーム"),      # 長野 (木曽馬ゆかり)
    ("中部", "安曇野牧場"),      # 長野 (安曇野高原)
    ("中部", "飛騨高山ファーム"),  # 岐阜 (飛騨高原)
    ("中部", "伊勢ファーム"),      # 三重 (伊勢志摩)

    # 5. 北陸地方 (2場: 石川・富山)
    ("北陸", "能登ファーム"),      # 石川 (能登半島)
    ("北陸", "立山高原ファーム"),  # 富山 (名峰立山)

    # 6. 近畿地方 (4場: 兵庫・京都・奈良・滋賀)
    ("近畿", "淡路島ファーム"),    # 兵庫 (淡路島)
    ("近畿", "丹波牧場"),        # 京都/兵庫 (丹波高原)
    ("近畿", "吉野ファーム"),      # 奈良 (吉野山麓)
    ("近畿", "近江ファーム"),      # 滋賀 (近江平野)

    # 7. 中国地方 (3場: 岡山・鳥取・島根)
    ("中国", "蒜山高原ファーム"),  # 岡山 (蒜山高原・大牧草地)
    ("中国", "大山ファーム"),      # 鳥取 (名峰大山)
    ("中国", "出雲牧場"),        # 島根 (出雲の里)

    # 8. 四国地方 (3場: 香川・徳島・高知)
    ("四国", "讃岐ファーム"),      # 香川 (讃岐平野)
    ("四国", "阿波牧場"),        # 徳島 (阿波山地)
    ("四国", "足摺ファーム"),      # 高知 (足摺・南国丘陵)

    # 9. 九州地方 (4場: 鹿児島・熊本・宮崎・大分)
    ("九州", "霧島高原ファーム"),  # 鹿児島/宮崎 (霧島・九州馬産地)
    ("九州", "阿蘇ファーム"),      # 熊本 (阿蘇草千里・大草原)
    ("九州", "指宿牧場"),        # 鹿児島 (薩摩半島南端)
    ("九州", "九重高原ファーム"),  # 大分 (くじゅう高原)
]

# 代表的サイアーライン（父系系統）
SIRE_LINES = [
    "サンデーサイレンス系",
    "ミスタープロスペクター系",
    "ノーザンダンサー系",
    "ナスルーラ系",
    "ロベルト系",
    "ヘイルトゥリーズン系",
]

# 代表的重賞勝ち鞍
MAJOR_G1_NAMES = [
    "日本ダービー", "皐月賞", "菊花賞", "天皇賞（春）", "天皇賞（秋）",
    "ジャパンカップ", "有馬記念", "宝塚記念", "安田記念", "マイルCS",
    "スプリンターズS", "高松宮記念", "エリザベス女王杯", "オークス", "桜花賞",
    "秋華賞", "チャンピオンズC", "フェブラリーS", "大阪杯", "ホープフルS", "朝日杯FS", "阪神JF"
]
MAJOR_G2_NAMES = [
    "京都大賞典", "毎日王冠", "札幌記念", "中山記念", "金鯱賞",
    "阪神大賞典", "目黒記念", "神戸新聞杯", "ローズS", "弥生賞", "青葉賞"
]
MAJOR_G3_NAMES = [
    "鳴尾記念", "エプソムC", "函館記念", "新潟記念", "京成杯",
    "共同通信杯", "きさらぎ賞", "シンザン記念", "武蔵野S", "根岸S"
]


class DatabaseInitializer:
    """データベース初期化＆初期データ生成クラス"""

    def __init__(self, db: Database):
        self.db = db
        self.name_gen = HorseNameGenerator()
        self.person_name_gen = PersonNameGenerator()

    def _sample_normal(self, mean: float = 50.0, std: float = 8.0, min_val: float = 10.0, max_val: float = 90.0) -> float:
        """平均 mean、標準偏差 std の正規乱数を生成し [min_val, max_val] にクリップ"""
        val = random.gauss(mean, std)
        return round(max(min_val, min(max_val, val)), 1)

    def _sample_mstn(self) -> GenotypeMSTN:
        """ミオスタチン遺伝子型をサンプリング (C/C: 25%, C/T: 50%, T/T: 25%)"""
        r = random.random()
        if r < 0.25:
            return GenotypeMSTN.CC
        elif r < 0.75:
            return GenotypeMSTN.CT
        else:
            return GenotypeMSTN.TT

    def _sample_growth(self) -> Tuple[GrowthType, float]:
        """成長型とピーク年齢をサンプリング"""
        r = random.random()
        if r < 0.20:
            # 早熟 (ピーク 2.5〜3.5歳)
            return GrowthType.EARLY, round(random.uniform(2.5, 3.5), 1)
        elif r < 0.75:
            # 普通 (ピーク 3.5〜5.0歳)
            return GrowthType.NORMAL, round(random.uniform(3.5, 5.0), 1)
        else:
            # 晩成 (ピーク 5.0〜6.2歳)
            return GrowthType.LATE, round(random.uniform(5.0, 6.2), 1)

    def _sample_running_style(self) -> RunningStyle:
        """脚質をサンプリング"""
        return random.choice([
            RunningStyle.ESCAPE,
            RunningStyle.LEADING,
            RunningStyle.BETWEEN,
            RunningStyle.CLOSING,
        ])

    def generate_initial_breeders(self, count: int = 50) -> List[int]:
        """全8地方の代表地名に基づく50生産牧場を生成してDBへ挿入し、IDリストを返却（初期成績0デフォルト）"""
        breeder_ids = []
        profiles = DEFAULT_BREEDER_PROFILES.copy()

        with self.db.session() as conn:
            for i in range(count):
                profile = profiles[i % len(profiles)]
                region, name = profile

                # 初期評判 45〜55、初期総繋養枠 15頭（全牧場同等）
                reputation = round(random.uniform(45.0, 55.0), 1)
                capacity = 15
                funds = 100_000_000

                cursor = conn.execute(
                    """
                    INSERT INTO breeders (
                        name, region, reputation, funds, horse_capacity, broodmare_capacity, created_year,
                        current_year_starts, current_year_wins, current_year_g1, current_year_g2, current_year_g3, current_year_earnings,
                        career_starts, career_wins, g1_wins, g2_wins, g3_wins, career_earnings
                    )
                    VALUES (?, ?, ?, ?, ?, ?, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
                    """,
                    (name, region, reputation, funds, capacity, capacity),
                )
                breeder_ids.append(cursor.lastrowid)
        return breeder_ids

    def generate_initial_owners(self, count: int = 100) -> List[int]:
        """
        100人の馬主を生成（苗字＋会社名、苗字から連想されるオリジナル冠名）してDBへ挿入
        """
        owner_ids = []
        profiles = DEFAULT_OWNER_PROFILES.copy()

        with self.db.session() as conn:
            for i in range(count):
                profile = profiles[i % len(profiles)]
                surname, company, prefix = profile
                name = f"{surname}{company}"

                funds = random.randint(80_000_000, 150_000_000)
                capacity = random.randint(15, 25)

                cursor = conn.execute(
                    """
                    INSERT INTO owners (name, prefix, funds, horse_capacity, created_year)
                    VALUES (?, ?, ?, ?, 1)
                    """,
                    (name, prefix, funds, capacity),
                )
                owner_ids.append(cursor.lastrowid)
        return owner_ids

    def generate_initial_trainers(self, count_miho: int = 30, count_ritto: int = 30) -> List[int]:
        """
        美浦（東）30厩舎、栗東（西）30厩舎（計60厩舎）を生成
        50歳〜80歳定年の均等分布、調教師歴1〜30年、スキルレベル初期値（初期成績0デフォルト）
        """
        trainer_ids = []
        specialties = list(TrainerSpecialty)

        with self.db.session() as conn:
            # 1. 美浦（東）30厩舎
            for i in range(count_miho):
                name = self.person_name_gen.generate_trainer_name(i)
                spec = specialties[i % len(specialties)].value
                age = 50 + (i % 30)
                trainer_years = age - 49
                reputation = round(random.uniform(45.0, 55.0), 1)
                skill_level = round(50.0 + (trainer_years * 0.4) + random.uniform(-1.5, 1.5), 1)

                cursor = conn.execute(
                    """
                    INSERT INTO trainers (
                        name, location, specialty, horse_capacity, reputation, skill_level, age, trainer_years, created_year,
                        current_year_starts, current_year_wins, current_year_g1, current_year_g2, current_year_g3, current_year_earnings,
                        career_starts, career_wins, g1_wins, g2_wins, g3_wins, career_earnings
                    )
                    VALUES (?, '美浦', ?, 30, ?, ?, ?, ?, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
                    """,
                    (name, spec, reputation, skill_level, age, trainer_years),
                )
                trainer_ids.append(cursor.lastrowid)

            # 2. 栗東（西）30厩舎
            for i in range(count_ritto):
                name = self.person_name_gen.generate_trainer_name(count_miho + i)
                spec = specialties[(count_miho + i) % len(specialties)].value
                age = 50 + (i % 30)
                trainer_years = age - 49
                reputation = round(random.uniform(45.0, 55.0), 1)
                skill_level = round(50.0 + (trainer_years * 0.4) + random.uniform(-1.5, 1.5), 1)

                cursor = conn.execute(
                    """
                    INSERT INTO trainers (
                        name, location, specialty, horse_capacity, reputation, skill_level, age, trainer_years, created_year,
                        current_year_starts, current_year_wins, current_year_g1, current_year_g2, current_year_g3, current_year_earnings,
                        career_starts, career_wins, g1_wins, g2_wins, g3_wins, career_earnings
                    )
                    VALUES (?, '栗東', ?, 30, ?, ?, ?, ?, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
                    """,
                    (name, spec, reputation, skill_level, age, trainer_years),
                )
                trainer_ids.append(cursor.lastrowid)

        return trainer_ids

    def generate_initial_jockeys(self, count_miho: int = 45, count_ritto: int = 45, trainer_ids: Optional[List[int]] = None) -> List[int]:
        """
        美浦（東）45名、栗東（西）45名（計90名、女性騎手各5名含む）の騎手を生成
        - デビュー年齢は18歳（初期年齢18〜58歳、キャリア1〜41年）
        - 美浦30厩舎・栗東30厩舎に専属所属騎手を1名ずつ配備 (計60名)
        - 残り30名（美浦15名/栗東15名）は実績上位のフリー騎手または追加所属騎手として配備
        """
        jockey_ids = []
        growth_types = ["early", "standard", "standard", "late", "persistent"]

        # 厩舎の取得（美浦30、栗東30に分類）
        with self.db.session() as conn:
            trainers_miho = [r["trainer_id"] for r in conn.execute("SELECT trainer_id FROM trainers WHERE location = '美浦' ORDER BY trainer_id").fetchall()]
            trainers_ritto = [r["trainer_id"] for r in conn.execute("SELECT trainer_id FROM trainers WHERE location = '栗東' ORDER BY trainer_id").fetchall()]

            for loc, count, t_ids in [("美浦", count_miho, trainers_miho), ("栗東", count_ritto, trainers_ritto)]:
                female_indices = {2, 9, 17, 26, 38}
                for i in range(count):
                    gender = "female" if i in female_indices else "male"
                    name = self.person_name_gen.generate_jockey_name(gender=gender)
                    
                    # 18歳から58歳までの年齢分布
                    career_years = (i % 40) + 1
                    age = 18 + (career_years - 1)
                    debut_year = -(career_years - 1)
                    g_type = growth_types[i % len(growth_types)]

                    # 所属厩舎の決定: 最初の30名は各厩舎に1名ずつ専属所属、残り15名はフリー騎手
                    if i < len(t_ids):
                        t_id = t_ids[i]
                        is_free = 0
                    else:
                        t_id = None
                        is_free = 1

                    # 年齢とピークに応じた基礎能力
                    peak = 36 if g_type == "early" else (43 if g_type == "late" else 40)
                    exp = round(min(100.0, career_years * 2.2), 1)

                    if age <= peak:
                        base_skill = 48.0 + (age - 18) * 0.8
                        base_drive = 50.0 + (age - 18) * 0.7
                        stamina = round(min(90.0, 50.0 + (age - 18) * 0.8), 1)
                    else:
                        base_skill = 48.0 + (peak - 18) * 0.8 + (age - peak) * 0.3
                        base_drive = max(35.0, 50.0 + (peak - 18) * 0.7 - (age - peak) * 0.9)
                        stamina = round(max(30.0, 70.0 - (age - peak) * 1.2), 1)

                    skill = self._sample_normal(mean=base_skill, std=6.0, min_val=30.0, max_val=92.0)
                    drive = self._sample_normal(mean=base_drive, std=6.0, min_val=30.0, max_val=92.0)
                    start_dash = self._sample_normal(mean=base_skill, std=6.0, min_val=30.0, max_val=90.0)
                    temp_hand = self._sample_normal(mean=base_skill, std=6.0, min_val=30.0, max_val=92.0)

                    cursor = conn.execute(
                        """
                        INSERT INTO jockeys (
                            name, gender, location, age, debut_year, career_years, is_active,
                            growth_type, is_free, trainer_id, experience, stamina,
                            skill, drive, start_dash, temperament_handling,
                            current_year_starts, current_year_wins, current_year_g1, current_year_g2, current_year_g3, current_year_earnings,
                            career_starts, career_wins, career_rides, career_earnings, g1_wins, g2_wins, g3_wins
                        ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
                        """,
                        (
                            name, gender, loc, age, debut_year, career_years,
                            g_type, is_free, t_id, exp, stamina,
                            skill, drive, start_dash, temp_hand,
                        ),
                    )
                    jockey_ids.append(cursor.lastrowid)

        return jockey_ids

    def generate_initial_population(
        self,
        breeder_ids: List[int],
        owner_ids: List[int],
        trainer_ids: Optional[List[int]] = None,
        jockey_ids: Optional[List[int]] = None,
        num_sires: int = 60,
        num_dams: int = 600,
        num_active_horses: int = 1250,
        with_careers: bool = False,
        include_yearlings: bool = False,
    ) -> None:
        """
        初期繁殖群（種牡馬・繁殖牝馬）および初期現役競走馬群を生成
        - 初期種牡馬・初期繁殖牝馬は始祖馬のため、sire_id=NULL, dam_id=NULL、戦績はすべてゼロ（未出走）
        - 初期現役馬は初期種牡馬・初期繁殖牝馬を父母とし、全頭未出走（0戦0勝、獲得賞金0）
        - 全60厩舎に現役馬を均等入厩（各20〜21頭）、上位騎手を有力馬の主戦騎手として優先配分
        """
        with self.db.session() as conn:
            # 既存馬名の読み込み（重複防止）
            rows = conn.execute("SELECT name FROM horses").fetchall()
            for r in rows:
                self.name_gen.register_name(r["name"])

            # 1. 初期種牡馬の生成 (num_sires頭: 年齢6〜15歳、引退扱い、is_sire=1)
            # 全50牧場に均等に配分（60頭の場合: 50場に各1頭、10場に各2頭）
            print(f"-> 初期種牡馬 {num_sires} 頭を生成中...")
            sire_horse_ids = []
            for i in range(num_sires):
                owner_id = random.choice(owner_ids)
                breeder_id = breeder_ids[i % len(breeder_ids)]
                prefix_row = conn.execute("SELECT prefix FROM owners WHERE owner_id = ?", (owner_id,)).fetchone()
                name = self.name_gen.generate_name(prefix_row["prefix"], sex="horse")

                growth_type, peak_age = self._sample_growth()
                # 種牡馬は平均よりやや高めの能力値 (平均55.0)
                speed = self._sample_normal(mean=55.0, std=7.0)
                stamina = self._sample_normal(mean=55.0, std=7.0)
                accel = self._sample_normal(mean=55.0, std=7.0)
                temp = self._sample_normal(mean=50.0, std=7.0)
                dura = self._sample_normal(mean=55.0, std=7.0)
                vitality = self._sample_normal(mean=50.0, std=7.0)

                age = random.randint(6, 14)
                birth_year = -(age - 1)  # シミュレーション開始時1年目想定

                cursor = conn.execute(
                    """
                    INSERT INTO horses (
                        name, sex, birth_year, age, breeder_id, owner_id,
                        sire_id, dam_id,
                        is_active, is_sire, is_dam, mstn_type,
                        speed, stamina, acceleration, temperament, durability, maternal_vitality,
                        growth_type, peak_age, current_ability_rate, running_style,
                        career_starts, career_wins, g1_wins, g2_wins, g3_wins, major_wins, prize_money, condition_prize_money
                    ) VALUES (
                        ?, 'horse', ?, ?, ?, ?,
                        NULL, NULL,
                        0, 1, 0, ?,
                        ?, ?, ?, ?, ?, ?,
                        ?, ?, 0.8, ?,
                        0, 0, 0, 0, 0, '', 0, 0
                    )
                    """,
                    (
                        name, birth_year, age, breeder_id, owner_id,
                        self._sample_mstn().value,
                        speed, stamina, accel, temp, dura, vitality,
                        growth_type.value, peak_age, self._sample_running_style().value,
                    ),
                )
                h_id = cursor.lastrowid
                sire_horse_ids.append(h_id)

                # sires テーブルに登録 (初期状態は自身の馬名を冠した系統の始祖とする)
                sire_line = f"{name}系"
                conn.execute(
                    """
                    INSERT INTO sires (horse_id, breeder_id, sire_line, max_coverings, stud_fee, is_active)
                    VALUES (?, ?, ?, 30, ?, 1)
                    """,
                    (h_id, breeder_id, sire_line, (random.randint(1_000_000, 5_000_000) // 100_000) * 100_000),
                )

            # 2. 初期繁殖牝馬の生成 (num_dams頭: 年齢5〜18歳、引退扱い、is_dam=1)
            print(f"-> 初期繁殖牝馬 {num_dams} 頭を生成中...")
            dam_horse_ids = []
            for i in range(num_dams):
                # 50牧場に均等に繋養牝馬を配分
                breeder_id = breeder_ids[i % len(breeder_ids)]
                owner_id = random.choice(owner_ids)
                prefix_row = conn.execute("SELECT prefix FROM owners WHERE owner_id = ?", (owner_id,)).fetchone()
                name = self.name_gen.generate_name(prefix_row["prefix"], sex="mare")

                growth_type, peak_age = self._sample_growth()
                speed = self._sample_normal(mean=50.0, std=8.0)
                stamina = self._sample_normal(mean=50.0, std=8.0)
                accel = self._sample_normal(mean=50.0, std=8.0)
                temp = self._sample_normal(mean=50.0, std=8.0)
                dura = self._sample_normal(mean=50.0, std=8.0)
                vitality = self._sample_normal(mean=52.0, std=7.0)

                age = random.randint(5, 16)
                birth_year = -(age - 1)

                cursor = conn.execute(
                    """
                    INSERT INTO horses (
                        name, sex, birth_year, age, breeder_id, owner_id,
                        sire_id, dam_id,
                        is_active, is_sire, is_dam, mstn_type,
                        speed, stamina, acceleration, temperament, durability, maternal_vitality,
                        growth_type, peak_age, current_ability_rate, running_style,
                        career_starts, career_wins, g1_wins, g2_wins, g3_wins, major_wins, prize_money, condition_prize_money
                    ) VALUES (
                        ?, 'mare', ?, ?, ?, ?,
                        NULL, NULL,
                        0, 0, 1, ?,
                        ?, ?, ?, ?, ?, ?,
                        ?, ?, 0.8, ?,
                        0, 0, 0, 0, 0, '', 0, 0
                    )
                    """,
                    (
                        name, birth_year, age, breeder_id, owner_id,
                        self._sample_mstn().value,
                        speed, stamina, accel, temp, dura, vitality,
                        growth_type.value, peak_age, self._sample_running_style().value,
                    ),
                )
                h_id = cursor.lastrowid
                dam_horse_ids.append(h_id)

                # dams テーブルに登録
                conn.execute(
                    """
                    INSERT INTO dams (horse_id, breeder_id, is_active)
                    VALUES (?, ?, 1)
                    """,
                    (h_id, breeder_id),
                )

            # 3. 初期現役競走馬の生成 (約1250頭: 2歳〜6歳、すべて未出走)
            print(f"-> 初期現役競走馬 {num_active_horses} 頭を生成中（未出走デフォルト）...")
            age_distribution = [
                (2, 350),
                (3, 350),
                (4, 250),
                (5, 180),
                (6, 120),
            ]

            active_horse_records = []
            active_idx = 0
            for age, count in age_distribution:
                for _ in range(count):
                    owner_id = random.choice(owner_ids)
                    breeder_id = random.choice(breeder_ids)
                    sex_str = "colt" if random.random() < 0.5 else "filly"
                    if age >= 4:
                        sex_str = "horse" if sex_str == "colt" else "mare"

                    prefix_row = conn.execute("SELECT prefix FROM owners WHERE owner_id = ?", (owner_id,)).fetchone()
                    name = self.name_gen.generate_name(prefix_row["prefix"], sex=sex_str)

                    growth_type, peak_age = self._sample_growth()
                    speed = self._sample_normal(mean=50.0, std=8.0)
                    stamina = self._sample_normal(mean=50.0, std=8.0)
                    accel = self._sample_normal(mean=50.0, std=8.0)
                    temp = self._sample_normal(mean=50.0, std=8.0)
                    dura = self._sample_normal(mean=50.0, std=8.0)
                    vitality = self._sample_normal(mean=50.0, std=8.0)

                    # 現在の成長係数
                    if age < peak_age:
                        current_ability = max(0.6, 1.0 - 0.2 * (peak_age - age))
                    else:
                        current_ability = max(0.6, 1.0 - 0.08 * (age - peak_age))

                    birth_year = -(age - 1)

                    # 初期クラス・出走実績の配分（with_careers=True時のみリアルな分布を付与）
                    starts = 0
                    wins = 0
                    g1_w = 0
                    g2_w = 0
                    g3_w = 0
                    prize = 0
                    c_prize = 0

                    if with_careers:
                        if age == 2:
                            starts = 0
                            wins = 0
                        elif age == 3:
                            overall = speed + stamina + accel
                            if overall >= 168.0:
                                starts = random.randint(4, 7)
                                wins = random.randint(3, 4)
                                c_prize = 16_000_000
                                prize = random.randint(30_000_000, 60_000_000)
                                if random.random() < 0.5:
                                    g3_w = 1
                            elif overall >= 153.0:
                                starts = random.randint(4, 6)
                                wins = 2
                                c_prize = 10_000_000
                                prize = random.randint(18_000_000, 28_000_000)
                            elif overall >= 138.0:
                                starts = random.randint(3, 5)
                                wins = 1
                                c_prize = 4_000_000
                                prize = random.randint(8_000_000, 14_000_000)
                            else:
                                starts = random.randint(1, 4)
                                wins = 0
                                c_prize = 0
                                prize = random.randint(500_000, 2_500_000)
                        else:
                            overall = speed + stamina + accel
                            if overall >= 168.0:
                                starts = random.randint(12, 22)
                                wins = random.randint(4, 7)
                                c_prize = random.randint(24_000_000, 48_000_000)
                                prize = random.randint(60_000_000, 180_000_000)
                                if random.random() < 0.4:
                                    g3_w = random.randint(1, 2)
                                if random.random() < 0.2:
                                    g2_w = 1
                                if random.random() < 0.08:
                                    g1_w = 1
                            elif overall >= 156.0:
                                starts = random.randint(10, 18)
                                wins = 3
                                c_prize = 15_000_000
                                prize = random.randint(35_000_000, 55_000_000)
                            elif overall >= 143.0:
                                starts = random.randint(8, 15)
                                wins = 2
                                c_prize = 9_000_000
                                prize = random.randint(20_000_000, 32_000_000)
                            else:
                                starts = random.randint(6, 12)
                                wins = 1
                                c_prize = 4_000_000
                                prize = random.randint(9_000_000, 15_000_000)

                    # 父母を初期種牡馬・初期繁殖牝馬から割り当て
                    sire_id = sire_horse_ids[active_idx % len(sire_horse_ids)]
                    dam_id = dam_horse_ids[active_idx % len(dam_horse_ids)]

                    # 厩舎の均等入厩 (60厩舎に均等)
                    trainer_id = None
                    if trainer_ids:
                        trainer_id = trainer_ids[active_idx % len(trainer_ids)]
                    active_idx += 1

                    cursor = conn.execute(
                        """
                        INSERT INTO horses (
                            name, sex, birth_year, age, breeder_id, owner_id, trainer_id,
                            sire_id, dam_id,
                            is_active, is_sire, is_dam, mstn_type,
                            speed, stamina, acceleration, temperament, durability, maternal_vitality,
                            growth_type, peak_age, current_ability_rate, running_style,
                            career_starts, career_wins, g1_wins, g2_wins, g3_wins, major_wins, prize_money, condition_prize_money
                        ) VALUES (
                            ?, ?, ?, ?, ?, ?, ?,
                            ?, ?,
                            1, 0, 0, ?,
                            ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?,
                            ?, ?, ?, ?, ?, '', ?, ?
                        )
                        """,
                        (
                            name, sex_str, birth_year, age, breeder_id, owner_id, trainer_id,
                            sire_id, dam_id,
                            self._sample_mstn().value,
                            speed, stamina, accel, temp, dura, vitality,
                            growth_type.value, peak_age, round(current_ability, 2), self._sample_running_style().value,
                            starts, wins, g1_w, g2_w, g3_w, prize, c_prize,
                        ),
                    )
                    h_id = cursor.lastrowid
                    active_horse_records.append({
                        "horse_id": h_id,
                        "overall_ability": speed + stamina + accel,
                    })

            # 3-2. 初期1歳幼駒の生成（翌年2歳デビュー用：350頭、is_active=0）
            if include_yearlings:
                print("-> 初期1歳幼駒 350 頭を生成中（翌年2歳デビュー用）...")
                for i in range(350):
                    owner_id = random.choice(owner_ids)
                    breeder_id = random.choice(breeder_ids)
                    sex_str = "colt" if random.random() < 0.5 else "filly"
                    prefix_row = conn.execute("SELECT prefix FROM owners WHERE owner_id = ?", (owner_id,)).fetchone()
                    name = self.name_gen.generate_name(prefix_row["prefix"], sex=sex_str)
                    growth_type, peak_age = self._sample_growth()
                    speed = self._sample_normal(mean=50.0, std=8.0)
                    stamina = self._sample_normal(mean=50.0, std=8.0)
                    accel = self._sample_normal(mean=50.0, std=8.0)
                    temp = self._sample_normal(mean=50.0, std=8.0)
                    dura = self._sample_normal(mean=50.0, std=8.0)
                    vitality = self._sample_normal(mean=50.0, std=8.0)
                    sire_id = sire_horse_ids[i % len(sire_horse_ids)]
                    dam_id = dam_horse_ids[i % len(dam_horse_ids)]
                    conn.execute(
                        """
                        INSERT INTO horses (
                            name, sex, birth_year, age, breeder_id, owner_id, trainer_id,
                            sire_id, dam_id, is_active, is_sire, is_dam, mstn_type,
                            speed, stamina, acceleration, temperament, durability, maternal_vitality,
                            growth_type, peak_age, current_ability_rate, running_style,
                            career_starts, career_wins, g1_wins, g2_wins, g3_wins, major_wins, prize_money, condition_prize_money
                        ) VALUES (
                            ?, ?, 0, 1, ?, ?, NULL,
                            ?, ?, 0, 0, 0, ?,
                            ?, ?, ?, ?, ?, ?,
                            ?, ?, 0.3, ?,
                            0, 0, 0, 0, 0, '', 0, 0
                        )
                        """,
                        (
                            name, sex_str, breeder_id, owner_id,
                            sire_id, dam_id, self._sample_mstn().value,
                            speed, stamina, accel, temp, dura, vitality,
                            growth_type.value, peak_age, self._sample_running_style().value,
                        ),
                    )

            # 4. 主戦騎手の優先配分（能力上位の馬に実力上位の騎手を優先）
            # 4. 主戦騎手の配分 (自厩舎の所属騎手を基本とし、有力馬には有力フリー騎手も配分可能)
            if jockey_ids:
                print("-> 現役馬への主戦騎手を割り当て中...")
                # 厩舎ごとの所属騎手マップ
                stable_jockey_map: Dict[int, int] = {}
                j_rows = conn.execute("SELECT jockey_id, trainer_id, is_free FROM jockeys WHERE is_active = 1").fetchall()
                for jr in j_rows:
                    if jr["trainer_id"] is not None:
                        stable_jockey_map[jr["trainer_id"]] = jr["jockey_id"]

                # フリー騎手および実力上位騎手
                free_jockeys = [jr["jockey_id"] for jr in j_rows if jr["is_free"] == 1]

                # 馬の能力上位20%は有力馬として扱い、フリー騎手も積極的に起用可能
                active_horse_records.sort(key=lambda x: x["overall_ability"], reverse=True)
                top_cutoff = len(active_horse_records) // 5

                for idx, h_rec in enumerate(active_horse_records):
                    h_row = conn.execute("SELECT trainer_id FROM horses WHERE horse_id = ?", (h_rec["horse_id"],)).fetchone()
                    t_id = h_row["trainer_id"] if h_row else None
                    
                    assigned_j_id = None
                    if idx < top_cutoff and free_jockeys and (idx % 2 == 0):
                        # 有力馬の一部はフリー騎手を主戦に
                        assigned_j_id = free_jockeys[idx % len(free_jockeys)]
                    elif t_id and t_id in stable_jockey_map:
                        # 基本は自厩舎の所属騎手
                        assigned_j_id = stable_jockey_map[t_id]
                    elif free_jockeys:
                        assigned_j_id = free_jockeys[idx % len(free_jockeys)]
                    else:
                        assigned_j_id = jockey_ids[idx % len(jockey_ids)]

                    conn.execute(
                        "UPDATE horses SET jockey_id = ? WHERE horse_id = ?",
                        (assigned_j_id, h_rec["horse_id"]),
                    )

    def initialize_all(
        self,
        force_recreate: bool = True,
        with_careers: bool = False,
        include_yearlings: bool = False,
    ) -> None:
        """スキーマ初期化から初期データ投入までを一括実行"""
        print("=== データベース初期化を開始 ===")
        self.db.initialize_schema(force_recreate=force_recreate)
        print("[OK] SQLite スキーマ作成完了")

        print("-> 生産牧場（50場）生成中...")
        breeder_ids = self.generate_initial_breeders(50)
        print(f"[OK] 生産牧場 {len(breeder_ids)} 場を登録完了")

        print("-> 馬主（100人、固有冠名）生成中...")
        owner_ids = self.generate_initial_owners(100)
        print(f"[OK] 馬主 {len(owner_ids)} 人を登録完了")

        print("-> 厩舎（美浦30場、栗東30場、計60厩舎）生成中...")
        trainer_ids = self.generate_initial_trainers(count_miho=30, count_ritto=30)
        print(f"[OK] 厩舎 {len(trainer_ids)} 厩舎を登録完了")

        print("-> 騎手（美浦45名、栗東45名、計90名・18歳デビュー・専属所属配備）生成中...")
        jockey_ids = self.generate_initial_jockeys(count_miho=45, count_ritto=45, trainer_ids=trainer_ids)
        print(f"[OK] 騎手 {len(jockey_ids)} 名を登録完了")

        print("-> 初期個体群（種牡馬60頭、繁殖牝馬600頭、現役馬1250頭）生成中...")
        self.generate_initial_population(
            breeder_ids=breeder_ids,
            owner_ids=owner_ids,
            trainer_ids=trainer_ids,
            jockey_ids=jockey_ids,
            num_sires=60,
            num_dams=600,
            num_active_horses=1250,
            with_careers=with_careers,
            include_yearlings=include_yearlings,
        )
        print("[OK] 初期個体群の生成完了")
        print("=== データベース初期化が正常に完了しました ===")
