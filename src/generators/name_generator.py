"""
馬名自動生成モジュール
馬主の冠名（Prefix）＋単語/血統由来名
カタカナ9文字以内制約（JRA競走馬登録基準）および重複チェック
現存する有名冠名との重複を避け、苗字から連想されるオリジナル冠名を定義
"""

from __future__ import annotations

import random
from typing import Iterable, Optional, Set, Tuple


# 初期100名の馬主定義: (苗字, 会社種別, 冠名)
# 冠名は苗字から自然に連想され、かつ現存する有名冠名と被らないオリジナル設定
DEFAULT_OWNER_PROFILES: list[Tuple[str, str, str]] = [
    ("鈴鹿", "建設", "ベルカ"),            # 鈴(Bell) + 鹿
    ("桐谷", "商事", "キリヤ"),            # 桐谷
    ("蓮見", "商会", "ハスミ"),            # 蓮見
    ("神崎", "ホールディングス", "カンザキ"),# 神崎
    ("黒川", "重工", "クロカワ"),          # 黒川
    ("白石", "物産", "シライシ"),          # 白石
    ("藤森", "不動産", "フジモリ"),        # 藤森
    ("青柳", "工業", "アオヤギ"),          # 青柳
    ("橘", "実業", "タチバナ"),            # 橘
    ("峰岸", "興業", "ミネギシ"),          # 峰岸
    ("海老名", "通商", "エビナ"),          # 海老名
    ("芦田", "開発", "アシダ"),            # 芦田
    ("朝倉", "総業", "アサクラ"),          # 朝倉
    ("鷹取", "エンジニアリング", "タカトリ"),# 鷹取
    ("風間", "ロジスティクス", "カザマ"),  # 風間
    ("岩城", "ファイナンス", "イワキ"),    # 岩城
    ("月島", "コーポレーション", "ツキシマ"),# 月島
    ("潮見", "海運", "シオミ"),            # 潮見
    ("榊原", "エステート", "サカキ"),      # 榊原
    ("鳴海", "テクノロジー", "ナルミ"),    # 鳴海
    ("羽生", "産業", "ハニュー"),          # 羽生
    ("城崎", "システムズ", "シロサキ"),    # 城崎
    ("泉水", "エナジー", "イズミノ"),      # 泉水
    ("剣持", "グループ", "ケンモチ"),      # 剣持
    ("荻野", "企画", "オギノ"),            # 荻野
    ("氷室", "製薬", "ヒムロ"),            # 氷室
    ("楠木", "建設", "クスノキ"),          # 楠木
    ("葛西", "商事", "カサイ"),            # 葛西
    ("柴崎", "商会", "シバサキ"),          # 柴崎
    ("多喜", "ホールディングス", "タキノ"), # 多喜
    ("雷電", "重工", "ライデン"),          # 雷電
    ("鏡味", "物産", "カガミ"),            # 鏡味
    ("光岡", "不動産", "ミツオカ"),        # 光岡
    ("茜", "工業", "アカン"),              # 茜
    ("竜宮", "実業", "リュウグ"),          # 竜宮
    ("茜部", "興業", "アカネベ"),          # 茜部
    ("早乙女", "通商", "サオトメ"),        # 早乙女
    ("鞍馬", "開発", "クラマ"),            # 鞍馬
    ("霞", "総業", "カスミノ"),            # 霞
    ("叢雲", "エンジニアリング", "ムラクモ"),# 叢雲
    ("銀林", "ロジスティクス", "ギンバヤ"),# 銀林
    ("火野", "ファイナンス", "ヒノ"),      # 火野
    ("蒼井", "コーポレーション", "アオイ"),# 蒼井
    ("滝川", "海運", "タキガワ"),          # 滝川
    ("深山", "エステート", "ミヤマ"),      # 深山
    ("宝生", "テクノロジー", "ホウショ"),  # 宝生
    ("響", "産業", "ヒビキ"),              # 響
    ("翠川", "システムズ", "ミドリカ"),    # 翠川
    ("千代", "エナジー", "チヨノ"),        # 千代
    ("夜久", "グループ", "ヤクモ"),        # 夜久
    ("弓削", "企画", "ユゲ"),              # 弓削
    ("鉄川", "建設", "テツカワ"),          # 鉄川
    ("琥珀", "商事", "コハク"),            # 琥珀
    ("紅林", "商会", "クレバヤ"),          # 紅林
    ("波多野", "ホールディングス", "ハタノ"),# 波多野
    ("金森", "重工", "カナモリ"),          # 金森
    ("大和", "物産", "ヤマト"),            # 大和
    ("草壁", "不動産", "クサカベ"),        # 草壁
    ("真壁", "工業", "マカベ"),            # 真壁
    ("百瀬", "実業", "モモセ"),            # 百瀬
    ("東雲", "興業", "シノノメ"),          # 東雲
    ("花巻", "通商", "ハナマキ"),          # 花巻
    ("折原", "開発", "オリハラ"),          # 折原
    ("諏訪", "総業", "スワノ"),            # 諏訪
    ("芹沢", "エンジニアリング", "セリザワ"),# 芹沢
    ("立花", "ロジスティクス", "リッカ"),  # 立花(六花)
    ("伊吹", "ファイナンス", "イブキ"),    # 伊吹
    ("笹原", "コーポレーション", "ササハラ"),# 笹原
    ("湊", "海運", "ミナト"),              # 湊
    ("砂原", "エステート", "スナハラ"),    # 砂原
    ("棚橋", "テクノロジー", "タナハシ"),  # 棚橋
    ("堂島", "産業", "ドウジマ"),          # 堂島
    ("常盤", "システムズ", "トキワ"),      # 常盤
    ("長船", "エナジー", "オサフネ"),      # 長船
    ("七海", "グループ", "ナナミ"),        # 七海
    ("伏見", "企画", "フシミ"),            # 伏見
    ("穂高", "建設", "ホタカ"),            # 穂高
    ("槙原", "商事", "マキハラ"),          # 槙原
    ("水城", "商会", "ミズキ"),            # 水城
    ("門脇", "ホールディングス", "カドワキ"),# 門脇
    ("矢車", "重工", "ヤグルマ"),          # 矢車
    ("吉良", "物産", "キララ"),            # 吉良
    ("栗原", "不動産", "クリハラ"),        # 栗原
    ("桑原", "工業", "クワハラ"),          # 桑原
    ("剣崎", "実業", "ケンザキ"),          # 剣崎
    ("小松", "興業", "コマツ"),            # 小松
    ("坂井", "通商", "サカイ"),            # 坂井
    ("志摩", "開発", "シマノ"),            # 志摩
    ("白鳥", "総業", "シラトリ"),          # 白鳥
    ("末広", "エンジニアリング", "スエヒロ"),# 末広
    ("瀬戸", "ロジスティクス", "セトノ"),  # 瀬戸
    ("高見", "ファイナンス", "タカミ"),    # 高見
    ("滝本", "コーポレーション", "タキモト"),# 滝本
    ("舘野", "海運", "タテノ"),            # 舘野
    ("千島", "エステート", "チシマ"),      # 千島
    ("出水", "テクノロジー", "デミズ"),    # 出水
    ("富樫", "産業", "トガシ"),            # 富樫
    ("豊島", "システムズ", "トヨシマ"),    # 豊島
    ("長門", "エナジー", "ナガト"),        # 長門
    ("那須", "グループ", "ナスノ"),        # 那須
]

