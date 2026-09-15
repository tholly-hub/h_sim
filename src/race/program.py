"""
年間レース番組表 (Race Program / Calendar)
- 年間48週 (12ヶ月 × 4週) の全レース体系
- 実在レース名に全面準拠（G1, G2, G3, OP, 3勝クラス）
- 3歳春マイルG1「NHKマイルカップ」＋トライアル（NZT・アーリントンC）
- 3歳ダート三冠（羽田盃・東京ダービー・ジャパンダートクラシック）＋古馬ダート王道
- 2歳王者決定戦（阪神JF・朝日杯FS・ホープフルS・全日本2歳優駿）
- 現役馬頭数（約1,250頭）に適正な週8〜9レース配分（頭数割れ防止）
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from src.db.database import Database
from src.models.race import AgeRestriction, Race, RaceGrade, RaceSurface, SexRestriction


GRADE_PRIZE_MAP: Dict[RaceGrade, tuple[int, int]] = {
    RaceGrade.G1: (150_000_000, 70_000_000),
    RaceGrade.G2: (60_000_000, 24_000_000),
    RaceGrade.G3: (40_000_000, 15_000_000),
    RaceGrade.L: (25_000_000, 10_000_000),
    RaceGrade.OP: (22_000_000, 10_000_000),
    RaceGrade.COND_3W: (18_400_000, 6_000_000),
    RaceGrade.COND_2W: (15_000_000, 5_000_000),
    RaceGrade.COND_1W: (11_000_000, 4_000_000),
    RaceGrade.NEWCOMER: (7_200_000, 4_000_000),
    RaceGrade.MAIDEN: (5_500_000, 4_000_000),
}


class RaceProgramBuilder:
    """実在レース名・適正頭数バランス番組表生成クラス"""

    def __init__(self, db: Database):
        self.db = db

    def generate_annual_program(self, year: int = 1) -> List[Race]:
        """年間48週の全レース一覧を生成"""
        races: List[Race] = []

        # =========================================================================
        # 1. 主要重賞・G1・G2・G3およびトライアル番組（実在名称）
        # =========================================================================

        # --- 1月 (第1週〜第4週) ---
        # 1週
        races.append(Race(name='中山金杯', track_id='C', month=1, week=1, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=2000, age_restriction=AgeRestriction.FOUR_YO_UP))
        races.append(Race(name='京都金杯', track_id='A', month=1, week=1, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=1600, age_restriction=AgeRestriction.FOUR_YO_UP))
        races.append(Race(name='シンザン記念', track_id='A', month=1, week=1, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=1600, age_restriction=AgeRestriction.THREE_YO))
        # 2週
        races.append(Race(name='フェアリーS', track_id='C', month=1, week=2, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=1600, age_restriction=AgeRestriction.THREE_YO, sex_restriction=SexRestriction.FILLY_MARE))
        races.append(Race(name='京成杯', track_id='C', month=1, week=2, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=2000, age_restriction=AgeRestriction.THREE_YO))
        # 3週
        races.append(Race(name='日経新春杯', track_id='A', month=1, week=3, grade=RaceGrade.G2, surface=RaceSurface.TURF, distance=2400, age_restriction=AgeRestriction.FOUR_YO_UP))
        races.append(Race(name='東海S', track_id='D', month=1, week=3, grade=RaceGrade.G2, surface=RaceSurface.DIRT, distance=1800, age_restriction=AgeRestriction.FOUR_YO_UP, is_trial=1, target_g1_name='フェブラリーS'))
        # 4週
        races.append(Race(name='アメリカJCC', track_id='C', month=1, week=4, grade=RaceGrade.G2, surface=RaceSurface.TURF, distance=2200, age_restriction=AgeRestriction.FOUR_YO_UP))
        races.append(Race(name='根岸S', track_id='B', month=1, week=4, grade=RaceGrade.G3, surface=RaceSurface.DIRT, distance=1400, age_restriction=AgeRestriction.FOUR_YO_UP, is_trial=1, target_g1_name='フェブラリーS'))
        races.append(Race(name='シルクロードS', track_id='A', month=1, week=4, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=1200, age_restriction=AgeRestriction.FOUR_YO_UP, is_trial=1, target_g1_name='高松宮記念'))

        # --- 2月 (第5週〜第8週) ---
        # 5週
        races.append(Race(name='東京新聞杯', track_id='B', month=2, week=5, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=1600, age_restriction=AgeRestriction.FOUR_YO_UP))
        races.append(Race(name='きさらぎ賞', track_id='A', month=2, week=5, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=1800, age_restriction=AgeRestriction.THREE_YO))
        # 6週
        races.append(Race(name='共同通信杯', track_id='B', month=2, week=6, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=1800, age_restriction=AgeRestriction.THREE_YO))
        races.append(Race(name='クイーンC', track_id='B', month=2, week=6, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=1600, age_restriction=AgeRestriction.THREE_YO, sex_restriction=SexRestriction.FILLY_MARE))
        races.append(Race(name='京都記念', track_id='A', month=2, week=6, grade=RaceGrade.G2, surface=RaceSurface.TURF, distance=2200, age_restriction=AgeRestriction.FOUR_YO_UP))
        # 7週
        races.append(Race(name='フェブラリーS', track_id='B', month=2, week=7, grade=RaceGrade.G1, surface=RaceSurface.DIRT, distance=1600, age_restriction=AgeRestriction.FOUR_YO_UP, base_prize=120_000_000))
        races.append(Race(name='小倉大賞典', track_id='D', month=2, week=7, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=1800, age_restriction=AgeRestriction.FOUR_YO_UP))
        # 8週
        races.append(Race(name='中山記念', track_id='C', month=2, week=8, grade=RaceGrade.G2, surface=RaceSurface.TURF, distance=1800, age_restriction=AgeRestriction.FOUR_YO_UP))
        races.append(Race(name='阪急杯', track_id='A', month=2, week=8, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=1400, age_restriction=AgeRestriction.FOUR_YO_UP, is_trial=1, target_g1_name='高松宮記念'))

        # --- 3月 (第9週〜第12週) ---
        # 9週: クラシック前哨戦開幕
        races.append(Race(name='弥生賞ディープインパクト記念', track_id='C', month=3, week=9, grade=RaceGrade.G2, surface=RaceSurface.TURF, distance=2000, age_restriction=AgeRestriction.THREE_YO, sex_restriction=SexRestriction.COLT_HORSE, is_trial=1, target_g1_name='皐月賞'))
        races.append(Race(name='チューリップ賞', track_id='A', month=3, week=9, grade=RaceGrade.G2, surface=RaceSurface.TURF, distance=1600, age_restriction=AgeRestriction.THREE_YO, sex_restriction=SexRestriction.FILLY_MARE, is_trial=1, target_g1_name='桜花賞'))
        races.append(Race(name='オーシャンS', track_id='C', month=3, week=9, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=1200, age_restriction=AgeRestriction.FOUR_YO_UP, is_trial=1, target_g1_name='高松宮記念'))
        # 10週
        races.append(Race(name='フィリーズレビュー', track_id='A', month=3, week=10, grade=RaceGrade.G2, surface=RaceSurface.TURF, distance=1400, age_restriction=AgeRestriction.THREE_YO, sex_restriction=SexRestriction.FILLY_MARE, is_trial=1, target_g1_name='桜花賞'))
        races.append(Race(name='金鯱賞', track_id='D', month=3, week=10, grade=RaceGrade.G2, surface=RaceSurface.TURF, distance=2000, age_restriction=AgeRestriction.FOUR_YO_UP, is_trial=1, target_g1_name='大阪杯'))
        races.append(Race(name='ファルコンS', track_id='D', month=3, week=10, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=1400, age_restriction=AgeRestriction.THREE_YO))
        # 11週
        races.append(Race(name='スプリングS', track_id='C', month=3, week=11, grade=RaceGrade.G2, surface=RaceSurface.TURF, distance=1800, age_restriction=AgeRestriction.THREE_YO, sex_restriction=SexRestriction.COLT_HORSE, is_trial=1, target_g1_name='皐月賞'))
        races.append(Race(name='阪神大賞典', track_id='A', month=3, week=11, grade=RaceGrade.G2, surface=RaceSurface.TURF, distance=3000, age_restriction=AgeRestriction.FOUR_YO_UP, is_trial=1, target_g1_name='天皇賞（春）'))
        races.append(Race(name='フラワーC', track_id='C', month=3, week=11, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=1800, age_restriction=AgeRestriction.THREE_YO, sex_restriction=SexRestriction.FILLY_MARE))
        races.append(Race(name='京浜盃', track_id='C', month=3, week=11, grade=RaceGrade.G3, surface=RaceSurface.DIRT, distance=1700, age_restriction=AgeRestriction.THREE_YO, is_trial=1, target_g1_name='羽田盃'))
        # 12週
        races.append(Race(name='高松宮記念', track_id='D', month=3, week=12, grade=RaceGrade.G1, surface=RaceSurface.TURF, distance=1200, age_restriction=AgeRestriction.FOUR_YO_UP, base_prize=170_000_000))
        races.append(Race(name='日経賞', track_id='C', month=3, week=12, grade=RaceGrade.G2, surface=RaceSurface.TURF, distance=2500, age_restriction=AgeRestriction.FOUR_YO_UP, is_trial=1, target_g1_name='天皇賞（春）'))
        races.append(Race(name='毎日杯', track_id='A', month=3, week=12, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=1800, age_restriction=AgeRestriction.THREE_YO))
        races.append(Race(name='ダービー卿チャレンジT', track_id='C', month=3, week=12, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=1600, age_restriction=AgeRestriction.FOUR_YO_UP))

        # --- 4月 (第13週〜第16週) ---
        # 13週
        races.append(Race(name='大阪杯', track_id='A', month=4, week=13, grade=RaceGrade.G1, surface=RaceSurface.TURF, distance=2000, age_restriction=AgeRestriction.FOUR_YO_UP, base_prize=200_000_000))
        races.append(Race(name='ダービー卿CT', track_id='C', month=4, week=13, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=1600, age_restriction=AgeRestriction.FOUR_YO_UP))
        # 14週: 桜花賞 ＆ NZT(NHKマイルC前哨戦)
        races.append(Race(name='桜花賞', track_id='A', month=4, week=14, grade=RaceGrade.G1, surface=RaceSurface.TURF, distance=1600, age_restriction=AgeRestriction.THREE_YO, sex_restriction=SexRestriction.FILLY_MARE, base_prize=140_000_000))
        races.append(Race(name='ニュージーランドトロフィー', track_id='C', month=4, week=14, grade=RaceGrade.G2, surface=RaceSurface.TURF, distance=1600, age_restriction=AgeRestriction.THREE_YO, is_trial=1, target_g1_name='NHKマイルカップ'))
        races.append(Race(name='阪神牝馬S', track_id='A', month=4, week=14, grade=RaceGrade.G2, surface=RaceSurface.TURF, distance=1600, age_restriction=AgeRestriction.FOUR_YO_UP, sex_restriction=SexRestriction.FILLY_MARE))
        # 15週: 皐月賞 ＆ アーリントンC(NHKマイルC前哨戦)
        races.append(Race(name='皐月賞', track_id='C', month=4, week=15, grade=RaceGrade.G1, surface=RaceSurface.TURF, distance=2000, age_restriction=AgeRestriction.THREE_YO, sex_restriction=SexRestriction.COLT_HORSE, base_prize=150_000_000))
        races.append(Race(name='アーリントンカップ', track_id='A', month=4, week=15, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=1600, age_restriction=AgeRestriction.THREE_YO, is_trial=1, target_g1_name='NHKマイルカップ'))
        races.append(Race(name='アンタレスS', track_id='A', month=4, week=15, grade=RaceGrade.G3, surface=RaceSurface.DIRT, distance=1800, age_restriction=AgeRestriction.FOUR_YO_UP))
        # 16週: ダート第1冠 羽田盃 ＆ 青葉賞・フローラS
        races.append(Race(name='青葉賞', track_id='B', month=4, week=16, grade=RaceGrade.G2, surface=RaceSurface.TURF, distance=2400, age_restriction=AgeRestriction.THREE_YO, sex_restriction=SexRestriction.COLT_HORSE, is_trial=1, target_g1_name='日本ダービー'))
        races.append(Race(name='フローラS', track_id='B', month=4, week=16, grade=RaceGrade.G2, surface=RaceSurface.TURF, distance=2000, age_restriction=AgeRestriction.THREE_YO, sex_restriction=SexRestriction.FILLY_MARE, is_trial=1, target_g1_name='オークス'))
        races.append(Race(name='マイラーズC', track_id='A', month=4, week=16, grade=RaceGrade.G2, surface=RaceSurface.TURF, distance=1600, age_restriction=AgeRestriction.FOUR_YO_UP, is_trial=1, target_g1_name='安田記念'))
        races.append(Race(name='羽田盃', track_id='C', month=4, week=16, grade=RaceGrade.G1, surface=RaceSurface.DIRT, distance=1800, age_restriction=AgeRestriction.THREE_YO, base_prize=80_000_000))

        # --- 5月 (第17週〜第20週) ---
        # 17週: 天皇賞(春) ＆ かしわ記念
        races.append(Race(name='天皇賞（春）', track_id='A', month=5, week=17, grade=RaceGrade.G1, surface=RaceSurface.TURF, distance=3200, age_restriction=AgeRestriction.FOUR_YO_UP, base_prize=200_000_000))
        races.append(Race(name='かしわ記念', track_id='C', month=5, week=17, grade=RaceGrade.G1, surface=RaceSurface.DIRT, distance=1600, age_restriction=AgeRestriction.FOUR_YO_UP, base_prize=80_000_000))
        races.append(Race(name='ユニコーンS', track_id='A', month=5, week=17, grade=RaceGrade.G3, surface=RaceSurface.DIRT, distance=1800, age_restriction=AgeRestriction.THREE_YO, is_trial=1, target_g1_name='東京ダービー'))
        races.append(Race(name='新潟大賞典', track_id='B', month=5, week=17, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=2000, age_restriction=AgeRestriction.FOUR_YO_UP))
        # 18週: 新設 NHKマイルカップ
        races.append(Race(name='NHKマイルカップ', track_id='B', month=5, week=18, grade=RaceGrade.G1, surface=RaceSurface.TURF, distance=1600, age_restriction=AgeRestriction.THREE_YO, sex_restriction=SexRestriction.MIXED, base_prize=130_000_000))
        races.append(Race(name='京王杯スプリングC', track_id='B', month=5, week=18, grade=RaceGrade.G2, surface=RaceSurface.TURF, distance=1400, age_restriction=AgeRestriction.FOUR_YO_UP, is_trial=1, target_g1_name='安田記念'))
        races.append(Race(name='京都新聞杯', track_id='A', month=5, week=18, grade=RaceGrade.G2, surface=RaceSurface.TURF, distance=2200, age_restriction=AgeRestriction.THREE_YO))
        # 19週: オークス
        races.append(Race(name='オークス', track_id='B', month=5, week=19, grade=RaceGrade.G1, surface=RaceSurface.TURF, distance=2400, age_restriction=AgeRestriction.THREE_YO, sex_restriction=SexRestriction.FILLY_MARE, base_prize=150_000_000))
        races.append(Race(name='平安S', track_id='A', month=5, week=19, grade=RaceGrade.G3, surface=RaceSurface.DIRT, distance=1900, age_restriction=AgeRestriction.FOUR_YO_UP))
        # 20週: 日本ダービー
        races.append(Race(name='日本ダービー', track_id='B', month=5, week=20, grade=RaceGrade.G1, surface=RaceSurface.TURF, distance=2400, age_restriction=AgeRestriction.THREE_YO, sex_restriction=SexRestriction.COLT_HORSE, base_prize=200_000_000))
        races.append(Race(name='目黒記念', track_id='B', month=5, week=20, grade=RaceGrade.G2, surface=RaceSurface.TURF, distance=2500, age_restriction=AgeRestriction.FOUR_YO_UP))

        # --- 6月 (第21週〜第24週) ---
        # 21週
        races.append(Race(name='鳴尾記念', track_id='A', month=6, week=21, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=2000, age_restriction=AgeRestriction.THREE_YO_UP))
        # 22週: 安田記念 ＆ ダート第2冠 東京ダービー
        races.append(Race(name='安田記念', track_id='B', month=6, week=22, grade=RaceGrade.G1, surface=RaceSurface.TURF, distance=1600, age_restriction=AgeRestriction.THREE_YO_UP, base_prize=180_000_000))
        races.append(Race(name='東京ダービー', track_id='B', month=6, week=22, grade=RaceGrade.G1, surface=RaceSurface.DIRT, distance=2000, age_restriction=AgeRestriction.THREE_YO, base_prize=100_000_000))
        races.append(Race(name='エプソムC', track_id='B', month=6, week=22, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=1800, age_restriction=AgeRestriction.THREE_YO_UP))
        # 23週
        races.append(Race(name='函館スプリントS', track_id='D', month=6, week=23, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=1200, age_restriction=AgeRestriction.THREE_YO_UP))
        races.append(Race(name='マーメイドS', track_id='A', month=6, week=23, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=2000, age_restriction=AgeRestriction.THREE_YO_UP, sex_restriction=SexRestriction.FILLY_MARE))
        # 24週: 宝塚記念 ＆ 初夏ダート頂上決戦 帝王賞
        races.append(Race(name='宝塚記念', track_id='A', month=6, week=24, grade=RaceGrade.G1, surface=RaceSurface.TURF, distance=2200, age_restriction=AgeRestriction.THREE_YO_UP, base_prize=200_000_000))
        races.append(Race(name='帝王賞', track_id='B', month=6, week=24, grade=RaceGrade.G1, surface=RaceSurface.DIRT, distance=2000, age_restriction=AgeRestriction.FOUR_YO_UP, base_prize=120_000_000))

        # --- 7月 (第25週〜第28週) ---
        # 25週
        races.append(Race(name='ラジオNIKKEI賞', track_id='D', month=7, week=25, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=1800, age_restriction=AgeRestriction.THREE_YO))
        # 26週
        races.append(Race(name='七夕賞', track_id='D', month=7, week=26, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=2000, age_restriction=AgeRestriction.THREE_YO_UP))
        races.append(Race(name='プロキオンS', track_id='D', month=7, week=26, grade=RaceGrade.G3, surface=RaceSurface.DIRT, distance=1400, age_restriction=AgeRestriction.THREE_YO_UP))
        # 27週
        races.append(Race(name='函館記念', track_id='D', month=7, week=27, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=2000, age_restriction=AgeRestriction.THREE_YO_UP))
        # 28週: 3歳未勝利戦足切り週
        races.append(Race(name='中京記念', track_id='D', month=7, week=28, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=1600, age_restriction=AgeRestriction.THREE_YO_UP))

        # --- 8月 (第29週〜第32週) ---
        # 29週
        races.append(Race(name='アイビスサマーダッシュ', track_id='B', month=8, week=29, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=1000, age_restriction=AgeRestriction.THREE_YO_UP))
        races.append(Race(name='クイーンS', track_id='D', month=8, week=29, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=1800, age_restriction=AgeRestriction.THREE_YO_UP, sex_restriction=SexRestriction.FILLY_MARE))
        # 30週
        races.append(Race(name='小倉記念', track_id='D', month=8, week=30, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=2000, age_restriction=AgeRestriction.THREE_YO_UP))
        races.append(Race(name='エルムS', track_id='D', month=8, week=30, grade=RaceGrade.G3, surface=RaceSurface.DIRT, distance=1700, age_restriction=AgeRestriction.THREE_YO_UP))
        # 31週: 2歳重賞開幕 ＆ レパードS
        races.append(Race(name='関屋記念', track_id='B', month=8, week=31, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=1600, age_restriction=AgeRestriction.THREE_YO_UP))
        races.append(Race(name='新潟2歳S', track_id='B', month=8, week=31, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=1600, age_restriction=AgeRestriction.TWO_YO))
        races.append(Race(name='レパードS', track_id='D', month=8, week=31, grade=RaceGrade.G3, surface=RaceSurface.DIRT, distance=1800, age_restriction=AgeRestriction.THREE_YO, is_trial=1, target_g1_name='ジャパンダートクラシック'))
        # 32週
        races.append(Race(name='札幌記念', track_id='D', month=8, week=32, grade=RaceGrade.G2, surface=RaceSurface.TURF, distance=2000, age_restriction=AgeRestriction.THREE_YO_UP))
        races.append(Race(name='札幌2歳S', track_id='D', month=8, week=32, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=1800, age_restriction=AgeRestriction.TWO_YO))
        races.append(Race(name='キーンランドC', track_id='D', month=8, week=32, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=1200, age_restriction=AgeRestriction.THREE_YO_UP))

        # --- 9月 (第33週〜第36週) ---
        # 33週
        races.append(Race(name='新潟記念', track_id='B', month=9, week=33, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=2000, age_restriction=AgeRestriction.THREE_YO_UP))
        races.append(Race(name='小倉2歳S', track_id='D', month=9, week=33, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=1200, age_restriction=AgeRestriction.TWO_YO))
        # 34週: 秋華賞トライアル 紫苑S
        races.append(Race(name='紫苑S', track_id='C', month=9, week=34, grade=RaceGrade.G2, surface=RaceSurface.TURF, distance=2000, age_restriction=AgeRestriction.THREE_YO, sex_restriction=SexRestriction.FILLY_MARE, is_trial=1, target_g1_name='秋華賞'))
        races.append(Race(name='京成杯オータムH', track_id='C', month=9, week=34, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=1600, age_restriction=AgeRestriction.THREE_YO_UP))
        # 35週: 菊花賞・秋華賞トライアル
        races.append(Race(name='セントライト記念', track_id='C', month=9, week=35, grade=RaceGrade.G2, surface=RaceSurface.TURF, distance=2200, age_restriction=AgeRestriction.THREE_YO, sex_restriction=SexRestriction.COLT_HORSE, is_trial=1, target_g1_name='菊花賞'))
        races.append(Race(name='ローズS', track_id='A', month=9, week=35, grade=RaceGrade.G2, surface=RaceSurface.TURF, distance=1800, age_restriction=AgeRestriction.THREE_YO, sex_restriction=SexRestriction.FILLY_MARE, is_trial=1, target_g1_name='秋華賞'))
        # 36週: 神戸新聞杯 ＆ オールカマー
        races.append(Race(name='神戸新聞杯', track_id='A', month=9, week=36, grade=RaceGrade.G2, surface=RaceSurface.TURF, distance=2400, age_restriction=AgeRestriction.THREE_YO, sex_restriction=SexRestriction.COLT_HORSE, is_trial=1, target_g1_name='菊花賞'))
        races.append(Race(name='オールカマー', track_id='C', month=9, week=36, grade=RaceGrade.G2, surface=RaceSurface.TURF, distance=2200, age_restriction=AgeRestriction.THREE_YO_UP, is_trial=1, target_g1_name='天皇賞（秋）'))
        races.append(Race(name='シリウスS', track_id='A', month=9, week=36, grade=RaceGrade.G3, surface=RaceSurface.DIRT, distance=2000, age_restriction=AgeRestriction.THREE_YO_UP))

        # --- 10月 (第37週〜第40週) ---
        # 37週: スプリンターズS
        races.append(Race(name='スプリンターズS', track_id='C', month=10, week=37, grade=RaceGrade.G1, surface=RaceSurface.TURF, distance=1200, age_restriction=AgeRestriction.THREE_YO_UP, base_prize=170_000_000))
        races.append(Race(name='サウジアラビアRC', track_id='B', month=10, week=37, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=1600, age_restriction=AgeRestriction.TWO_YO))
        races.append(Race(name='毎日王冠', track_id='B', month=10, week=37, grade=RaceGrade.G2, surface=RaceSurface.TURF, distance=1800, age_restriction=AgeRestriction.THREE_YO_UP, is_trial=1, target_g1_name='天皇賞（秋）'))
        # 38週: ダート最終冠 ジャパンダートクラシック ＆ 京都大賞典
        races.append(Race(name='ジャパンダートクラシック', track_id='B', month=10, week=38, grade=RaceGrade.G1, surface=RaceSurface.DIRT, distance=2000, age_restriction=AgeRestriction.THREE_YO, base_prize=100_000_000))
        races.append(Race(name='京都大賞典', track_id='A', month=10, week=38, grade=RaceGrade.G2, surface=RaceSurface.TURF, distance=2400, age_restriction=AgeRestriction.THREE_YO_UP, is_trial=1, target_g1_name='ジャパンC'))
        # 39週: 牝馬三冠 秋華賞
        races.append(Race(name='秋華賞', track_id='A', month=10, week=39, grade=RaceGrade.G1, surface=RaceSurface.TURF, distance=2000, age_restriction=AgeRestriction.THREE_YO, sex_restriction=SexRestriction.FILLY_MARE, base_prize=140_000_000))
        races.append(Race(name='府中牝馬S', track_id='B', month=10, week=39, grade=RaceGrade.G2, surface=RaceSurface.TURF, distance=1800, age_restriction=AgeRestriction.THREE_YO_UP, sex_restriction=SexRestriction.FILLY_MARE, is_trial=1, target_g1_name='エリザベス女王杯'))
        races.append(Race(name='アルテミスS', track_id='B', month=10, week=39, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=1600, age_restriction=AgeRestriction.TWO_YO, sex_restriction=SexRestriction.FILLY_MARE))
        races.append(Race(name='エーデルワイス賞', track_id='D', month=10, week=39, grade=RaceGrade.G3, surface=RaceSurface.DIRT, distance=1200, age_restriction=AgeRestriction.TWO_YO, sex_restriction=SexRestriction.FILLY_MARE))
        # 40週: 牡馬三冠 菊花賞
        races.append(Race(name='菊花賞', track_id='A', month=10, week=40, grade=RaceGrade.G1, surface=RaceSurface.TURF, distance=3000, age_restriction=AgeRestriction.THREE_YO, sex_restriction=SexRestriction.COLT_HORSE, base_prize=180_000_000))
        races.append(Race(name='富士S', track_id='B', month=10, week=40, grade=RaceGrade.G2, surface=RaceSurface.TURF, distance=1600, age_restriction=AgeRestriction.THREE_YO_UP, is_trial=1, target_g1_name='マイルCS'))

        # --- 11月 (第41週〜第44週) ---
        # 41週: 天皇賞(秋)
        races.append(Race(name='天皇賞（秋）', track_id='B', month=11, week=41, grade=RaceGrade.G1, surface=RaceSurface.TURF, distance=2000, age_restriction=AgeRestriction.THREE_YO_UP, base_prize=200_000_000))
        races.append(Race(name='アルゼンチン共和国杯', track_id='B', month=11, week=41, grade=RaceGrade.G2, surface=RaceSurface.TURF, distance=2500, age_restriction=AgeRestriction.THREE_YO_UP, is_trial=1, target_g1_name='ジャパンC'))
        races.append(Race(name='みやこS', track_id='A', month=11, week=41, grade=RaceGrade.G3, surface=RaceSurface.DIRT, distance=1800, age_restriction=AgeRestriction.THREE_YO_UP, is_trial=1, target_g1_name='チャンピオンズC'))
        races.append(Race(name='ファンタジーS', track_id='A', month=11, week=41, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=1400, age_restriction=AgeRestriction.TWO_YO, sex_restriction=SexRestriction.FILLY_MARE))
        races.append(Race(name='京王杯2歳S', track_id='B', month=11, week=41, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=1400, age_restriction=AgeRestriction.TWO_YO))
        # 42週: エリザベス女王杯
        races.append(Race(name='エリザベス女王杯', track_id='A', month=11, week=42, grade=RaceGrade.G1, surface=RaceSurface.TURF, distance=2200, age_restriction=AgeRestriction.THREE_YO_UP, sex_restriction=SexRestriction.FILLY_MARE, base_prize=150_000_000))
        races.append(Race(name='武蔵野S', track_id='B', month=11, week=42, grade=RaceGrade.G3, surface=RaceSurface.DIRT, distance=1600, age_restriction=AgeRestriction.THREE_YO_UP, is_trial=1, target_g1_name='チャンピオンズC'))
        races.append(Race(name='デイリー杯2歳S', track_id='A', month=11, week=42, grade=RaceGrade.G2, surface=RaceSurface.TURF, distance=1600, age_restriction=AgeRestriction.TWO_YO))
        races.append(Race(name='福島記念', track_id='D', month=11, week=42, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=2000, age_restriction=AgeRestriction.THREE_YO_UP))
        # 43週: マイルチャンピオンシップ
        races.append(Race(name='マイルCS', track_id='A', month=11, week=43, grade=RaceGrade.G1, surface=RaceSurface.TURF, distance=1600, age_restriction=AgeRestriction.THREE_YO_UP, base_prize=180_000_000))
        races.append(Race(name='東京スポーツ杯2歳S', track_id='B', month=11, week=43, grade=RaceGrade.G2, surface=RaceSurface.TURF, distance=1800, age_restriction=AgeRestriction.TWO_YO))
        races.append(Race(name='兵庫ジュニアGP', track_id='D', month=11, week=43, grade=RaceGrade.G3, surface=RaceSurface.DIRT, distance=1400, age_restriction=AgeRestriction.TWO_YO))
        # 44週: ジャパンカップ
        races.append(Race(name='ジャパンC', track_id='B', month=11, week=44, grade=RaceGrade.G1, surface=RaceSurface.TURF, distance=2400, age_restriction=AgeRestriction.THREE_YO_UP, base_prize=300_000_000))
        races.append(Race(name='京都2歳S', track_id='A', month=11, week=44, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=2000, age_restriction=AgeRestriction.TWO_YO))
        races.append(Race(name='京阪杯', track_id='A', month=11, week=44, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=1200, age_restriction=AgeRestriction.THREE_YO_UP))

        # --- 12月 (第45週〜第48週) ---
        # 45週: チャンピオンズC
        races.append(Race(name='チャンピオンズC', track_id='D', month=12, week=45, grade=RaceGrade.G1, surface=RaceSurface.DIRT, distance=1800, age_restriction=AgeRestriction.THREE_YO_UP, base_prize=140_000_000))
        races.append(Race(name='ステイヤーズS', track_id='C', month=12, week=45, grade=RaceGrade.G2, surface=RaceSurface.TURF, distance=3600, age_restriction=AgeRestriction.THREE_YO_UP))
        races.append(Race(name='チャレンジC', track_id='A', month=12, week=45, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=2000, age_restriction=AgeRestriction.THREE_YO_UP))
        # 46週: 阪神ジュベナイルフィリーズ
        races.append(Race(name='阪神ジュベナイルフィリーズ', track_id='A', month=12, week=46, grade=RaceGrade.G1, surface=RaceSurface.TURF, distance=1600, age_restriction=AgeRestriction.TWO_YO, sex_restriction=SexRestriction.FILLY_MARE, base_prize=140_000_000))
        races.append(Race(name='中日新聞杯', track_id='D', month=12, week=46, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=2000, age_restriction=AgeRestriction.THREE_YO_UP))
        races.append(Race(name='カペラS', track_id='C', month=12, week=46, grade=RaceGrade.G3, surface=RaceSurface.DIRT, distance=1200, age_restriction=AgeRestriction.THREE_YO_UP))
        # 47週: 朝日杯FS ＆ 全日本2歳優駿
        races.append(Race(name='朝日杯フューチュリティS', track_id='A', month=12, week=47, grade=RaceGrade.G1, surface=RaceSurface.TURF, distance=1600, age_restriction=AgeRestriction.TWO_YO, sex_restriction=SexRestriction.COLT_HORSE, base_prize=140_000_000))
        races.append(Race(name='全日本2歳優駿', track_id='C', month=12, week=47, grade=RaceGrade.G1, surface=RaceSurface.DIRT, distance=1400, age_restriction=AgeRestriction.TWO_YO, base_prize=80_000_000))
        races.append(Race(name='ターコイズS', track_id='C', month=12, week=47, grade=RaceGrade.G3, surface=RaceSurface.TURF, distance=1600, age_restriction=AgeRestriction.THREE_YO_UP, sex_restriction=SexRestriction.FILLY_MARE))
        # 48週: 有馬記念 ＆ ホープフルS ＆ 東京大賞典
        races.append(Race(name='有馬記念', track_id='C', month=12, week=48, grade=RaceGrade.G1, surface=RaceSurface.TURF, distance=2500, age_restriction=AgeRestriction.THREE_YO_UP, base_prize=300_000_000))
        races.append(Race(name='ホープフルS', track_id='C', month=12, week=48, grade=RaceGrade.G1, surface=RaceSurface.TURF, distance=2000, age_restriction=AgeRestriction.TWO_YO, sex_restriction=SexRestriction.COLT_HORSE, base_prize=140_000_000))
        races.append(Race(name='東京大賞典', track_id='B', month=12, week=48, grade=RaceGrade.G1, surface=RaceSurface.DIRT, distance=2000, age_restriction=AgeRestriction.THREE_YO_UP, base_prize=150_000_000))
        races.append(Race(name='阪神C', track_id='A', month=12, week=48, grade=RaceGrade.G2, surface=RaceSurface.TURF, distance=1400, age_restriction=AgeRestriction.THREE_YO_UP))

        # =========================================================================
        # 2. 実在オープン特別 (OP/L) ＆ 3勝クラス (実在名称)
        # =========================================================================
        # 各週1レースのオープン特別
        op_race_names = [
            # 1月
            (1, 'ジュニアカップ', 'C', RaceSurface.TURF, 1600, AgeRestriction.THREE_YO),
            (2, '紅梅ステークス', 'A', RaceSurface.TURF, 1400, AgeRestriction.THREE_YO),
            (3, '白富士ステークス', 'B', RaceSurface.TURF, 2000, AgeRestriction.FOUR_YO_UP),
            (4, 'ポラリスステークス', 'A', RaceSurface.DIRT, 1400, AgeRestriction.FOUR_YO_UP),
            # 2月
            (5, 'クロッカスステークス', 'B', RaceSurface.TURF, 1400, AgeRestriction.THREE_YO),
            (6, '洛陽ステークス', 'A', RaceSurface.TURF, 1600, AgeRestriction.FOUR_YO_UP),
            (7, 'ヒヤシンスステークス', 'B', RaceSurface.DIRT, 1600, AgeRestriction.THREE_YO),
            (8, '仁川ステークス', 'A', RaceSurface.DIRT, 2000, AgeRestriction.FOUR_YO_UP),
            # 3月
            (9, '総武ステークス', 'C', RaceSurface.DIRT, 1800, AgeRestriction.FOUR_YO_UP),
            (10, '東風ステークス', 'C', RaceSurface.TURF, 1600, AgeRestriction.FOUR_YO_UP),
            (11, '若葉ステークス', 'A', RaceSurface.TURF, 2000, AgeRestriction.THREE_YO),
            (12, '六甲ステークス', 'A', RaceSurface.TURF, 1600, AgeRestriction.FOUR_YO_UP),
            # 4月
            (13, '大阪城ステークス', 'A', RaceSurface.TURF, 1800, AgeRestriction.FOUR_YO_UP),
            (14, '吾妻小富士賞', 'D', RaceSurface.DIRT, 1700, AgeRestriction.FOUR_YO_UP),
            (15, 'オアシスステークス', 'B', RaceSurface.DIRT, 1600, AgeRestriction.FOUR_YO_UP),
            (16, 'プリンシパルステークス', 'B', RaceSurface.TURF, 2000, AgeRestriction.THREE_YO),
            # 5月
            (17, 'スイートピーステークス', 'B', RaceSurface.TURF, 1800, AgeRestriction.THREE_YO),
            (18, '都大路ステークス', 'A', RaceSurface.TURF, 1800, AgeRestriction.FOUR_YO_UP),
            (19, 'メイステークス', 'B', RaceSurface.TURF, 1800, AgeRestriction.FOUR_YO_UP),
            (20, '欅ステークス', 'B', RaceSurface.DIRT, 1400, AgeRestriction.FOUR_YO_UP),
            # 6月
            (21, '米子ステークス', 'A', RaceSurface.TURF, 1600, AgeRestriction.THREE_YO_UP),
            (22, '天保山ステークス', 'A', RaceSurface.DIRT, 1400, AgeRestriction.THREE_YO_UP),
            (23, 'パラダイスステークス', 'B', RaceSurface.TURF, 1400, AgeRestriction.THREE_YO_UP),
            (24, '大沼ステークス', 'D', RaceSurface.DIRT, 1700, AgeRestriction.THREE_YO_UP),
            # 7月
            (25, '巴賞', 'D', RaceSurface.TURF, 1800, AgeRestriction.THREE_YO_UP),
            (26, '名鉄杯', 'D', RaceSurface.DIRT, 1800, AgeRestriction.THREE_YO_UP),
            (27, 'ジュライステークス', 'D', RaceSurface.DIRT, 1800, AgeRestriction.THREE_YO_UP),
            (28, '関越ステークス', 'B', RaceSurface.TURF, 1800, AgeRestriction.THREE_YO_UP),
            # 8月
            (29, 'エルムステークス前哨戦', 'D', RaceSurface.DIRT, 1700, AgeRestriction.THREE_YO_UP),
            (30, 'BSN賞', 'B', RaceSurface.DIRT, 1800, AgeRestriction.THREE_YO_UP),
            (31, '朱鷺ステークス', 'B', RaceSurface.TURF, 1400, AgeRestriction.THREE_YO_UP),
            (32, '丹頂ステークス', 'D', RaceSurface.TURF, 2600, AgeRestriction.THREE_YO_UP),
            # 9月
            (33, 'エニフステークス', 'A', RaceSurface.DIRT, 1400, AgeRestriction.THREE_YO_UP),
            (34, 'ラジオ日本賞', 'C', RaceSurface.DIRT, 1800, AgeRestriction.THREE_YO_UP),
            (35, 'ケフェウスステークス', 'A', RaceSurface.TURF, 2000, AgeRestriction.THREE_YO_UP),
            (36, 'ポートアイランドS', 'A', RaceSurface.TURF, 1600, AgeRestriction.THREE_YO_UP),
            # 10月
            (37, 'グリーンチャンネルC', 'B', RaceSurface.DIRT, 1600, AgeRestriction.THREE_YO_UP),
            (38, 'オパールステークス', 'A', RaceSurface.TURF, 1200, AgeRestriction.THREE_YO_UP),
            (39, 'ブラジルカップ', 'B', RaceSurface.DIRT, 2100, AgeRestriction.THREE_YO_UP),
            (40, 'カシオペアステークス', 'A', RaceSurface.TURF, 1800, AgeRestriction.THREE_YO_UP),
            # 11月
            (41, 'ルミエールオータムD', 'B', RaceSurface.TURF, 1000, AgeRestriction.THREE_YO_UP),
            (42, 'オーロカップ', 'B', RaceSurface.TURF, 1400, AgeRestriction.THREE_YO_UP),
            (43, 'アンドロメダステークス', 'A', RaceSurface.TURF, 2000, AgeRestriction.THREE_YO_UP),
            (44, 'キャピタルステークス', 'B', RaceSurface.TURF, 1600, AgeRestriction.THREE_YO_UP),
            # 12月
            (45, '師走ステークス', 'C', RaceSurface.DIRT, 1800, AgeRestriction.THREE_YO_UP),
            (46, 'リゲルステークス', 'A', RaceSurface.TURF, 1600, AgeRestriction.THREE_YO_UP),
            (47, 'ディセンバーステークス', 'C', RaceSurface.TURF, 1800, AgeRestriction.THREE_YO_UP),
            (48, 'ベテルギウスステークス', 'A', RaceSurface.DIRT, 1800, AgeRestriction.THREE_YO_UP),
        ]

        for w, name, trk, surf, dist, age_r in op_race_names:
            m = (w - 1) // 4 + 1
            is_tr = 1 if '若葉' in name or 'プリンシパル' in name or 'スイートピー' in name else 0
            tg1 = '日本ダービー' if 'プリンシパル' in name else ('オークス' if 'スイートピー' in name else ('皐月賞' if '若葉' in name else None))
            races.append(Race(name=name, track_id=trk, month=m, week=w, grade=RaceGrade.OP, surface=surf, distance=dist, age_restriction=age_r, is_trial=is_tr, target_g1_name=tg1))

        # 実在3勝クラス（1600万下）レース名
        cond3_names = [
            '初富士S', '初春S', '節分S', '飛鳥S', '雲雀S', 'アクアマリンS', '甲南S', '春風S',
            '美浦S', '心斎橋S', 'サンシャインS', '錦S', 'むらさき賞', '烏丸S', '緑風S', '安土城S',
            '垂水S', '夏至S', '甲東特別', '天の川S', '佐渡S', '博多S', '日本海S', '長篠S',
            'レインボーS', 'ムーンライトH', '白秋S', 'トルマリンS', '魚沼S', '紅葉S', 'ユートピアS', '奥羽S',
            'ノベンバーS', '清水S', '市川S', '御影S', '元町S', '逆瀬川S', 'クリスマスC', 'サンタクロースH'
        ]

        # =========================================================================
        # 3. 条件戦 (3勝・2勝・1勝クラス) ＆ 新馬・未勝利戦の均等バランス配置
        # =========================================================================
        # 年間約420レースになるよう、各週の条件戦・新馬・未勝利を均等配置
        for w in range(1, 49):
            m = (w - 1) // 4 + 1
            age_cond = AgeRestriction.FOUR_YO_UP if w <= 20 else AgeRestriction.THREE_YO_UP

            # 3勝クラス (実在名称)
            c3_name = cond3_names[(w - 1) % len(cond3_names)]
            c3_surf = RaceSurface.TURF if w % 3 != 0 else RaceSurface.DIRT
            c3_dist = 1800 if w % 2 == 1 else (2000 if c3_surf == RaceSurface.TURF else 1400)
            races.append(Race(name=f'{c3_name}(3勝C)', track_id='B' if w % 2 == 1 else 'A', month=m, week=w, grade=RaceGrade.COND_3W, surface=c3_surf, distance=c3_dist, age_restriction=age_cond))

            # 2勝クラス (1000万下)
            c2_surf = RaceSurface.DIRT if w % 2 == 1 else RaceSurface.TURF
            c2_dist = 1600 if c2_surf == RaceSurface.TURF else 1800
            races.append(Race(name=f'2勝クラス({c2_surf.value}・{c2_dist}m)', track_id='C' if w % 2 == 1 else 'D', month=m, week=w, grade=RaceGrade.COND_2W, surface=c2_surf, distance=c2_dist, age_restriction=age_cond))

            # 1勝クラス (500万下: 芝 & ダート)
            races.append(Race(name=f'1勝クラス(芝・{1400 if w % 2 == 1 else 2000}m)', track_id='A' if w % 2 == 1 else 'B', month=m, week=w, grade=RaceGrade.COND_1W, surface=RaceSurface.TURF, distance=1400 if w % 2 == 1 else 2000, age_restriction=age_cond))
            races.append(Race(name=f'1勝クラス(ダ・{1800 if w % 2 == 1 else 1200}m)', track_id='C' if w % 2 == 1 else 'D', month=m, week=w, grade=RaceGrade.COND_1W, surface=RaceSurface.DIRT, distance=1800 if w % 2 == 1 else 1200, age_restriction=age_cond))

            # 3歳未勝利戦 (1月〜9月第28週まで)
            if w <= 28:
                races.append(Race(name=f'3歳未勝利(芝・{1600 if w % 2 == 1 else 2000}m)', track_id='A' if w % 2 == 1 else 'C', month=m, week=w, grade=RaceGrade.MAIDEN, surface=RaceSurface.TURF, distance=1600 if w % 2 == 1 else 2000, age_restriction=AgeRestriction.THREE_YO))
                races.append(Race(name=f'3歳未勝利(ダ・{1400 if w % 2 == 1 else 1800}m)', track_id='C' if w % 2 == 1 else 'D', month=m, week=w, grade=RaceGrade.MAIDEN, surface=RaceSurface.DIRT, distance=1400 if w % 2 == 1 else 1800, age_restriction=AgeRestriction.THREE_YO))

            # 2歳新馬戦 ＆ 2歳未勝利戦 (6月第21週〜12月第48週)
            if w >= 21:
                # 2歳新馬 (牡馬/牝馬分離)
                races.append(Race(name=f'2歳新馬(芝・{1600 if w % 2 == 1 else 1400}m)', track_id='B' if w % 2 == 1 else 'A', month=m, week=w, grade=RaceGrade.NEWCOMER, surface=RaceSurface.TURF, distance=1600 if w % 2 == 1 else 1400, age_restriction=AgeRestriction.TWO_YO, sex_restriction=SexRestriction.COLT_HORSE if w % 2 == 1 else SexRestriction.FILLY_MARE))
                if w >= 25:
                    races.append(Race(name=f'2歳未勝利(芝・{1200 if w % 2 == 1 else 1800}m)', track_id='C' if w % 2 == 1 else 'D', month=m, week=w, grade=RaceGrade.MAIDEN, surface=RaceSurface.TURF, distance=1200 if w % 2 == 1 else 1800, age_restriction=AgeRestriction.TWO_YO))
                if w >= 33:
                    races.append(Race(name=f'2歳未勝利(ダ・1400m)', track_id='D', month=m, week=w, grade=RaceGrade.MAIDEN, surface=RaceSurface.DIRT, distance=1400, age_restriction=AgeRestriction.TWO_YO))

        # 賞金マッピング
        for r in races:
            r.year = year
            if r.base_prize == 0:
                prizes = GRADE_PRIZE_MAP.get(r.grade, (10_000_000, 4_000_000))
                r.base_prize = prizes[0]
                r.condition_prize = prizes[1]

        return races

    def register_annual_program(self, year: int = 1) -> int:
        """年間番組表をDBへ登録"""
        races = self.generate_annual_program(year=year)
        with self.db.session() as conn:
            conn.execute("DELETE FROM results WHERE race_id IN (SELECT race_id FROM races WHERE year = ?)", (year,))
            conn.execute("DELETE FROM races WHERE year = ?", (year,))
            for r in races:
                conn.execute(
                    """
                    INSERT INTO races (
                        year, month, week, track_id, name, grade, surface, distance,
                        age_restriction, sex_restriction, condition, full_gate,
                        is_trial, target_g1_name, base_prize, condition_prize
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        r.year, r.month, r.week, r.track_id, r.name, r.grade.value,
                        r.surface.value, r.distance, r.age_restriction.value,
                        r.sex_restriction.value, r.condition, r.full_gate,
                        r.is_trial, r.target_g1_name, r.base_prize, r.condition_prize,
                    ),
                )
        return len(races)
