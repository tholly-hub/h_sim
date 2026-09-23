"""
年間レース番組表定義モジュール (Annual Race Program)
- 年間48週 (12ヶ月 × 4週) の全レース体系 (約1,070レース)
- JRA 8場 ＋ 地方 4場（大井・川崎・船橋・盛岡）の12競馬場開催
- 2歳戦線、3歳クラシック・ダート三冠戦線、古馬王道路線
- 冠名付きリステッド・3勝クラス、1000mおよび2400〜3600m番組、牝馬限定戦
- 1レース8頭限定フルゲート
"""

from __future__ import annotations

from collections import Counter
from typing import Dict, List, Optional, Tuple

from src.models.race import AgeRestriction, Race, RaceGrade, RaceSurface, SexRestriction
from src.race.track import TRACK_CONFIGS

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

COND3_TITLES = [
    '初富士S', '初春S', '節分S', '飛鳥S', '雲雀S', 'アクアマリンS', '甲南S', '春風S',
    '美浦S', '心斎橋S', 'サンシャインS', '錦S', 'むらさき賞', '烏丸S', '緑風S', '安土城S',
    '垂水S', '夏至S', '甲東特別', '天の川S', '佐渡S', '博多S', '日本海S', '長篠S',
    'レインボーS', 'ムーンライトH', '白秋S', 'トルマリンS', '魚沼S', '紅葉S', 'ユートピアS', '奥羽S',
    'ノベンバーS', '清水S', '市川S', '御影S', '元町S', '逆瀬川S', 'クリスマスC', 'サンタクロースH',
    '斑鳩S', 'うずしおS', '潮騒特別', '下鴨S', '釜山S', '納屋橋S', '関ヶ原S', '秋嶺S'
]

LISTED_TITLES = [
    (1, 'ジュニアカップ', 'NAKAYAMA', RaceSurface.TURF, 1600, AgeRestriction.THREE_YO, SexRestriction.MIXED, False, None),
    (2, 'ニューイヤーS', 'NAKAYAMA', RaceSurface.TURF, 1600, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, False, None),
    (3, '紅梅ステークス', 'CHUKYO', RaceSurface.TURF, 1400, AgeRestriction.THREE_YO, SexRestriction.FILLY_MARE, False, None),
    (4, '白富士ステークス', 'TOKYO', RaceSurface.TURF, 2000, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, False, None),
    (5, '洛陽ステークス', 'HANSHIN', RaceSurface.TURF, 1600, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, False, None),
    (6, 'ヒヤシンスS', 'TOKYO', RaceSurface.DIRT, 1600, AgeRestriction.THREE_YO, SexRestriction.MIXED, False, None),
    (8, '仁川ステークス', 'HANSHIN', RaceSurface.DIRT, 2000, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, False, None),
    (9, '総武ステークス', 'NAKAYAMA', RaceSurface.DIRT, 1800, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, False, None),
    (9, 'アネモネS', 'NAKAYAMA', RaceSurface.TURF, 1600, AgeRestriction.THREE_YO, SexRestriction.FILLY_MARE, True, '桜花賞'),
    (10, '若葉ステークス', 'HANSHIN', RaceSurface.TURF, 2000, AgeRestriction.THREE_YO, SexRestriction.COLT_HORSE, True, '皐月賞'),
    (12, '六甲ステークス', 'HANSHIN', RaceSurface.TURF, 1600, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, False, None),
    (13, '春雷ステークス', 'NAKAYAMA', RaceSurface.TURF, 1200, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, False, None),
    (14, '福島民報杯', 'FUKUSHIMA', RaceSurface.TURF, 2000, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, False, None),
    (15, 'スイートピーS', 'TOKYO', RaceSurface.TURF, 1800, AgeRestriction.THREE_YO, SexRestriction.FILLY_MARE, True, 'オークス'),
    (16, 'オアシスS', 'TOKYO', RaceSurface.DIRT, 1600, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, False, None),
    (16, 'プリンシパルS', 'TOKYO', RaceSurface.TURF, 2000, AgeRestriction.THREE_YO, SexRestriction.COLT_HORSE, True, '日本ダービー'),
    (19, '都大路ステークス', 'KYOTO', RaceSurface.TURF, 1800, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, False, None),
    (20, 'メイステークス', 'TOKYO', RaceSurface.TURF, 1800, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, False, None),
    (21, '安土城ステークス', 'HANSHIN', RaceSurface.TURF, 1400, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, False, None),
    (22, '米子ステークス', 'HANSHIN', RaceSurface.TURF, 1600, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, False, None),
    (23, 'パラダイスS', 'TOKYO', RaceSurface.TURF, 1400, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, False, None),
    (24, '巴賞', 'HANSHIN', RaceSurface.TURF, 1800, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, False, None),
    (26, '福島テレビOP', 'FUKUSHIMA', RaceSurface.TURF, 1200, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, False, None),
    (27, 'マリーンステークス', 'KOKURA', RaceSurface.DIRT, 1700, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, False, None),
    (28, 'アイビスSD前哨戦', 'NIIGATA', RaceSurface.TURF, 1000, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, False, None),
    (30, '関屋記念直前OP', 'NIIGATA', RaceSurface.TURF, 1600, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, False, None),
    (32, '朱鷺ステークス', 'NIIGATA', RaceSurface.TURF, 1400, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, False, None),
    (34, 'エニフステークス', 'HANSHIN', RaceSurface.DIRT, 1400, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, False, None),
    (35, 'ラジオ日本賞', 'NAKAYAMA', RaceSurface.DIRT, 1800, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, False, None),
    (36, 'ポートアイランドS', 'HANSHIN', RaceSurface.TURF, 1600, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, False, None),
    (36, '芙蓉ステークス', 'NAKAYAMA', RaceSurface.TURF, 2000, AgeRestriction.TWO_YO, SexRestriction.MIXED, False, None),
    (37, 'オパールS', 'KYOTO', RaceSurface.TURF, 1200, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, False, None),
    (38, '信越ステークス', 'TOKYO', RaceSurface.TURF, 1400, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, False, None),
    (39, 'ブラジルカップ', 'TOKYO', RaceSurface.DIRT, 2100, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, False, None),
    (39, 'アイビーステークス', 'TOKYO', RaceSurface.TURF, 1800, AgeRestriction.TWO_YO, SexRestriction.MIXED, False, None),
    (40, 'カシオペアS', 'KYOTO', RaceSurface.TURF, 1800, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, False, None),
    (40, '萩ステークス', 'KYOTO', RaceSurface.TURF, 1800, AgeRestriction.TWO_YO, SexRestriction.MIXED, False, None),
    (41, 'カトレアステークス', 'TOKYO', RaceSurface.DIRT, 1600, AgeRestriction.TWO_YO, SexRestriction.MIXED, True, '全日本２歳優駿'),

    (41, 'ルミエールオータムD', 'TOKYO', RaceSurface.TURF, 1000, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, False, None),
    (42, 'オーロカップ', 'TOKYO', RaceSurface.TURF, 1400, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, False, None),
    (43, 'アンドロメダS', 'KYOTO', RaceSurface.TURF, 2000, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, False, None),
    (44, 'キャピタルS', 'TOKYO', RaceSurface.TURF, 1600, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, False, None),
    (45, '師走ステークス', 'NAKAYAMA', RaceSurface.DIRT, 1800, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, False, None),
    (46, 'リゲルステークス', 'HANSHIN', RaceSurface.TURF, 1600, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, False, None),
    (47, 'ディセンバーS', 'NAKAYAMA', RaceSurface.TURF, 1800, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, False, None),
    (48, 'ベテルギウスS', 'HANSHIN', RaceSurface.DIRT, 1800, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, False, None),
]