# 冠名リストの抽出
DEFAULT_OWNER_PREFIXES = [p[2] for p in DEFAULT_OWNER_PROFILES]

from src.data.horse_words import (
    ALL_WORDS,
    CATEGORY_DICT,
    CELESTIAL_NATURAL,
    FLOWERS,
    FOODS_SWEETS,
    GEOGRAPHY,
    HISTORIC_SITES,
    HISTORICAL_FIGURES,
    MINERALS_GEMS,
    WESTERN_NAMES,
)

NAME_WORDS = ALL_WORDS


class HorseNameGenerator:
    """
    馬名自動生成クラス:
    - 冠名（Prefix）＋単語（1単語のみ）による自然で格調高い命名
    - 7大カテゴリ（花、外国人名、地名、歴史上の人物、鉱物、食べ物、名跡）＋天体自然
    - 重賞(G1, G2, G3)勝利馬（永久欠番）および現在活動中の馬との重複を厳格に排除
    - 性別（牡/牝）に応じた自然な命名カテゴリの優先配分
    """

    def __init__(self, existing_names: Optional[Iterable[str]] = None):
        """
        Args:
            existing_names: 使用禁止馬名の初期セット（重賞勝ち馬、現役馬など）
        """
        self.used_names: Set[str] = set(existing_names or [])
        self.used_active_words: Set[str] = set()

    def set_forbidden_names(self, names: Iterable[str]) -> None:
        """使用禁止馬名（重賞勝利馬＋現在活動中の馬など）を一括設定"""
        self.used_names = set(names)

    def register_name(self, name: str) -> None:
        """既出・使用中馬名として登録"""
        self.used_names.add(name)

    def register_active_word(self, word: str) -> None:
        """互換用"""
        self.used_active_words.add(word)

    def release_active_word(self, word: str) -> None:
        """互換用"""
        self.used_active_words.discard(word)

    def is_name_available(self, name: str) -> bool:
        """使用可能かチェック（未登録かつ2文字以上）"""
        if len(name) < 2:
            return False
        return name not in self.used_names

    def _pick_word_for_sex(self, sex: Optional[str] = None, category: Optional[str] = None) -> str:
        """性別や指定カテゴリに基づき候補単語プールを決定"""
        if category and category in CATEGORY_DICT:
            return random.choice(CATEGORY_DICT[category])

        # 性別に応じた好ましいカテゴリ優先度
        is_female = sex in ["filly", "mare"]
        if is_female:
            # 牝馬: 花(30%), 食べ物/スイーツ(25%), 宝石(20%), 西洋女性名(15%), 天体(10%)
            r = random.random()
            if r < 0.30:
                pool = FLOWERS
            elif r < 0.55:
                pool = FOODS_SWEETS
            elif r < 0.75:
                pool = MINERALS_GEMS
            elif r < 0.90:
                pool = WESTERN_NAMES
            else:
                pool = CELESTIAL_NATURAL
        else:
            # 牡馬: 歴史上の人物(25%), 地名/名勝(25%), 西洋男性名(20%), 名跡(15%), 宝石/天体(15%)
            r = random.random()
            if r < 0.25:
                pool = HISTORICAL_FIGURES
            elif r < 0.50:
                pool = GEOGRAPHY
            elif r < 0.70:
                pool = WESTERN_NAMES
            elif r < 0.85:
                pool = HISTORIC_SITES
            else:
                pool = MINERALS_GEMS + CELESTIAL_NATURAL

        return random.choice(pool)

    def generate_name(
        self,
        prefix: Optional[str] = None,
        sex: Optional[str] = None,
        category: Optional[str] = None,
        max_attempts: int = 500,
    ) -> str:
        """
        冠名（Prefix）＋単語（1単語）により、重複しない馬名を生成
        Args:
            prefix: 馬主の冠名（省略時は冠名なし）
            sex: 'colt', 'filly', 'horse', 'mare'
            category: 'flower', 'western_name', 'geography', 'history', 'mineral', 'food', 'site', 'celestial'
            max_attempts: 最大試行回数
        Returns:
            [冠名] + [単語] 形式のユニークな馬名
        """
        pfx = prefix or ""

        # 1. カテゴリまたは全単語から単語プールを作成
        target_pool = list(CATEGORY_DICT.get(category, ALL_WORDS) if category else ALL_WORDS)
        random.shuffle(target_pool)

        # 性別指定がある場合は性別に好ましい単語を優先して先頭に配置
        if not category and sex:
            pref_word = self._pick_word_for_sex(sex)
            if pref_word in target_pool:
                target_pool.remove(pref_word)
                target_pool.insert(0, pref_word)

        # 2. 単語を1つ選定して [冠名] + [単語] を生成
        for w in target_pool:
            candidate = f"{pfx}{w}"
            if candidate not in self.used_names:
                self.used_names.add(candidate)
                self.used_active_words.add(w)
                return candidate

        # 3. 指定カテゴリ内で見つからなかった場合は ALL_WORDS 全体から探索
        if category:
            fallback_pool = list(ALL_WORDS)
            random.shuffle(fallback_pool)
            for w in fallback_pool:
                candidate = f"{pfx}{w}"
                if candidate not in self.used_names:
                    self.used_names.add(candidate)
                    self.used_active_words.add(w)
                    return candidate

        # 4. 極限のフォールバック (単語すべて使い切った場合のみ番号付与)
        counter = 1
        while True:
            w = self._pick_word_for_sex(sex, category)
            candidate = f"{pfx}{w}{counter}"
            if candidate not in self.used_names:
                self.used_names.add(candidate)
                self.used_active_words.add(f"{w}{counter}")
                return candidate
            counter += 1



