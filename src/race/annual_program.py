"""
年間レース番組表定義モジュール (Annual Race Program)
- 年間48週 (12ヶ月 × 4週) の全レース体系 (約1,070レース)
- JRA 8場 ＋ 地方 4場（大井・川崎・船橋・盛岡）の12競馬場開催
- 2歳戦線、3歳クラシック・ダート三冠戦線、古馬王道路線
- 冠名付きリステッド・3勝クラス、1000mおよび2400〜3600m番組、牝馬限定戦
- 1レース8頭限定フルゲート
"""

from __future__ import annotations

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
    (1, 'ジュニアカップ', 'NAKAYAMA', RaceSurface.TURF, 1600, AgeRestriction.THREE_YO, False, None),
    (2, 'ニューイヤーS', 'NAKAYAMA', RaceSurface.TURF, 1600, AgeRestriction.FOUR_YO_UP, False, None),
    (3, '紅梅ステークス', 'KYOTO', RaceSurface.TURF, 1400, AgeRestriction.THREE_YO, False, None),
    (4, '白富士ステークス', 'TOKYO', RaceSurface.TURF, 2000, AgeRestriction.FOUR_YO_UP, False, None),
    (5, '洛陽ステークス', 'KYOTO', RaceSurface.TURF, 1600, AgeRestriction.FOUR_YO_UP, False, None),
    (6, 'ヒヤシンスS', 'TOKYO', RaceSurface.DIRT, 1600, AgeRestriction.THREE_YO, False, None),
    (8, '仁川ステークス', 'HANSHIN', RaceSurface.DIRT, 2000, AgeRestriction.FOUR_YO_UP, False, None),
    (9, '総武ステークス', 'NAKAYAMA', RaceSurface.DIRT, 1800, AgeRestriction.FOUR_YO_UP, False, None),
    (10, 'アネモネS', 'NAKAYAMA', RaceSurface.TURF, 1600, AgeRestriction.THREE_YO, True, '桜花賞'),
    (11, '若葉ステークス', 'HANSHIN', RaceSurface.TURF, 2000, AgeRestriction.THREE_YO, True, '皐月賞'),
    (12, '六甲ステークス', 'HANSHIN', RaceSurface.TURF, 1600, AgeRestriction.FOUR_YO_UP, False, None),
    (13, '春雷ステークス', 'NAKAYAMA', RaceSurface.TURF, 1200, AgeRestriction.FOUR_YO_UP, False, None),
    (14, '福島民報杯', 'FUKUSHIMA', RaceSurface.TURF, 2000, AgeRestriction.FOUR_YO_UP, False, None),
    (16, 'オアシスS', 'TOKYO', RaceSurface.DIRT, 1600, AgeRestriction.FOUR_YO_UP, False, None),
    (17, 'スイートピーS', 'TOKYO', RaceSurface.TURF, 1800, AgeRestriction.THREE_YO, True, 'オークス'),
    (18, 'プリンシパルS', 'TOKYO', RaceSurface.TURF, 2000, AgeRestriction.THREE_YO, True, '日本ダービー'),
    (19, '都大路ステークス', 'KYOTO', RaceSurface.TURF, 1800, AgeRestriction.FOUR_YO_UP, False, None),
    (20, 'メイステークス', 'TOKYO', RaceSurface.TURF, 1800, AgeRestriction.FOUR_YO_UP, False, None),
    (21, '安土城ステークス', 'KYOTO', RaceSurface.TURF, 1400, AgeRestriction.FOUR_YO_UP, False, None),
    (22, '米子ステークス', 'HANSHIN', RaceSurface.TURF, 1600, AgeRestriction.FOUR_YO_UP, False, None),
    (23, 'パラダイスS', 'TOKYO', RaceSurface.TURF, 1400, AgeRestriction.FOUR_YO_UP, False, None),
    (24, '巴賞', 'KOKURA', RaceSurface.TURF, 1800, AgeRestriction.THREE_YO_UP, False, None),
    (26, '福島テレビOP', 'FUKUSHIMA', RaceSurface.TURF, 1200, AgeRestriction.THREE_YO_UP, False, None),
    (28, 'アイビスSD前哨戦', 'NIIGATA', RaceSurface.TURF, 1000, AgeRestriction.THREE_YO_UP, False, None),
    (30, '関屋記念直前OP', 'NIIGATA', RaceSurface.TURF, 1600, AgeRestriction.THREE_YO_UP, False, None),
    (32, '朱鷺ステークス', 'NIIGATA', RaceSurface.TURF, 1400, AgeRestriction.THREE_YO_UP, False, None),
    (34, 'エニフステークス', 'HANSHIN', RaceSurface.DIRT, 1400, AgeRestriction.THREE_YO_UP, False, None),
    (35, 'ラジオ日本賞', 'NAKAYAMA', RaceSurface.DIRT, 1800, AgeRestriction.THREE_YO_UP, False, None),
    (36, 'ポートアイランドS', 'HANSHIN', RaceSurface.TURF, 1600, AgeRestriction.THREE_YO_UP, False, None),
    (37, 'オパールS', 'KYOTO', RaceSurface.TURF, 1200, AgeRestriction.THREE_YO_UP, False, None),
    (38, '信越ステークス', 'NIIGATA', RaceSurface.TURF, 1400, AgeRestriction.THREE_YO_UP, False, None),
    (39, 'ブラジルカップ', 'TOKYO', RaceSurface.DIRT, 2100, AgeRestriction.THREE_YO_UP, False, None),
    (40, 'カシオペアS', 'KYOTO', RaceSurface.TURF, 1800, AgeRestriction.THREE_YO_UP, False, None),
    (41, 'ルミエールオータムD', 'NIIGATA', RaceSurface.TURF, 1000, AgeRestriction.THREE_YO_UP, False, None),
    (42, 'オーロカップ', 'TOKYO', RaceSurface.TURF, 1400, AgeRestriction.THREE_YO_UP, False, None),
    (43, 'カトレアステークス', 'TOKYO', RaceSurface.DIRT, 1600, AgeRestriction.TWO_YO, True, '全日本２歳優駿'),
    (43, 'アンドロメダS', 'KYOTO', RaceSurface.TURF, 2000, AgeRestriction.THREE_YO_UP, False, None),
    (44, 'キャピタルS', 'TOKYO', RaceSurface.TURF, 1600, AgeRestriction.THREE_YO_UP, False, None),
    (45, '師走ステークス', 'NAKAYAMA', RaceSurface.DIRT, 1800, AgeRestriction.THREE_YO_UP, False, None),
    (46, 'リゲルステークス', 'HANSHIN', RaceSurface.TURF, 1600, AgeRestriction.THREE_YO_UP, False, None),
    (47, 'ディセンバーS', 'NAKAYAMA', RaceSurface.TURF, 1800, AgeRestriction.THREE_YO_UP, False, None),
    (48, 'ベテルギウスS', 'HANSHIN', RaceSurface.DIRT, 1800, AgeRestriction.THREE_YO_UP, False, None),
]