def generate_full_program(year: int = 1) -> List[Race]:
    # 週間開催競馬場ローテーション（2〜3場）
    weekly_tracks = {
        1: ['NAKAYAMA', 'CHUKYO', 'KOKURA'],
        2: ['NAKAYAMA', 'TOKYO', 'CHUKYO'],
        3: ['NAKAYAMA', 'CHUKYO', 'KOKURA'],
        4: ['NAKAYAMA', 'TOKYO', 'KAWASAKI'],
        5: ['TOKYO', 'HANSHIN', 'KOKURA'],
        6: ['TOKYO', 'HANSHIN', 'KOKURA'],
        7: ['TOKYO', 'HANSHIN', 'OI'],
        8: ['NAKAYAMA', 'HANSHIN', 'CHUKYO'],
        9: ['NAKAYAMA', 'HANSHIN', 'CHUKYO'],
        10: ['NAKAYAMA', 'HANSHIN', 'CHUKYO'],
        11: ['NAKAYAMA', 'HANSHIN', 'OI'],
        12: ['NAKAYAMA', 'HANSHIN', 'CHUKYO'],
        13: ['HANSHIN', 'NAKAYAMA', 'FUKUSHIMA'],
        14: ['HANSHIN', 'NAKAYAMA', 'FUKUSHIMA'],
        15: ['TOKYO', 'HANSHIN', 'NAKAYAMA'],
        16: ['TOKYO', 'KYOTO', 'OI'],
        17: ['KYOTO', 'TOKYO', 'FUNABASHI'],
        18: ['TOKYO', 'KYOTO', 'NIIGATA'],
        19: ['TOKYO', 'KYOTO', 'NIIGATA'],
        20: ['TOKYO', 'KYOTO', 'NIIGATA'],
        21: ['TOKYO', 'HANSHIN', 'OI'],
        22: ['TOKYO', 'HANSHIN', 'CHUKYO'],
        23: ['TOKYO', 'HANSHIN', 'CHUKYO'],
        24: ['HANSHIN', 'TOKYO', 'FUKUSHIMA'],
        25: ['FUKUSHIMA', 'KOKURA', 'CHUKYO'],
        26: ['FUKUSHIMA', 'KOKURA', 'CHUKYO'],
        27: ['NIIGATA', 'KOKURA', 'MORIOKA'],
        28: ['NIIGATA', 'KOKURA', 'MORIOKA'],
        29: ['NIIGATA', 'KOKURA', 'MORIOKA'],
        30: ['NIIGATA', 'KOKURA', 'MORIOKA'],
        31: ['NIIGATA', 'KOKURA', 'CHUKYO'],
        32: ['NIIGATA', 'KOKURA', 'CHUKYO'],
        33: ['NAKAYAMA', 'HANSHIN', 'MORIOKA'],
        34: ['NAKAYAMA', 'HANSHIN', 'NIIGATA'],
        35: ['NAKAYAMA', 'TOKYO', 'FUNABASHI'],
        36: ['NAKAYAMA', 'HANSHIN', 'CHUKYO'],
        37: ['TOKYO', 'KYOTO', 'MORIOKA'],
        38: ['TOKYO', 'KYOTO', 'OI'],
        39: ['TOKYO', 'KYOTO', 'NIIGATA'],
        40: ['TOKYO', 'KYOTO', 'NIIGATA'],
        41: ['TOKYO', 'KYOTO', 'OI'],
        42: ['KYOTO', 'TOKYO', 'FUKUSHIMA'],
        43: ['KYOTO', 'TOKYO', 'FUKUSHIMA'],
        44: ['TOKYO', 'KYOTO', 'CHUKYO'],
        45: ['CHUKYO', 'NAKAYAMA', 'HANSHIN'],
        46: ['HANSHIN', 'NAKAYAMA', 'KAWASAKI'],
        47: ['HANSHIN', 'NAKAYAMA', 'CHUKYO'],
        48: ['NAKAYAMA', 'HANSHIN', 'OI'],
    }

    races: List[Race] = []

    # 地方競馬場セット（芝コースなし、すべてダート）
    NAR_TRACKS = {'OI', 'KAWASAKI', 'FUNABASHI', 'MORIOKA'}

    def resolve_surface(track_id: str, surf: RaceSurface) -> RaceSurface:
        """地方競馬場の場合は強制的にダートを返す"""
        if track_id in NAR_TRACKS:
            return RaceSurface.DIRT
        return surf

    # 1. 重賞レース定義
    major_races = [
        # 1月
        (1, '中山金杯', 'NAKAYAMA', RaceGrade.G3, RaceSurface.TURF, 2000, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 0, None, 43_000_000),
        (1, '京都金杯', 'CHUKYO', RaceGrade.G3, RaceSurface.TURF, 1600, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 0, None, 43_000_000),
        (1, 'シンザン記念', 'CHUKYO', RaceGrade.G3, RaceSurface.TURF, 1600, AgeRestriction.THREE_YO, SexRestriction.MIXED, 0, None, 40_000_000),
        (2, 'フェアリーS', 'NAKAYAMA', RaceGrade.G3, RaceSurface.TURF, 1600, AgeRestriction.THREE_YO, SexRestriction.FILLY_MARE, 0, None, 38_000_000),
        (2, '京成杯', 'NAKAYAMA', RaceGrade.G3, RaceSurface.TURF, 2000, AgeRestriction.THREE_YO, SexRestriction.MIXED, 0, None, 40_000_000),
        (2, '東海S', 'CHUKYO', RaceGrade.G2, RaceSurface.DIRT, 1800, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 1, 'フェブラリーS', 55_000_000),
        (2, '根岸S', 'TOKYO', RaceGrade.G3, RaceSurface.DIRT, 1400, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 1, 'フェブラリーS', 40_000_000),
        (3, '日経新春杯', 'CHUKYO', RaceGrade.G2, RaceSurface.TURF, 2200, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 0, None, 57_000_000),
        (4, 'アメリカJCC', 'NAKAYAMA', RaceGrade.G2, RaceSurface.TURF, 2200, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 0, None, 62_000_000),
        (4, '川崎記念', 'KAWASAKI', RaceGrade.G1, RaceSurface.DIRT, 2100, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 0, None, 100_000_000),
        # 2月
        (5, '東京新聞杯', 'TOKYO', RaceGrade.G3, RaceSurface.TURF, 1600, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 0, None, 41_000_000),
        (5, 'きさらぎ賞', 'HANSHIN', RaceGrade.G3, RaceSurface.TURF, 1800, AgeRestriction.THREE_YO, SexRestriction.MIXED, 0, None, 40_000_000),
        (5, 'シルクロードS', 'HANSHIN', RaceGrade.G3, RaceSurface.TURF, 1200, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 1, '高松宮記念', 41_000_000),
        (6, '共同通信杯', 'TOKYO', RaceGrade.G3, RaceSurface.TURF, 1800, AgeRestriction.THREE_YO, SexRestriction.MIXED, 0, None, 40_000_000),
        (6, 'クイーンC', 'TOKYO', RaceGrade.G3, RaceSurface.TURF, 1600, AgeRestriction.THREE_YO, SexRestriction.FILLY_MARE, 0, None, 38_000_000),
        (6, '京都記念', 'HANSHIN', RaceGrade.G2, RaceSurface.TURF, 2200, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 0, None, 62_000_000),
        (7, 'フェブラリーS', 'TOKYO', RaceGrade.G1, RaceSurface.DIRT, 1600, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 0, None, 120_000_000),
        (7, '雲取賞', 'OI', RaceGrade.G3, RaceSurface.DIRT, 1800, AgeRestriction.THREE_YO, SexRestriction.MIXED, 1, '羽田盃', 35_000_000),
        (7, '小倉大賞典', 'HANSHIN', RaceGrade.G3, RaceSurface.TURF, 1800, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 0, None, 43_000_000),
        (7, '阪急杯', 'HANSHIN', RaceGrade.G3, RaceSurface.TURF, 1400, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 1, '高松宮記念', 43_000_000),
        (7, 'オーシャンS', 'TOKYO', RaceGrade.G3, RaceSurface.TURF, 1200, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 1, '高松宮記念', 43_000_000),
        (8, '中山記念', 'NAKAYAMA', RaceGrade.G2, RaceSurface.TURF, 1800, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 1, '大阪杯', 67_000_000),
        (8, '金鯱賞', 'CHUKYO', RaceGrade.G2, RaceSurface.TURF, 2000, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 1, '大阪杯', 67_000_000),
        # 3月
        (9, '弥生賞ディープ記念', 'NAKAYAMA', RaceGrade.G2, RaceSurface.TURF, 2000, AgeRestriction.THREE_YO, SexRestriction.COLT_HORSE, 1, '皐月賞', 54_000_000),
        (9, 'チューリップ賞', 'HANSHIN', RaceGrade.G2, RaceSurface.TURF, 1600, AgeRestriction.THREE_YO, SexRestriction.FILLY_MARE, 1, '桜花賞', 52_000_000),
        (9, 'フィリーズレビュー', 'HANSHIN', RaceGrade.G2, RaceSurface.TURF, 1400, AgeRestriction.THREE_YO, SexRestriction.FILLY_MARE, 1, '桜花賞', 52_000_000),
        (10, 'ファルコンS', 'CHUKYO', RaceGrade.G3, RaceSurface.TURF, 1400, AgeRestriction.THREE_YO, SexRestriction.MIXED, 0, None, 40_000_000),
        (10, 'スプリングS', 'NAKAYAMA', RaceGrade.G2, RaceSurface.TURF, 1800, AgeRestriction.THREE_YO, SexRestriction.COLT_HORSE, 1, '皐月賞', 54_000_000),
        (11, '阪神大賞典', 'HANSHIN', RaceGrade.G2, RaceSurface.TURF, 3000, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 1, '天皇賞（春）', 67_000_000),
        (11, '京浜盃', 'OI', RaceGrade.G2, RaceSurface.DIRT, 1700, AgeRestriction.THREE_YO, SexRestriction.MIXED, 1, '羽田盃', 40_000_000),
        (11, 'フラワーC', 'NAKAYAMA', RaceGrade.G3, RaceSurface.TURF, 1800, AgeRestriction.THREE_YO, SexRestriction.FILLY_MARE, 0, None, 38_000_000),
        (12, '高松宮記念', 'CHUKYO', RaceGrade.G1, RaceSurface.TURF, 1200, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 0, None, 170_000_000),
        (12, '日経賞', 'NAKAYAMA', RaceGrade.G2, RaceSurface.TURF, 2500, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 1, '天皇賞（春）', 67_000_000),
        (12, '毎日杯', 'HANSHIN', RaceGrade.G3, RaceSurface.TURF, 1800, AgeRestriction.THREE_YO, SexRestriction.MIXED, 0, None, 40_000_000),
        (12, 'ダービー卿CT', 'NAKAYAMA', RaceGrade.G3, RaceSurface.TURF, 1600, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 0, None, 41_000_000),
        # 4月
        (13, '大阪杯', 'HANSHIN', RaceGrade.G1, RaceSurface.TURF, 2000, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 0, None, 200_000_000),
        (13, '中山牝馬S', 'NAKAYAMA', RaceGrade.G3, RaceSurface.TURF, 1800, AgeRestriction.FOUR_YO_UP, SexRestriction.FILLY_MARE, 0, None, 38_000_000),
        (13, 'ニュージーランドT', 'NAKAYAMA', RaceGrade.G2, RaceSurface.TURF, 1600, AgeRestriction.THREE_YO, SexRestriction.MIXED, 1, 'NHKマイルカップ', 54_000_000),
        (13, 'アーリントンカップ', 'HANSHIN', RaceGrade.G3, RaceSurface.TURF, 1600, AgeRestriction.THREE_YO, SexRestriction.MIXED, 1, 'NHKマイルカップ', 40_000_000),
        (14, '桜花賞', 'HANSHIN', RaceGrade.G1, RaceSurface.TURF, 1600, AgeRestriction.THREE_YO, SexRestriction.FILLY_MARE, 0, None, 140_000_000),
        (14, '阪神牝馬S', 'HANSHIN', RaceGrade.G2, RaceSurface.TURF, 1600, AgeRestriction.FOUR_YO_UP, SexRestriction.FILLY_MARE, 1, 'ヴィクトリアマイル', 55_000_000),
        (15, '皐月賞', 'NAKAYAMA', RaceGrade.G1, RaceSurface.TURF, 2000, AgeRestriction.THREE_YO, SexRestriction.COLT_HORSE, 0, None, 200_000_000),
        (15, 'アンタレスS', 'HANSHIN', RaceGrade.G3, RaceSurface.DIRT, 1800, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 0, None, 40_000_000),
        (15, 'フローラS', 'TOKYO', RaceGrade.G2, RaceSurface.TURF, 2000, AgeRestriction.THREE_YO, SexRestriction.FILLY_MARE, 1, 'オークス', 52_000_000),
        (16, '青葉賞', 'TOKYO', RaceGrade.G2, RaceSurface.TURF, 2400, AgeRestriction.THREE_YO, SexRestriction.COLT_HORSE, 1, '日本ダービー', 54_000_000),
        (16, '京都新聞杯', 'KYOTO', RaceGrade.G2, RaceSurface.TURF, 2200, AgeRestriction.THREE_YO, SexRestriction.COLT_HORSE, 1, '日本ダービー', 54_000_000),
        (16, 'ユニコーンS', 'KYOTO', RaceGrade.G3, RaceSurface.DIRT, 1900, AgeRestriction.THREE_YO, SexRestriction.MIXED, 1, '東京ダービー', 40_000_000),
        (16, 'マイラーズC', 'KYOTO', RaceGrade.G2, RaceSurface.TURF, 1600, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 1, '安田記念', 59_000_000),
        (16, '羽田盃', 'OI', RaceGrade.G1, RaceSurface.DIRT, 1800, AgeRestriction.THREE_YO, SexRestriction.MIXED, 0, None, 80_000_000),
        # 5月
        (17, '天皇賞（春）', 'KYOTO', RaceGrade.G1, RaceSurface.TURF, 3200, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 0, None, 220_000_000),
        (17, 'かしわ記念', 'FUNABASHI', RaceGrade.G1, RaceSurface.DIRT, 1600, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 0, None, 80_000_000),
        (17, '京王杯スプリングC', 'TOKYO', RaceGrade.G2, RaceSurface.TURF, 1400, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 1, '安田記念', 59_000_000),
        (18, 'NHKマイルカップ', 'TOKYO', RaceGrade.G1, RaceSurface.TURF, 1600, AgeRestriction.THREE_YO, SexRestriction.MIXED, 0, None, 130_000_000),
        (18, '新潟大賞典', 'NIIGATA', RaceGrade.G3, RaceSurface.TURF, 2000, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 0, None, 43_000_000),
        (19, 'ヴィクトリアマイル', 'TOKYO', RaceGrade.G1, RaceSurface.TURF, 1600, AgeRestriction.FOUR_YO_UP, SexRestriction.FILLY_MARE, 0, None, 130_000_000),
        (19, '平安S', 'KYOTO', RaceGrade.G3, RaceSurface.DIRT, 1900, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 0, None, 40_000_000),
        (20, 'オークス', 'TOKYO', RaceGrade.G1, RaceSurface.TURF, 2400, AgeRestriction.THREE_YO, SexRestriction.FILLY_MARE, 0, None, 150_000_000),
        # 6月
        (21, '日本ダービー', 'TOKYO', RaceGrade.G1, RaceSurface.TURF, 2400, AgeRestriction.THREE_YO, SexRestriction.COLT_HORSE, 0, None, 300_000_000),
        (21, '東京ダービー', 'OI', RaceGrade.G1, RaceSurface.DIRT, 2000, AgeRestriction.THREE_YO, SexRestriction.MIXED, 0, None, 100_000_000),
        (21, '目黒記念', 'TOKYO', RaceGrade.G2, RaceSurface.TURF, 2500, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 0, None, 57_000_000),
        (21, '葵ステークス', 'HANSHIN', RaceGrade.G3, RaceSurface.TURF, 1200, AgeRestriction.THREE_YO, SexRestriction.MIXED, 0, None, 40_000_000),
        (22, '安田記念', 'TOKYO', RaceGrade.G1, RaceSurface.TURF, 1600, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 0, None, 180_000_000),
        (22, '鳴尾記念', 'HANSHIN', RaceGrade.G3, RaceSurface.TURF, 2000, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 0, None, 43_000_000),
        (23, 'エプソムC', 'TOKYO', RaceGrade.G3, RaceSurface.TURF, 1800, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 0, None, 43_000_000),
        (23, 'マーメイドS', 'HANSHIN', RaceGrade.G3, RaceSurface.TURF, 2000, AgeRestriction.FOUR_YO_UP, SexRestriction.FILLY_MARE, 0, None, 38_000_000),
        (24, '宝塚記念', 'HANSHIN', RaceGrade.G1, RaceSurface.TURF, 2200, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 220_000_000),
        # 7月
        (25, 'ラジオNIKKEI賞', 'FUKUSHIMA', RaceGrade.G3, RaceSurface.TURF, 1800, AgeRestriction.THREE_YO, SexRestriction.MIXED, 0, None, 40_000_000),
        (25, 'CBC賞', 'CHUKYO', RaceGrade.G3, RaceSurface.TURF, 1200, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 41_000_000),
        (26, '七夕賞', 'FUKUSHIMA', RaceGrade.G3, RaceSurface.TURF, 2000, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 43_000_000),
        (26, 'プロキオンS', 'KOKURA', RaceGrade.G3, RaceSurface.DIRT, 1700, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 40_000_000),
        (27, '小倉記念', 'KOKURA', RaceGrade.G3, RaceSurface.TURF, 2000, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 43_000_000),
        (28, 'アイビスサマーダッシュ', 'NIIGATA', RaceGrade.G3, RaceSurface.TURF, 1000, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 41_000_000),
        (28, 'クイーンS', 'NIIGATA', RaceGrade.G3, RaceSurface.TURF, 1800, AgeRestriction.THREE_YO_UP, SexRestriction.FILLY_MARE, 0, None, 38_000_000),
        # 8月
        (29, 'レパードS', 'NIIGATA', RaceGrade.G3, RaceSurface.DIRT, 1800, AgeRestriction.THREE_YO, SexRestriction.MIXED, 1, 'ジャパンダートクラシック', 40_000_000),
        (29, 'エルムS', 'NIIGATA', RaceGrade.G3, RaceSurface.DIRT, 1700, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 40_000_000),
        (30, '小倉記念', 'KOKURA', RaceGrade.G3, RaceSurface.TURF, 2000, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 43_000_000),
        (30, '関屋記念', 'NIIGATA', RaceGrade.G3, RaceSurface.TURF, 1600, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 41_000_000),
        (31, '北九州記念', 'KOKURA', RaceGrade.G3, RaceSurface.TURF, 1200, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 41_000_000),
        (31, '新潟2歳S', 'NIIGATA', RaceGrade.G3, RaceSurface.TURF, 1600, AgeRestriction.TWO_YO, SexRestriction.MIXED, 0, None, 31_000_000),
        (31, 'キーンランドC', 'NIIGATA', RaceGrade.G3, RaceSurface.TURF, 1200, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 1, 'スプリンターズS', 43_000_000),
        (32, '新潟記念', 'NIIGATA', RaceGrade.G3, RaceSurface.TURF, 2000, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 43_000_000),
        (32, '小倉2歳S', 'KOKURA', RaceGrade.G3, RaceSurface.TURF, 1200, AgeRestriction.TWO_YO, SexRestriction.MIXED, 0, None, 31_000_000),
        # 9月
        (33, '紫苑S', 'NAKAYAMA', RaceGrade.G2, RaceSurface.TURF, 2000, AgeRestriction.THREE_YO, SexRestriction.FILLY_MARE, 1, '秋華賞', 52_000_000),
        (33, 'ローズS', 'HANSHIN', RaceGrade.G2, RaceSurface.TURF, 1800, AgeRestriction.THREE_YO, SexRestriction.FILLY_MARE, 1, '秋華賞', 52_000_000),
        (33, '京成杯オータムH', 'NAKAYAMA', RaceGrade.G3, RaceSurface.TURF, 1600, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 41_000_000),
        (33, '不来方賞', 'MORIOKA', RaceGrade.G2, RaceSurface.DIRT, 2000, AgeRestriction.THREE_YO, SexRestriction.MIXED, 1, 'ジャパンダートクラシック', 40_000_000),
        (34, 'セントライト記念', 'NAKAYAMA', RaceGrade.G2, RaceSurface.TURF, 2200, AgeRestriction.THREE_YO, SexRestriction.COLT_HORSE, 1, '菊花賞', 54_000_000),
        (34, '神戸新聞杯', 'HANSHIN', RaceGrade.G2, RaceSurface.TURF, 2400, AgeRestriction.THREE_YO, SexRestriction.COLT_HORSE, 1, '菊花賞', 54_000_000),
        (35, 'オールカマー', 'NAKAYAMA', RaceGrade.G2, RaceSurface.TURF, 2200, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 1, '天皇賞（秋）', 67_000_000),
        (35, '毎日王冠', 'TOKYO', RaceGrade.G2, RaceSurface.TURF, 1800, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 1, '天皇賞（秋）', 67_000_000),
        (35, '日本テレビ盃', 'FUNABASHI', RaceGrade.G2, RaceSurface.DIRT, 1800, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 1, 'JBCクラシック', 40_000_000),
        (36, 'スプリンターズS', 'NAKAYAMA', RaceGrade.G1, RaceSurface.TURF, 1200, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 170_000_000),
        (36, 'シリウスS', 'HANSHIN', RaceGrade.G3, RaceSurface.DIRT, 2000, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 40_000_000),
        # 10月
        (37, '京都大賞典', 'KYOTO', RaceGrade.G2, RaceSurface.TURF, 2400, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 1, 'ジャパンカップ', 67_000_000),
        (37, '府中牝馬S', 'TOKYO', RaceGrade.G2, RaceSurface.TURF, 1800, AgeRestriction.THREE_YO_UP, SexRestriction.FILLY_MARE, 1, 'エリザベス女王杯', 55_000_000),
        (37, 'サウジアラビアRC', 'TOKYO', RaceGrade.G3, RaceSurface.TURF, 1600, AgeRestriction.TWO_YO, SexRestriction.MIXED, 0, None, 33_000_000),
        (37, 'マイルCS南部杯', 'MORIOKA', RaceGrade.G1, RaceSurface.DIRT, 1600, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 80_000_000),
        (38, '秋華賞', 'KYOTO', RaceGrade.G1, RaceSurface.TURF, 2000, AgeRestriction.THREE_YO, SexRestriction.FILLY_MARE, 0, None, 110_000_000),
        (38, 'ジャパンダートクラシック', 'OI', RaceGrade.G1, RaceSurface.DIRT, 2000, AgeRestriction.THREE_YO, SexRestriction.MIXED, 0, None, 100_000_000),
        (38, '富士S', 'TOKYO', RaceGrade.G2, RaceSurface.TURF, 1600, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 1, 'マイルチャンピオンシップ', 59_000_000),
        (38, 'スワンS', 'KYOTO', RaceGrade.G2, RaceSurface.TURF, 1400, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 1, 'マイルチャンピオンシップ', 59_000_000),
        (39, '菊花賞', 'KYOTO', RaceGrade.G1, RaceSurface.TURF, 3000, AgeRestriction.THREE_YO, SexRestriction.COLT_HORSE, 0, None, 200_000_000),
        (40, '天皇賞（秋）', 'TOKYO', RaceGrade.G1, RaceSurface.TURF, 2000, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 220_000_000),
        (40, '武蔵野S', 'TOKYO', RaceGrade.G3, RaceSurface.DIRT, 1600, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 1, 'チャンピオンズカップ', 40_000_000),
        (40, 'みやこS', 'KYOTO', RaceGrade.G3, RaceSurface.DIRT, 1800, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 1, 'チャンピオンズカップ', 40_000_000),
        (40, 'アルテミスS', 'TOKYO', RaceGrade.G3, RaceSurface.TURF, 1600, AgeRestriction.TWO_YO, SexRestriction.FILLY_MARE, 1, '阪神ジュベナイルフィリーズ', 31_000_000),
        # 11月
        (41, 'JBCクラシック', 'OI', RaceGrade.G1, RaceSurface.DIRT, 2000, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 100_000_000),
        (41, 'JBCスプリント', 'OI', RaceGrade.G1, RaceSurface.DIRT, 1200, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 80_000_000),
        (41, 'JBC2歳優駿', 'OI', RaceGrade.G3, RaceSurface.DIRT, 1800, AgeRestriction.TWO_YO, SexRestriction.MIXED, 1, '全日本２歳優駿', 35_000_000),
        (41, '兵庫ジュニアグランプリ', 'OI', RaceGrade.G2, RaceSurface.DIRT, 1400, AgeRestriction.TWO_YO, SexRestriction.MIXED, 1, '全日本２歳優駿', 40_000_000),
        (41, '京王杯2歳S', 'TOKYO', RaceGrade.G2, RaceSurface.TURF, 1400, AgeRestriction.TWO_YO, SexRestriction.COLT_HORSE, 1, '朝日杯フューチュリティS', 38_000_000),
        (41, 'ファンタジーS', 'KYOTO', RaceGrade.G3, RaceSurface.TURF, 1400, AgeRestriction.TWO_YO, SexRestriction.FILLY_MARE, 1, '阪神ジュベナイルフィリーズ', 31_000_000),
        (42, 'エリザベス女王杯', 'KYOTO', RaceGrade.G1, RaceSurface.TURF, 2200, AgeRestriction.THREE_YO_UP, SexRestriction.FILLY_MARE, 0, None, 140_000_000),
        (42, 'デイリー杯2歳S', 'KYOTO', RaceGrade.G2, RaceSurface.TURF, 1600, AgeRestriction.TWO_YO, SexRestriction.COLT_HORSE, 1, '朝日杯フューチュリティS', 38_000_000),
        (42, '福島記念', 'FUKUSHIMA', RaceGrade.G3, RaceSurface.TURF, 2000, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 43_000_000),
        (43, 'マイルチャンピオンシップ', 'KYOTO', RaceGrade.G1, RaceSurface.TURF, 1600, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 180_000_000),
        (43, '東京スポーツ杯2歳S', 'TOKYO', RaceGrade.G2, RaceSurface.TURF, 1800, AgeRestriction.TWO_YO, SexRestriction.MIXED, 1, 'ホープフルS', 38_000_000),
        (43, '京都2歳S', 'KYOTO', RaceGrade.G3, RaceSurface.TURF, 2000, AgeRestriction.TWO_YO, SexRestriction.MIXED, 1, 'ホープフルS', 33_000_000),
        (44, 'ジャパンカップ', 'TOKYO', RaceGrade.G1, RaceSurface.TURF, 2400, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 500_000_000),
        (44, '京阪杯', 'KYOTO', RaceGrade.G3, RaceSurface.TURF, 1200, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 41_000_000),
        # 12月
        (45, 'チャンピオンズカップ', 'CHUKYO', RaceGrade.G1, RaceSurface.DIRT, 1800, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 120_000_000),
        (45, 'ステイヤーズS', 'NAKAYAMA', RaceGrade.G2, RaceSurface.TURF, 3600, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 62_000_000),
        (45, 'チャレンジカップ', 'HANSHIN', RaceGrade.G3, RaceSurface.TURF, 2000, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 43_000_000),
        (46, '阪神ジュベナイルフィリーズ', 'HANSHIN', RaceGrade.G1, RaceSurface.TURF, 1600, AgeRestriction.TWO_YO, SexRestriction.FILLY_MARE, 0, None, 65_000_000),
        (46, '全日本２歳優駿', 'KAWASAKI', RaceGrade.G1, RaceSurface.DIRT, 1600, AgeRestriction.TWO_YO, SexRestriction.MIXED, 0, None, 42_000_000),
        (46, 'カペラS', 'NAKAYAMA', RaceGrade.G3, RaceSurface.DIRT, 1200, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 38_000_000),
        (46, '中日新聞杯', 'HANSHIN', RaceGrade.G3, RaceSurface.TURF, 2000, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 43_000_000),
        (47, '朝日杯フューチュリティS', 'HANSHIN', RaceGrade.G1, RaceSurface.TURF, 1600, AgeRestriction.TWO_YO, SexRestriction.COLT_HORSE, 0, None, 70_000_000),
        (47, 'ターコイズS', 'NAKAYAMA', RaceGrade.G3, RaceSurface.TURF, 1600, AgeRestriction.THREE_YO_UP, SexRestriction.FILLY_MARE, 0, None, 38_000_000),
        (48, '有馬記念', 'NAKAYAMA', RaceGrade.G1, RaceSurface.TURF, 2500, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 500_000_000),
        (48, 'ホープフルS', 'NAKAYAMA', RaceGrade.G1, RaceSurface.TURF, 2000, AgeRestriction.TWO_YO, SexRestriction.MIXED, 0, None, 70_000_000),
        (48, '東京大賞典', 'OI', RaceGrade.G1, RaceSurface.DIRT, 2000, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 100_000_000),
        (48, '阪神カップ', 'HANSHIN', RaceGrade.G2, RaceSurface.TURF, 1400, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 67_000_000),
    ]

    for w, name, trk, grd, surf, dist, age_r, sex_r, is_tr, tg1, bp in major_races:
        if year <= 2 and age_r in (AgeRestriction.FOUR_YO_UP, AgeRestriction.THREE_YO_UP):
            continue
        m = (w - 1) // 4 + 1
        disp_name = f"{name} [{tg1}トライアル]" if (is_tr and tg1) else name
        real_surf = resolve_surface(trk, surf)
        races.append(Race(
            name=disp_name, track_id=trk, month=m, week=w, grade=grd,
            surface=real_surf, distance=dist, age_restriction=age_r,
            sex_restriction=sex_r, full_gate=8, is_trial=is_tr,
            target_g1_name=tg1, base_prize=bp, year=year
        ))

    # 2. リステッドレース (L / OP・実在冠名付き)
    for w, name, trk, surf, dist, age_r, sex_r, is_tr, tg1 in LISTED_TITLES:
        if year <= 2 and age_r in (AgeRestriction.FOUR_YO_UP, AgeRestriction.THREE_YO_UP):
            continue
        m = (w - 1) // 4 + 1
        base_name = f"{name}(L)"
        disp_name = f"{base_name} [{tg1}トライアル]" if (is_tr and tg1) else base_name
        real_surf = resolve_surface(trk, surf)
        races.append(Race(
            name=disp_name, track_id=trk, month=m, week=w, grade=RaceGrade.L,
            surface=real_surf, distance=dist, age_restriction=age_r,
            sex_restriction=sex_r, full_gate=8, is_trial=1 if is_tr else 0,
            target_g1_name=tg1, base_prize=25_000_000, condition_prize=10_000_000, year=year
        ))

    # 3. 冠名付き特別競走 (1〜36週は2勝C特別、10月1週・第37週以降に3勝クラス特別を開催)
    for w in range(1, 49):
        m = (w - 1) // 4 + 1
        tracks = weekly_tracks.get(w, ['TOKYO', 'HANSHIN', 'CHUKYO'])
        age_cond = AgeRestriction.FOUR_YO_UP if w <= 20 else AgeRestriction.THREE_YO_UP
        is_cond3_season = (w >= 37)
        grade_to_use = RaceGrade.COND_3W if is_cond3_season else RaceGrade.COND_2W
        prize_base = 18_400_000 if is_cond3_season else 15_000_000
        prize_cond = 6_000_000 if is_cond3_season else 5_000_000
        suffix = "(3勝C)" if is_cond3_season else "(特別)"

        # 特別戦1: 主場1 (芝中距離/マイル)
        c3_name1 = COND3_TITLES[(w - 1) % len(COND3_TITLES)]
        t1 = tracks[0]
        dist1 = 1600 if w % 3 == 0 else (2000 if w % 3 == 1 else 2400)
        s1 = resolve_surface(t1, RaceSurface.TURF)
        races.append(Race(
            name=f"{c3_name1}{suffix}", track_id=t1, month=m, week=w,
            grade=grade_to_use, surface=s1, distance=dist1,
            age_restriction=age_cond, full_gate=8, base_prize=prize_base, condition_prize=prize_cond, year=year
        ))

        # 特別戦2: 主場2 (ダート中短距離)
        c3_name2 = COND3_TITLES[(w + 12) % len(COND3_TITLES)]
        t2 = tracks[1] if len(tracks) > 1 else tracks[0]
        dist2 = 1800 if w % 2 == 1 else 1400
        s2 = resolve_surface(t2, RaceSurface.DIRT)
        races.append(Race(
            name=f"{c3_name2}特別{suffix}", track_id=t2, month=m, week=w,
            grade=grade_to_use, surface=s2, distance=dist2,
            age_restriction=age_cond, full_gate=8, base_prize=prize_base, condition_prize=prize_cond, year=year
        ))

        # 特別戦3: 第3場がある場合は第3場 (芝短距離/長距離 または ダート)
        if len(tracks) > 2:
            c3_name3 = COND3_TITLES[(w + 24) % len(COND3_TITLES)]
            t3 = tracks[2]
            surf3 = resolve_surface(t3, RaceSurface.DIRT if (w % 3 == 0) else RaceSurface.TURF)
            dist3 = 1200 if (w % 2 == 1) else (2000 if surf3 == RaceSurface.TURF else 1800)
            races.append(Race(
                name=f"{c3_name3}特別{suffix}", track_id=t3, month=m, week=w,
                grade=grade_to_use, surface=surf3, distance=dist3,
                age_restriction=age_cond, full_gate=8, base_prize=prize_base, condition_prize=prize_cond, year=year
            ))

    # 4. 2勝クラス (各開催場にバランスよく配置)
    for w in range(1, 49):
        m = (w - 1) // 4 + 1
        tracks = weekly_tracks.get(w, ['TOKYO', 'HANSHIN', 'CHUKYO'])
        age_cond = AgeRestriction.FOUR_YO_UP if w <= 20 else AgeRestriction.THREE_YO_UP

        # 2勝C 芝中距離 (主場1)
        t1 = tracks[0]
        dist_turf = 2000 if w % 2 == 1 else 1800
        s1 = resolve_surface(t1, RaceSurface.TURF)
        races.append(Race(
            name=f"2勝クラス({'ダ' if s1 == RaceSurface.DIRT else '芝'}{dist_turf}m)", track_id=t1, month=m, week=w,
            grade=RaceGrade.COND_2W, surface=s1, distance=dist_turf,
            age_restriction=age_cond, full_gate=8, base_prize=15_000_000, condition_prize=5_000_000, year=year
        ))

        # 2勝C ダート (主場2)
        t2 = tracks[1] if len(tracks) > 1 else tracks[0]
        dist_dirt = 1800 if w % 2 == 1 else 1400
        s2 = resolve_surface(t2, RaceSurface.DIRT)
        races.append(Race(
            name=f"2勝クラス(ダ{dist_dirt}m)", track_id=t2, month=m, week=w,
            grade=RaceGrade.COND_2W, surface=s2, distance=dist_dirt,
            age_restriction=age_cond, full_gate=8, base_prize=15_000_000, condition_prize=5_000_000, year=year
        ))

        # 2勝C 短距離 または 中長距離 (第3場 または 主場2)
        t3 = tracks[2] if len(tracks) > 2 else (tracks[1] if len(tracks) > 1 else tracks[0])
        is_sprint = (w % 2 == 1)
        special_dist = (1000 if 'NIIGATA' in tracks else 1200) if is_sprint else 2400
        s3 = resolve_surface(t3, RaceSurface.TURF)
        races.append(Race(
            name=f"2勝クラス({'短距離' if is_sprint else '中長距離'}・{'ダ' if s3 == RaceSurface.DIRT else '芝'}{special_dist}m)", track_id=t3, month=m, week=w,
            grade=RaceGrade.COND_2W, surface=s3, distance=special_dist,
            age_restriction=age_cond, full_gate=8, base_prize=15_000_000, condition_prize=5_000_000, year=year
        ))

        # 2勝C 芝中距離 または ダート短距離 (主場1 または 第3場)
        if w % 2 == 0:
            s_ex = resolve_surface(t1, RaceSurface.TURF)
            races.append(Race(
                name=f"2勝クラス({'ダ' if s_ex == RaceSurface.DIRT else '芝'}1600m)", track_id=t1, month=m, week=w,
                grade=RaceGrade.COND_2W, surface=s_ex, distance=1600,
                age_restriction=age_cond, full_gate=8, base_prize=15_000_000, condition_prize=5_000_000, year=year
            ))
        else:
            t_d_target = tracks[2] if len(tracks) > 2 else t1
            s_ex = resolve_surface(t_d_target, RaceSurface.DIRT)
            races.append(Race(
                name=f"2勝クラス(ダ1200m)", track_id=t_d_target, month=m, week=w,
                grade=RaceGrade.COND_2W, surface=s_ex, distance=1200,
                age_restriction=age_cond, full_gate=8, base_prize=15_000_000, condition_prize=5_000_000, year=year
            ))

    # 5. 1勝クラス (週3レースの適正規模に集約し、全場4レース以上開催＆6〜8頭の多頭数・フルゲート熱戦を実現)
    for w in range(1, 49):
        m = (w - 1) // 4 + 1
        tracks = weekly_tracks.get(w, ['TOKYO', 'HANSHIN', 'CHUKYO'])
        t0 = tracks[0]
        t1 = tracks[1] if len(tracks) > 1 else tracks[0]
        t2 = tracks[2] if len(tracks) > 2 else t0

        # (A) 1〜20週は4歳以上(FOUR_YO_UP)＆3歳限定(THREE_YO)、21〜48週は3歳以上(THREE_YO_UP)
        if w <= 20:
            # 1〜20週（春競馬）: 主場1(芝)、主場2(ダート)、第3場(短距離/長距離)
            # 1. 芝レース（4歳以上 または 3歳）
            if w % 2 == 1:
                d_t0 = 1600 if (w // 2) % 2 == 0 else 2000
                s_t0 = resolve_surface(t0, RaceSurface.TURF)
                races.append(Race(
                    name=f"1勝クラス({'ダ' if s_t0 == RaceSurface.DIRT else '芝'}{d_t0}m)", track_id=t0, month=m, week=w,
                    grade=RaceGrade.COND_1W, surface=s_t0, distance=d_t0,
                    age_restriction=AgeRestriction.FOUR_YO_UP, full_gate=8, base_prize=11_000_000, condition_prize=4_000_000, year=year
                ))
                d_3d = 1400 if (w // 2) % 2 == 0 else 1800
                s_3d = resolve_surface(t1, RaceSurface.DIRT)
                races.append(Race(
                    name=f"3歳1勝クラス(ダ{d_3d}m)", track_id=t1, month=m, week=w,
                    grade=RaceGrade.COND_1W, surface=s_3d, distance=d_3d,
                    age_restriction=AgeRestriction.THREE_YO, full_gate=8, base_prize=10_500_000, condition_prize=4_000_000, year=year
                ))
            else:
                d_3t = 1600 if (w // 2) % 2 == 0 else 2000
                s_3t = resolve_surface(t0, RaceSurface.TURF)
                races.append(Race(
                    name=f"3歳1勝クラス({'ダ' if s_3t == RaceSurface.DIRT else '芝'}{d_3t}m)", track_id=t0, month=m, week=w,
                    grade=RaceGrade.COND_1W, surface=s_3t, distance=d_3t,
                    age_restriction=AgeRestriction.THREE_YO, full_gate=8, base_prize=10_500_000, condition_prize=4_000_000, year=year
                ))
                d_4d = 1400 if (w // 2) % 2 == 0 else 1800
                s_4d = resolve_surface(t1, RaceSurface.DIRT)
                races.append(Race(
                    name=f"1勝クラス(ダ{d_4d}m)", track_id=t1, month=m, week=w,
                    grade=RaceGrade.COND_1W, surface=s_4d, distance=d_4d,
                    age_restriction=AgeRestriction.FOUR_YO_UP, full_gate=8, base_prize=11_000_000, condition_prize=4_000_000, year=year
                ))

            # 第3場 (t2): 短距離 または 長距離
            if len(tracks) > 2:
                dist_ex = 1200 if w % 2 == 1 else 2400
                s_t2 = resolve_surface(t2, RaceSurface.TURF)
                races.append(Race(
                    name=f"1勝クラス({'短距離' if dist_ex == 1200 else '長距離'}・{'ダ' if s_t2 == RaceSurface.DIRT else '芝'}{dist_ex}m)", track_id=t2, month=m, week=w,
                    grade=RaceGrade.COND_1W, surface=s_t2, distance=dist_ex,
                    age_restriction=AgeRestriction.FOUR_YO_UP, full_gate=8, base_prize=11_000_000, condition_prize=4_000_000, year=year
                ))

        else:
            # 21〜48週（夏〜秋冬競馬）: 3歳以上1勝クラス (週3レース)
            # 1. 芝レース (t0: マイル/中距離/短距離ローテ)
            d_t0 = 1600 if w % 3 == 0 else (2000 if w % 3 == 1 else 1400)
            s_t0 = resolve_surface(t0, RaceSurface.TURF)
            races.append(Race(
                name=f"1勝クラス({'ダ' if s_t0 == RaceSurface.DIRT else '芝'}{d_t0}m)", track_id=t0, month=m, week=w,
                grade=RaceGrade.COND_1W, surface=s_t0, distance=d_t0,
                age_restriction=AgeRestriction.THREE_YO_UP, full_gate=8, base_prize=11_000_000, condition_prize=4_000_000, year=year
            ))

            # 2. ダートレース (t1: 1400m / 1800m ローテ)
            d_t1 = 1800 if w % 2 == 1 else 1400
            s_t1 = resolve_surface(t1, RaceSurface.DIRT)
            races.append(Race(
                name=f"1勝クラス(ダ{d_t1}m)", track_id=t1, month=m, week=w,
                grade=RaceGrade.COND_1W, surface=s_t1, distance=d_t1,
                age_restriction=AgeRestriction.THREE_YO_UP, full_gate=8, base_prize=11_000_000, condition_prize=4_000_000, year=year
            ))

            # 3. 第3場 (t2): 2歳秋（第33〜48週）は2歳1勝C、夏競馬（第21〜32週）は直線/長距離/短距離
            if len(tracks) > 2:
                if w >= 33:
                    d_2yo = 1400 if w % 3 == 0 else (1600 if w % 3 == 1 else 1800)
                    s_2yo = resolve_surface(t2, RaceSurface.TURF if (w % 3 != 0) else RaceSurface.DIRT)
                    races.append(Race(
                        name=f"2歳1勝クラス({'ダ' if s_2yo == RaceSurface.DIRT else '芝'}{d_2yo}m)", track_id=t2, month=m, week=w,
                        grade=RaceGrade.COND_1W, surface=s_2yo, distance=d_2yo,
                        age_restriction=AgeRestriction.TWO_YO, full_gate=8, base_prize=10_200_000, condition_prize=4_000_000, year=year
                    ))
                else:
                    dist_ex = 1000 if 'NIIGATA' in tracks else (1200 if w % 2 == 1 else 2400)
                    s_t2 = resolve_surface(t2, RaceSurface.TURF)
                    races.append(Race(
                        name=f"1勝クラス({'直線' if dist_ex == 1000 else ('短距離' if dist_ex == 1200 else '長距離')}・{'ダ' if s_t2 == RaceSurface.DIRT else '芝'}{dist_ex}m)", track_id=t2, month=m, week=w,
                        grade=RaceGrade.COND_1W, surface=s_t2, distance=dist_ex,
                        age_restriction=AgeRestriction.THREE_YO_UP, full_gate=8, base_prize=11_000_000, condition_prize=4_000_000, year=year
                    ))

    # 6. 新馬・未勝利戦 (年間600頭・フルゲート8頭に対応し、新馬戦は年間厳密に75番組配置)
    # - 2歳新馬（第21週〜第48週・28週）: 各週2R = 56レース
    # - 3歳新馬（第1週〜第12週・3月4週まで・12週）: 19レース (第1〜7週は週2R=14R、第8〜12週は週1R=5R)
    # 合計: 56 + 19 = 75番組の新馬戦を配置！
    for w in range(1, 49):
        m = (w - 1) // 4 + 1
        tracks = weekly_tracks.get(w, ['TOKYO', 'HANSHIN', 'CHUKYO'])
        t0 = tracks[0]
        t1 = tracks[1] if len(tracks) > 1 else tracks[0]
        t2 = tracks[2] if len(tracks) > 2 else t0

        # --- 3歳新馬戦（第1週〜第12週・3月4週までに19レース配置） ---
        if w <= 12:
            # 3歳新馬1 (主場1: 芝1600m/1800m/2000m または ダート)
            dist_3new0 = 1600 if w % 3 == 0 else (1800 if w % 3 == 1 else 2000)
            s_3new0 = resolve_surface(t0, RaceSurface.DIRT if (w % 4 == 0) else RaceSurface.TURF)
            races.append(Race(
                name=f"3歳新馬({'ダ' if s_3new0 == RaceSurface.DIRT else '芝'}{dist_3new0}m)",
                track_id=t0, month=m, week=w,
                grade=RaceGrade.NEWCOMER, surface=s_3new0, distance=dist_3new0,
                age_restriction=AgeRestriction.THREE_YO, full_gate=8, base_prize=6_000_000, condition_prize=4_000_000, year=year
            ))

            # 第1週〜第7週はさらに主場2にも3歳新馬を配置（14 + 5 = 19レース）
            if w <= 7:
                dist_3new1 = 1400 if w % 2 == 1 else 1800
                s_3new1 = resolve_surface(t1, RaceSurface.TURF if (w % 3 != 0) else RaceSurface.DIRT)
                races.append(Race(
                    name=f"3歳新馬({'ダ' if s_3new1 == RaceSurface.DIRT else '芝'}{dist_3new1}m)",
                    track_id=t1, month=m, week=w,
                    grade=RaceGrade.NEWCOMER, surface=s_3new1, distance=dist_3new1,
                    age_restriction=AgeRestriction.THREE_YO, full_gate=8, base_prize=6_000_000, condition_prize=4_000_000, year=year
                ))

        # --- 3歳未勝利戦: 1月〜9月（第36週・9月末まで、各開催場に1〜2R配置） ---
        if w <= 36:
            # 主場1 (t0): 芝中距離/マイル
            dist_turf_m0 = 1600 if w % 2 == 1 else 2000
            s_m0 = resolve_surface(t0, RaceSurface.TURF)
            races.append(Race(
                name=f"3歳未勝利({'ダ' if s_m0 == RaceSurface.DIRT else '芝'}{dist_turf_m0}m)", track_id=t0, month=m, week=w,
                grade=RaceGrade.MAIDEN, surface=s_m0, distance=dist_turf_m0,
                age_restriction=AgeRestriction.THREE_YO, full_gate=8, base_prize=5_500_000, condition_prize=4_000_000, year=year
            ))
            # 主場2 (t1): ダート短距離/中距離
            dist_dirt_m1 = 1400 if w % 2 == 1 else 1800
            s_m1 = resolve_surface(t1, RaceSurface.DIRT)
            races.append(Race(
                name=f"3歳未勝利(ダ{dist_dirt_m1}m)", track_id=t1, month=m, week=w,
                grade=RaceGrade.MAIDEN, surface=s_m1, distance=dist_dirt_m1,
                age_restriction=AgeRestriction.THREE_YO, full_gate=8, base_prize=5_500_000, condition_prize=4_000_000, year=year
            ))
            # 第3場 (t2): 芝短距離 または 芝中距離
            if len(tracks) > 2:
                dist_m2 = 1200 if w % 4 == 1 else 1800
                s_m2 = resolve_surface(t2, RaceSurface.TURF)
                races.append(Race(
                    name=f"3歳未勝利({'ダ' if s_m2 == RaceSurface.DIRT else '芝'}{dist_m2}m)", track_id=t2, month=m, week=w,
                    grade=RaceGrade.MAIDEN, surface=s_m2, distance=dist_m2,
                    age_restriction=AgeRestriction.THREE_YO, full_gate=8, base_prize=5_500_000, condition_prize=4_000_000, year=year
                ))

        # --- 2歳戦: 6月（第21週）〜12月（第48週） ---
        if w >= 21:
            # 2歳新馬1（主場1: 芝1200m/1600m/1800m または ダート）
            dist_new0 = 1200 if w % 3 == 0 else (1600 if w % 3 == 1 else 1800)
            surf_new0 = resolve_surface(t0, RaceSurface.DIRT if (w % 4 == 0) else RaceSurface.TURF)
            races.append(Race(
                name=f"2歳新馬({'ダ' if surf_new0 == RaceSurface.DIRT else '芝'}{dist_new0}m)",
                track_id=t0, month=m, week=w,
                grade=RaceGrade.NEWCOMER, surface=surf_new0, distance=dist_new0,
                age_restriction=AgeRestriction.TWO_YO, full_gate=8, base_prize=7_200_000, condition_prize=4_000_000, year=year
            ))
            
            # 2歳新馬2（主場2: 芝1400m/1600m、第32週は小倉2歳S小倉開催に伴い中京へ移動）
            track_new1 = t2 if w == 32 else t1
            s_new1 = resolve_surface(track_new1, RaceSurface.TURF)
            races.append(Race(
                name=f"2歳新馬({'ダ' if s_new1 == RaceSurface.DIRT else '芝'}{1400 if w % 2 == 1 else 1600}m)",
                track_id=track_new1, month=m, week=w,
                grade=RaceGrade.NEWCOMER, surface=s_new1, distance=1400 if w % 2 == 1 else 1600,
                age_restriction=AgeRestriction.TWO_YO, full_gate=8, base_prize=7_200_000, condition_prize=4_000_000, year=year
            ))

            # 2歳未勝利戦（第25週〜第48週）
            if w >= 25:
                s_2m1 = resolve_surface(t1, RaceSurface.TURF)
                races.append(Race(
                    name=f"2歳未勝利({'ダ' if s_2m1 == RaceSurface.DIRT else '芝'}{1400 if w % 2 == 1 else 1800}m)", track_id=t1, month=m, week=w,
                    grade=RaceGrade.MAIDEN, surface=s_2m1, distance=1400 if w % 2 == 1 else 1800,
                    age_restriction=AgeRestriction.TWO_YO, full_gate=8, base_prize=5_500_000, condition_prize=4_000_000, year=year
                ))
                s_2m2 = resolve_surface(t2, RaceSurface.DIRT)
                races.append(Race(
                    name=f"2歳未勝利(ダ{1400 if w % 4 == 0 else 1800}m)", track_id=t2, month=m, week=w,
                    grade=RaceGrade.MAIDEN, surface=s_2m2, distance=1400 if w % 4 == 0 else 1800,
                    age_restriction=AgeRestriction.TWO_YO, full_gate=8, base_prize=5_500_000, condition_prize=4_000_000, year=year
                ))

    return races

if __name__ == "__main__":
    races = generate_full_program(1)
    print(f"総生成レース数: {len(races)} レース")
    
    weeks = Counter(r.week for r in races)
    print(f"週あたり平均レース数: {len(races)/48.0:.2f} (最小={min(weeks.values())}, 最大={max(weeks.values())})")
    
    grades = Counter(r.grade.value for r in races)
    print("\n【グレード別内訳】")
    for g, cnt in sorted(grades.items()):
        print(f"  {g:10s}: {cnt:4d} レース ({cnt/len(races)*100:.1f}%)")
        
    surfs = Counter(r.surface.value for r in races)
    print("\n【馬場別内訳】")
    for s, cnt in surfs.items():
        print(f"  {s:10s}: {cnt:4d} レース ({cnt/len(races)*100:.1f}%)")

    tracks = Counter(r.track_id for r in races)
    print("\n【競馬場別内訳】")
    for t, cnt in sorted(tracks.items(), key=lambda x: x[1], reverse=True):
        print(f"  {t:12s}: {cnt:4d} レース")

    print("\n【距離帯別内訳】")
    d_1000 = sum(1 for r in races if r.distance <= 1000)
    d_sprint = sum(1 for r in races if 1200 <= r.distance <= 1400)
    d_mile = sum(1 for r in races if r.distance == 1600)
    d_inter = sum(1 for r in races if 1800 <= r.distance <= 2000)
    d_long = sum(1 for r in races if r.distance >= 2200)
    print(f"  超短距離 (1000m)     : {d_1000:4d} レース")
    print(f"  短距離   (1200-1400m): {d_sprint:4d} レース")
    print(f"  マイル   (1600m)     : {d_mile:4d} レース")
    print(f"  中距離   (1800-2000m): {d_inter:4d} レース")
    print(f"  中長・長距離(2200m〜): {d_long:4d} レース")
    
    filly_cnt = sum(1 for r in races if r.sex_restriction == SexRestriction.FILLY_MARE)
    print(f"\n【牝馬限定戦数】: {filly_cnt:4d} レース ({filly_cnt/len(races)*100:.1f}%)")