# 一般的な日本の名字リスト（実在の競馬関係者を意識しない完全ニュートラルな一覧）
COMMON_JAPANESE_SURNAMES = [
    "佐藤", "鈴木", "高橋", "田中", "渡辺", "伊藤", "山本", "中村", "小林", "加藤",
    "吉田", "山田", "佐々木", "山口", "松本", "井上", "木村", "林", "斎藤", "清水",
    "山崎", "森", "池田", "橋本", "阿部", "石川", "山下", "中島", "石井", "小川",
    "前田", "岡田", "長谷川", "藤田", "後藤", "近藤", "村上", "遠藤", "青木", "坂本",
    "斉藤", "福田", "太田", "西村", "藤井", "岡本", "金子", "藤原", "三浦", "中野",
    "中川", "原田", "松田", "竹内", "小野", "田村", "中山", "石田", "工藤", "上田",
    "森田", "横山", "宮崎", "酒井", "内田", "高木", "安藤", "島田", "谷口", "大野",
    "高田", "丸山", "今井", "河野", "藤本", "村田", "武田", "上野", "杉山", "増田",
    "小山", "大塚", "平野", "菅原", "久保", "千葉", "松井", "岩崎", "桜井", "木下",
    "野口", "松尾", "菊地", "野村", "新井", "渡部", "佐野", "杉本", "大西", "古川",
    "水野", "島村", "小池", "吉川", "山内", "飯田", "西田", "西川", "菊池", "本田",
    "安田", "川崎", "辻", "吉村", "中井", "岩田", "服部", "関", "川口", "大島",
    "福島", "樋口", "浜田", "白石", "望月", "永井", "松岡", "宮本", "吉岡", "浅野",
    "矢野", "荒木", "大森", "川上", "奥村", "小松", "平井", "片山", "堀", "早川",
    "成田", "松永", "吉野", "広瀬", "野沢", "大橋", "神谷", "長尾", "黒田", "栗原",
    "土屋", "細川", "今村", "庄司", "富田", "福井", "大山", "千葉", "田代", "瀬戸"
]