def generate_full_program(year: int = 1) -> List[Race]:
    # 週間開催競馬場ローテーション（2〜3場）
    weekly_tracks = {
        1: ['NAKAYAMA', 'CHUKYO', 'KOKURA'],
        2: ['NAKAYAMA', 'CHUKYO', 'KOKURA'],
        3: ['NAKAYAMA', 'CHUKYO', 'KOKURA'],
        4: ['NAKAYAMA', 'CHUKYO', 'KAWASAKI'],
        5: ['TOKYO', 'HANSHIN', 'KOKURA'],
        6: ['TOKYO', 'HANSHIN', 'KOKURA'],
        7: ['TOKYO', 'HANSHIN', 'OI'],
        8: ['TOKYO', 'HANSHIN', 'KOKURA'],
        9: ['NAKAYAMA', 'HANSHIN', 'CHUKYO'],
        10: ['NAKAYAMA', 'HANSHIN', 'CHUKYO'],
        11: ['NAKAYAMA', 'HANSHIN', 'OI'],
        12: ['NAKAYAMA', 'HANSHIN', 'CHUKYO'],
        13: ['HANSHIN', 'NAKAYAMA', 'FUKUSHIMA'],
        14: ['HANSHIN', 'NAKAYAMA', 'FUKUSHIMA'],
        15: ['NAKAYAMA', 'HANSHIN', 'FUKUSHIMA'],
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
        35: ['NAKAYAMA', 'HANSHIN', 'FUNABASHI'],
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

    # 1. 重賞レース定義
    major_races = [
        # 1月
        (1, '中山金杯', 'NAKAYAMA', RaceGrade.G3, RaceSurface.TURF, 2000, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 0, None, 43_000_000),
        (1, '京都金杯', 'CHUKYO', RaceGrade.G3, RaceSurface.TURF, 1600, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 0, None, 43_000_000),
        (1, 'シンザン記念', 'CHUKYO', RaceGrade.G3, RaceSurface.TURF, 1600, AgeRestriction.THREE_YO, SexRestriction.MIXED, 0, None, 40_000_000),
        (2, 'フェアリーS', 'NAKAYAMA', RaceGrade.G3, RaceSurface.TURF, 1600, AgeRestriction.THREE_YO, SexRestriction.FILLY_MARE, 0, None, 38_000_000),
        (2, '京成杯', 'NAKAYAMA', RaceGrade.G3, RaceSurface.TURF, 2000, AgeRestriction.THREE_YO, SexRestriction.MIXED, 0, None, 40_000_000),
        (3, '日経新春杯', 'CHUKYO', RaceGrade.G2, RaceSurface.TURF, 2200, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 0, None, 57_000_000),
        (3, '東海S', 'CHUKYO', RaceGrade.G2, RaceSurface.DIRT, 1800, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 1, 'フェブラリーS', 55_000_000),
        (4, 'アメリカJCC', 'NAKAYAMA', RaceGrade.G2, RaceSurface.TURF, 2200, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 0, None, 62_000_000),
        (4, '根岸S', 'TOKYO', RaceGrade.G3, RaceSurface.DIRT, 1400, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 1, 'フェブラリーS', 40_000_000),
        (4, '川崎記念', 'KAWASAKI', RaceGrade.G1, RaceSurface.DIRT, 2100, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 0, None, 100_000_000),
        # 2月
        (5, '東京新聞杯', 'TOKYO', RaceGrade.G3, RaceSurface.TURF, 1600, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 0, None, 41_000_000),
        (5, 'きさらぎ賞', 'HANSHIN', RaceGrade.G3, RaceSurface.TURF, 1800, AgeRestriction.THREE_YO, SexRestriction.MIXED, 0, None, 40_000_000),
        (5, 'シルクロードS', 'CHUKYO', RaceGrade.G3, RaceSurface.TURF, 1200, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 1, '高松宮記念', 41_000_000),
        (6, '共同通信杯', 'TOKYO', RaceGrade.G3, RaceSurface.TURF, 1800, AgeRestriction.THREE_YO, SexRestriction.MIXED, 0, None, 40_000_000),
        (6, 'クイーンC', 'TOKYO', RaceGrade.G3, RaceSurface.TURF, 1600, AgeRestriction.THREE_YO, SexRestriction.FILLY_MARE, 0, None, 38_000_000),
        (6, '京都記念', 'HANSHIN', RaceGrade.G2, RaceSurface.TURF, 2200, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 0, None, 62_000_000),
        (7, 'フェブラリーS', 'TOKYO', RaceGrade.G1, RaceSurface.DIRT, 1600, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 0, None, 120_000_000),
        (7, '雲取賞', 'OI', RaceGrade.G3, RaceSurface.DIRT, 1800, AgeRestriction.THREE_YO, SexRestriction.MIXED, 1, '羽田盃', 35_000_000),
        (7, '小倉大賞典', 'KOKURA', RaceGrade.G3, RaceSurface.TURF, 1800, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 0, None, 43_000_000),
        (8, '中山記念', 'NAKAYAMA', RaceGrade.G2, RaceSurface.TURF, 1800, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 1, '大阪杯', 67_000_000),
        (8, '阪急杯', 'HANSHIN', RaceGrade.G3, RaceSurface.TURF, 1400, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 1, '高松宮記念', 43_000_000),
        # 3月
        (9, '弥生賞ディープ記念', 'NAKAYAMA', RaceGrade.G2, RaceSurface.TURF, 2000, AgeRestriction.THREE_YO, SexRestriction.COLT_HORSE, 1, '皐月賞', 54_000_000),
        (9, 'チューリップ賞', 'HANSHIN', RaceGrade.G2, RaceSurface.TURF, 1600, AgeRestriction.THREE_YO, SexRestriction.FILLY_MARE, 1, '桜花賞', 52_000_000),
        (9, 'オーシャンS', 'NAKAYAMA', RaceGrade.G3, RaceSurface.TURF, 1200, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 1, '高松宮記念', 43_000_000),
        (10, '金鯱賞', 'CHUKYO', RaceGrade.G2, RaceSurface.TURF, 2000, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 1, '大阪杯', 67_000_000),
        (10, 'フィリーズレビュー', 'HANSHIN', RaceGrade.G2, RaceSurface.TURF, 1400, AgeRestriction.THREE_YO, SexRestriction.FILLY_MARE, 1, '桜花賞', 52_000_000),
        (10, 'ファルコンS', 'CHUKYO', RaceGrade.G3, RaceSurface.TURF, 1400, AgeRestriction.THREE_YO, SexRestriction.MIXED, 0, None, 40_000_000),
        (11, 'スプリングS', 'NAKAYAMA', RaceGrade.G2, RaceSurface.TURF, 1800, AgeRestriction.THREE_YO, SexRestriction.COLT_HORSE, 1, '皐月賞', 54_000_000),
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
        (14, '桜花賞', 'HANSHIN', RaceGrade.G1, RaceSurface.TURF, 1600, AgeRestriction.THREE_YO, SexRestriction.FILLY_MARE, 0, None, 140_000_000),
        (14, 'ニュージーランドT', 'NAKAYAMA', RaceGrade.G2, RaceSurface.TURF, 1600, AgeRestriction.THREE_YO, SexRestriction.MIXED, 1, 'NHKマイルカップ', 54_000_000),
        (14, '阪神牝馬S', 'HANSHIN', RaceGrade.G2, RaceSurface.TURF, 1600, AgeRestriction.FOUR_YO_UP, SexRestriction.FILLY_MARE, 1, 'ヴィクトリアマイル', 55_000_000),
        (15, '皐月賞', 'NAKAYAMA', RaceGrade.G1, RaceSurface.TURF, 2000, AgeRestriction.THREE_YO, SexRestriction.COLT_HORSE, 0, None, 200_000_000),
        (15, 'アーリントンカップ', 'HANSHIN', RaceGrade.G3, RaceSurface.TURF, 1600, AgeRestriction.THREE_YO, SexRestriction.MIXED, 1, 'NHKマイルカップ', 40_000_000),
        (15, 'アンタレスS', 'HANSHIN', RaceGrade.G3, RaceSurface.DIRT, 1800, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 0, None, 40_000_000),
        (16, '青葉賞', 'TOKYO', RaceGrade.G2, RaceSurface.TURF, 2400, AgeRestriction.THREE_YO, SexRestriction.COLT_HORSE, 1, '日本ダービー', 54_000_000),
        (16, 'フローラS', 'TOKYO', RaceGrade.G2, RaceSurface.TURF, 2000, AgeRestriction.THREE_YO, SexRestriction.FILLY_MARE, 1, 'オークス', 52_000_000),
        (16, 'マイラーズC', 'KYOTO', RaceGrade.G2, RaceSurface.TURF, 1600, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 1, '安田記念', 59_000_000),
        (16, '羽田盃', 'OI', RaceGrade.G1, RaceSurface.DIRT, 1800, AgeRestriction.THREE_YO, SexRestriction.MIXED, 0, None, 80_000_000),
        # 5月
        (17, '天皇賞（春）', 'KYOTO', RaceGrade.G1, RaceSurface.TURF, 3200, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 0, None, 220_000_000),
        (17, 'かしわ記念', 'FUNABASHI', RaceGrade.G1, RaceSurface.DIRT, 1600, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 0, None, 80_000_000),
        (17, 'ユニコーンS', 'KYOTO', RaceGrade.G3, RaceSurface.DIRT, 1900, AgeRestriction.THREE_YO, SexRestriction.MIXED, 1, '東京ダービー', 40_000_000),
        (18, 'NHKマイルカップ', 'TOKYO', RaceGrade.G1, RaceSurface.TURF, 1600, AgeRestriction.THREE_YO, SexRestriction.MIXED, 0, None, 130_000_000),
        (18, '京都新聞杯', 'KYOTO', RaceGrade.G2, RaceSurface.TURF, 2200, AgeRestriction.THREE_YO, SexRestriction.MIXED, 1, '日本ダービー', 54_000_000),
        (18, '新潟大賞典', 'NIIGATA', RaceGrade.G3, RaceSurface.TURF, 2000, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 0, None, 43_000_000),
        (19, 'ヴィクトリアマイル', 'TOKYO', RaceGrade.G1, RaceSurface.TURF, 1600, AgeRestriction.FOUR_YO_UP, SexRestriction.FILLY_MARE, 0, None, 130_000_000),
        (19, '京王杯スプリングC', 'TOKYO', RaceGrade.G2, RaceSurface.TURF, 1400, AgeRestriction.FOUR_YO_UP, SexRestriction.MIXED, 1, '安田記念', 59_000_000),
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
        (27, '函館記念', 'KOKURA', RaceGrade.G3, RaceSurface.TURF, 2000, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 43_000_000),
        (27, '函館2歳S', 'KOKURA', RaceGrade.G3, RaceSurface.TURF, 1200, AgeRestriction.TWO_YO, SexRestriction.MIXED, 0, None, 31_000_000),
        (28, 'アイビスサマーダッシュ', 'NIIGATA', RaceGrade.G3, RaceSurface.TURF, 1000, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 41_000_000),
        (28, 'クイーンS', 'NIIGATA', RaceGrade.G3, RaceSurface.TURF, 1800, AgeRestriction.THREE_YO_UP, SexRestriction.FILLY_MARE, 0, None, 38_000_000),
        # 8月
        (29, 'レパードS', 'NIIGATA', RaceGrade.G3, RaceSurface.DIRT, 1800, AgeRestriction.THREE_YO, SexRestriction.MIXED, 1, 'ジャパンダートクラシック', 40_000_000),
        (29, 'エルムS', 'NIIGATA', RaceGrade.G3, RaceSurface.DIRT, 1700, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 40_000_000),
        (30, '小倉記念', 'KOKURA', RaceGrade.G3, RaceSurface.TURF, 2000, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 43_000_000),
        (30, '関屋記念', 'NIIGATA', RaceGrade.G3, RaceSurface.TURF, 1600, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 41_000_000),
        (31, '北九州記念', 'KOKURA', RaceGrade.G3, RaceSurface.TURF, 1200, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 41_000_000),
        (31, '新潟2歳S', 'NIIGATA', RaceGrade.G3, RaceSurface.TURF, 1600, AgeRestriction.TWO_YO, SexRestriction.MIXED, 0, None, 31_000_000),
        (32, 'キーンランドC', 'NIIGATA', RaceGrade.G3, RaceSurface.TURF, 1200, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 1, 'スプリンターズS', 43_000_000),
        (32, '新潟記念', 'NIIGATA', RaceGrade.G3, RaceSurface.TURF, 2000, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 43_000_000),
        (32, '小倉2歳S', 'CHUKYO', RaceGrade.G3, RaceSurface.TURF, 1200, AgeRestriction.TWO_YO, SexRestriction.MIXED, 0, None, 31_000_000),
        # 9月
        (33, '紫苑S', 'NAKAYAMA', RaceGrade.G2, RaceSurface.TURF, 2000, AgeRestriction.THREE_YO, SexRestriction.FILLY_MARE, 1, '秋華賞', 52_000_000),
        (33, '京成杯オータムH', 'NAKAYAMA', RaceGrade.G3, RaceSurface.TURF, 1600, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 41_000_000),
        (33, '不来方賞', 'MORIOKA', RaceGrade.G2, RaceSurface.DIRT, 2000, AgeRestriction.THREE_YO, SexRestriction.MIXED, 1, 'ジャパンダートクラシック', 40_000_000),
        (34, 'ローズS', 'HANSHIN', RaceGrade.G2, RaceSurface.TURF, 1800, AgeRestriction.THREE_YO, SexRestriction.FILLY_MARE, 1, '秋華賞', 52_000_000),
        (34, 'セントライト記念', 'NAKAYAMA', RaceGrade.G2, RaceSurface.TURF, 2200, AgeRestriction.THREE_YO, SexRestriction.COLT_HORSE, 1, '菊花賞', 54_000_000),
        (35, '神戸新聞杯', 'HANSHIN', RaceGrade.G2, RaceSurface.TURF, 2400, AgeRestriction.THREE_YO, SexRestriction.COLT_HORSE, 1, '菊花賞', 54_000_000),
        (35, 'オールカマー', 'NAKAYAMA', RaceGrade.G2, RaceSurface.TURF, 2200, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 1, '天皇賞（秋）', 67_000_000),
        (35, '日本テレビ盃', 'FUNABASHI', RaceGrade.G2, RaceSurface.DIRT, 1800, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 1, 'JBCクラシック', 40_000_000),
        (36, 'スプリンターズS', 'NAKAYAMA', RaceGrade.G1, RaceSurface.TURF, 1200, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 170_000_000),
        (36, 'シリウスS', 'HANSHIN', RaceGrade.G3, RaceSurface.DIRT, 2000, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 40_000_000),
        # 10月
        (37, '毎日王冠', 'TOKYO', RaceGrade.G2, RaceSurface.TURF, 1800, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 1, '天皇賞（秋）', 67_000_000),
        (37, '京都大賞典', 'KYOTO', RaceGrade.G2, RaceSurface.TURF, 2400, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 1, 'ジャパンカップ', 67_000_000),
        (37, 'サウジアラビアRC', 'TOKYO', RaceGrade.G3, RaceSurface.TURF, 1600, AgeRestriction.TWO_YO, SexRestriction.MIXED, 0, None, 33_000_000),
        (37, 'マイルCS南部杯', 'MORIOKA', RaceGrade.G1, RaceSurface.DIRT, 1600, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 80_000_000),
        (38, '秋華賞', 'KYOTO', RaceGrade.G1, RaceSurface.TURF, 2000, AgeRestriction.THREE_YO, SexRestriction.FILLY_MARE, 0, None, 110_000_000),
        (38, '府中牝馬S', 'TOKYO', RaceGrade.G2, RaceSurface.TURF, 1800, AgeRestriction.THREE_YO_UP, SexRestriction.FILLY_MARE, 1, 'エリザベス女王杯', 55_000_000),
        (38, 'ジャパンダートクラシック', 'OI', RaceGrade.G1, RaceSurface.DIRT, 2000, AgeRestriction.THREE_YO, SexRestriction.MIXED, 0, None, 100_000_000),
        (39, '菊花賞', 'KYOTO', RaceGrade.G1, RaceSurface.TURF, 3000, AgeRestriction.THREE_YO, SexRestriction.COLT_HORSE, 0, None, 200_000_000),
        (39, '富士S', 'TOKYO', RaceGrade.G2, RaceSurface.TURF, 1600, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 1, 'マイルCS', 59_000_000),
        (40, '天皇賞（秋）', 'TOKYO', RaceGrade.G1, RaceSurface.TURF, 2000, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 220_000_000),
        (40, 'スワンS', 'KYOTO', RaceGrade.G2, RaceSurface.TURF, 1400, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 1, 'マイルCS', 59_000_000),
        (40, 'アルテミスS', 'TOKYO', RaceGrade.G3, RaceSurface.TURF, 1600, AgeRestriction.TWO_YO, SexRestriction.FILLY_MARE, 0, None, 31_000_000),
        # 11月
        (41, 'JBCクラシック', 'OI', RaceGrade.G1, RaceSurface.DIRT, 2000, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 100_000_000),
        (41, 'JBCスプリント', 'OI', RaceGrade.G1, RaceSurface.DIRT, 1200, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 80_000_000),
        (41, 'JBC2歳優駿', 'MORIOKA', RaceGrade.G3, RaceSurface.DIRT, 1800, AgeRestriction.TWO_YO, SexRestriction.MIXED, 1, '全日本２歳優駿', 35_000_000),
        (41, '京王杯2歳S', 'TOKYO', RaceGrade.G2, RaceSurface.TURF, 1400, AgeRestriction.TWO_YO, SexRestriction.MIXED, 1, '朝日杯FS', 38_000_000),
        (41, 'ファンタジーS', 'KYOTO', RaceGrade.G3, RaceSurface.TURF, 1400, AgeRestriction.TWO_YO, SexRestriction.FILLY_MARE, 1, '阪神JF', 31_000_000),
        (42, 'エリザベス女王杯', 'KYOTO', RaceGrade.G1, RaceSurface.TURF, 2200, AgeRestriction.THREE_YO_UP, SexRestriction.FILLY_MARE, 0, None, 140_000_000),
        (42, 'デイリー杯2歳S', 'KYOTO', RaceGrade.G2, RaceSurface.TURF, 1600, AgeRestriction.TWO_YO, SexRestriction.MIXED, 1, '朝日杯FS', 38_000_000),
        (42, '武蔵野S', 'TOKYO', RaceGrade.G3, RaceSurface.DIRT, 1600, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 1, 'チャンピオンズC', 40_000_000),
        (42, '福島記念', 'FUKUSHIMA', RaceGrade.G3, RaceSurface.TURF, 2000, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 43_000_000),
        (43, 'マイルチャンピオンシップ', 'KYOTO', RaceGrade.G1, RaceSurface.TURF, 1600, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 180_000_000),
        (43, '東京スポーツ杯2歳S', 'TOKYO', RaceGrade.G2, RaceSurface.TURF, 1800, AgeRestriction.TWO_YO, SexRestriction.MIXED, 1, 'ホープフルS', 38_000_000),
        (43, 'みやこS', 'KYOTO', RaceGrade.G3, RaceSurface.DIRT, 1800, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 1, 'チャンピオンズC', 40_000_000),
        (44, 'ジャパンカップ', 'TOKYO', RaceGrade.G1, RaceSurface.TURF, 2400, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 500_000_000),
        (44, '兵庫ジュニアグランプリ', 'FUNABASHI', RaceGrade.G2, RaceSurface.DIRT, 1400, AgeRestriction.TWO_YO, SexRestriction.MIXED, 1, '全日本２歳優駿', 40_000_000),
        (44, '京都2歳S', 'KYOTO', RaceGrade.G3, RaceSurface.TURF, 2000, AgeRestriction.TWO_YO, SexRestriction.MIXED, 1, 'ホープフルS', 33_000_000),
        (44, '京阪杯', 'KYOTO', RaceGrade.G3, RaceSurface.TURF, 1200, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 41_000_000),
        # 12月
        (45, 'チャンピオンズカップ', 'CHUKYO', RaceGrade.G1, RaceSurface.DIRT, 1800, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 120_000_000),
        (45, 'ステイヤーズS', 'NAKAYAMA', RaceGrade.G2, RaceSurface.TURF, 3600, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 62_000_000),
        (45, 'チャレンジカップ', 'HANSHIN', RaceGrade.G3, RaceSurface.TURF, 2000, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 43_000_000),
        (46, '阪神ジュベナイルフィリーズ', 'HANSHIN', RaceGrade.G1, RaceSurface.TURF, 1600, AgeRestriction.TWO_YO, SexRestriction.FILLY_MARE, 0, None, 65_000_000),
        (46, '全日本２歳優駿', 'KAWASAKI', RaceGrade.G1, RaceSurface.DIRT, 1600, AgeRestriction.TWO_YO, SexRestriction.MIXED, 0, None, 42_000_000),
        (46, 'カペラS', 'NAKAYAMA', RaceGrade.G3, RaceSurface.DIRT, 1200, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 38_000_000),
        (46, '中日新聞杯', 'CHUKYO', RaceGrade.G3, RaceSurface.TURF, 2000, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 43_000_000),
        (47, '朝日杯フューチュリティS', 'HANSHIN', RaceGrade.G1, RaceSurface.TURF, 1600, AgeRestriction.TWO_YO, SexRestriction.COLT_HORSE, 0, None, 70_000_000),
        (47, 'ターコイズS', 'NAKAYAMA', RaceGrade.G3, RaceSurface.TURF, 1600, AgeRestriction.THREE_YO_UP, SexRestriction.FILLY_MARE, 0, None, 38_000_000),
        (48, '有馬記念', 'NAKAYAMA', RaceGrade.G1, RaceSurface.TURF, 2500, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 500_000_000),
        (48, 'ホープフルS', 'NAKAYAMA', RaceGrade.G1, RaceSurface.TURF, 2000, AgeRestriction.TWO_YO, SexRestriction.MIXED, 0, None, 70_000_000),
        (48, '東京大賞典', 'OI', RaceGrade.G1, RaceSurface.DIRT, 2000, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 100_000_000),
        (48, '阪神カップ', 'HANSHIN', RaceGrade.G2, RaceSurface.TURF, 1400, AgeRestriction.THREE_YO_UP, SexRestriction.MIXED, 0, None, 67_000_000),
    ]

    for w, name, trk, grd, surf, dist, age_r, sex_r, is_tr, tg1, bp in major_races:
        m = (w - 1) // 4 + 1
        disp_name = f"{name} [{tg1}トライアル]" if (is_tr and tg1) else name
        races.append(Race(
            name=disp_name, track_id=trk, month=m, week=w, grade=grd,
            surface=surf, distance=dist, age_restriction=age_r,
            sex_restriction=sex_r, full_gate=8, is_trial=is_tr,
            target_g1_name=tg1, base_prize=bp, year=year
        ))

    # 2. リステッドレース (L / OP・実在冠名付き)
    for w, name, trk, surf, dist, age_r, is_tr, tg1 in LISTED_TITLES:
        m = (w - 1) // 4 + 1
        base_name = f"{name}(L)"
        disp_name = f"{base_name} [{tg1}トライアル]" if (is_tr and tg1) else base_name
        races.append(Race(
            name=disp_name, track_id=trk, month=m, week=w, grade=RaceGrade.L,
            surface=surf, distance=dist, age_restriction=age_r,
            sex_restriction=SexRestriction.MIXED, full_gate=8, is_trial=1 if is_tr else 0,
            target_g1_name=tg1, base_prize=25_000_000, condition_prize=10_000_000, year=year
        ))

    # 3. 冠名付き3勝クラス特別 (各週2〜3レース)
    for w in range(1, 49):
        m = (w - 1) // 4 + 1
        tracks = weekly_tracks.get(w, ['TOKYO', 'HANSHIN', 'CHUKYO'])
        age_cond = AgeRestriction.FOUR_YO_UP if w <= 20 else AgeRestriction.THREE_YO_UP

        # 3勝クラス1: 芝中距離またはマイル
        c3_name1 = COND3_TITLES[(w - 1) % len(COND3_TITLES)]
        t1 = tracks[0]
        dist1 = 1600 if w % 3 == 0 else (2000 if w % 3 == 1 else 2400)
        races.append(Race(
            name=f"{c3_name1}(3勝C)", track_id=t1, month=m, week=w,
            grade=RaceGrade.COND_3W, surface=RaceSurface.TURF, distance=dist1,
            age_restriction=age_cond, full_gate=8, base_prize=18_400_000, condition_prize=6_000_000, year=year
        ))

        # 3勝クラス2: ダート中距離または短距離
        c3_name2 = COND3_TITLES[(w + 12) % len(COND3_TITLES)]
        t2 = tracks[1] if len(tracks) > 1 else tracks[0]
        dist2 = 1800 if w % 2 == 1 else 1400
        races.append(Race(
            name=f"{c3_name2}特別(3勝C)", track_id=t2, month=m, week=w,
            grade=RaceGrade.COND_3W, surface=RaceSurface.DIRT, distance=dist2,
            age_restriction=age_cond, full_gate=8, base_prize=18_400_000, condition_prize=6_000_000, year=year
        ))

    # 4. 2勝クラス (各週3〜4レース、1000m、2400m、牝馬限定含む)
    for w in range(1, 49):
        m = (w - 1) // 4 + 1
        tracks = weekly_tracks.get(w, ['TOKYO', 'HANSHIN', 'CHUKYO'])
        age_cond = AgeRestriction.FOUR_YO_UP if w <= 20 else AgeRestriction.THREE_YO_UP

        # 2勝C 芝中距離
        t1 = tracks[0]
        dist_turf = 2000 if w % 2 == 1 else 1800
        races.append(Race(
            name=f"2勝クラス(芝{dist_turf}m)", track_id=t1, month=m, week=w,
            grade=RaceGrade.COND_2W, surface=RaceSurface.TURF, distance=dist_turf,
            age_restriction=age_cond, full_gate=8, base_prize=15_000_000, condition_prize=5_000_000, year=year
        ))

        # 2勝C ダート
        t2 = tracks[1] if len(tracks) > 1 else tracks[0]
        dist_dirt = 1800 if w % 2 == 1 else 1400
        races.append(Race(
            name=f"2勝クラス(ダ{dist_dirt}m)", track_id=t2, month=m, week=w,
            grade=RaceGrade.COND_2W, surface=RaceSurface.DIRT, distance=dist_dirt,
            age_restriction=age_cond, full_gate=8, base_prize=15_000_000, condition_prize=5_000_000, year=year
        ))

        # 2勝C 短距離(1000m/1200m) または 中長距離(2400m/2600m)
        t3 = tracks[2] if len(tracks) > 2 else tracks[0]
        is_sprint = (w % 2 == 1)
        special_dist = (1000 if 'NIIGATA' in tracks else 1200) if is_sprint else 2400
        races.append(Race(
            name=f"2勝クラス({'短距離' if is_sprint else '中長距離'}・芝{special_dist}m)", track_id=t3, month=m, week=w,
            grade=RaceGrade.COND_2W, surface=RaceSurface.TURF, distance=special_dist,
            age_restriction=age_cond, full_gate=8, base_prize=15_000_000, condition_prize=5_000_000, year=year
        ))

        # 2勝C 牝馬限定戦
        if w % 2 == 0:
            races.append(Race(
                name=f"2勝クラス(牝馬限定・芝1600m)", track_id=t1, month=m, week=w,
                grade=RaceGrade.COND_2W, surface=RaceSurface.TURF, distance=1600,
                age_restriction=age_cond, sex_restriction=SexRestriction.FILLY_MARE,
                full_gate=8, base_prize=15_000_000, condition_prize=5_000_000, year=year
            ))

        # 2勝C ダート短距離 (1200m/1400m)
        races.append(Race(
            name=f"2勝クラス(ダ{1200 if w % 2 == 1 else 1400}m)", track_id=t1, month=m, week=w,
            grade=RaceGrade.COND_2W, surface=RaceSurface.DIRT, distance=1200 if w % 2 == 1 else 1400,
            age_restriction=age_cond, full_gate=8, base_prize=15_000_000, condition_prize=5_000_000, year=year
        ))

    # 5. 1勝クラス (各週5〜6レース、1000m、2400〜2600m、牝馬限定含む)
    for w in range(1, 49):
        m = (w - 1) // 4 + 1
        tracks = weekly_tracks.get(w, ['TOKYO', 'HANSHIN', 'CHUKYO'])
        age_cond = AgeRestriction.FOUR_YO_UP if w <= 20 else AgeRestriction.THREE_YO_UP

        # 芝マイル/短距離
        races.append(Race(
            name=f"1勝クラス(芝{1400 if w % 2 == 1 else 1600}m)", track_id=tracks[0], month=m, week=w,
            grade=RaceGrade.COND_1W, surface=RaceSurface.TURF, distance=1400 if w % 2 == 1 else 1600,
            age_restriction=age_cond, full_gate=8, base_prize=11_000_000, condition_prize=4_000_000, year=year
        ))
        # 芝中距離
        races.append(Race(
            name=f"1勝クラス(芝{1800 if w % 2 == 1 else 2000}m)", track_id=tracks[1] if len(tracks) > 1 else tracks[0], month=m, week=w,
            grade=RaceGrade.COND_1W, surface=RaceSurface.TURF, distance=1800 if w % 2 == 1 else 2000,
            age_restriction=age_cond, full_gate=8, base_prize=11_000_000, condition_prize=4_000_000, year=year
        ))
        # ダート中距離
        races.append(Race(
            name=f"1勝クラス(ダ{1800 if w % 2 == 1 else 1700}m)", track_id=tracks[0], month=m, week=w,
            grade=RaceGrade.COND_1W, surface=RaceSurface.DIRT, distance=1800 if w % 2 == 1 else 1700,
            age_restriction=age_cond, full_gate=8, base_prize=11_000_000, condition_prize=4_000_000, year=year
        ))
        # ダート短距離
        races.append(Race(
            name=f"1勝クラス(ダ{1200 if w % 2 == 1 else 1400}m)", track_id=tracks[1] if len(tracks) > 1 else tracks[0], month=m, week=w,
            grade=RaceGrade.COND_1W, surface=RaceSurface.DIRT, distance=1200 if w % 2 == 1 else 1400,
            age_restriction=age_cond, full_gate=8, base_prize=11_000_000, condition_prize=4_000_000, year=year
        ))
        # 1000m または 長距離 (2400m〜2600m)
        t_third = tracks[2] if len(tracks) > 2 else tracks[0]
        if w % 2 == 1:
            dist_ex = 1000 if 'NIIGATA' in tracks else 1200
            races.append(Race(
                name=f"1勝クラス(短距離・芝{dist_ex}m)", track_id=t_third, month=m, week=w,
                grade=RaceGrade.COND_1W, surface=RaceSurface.TURF, distance=dist_ex,
                age_restriction=age_cond, full_gate=8, base_prize=11_000_000, condition_prize=4_000_000, year=year
            ))
        else:
            races.append(Race(
                name=f"1勝クラス(長距離・芝2400m)", track_id=t_third, month=m, week=w,
                grade=RaceGrade.COND_1W, surface=RaceSurface.TURF, distance=2400,
                age_restriction=age_cond, full_gate=8, base_prize=11_000_000, condition_prize=4_000_000, year=year
            ))
        # 牝馬限定戦
        races.append(Race(
            name=f"1勝クラス(牝馬限定・芝{1600 if w % 2 == 1 else 1800}m)", track_id=tracks[0], month=m, week=w,
            grade=RaceGrade.COND_1W, surface=RaceSurface.TURF, distance=1600 if w % 2 == 1 else 1800,
            age_restriction=age_cond, sex_restriction=SexRestriction.FILLY_MARE,
            full_gate=8, base_prize=11_000_000, condition_prize=4_000_000, year=year
        ))

    # 6. 新馬・未勝利戦 (各週7〜9レース)
    for w in range(1, 49):
        m = (w - 1) // 4 + 1
        tracks = weekly_tracks.get(w, ['TOKYO', 'HANSHIN', 'CHUKYO'])

        # 3歳未勝利戦: 1月〜9月（第36週・9月末まで、週2〜3レースで未勝利馬の頭数と完全整合）
        if w <= 36:
            # 芝マイル/中距離 (隔週で距離切替)
            dist_turf_m = 1600 if w % 2 == 1 else 2000
            races.append(Race(
                name=f"3歳未勝利(芝{dist_turf_m}m)", track_id=tracks[0], month=m, week=w,
                grade=RaceGrade.MAIDEN, surface=RaceSurface.TURF, distance=dist_turf_m,
                age_restriction=AgeRestriction.THREE_YO, full_gate=8, base_prize=5_500_000, condition_prize=4_000_000, year=year
            ))
            # ダート短距離/中距離 (隔週で距離切替)
            dist_dirt_m = 1400 if w % 2 == 1 else 1800
            races.append(Race(
                name=f"3歳未勝利(ダ{dist_dirt_m}m)", track_id=tracks[1] if len(tracks) > 1 else tracks[0], month=m, week=w,
                grade=RaceGrade.MAIDEN, surface=RaceSurface.DIRT, distance=dist_dirt_m,
                age_restriction=AgeRestriction.THREE_YO, full_gate=8, base_prize=5_500_000, condition_prize=4_000_000, year=year
            ))
            # 3歳春（第1週〜第20週）は牝馬限定や追加ダートを週1R配置
            if w <= 20 and w % 2 == 0:
                races.append(Race(
                    name=f"3歳未勝利(牝馬限定・芝1800m)", track_id=tracks[2] if len(tracks) > 2 else tracks[0], month=m, week=w,
                    grade=RaceGrade.MAIDEN, surface=RaceSurface.TURF, distance=1800,
                    age_restriction=AgeRestriction.THREE_YO, sex_restriction=SexRestriction.FILLY_MARE,
                    full_gate=8, base_prize=5_500_000, condition_prize=4_000_000, year=year
                ))

        # 2歳戦: 6月（第21週）〜12月（第48週）
        if w >= 21:
            # 2歳新馬（週1〜2レース、年間約40レース・約320枠で2歳300頭が完全満席デビュー）
            dist_new = 1200 if w % 3 == 0 else (1600 if w % 3 == 1 else 1800)
            surf_new = RaceSurface.DIRT if (w % 4 == 0) else RaceSurface.TURF
            races.append(Race(
                name=f"2歳新馬({'ダ' if surf_new == RaceSurface.DIRT else '芝'}{dist_new}m)",
                track_id=tracks[0], month=m, week=w,
                grade=RaceGrade.NEWCOMER, surface=surf_new, distance=dist_new,
                age_restriction=AgeRestriction.TWO_YO, full_gate=8, base_prize=7_200_000, condition_prize=4_000_000, year=year
            ))
            if w % 2 == 1:
                # 隔週で牝馬限定またはマイル新馬を追加
                races.append(Race(
                    name=f"2歳新馬(牝馬限定・芝{1400 if w % 4 == 1 else 1600}m)",
                    track_id=tracks[1] if len(tracks) > 1 else tracks[0], month=m, week=w,
                    grade=RaceGrade.NEWCOMER, surface=RaceSurface.TURF, distance=1400 if w % 4 == 1 else 1600,
                    age_restriction=AgeRestriction.TWO_YO, sex_restriction=SexRestriction.FILLY_MARE,
                    full_gate=8, base_prize=7_200_000, condition_prize=4_000_000, year=year
                ))

            # 2歳未勝利戦（第25週〜第48週、週1〜2レース）
            if w >= 25:
                races.append(Race(
                    name=f"2歳未勝利(芝{1400 if w % 2 == 1 else 1800}m)", track_id=tracks[1] if len(tracks) > 1 else tracks[0], month=m, week=w,
                    grade=RaceGrade.MAIDEN, surface=RaceSurface.TURF, distance=1400 if w % 2 == 1 else 1800,
                    age_restriction=AgeRestriction.TWO_YO, full_gate=8, base_prize=5_500_000, condition_prize=4_000_000, year=year
                ))
                if w % 2 == 0:
                    races.append(Race(
                        name=f"2歳未勝利(ダ{1400 if w % 4 == 0 else 1800}m)", track_id=tracks[2] if len(tracks) > 2 else tracks[0], month=m, week=w,
                        grade=RaceGrade.MAIDEN, surface=RaceSurface.DIRT, distance=1400 if w % 4 == 0 else 1800,
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