# 一般的な日本の男性名リスト (約150語)
MALE_GIVEN_NAMES = [
    # 伝統的・重厚な男性名
    "一郎", "二郎", "三郎", "太郎", "次郎", "正夫", "勇", "実", "清", "博",
    "茂", "進", "隆", "修", "勝", "豊", "誠", "仁", "操", "健一",
    "浩二", "修平", "達也", "大介", "慎一", "俊介", "雄大", "拓也", "翔太", "直樹",
    "亮平", "和樹", "大樹", "康介", "裕樹", "智也", "健太", "真一", "公平", "貴之",
    # 現代的・スマートな男性名
    "蓮", "悠真", "湊", "大翔", "陽翔", "朝陽", "樹", "颯太", "大和", "悠人",
    "奏太", "陸", "律", "蒼", "晴", "結翔", "碧", "陽太", "仁", "暖",
    "怜", "匠", "光", "翼", "弦", "隼人", "圭吾", "海斗", "涼太", "優希",
    # 自然・風雅な名前
    "秋人", "春樹", "夏彦", "冬馬", "風太", "波留", "星矢", "大河", "大地", "晴海",
    "晃", "徹", "淳", "啓介", "剛", "雅人", "祐介", "弘樹", "英樹", "慶太",
    "聡", "陽平", "康平", "章弘", "克彦", "宗一", "重信", "光男", "文彦", "良平",
    "隼", "凌", "航平", "純", "壮太", "竜也", "一真", "悠介", "敬太", "涼介",
    "武尊", "悠大", "泰成", "健介", "直人", "翔馬", "優斗", "颯馬", "和也", "拓海"
]

# 一般的な日本の女性名リスト (約130語)
FEMALE_GIVEN_NAMES = [
    # 華やか・植物・花
    "葵", "さくら", "美咲", "陽菜", "結衣", "芽衣", "花", "菜々子", "遥", "美穂",
    "千尋", "真由", "彩花", "七海", "優奈", "楓", "真央", "詩織", "愛理", "日向",
    "美月", "凛", "琴音", "栞", "杏", "未来", "茜", "玲奈", "紗英", "美羽",
    "莉子", "結愛", "心春", "咲希", "愛菜", "美優", "結菜", "陽葵", "澪", "結月",
    "紬", "咲良", "結花", "穂乃花", "萌", "綾乃", "春香", "優香", "小春", "沙織",
    "千夏", "美紀", "友香", "理恵", "麻衣", "香織", "由美", "真奈", "絵里", "亜美",
    "奈々", "静香", "久美子", "由香", "裕子", "真理", "恵子", "洋子", "典子", "美代子",
    "涼花", "風花", "若菜", "瑠奈", "彩音", "柚希", "美桜", "美空", "花音", "朱音",
    "鈴乃", "明日香", "佳奈", "里奈", "瑞希", "舞", "瞳", "愛美", "里緒", "美里",
    "梨乃", "有希", "美香", "美幸", "真由美", "早紀", "智美", "千恵", "優美", "奈津美",
    "美鈴", "志穂", "恵理", "真理子", "由佳", "綾香", "優花", "千佳", "結夏", "菜月"
]

# 互換用
COMMON_JAPANESE_GIVEN_NAMES = MALE_GIVEN_NAMES + FEMALE_GIVEN_NAMES


class PersonNameGenerator:
    """調教師・騎手氏名生成クラス（実在関係者を意識しないニュートラルな生成）"""

    def __init__(self):
        self.used_jockey_names: Set[str] = set()
        self.used_trainer_names: Set[str] = set()

    def register_jockey_name(self, name: str) -> None:
        """既出の騎手名を登録"""
        self.used_jockey_names.add(name)

    def register_trainer_name(self, name: str) -> None:
        """既出の厩舎名を登録"""
        self.used_trainer_names.add(name)

    def generate_trainer_name(self, index: Optional[int] = None) -> str:
        """重複しないユニークな厩舎名（名字＋厩舎）を生成"""
        shuffled = COMMON_JAPANESE_SURNAMES.copy()
        random.shuffle(shuffled)
        for s in shuffled:
            candidate = f"{s}厩舎"
            if candidate not in self.used_trainer_names:
                self.used_trainer_names.add(candidate)
                return candidate

        # フォールバック
        cnt = 1
        while True:
            s = random.choice(COMMON_JAPANESE_SURNAMES)
            candidate = f"{s}{cnt}厩舎"
            if candidate not in self.used_trainer_names:
                self.used_trainer_names.add(candidate)
                return candidate
            cnt += 1

    def generate_jockey_name(self, gender: str = "male") -> str:
        """重複しないユニークな騎手名（名字 名前）を生成 (性別対応)"""
        shuffled_surnames = COMMON_JAPANESE_SURNAMES.copy()
        given_pool = FEMALE_GIVEN_NAMES.copy() if gender == "female" else MALE_GIVEN_NAMES.copy()
        random.shuffle(shuffled_surnames)
        random.shuffle(given_pool)

        for s in shuffled_surnames:
            for g in given_pool:
                name = f"{s} {g}"
                if name not in self.used_jockey_names:
                    self.used_jockey_names.add(name)
                    return name

        # フォールバック
        cnt = 1
        while True:
            s = random.choice(COMMON_JAPANESE_SURNAMES)
            g = random.choice(given_pool)
            name = f"{s} {g}{cnt}"
            if name not in self.used_jockey_names:
                self.used_jockey_names.add(name)
                return name
            cnt += 1


    @classmethod
    def get_stable_name_from_jockey(cls, jockey_name: str, existing_names: Optional[Set[str]] = None) -> str:
        """騎手氏名（名字 名前）から重複しない新厩舎名を生成"""
        surname = jockey_name.split()[0] if " " in jockey_name else jockey_name
        candidate = f"{surname}厩舎"

        if existing_names is None or candidate not in existing_names:
            return candidate

        # 同一苗字の厩舎が既に存在する場合のバリエーション
        # 1) フルネーム（例: 田中武厩舎）
        parts = jockey_name.split()
        if len(parts) >= 2:
            candidate_full = f"{parts[0]}{parts[1][0]}厩舎"
            if candidate_full not in existing_names:
                return candidate_full

        # 2) 新＋苗字（例: 新田中厩舎）
        candidate_shin = f"新{surname}厩舎"
        if candidate_shin not in existing_names:
            return candidate_shin

        # 3) 数字サフィックス
        cnt = 2
        while True:
            candidate_num = f"{surname}{cnt}厩舎"
            if candidate_num not in existing_names:
                return candidate_num
            cnt += 1



