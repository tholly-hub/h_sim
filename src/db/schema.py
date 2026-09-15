"""
SQLite データベース DDL スキーマ定義
Mac / Windows 共通、将来の拡張（Phase 2-4）に対応可能なスキーマ構造
"""

DDL_STATEMENTS = """
-- 外部キー制約を有効化
PRAGMA foreign_keys = ON;

-- 1. 生産牧場テーブル (Breeders: 初期50場、動的分化)
CREATE TABLE IF NOT EXISTS breeders (
    breeder_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    region TEXT NOT NULL DEFAULT '北海道',        -- 所在地（北海道、東北、関東、中部、北陸、近畿、中国、四国、九州）
    reputation REAL NOT NULL DEFAULT 50.0,       -- 評判 (0.0〜100.0)
    funds INTEGER NOT NULL DEFAULT 100000000,    -- 資金 (円)
    horse_capacity INTEGER NOT NULL DEFAULT 15,  -- 総繋養枠数 (初期15頭、最大100頭まで拡張可能)
    broodmare_capacity INTEGER NOT NULL DEFAULT 15, -- 互換性用
    current_year_starts INTEGER NOT NULL DEFAULT 0, -- 今年の出走数
    current_year_wins INTEGER NOT NULL DEFAULT 0,   -- 今年の勝利数
    current_year_g1 INTEGER NOT NULL DEFAULT 0,     -- 今年のG1勝利数
    current_year_g2 INTEGER NOT NULL DEFAULT 0,     -- 今年のG2勝利数
    current_year_g3 INTEGER NOT NULL DEFAULT 0,     -- 今年のG3勝利数
    current_year_earnings INTEGER NOT NULL DEFAULT 0, -- 今年の生産馬獲得賞金
    career_starts INTEGER NOT NULL DEFAULT 0,       -- 通算生産馬出走数
    career_wins INTEGER NOT NULL DEFAULT 0,         -- 通算勝利数
    g1_wins INTEGER NOT NULL DEFAULT 0,             -- 通算G1勝利数
    g2_wins INTEGER NOT NULL DEFAULT 0,             -- 通算G2勝利数
    g3_wins INTEGER NOT NULL DEFAULT 0,             -- 通算G3勝利数
    career_earnings INTEGER NOT NULL DEFAULT 0,     -- 通算生産馬獲得賞金
    created_year INTEGER NOT NULL DEFAULT 1
);

-- 2. 馬主テーブル (Owners: 初期100人、冠名、動的分化)
CREATE TABLE IF NOT EXISTS owners (
    owner_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    prefix TEXT NOT NULL UNIQUE,                 -- 固有の冠名 (例: サトノ, トウカイ等)
    funds INTEGER NOT NULL DEFAULT 100000000,    -- 購買力・資金 (円)
    horse_capacity INTEGER NOT NULL DEFAULT 20,  -- 最大所有頭数枠
    current_year_wins INTEGER NOT NULL DEFAULT 0, -- 今年の勝利数
    career_wins INTEGER NOT NULL DEFAULT 0,       -- 通算勝利数
    career_earnings INTEGER NOT NULL DEFAULT 0,   -- 通算所有馬獲得賞金
    g1_wins INTEGER NOT NULL DEFAULT 0,           -- 通算G1勝利数
    created_year INTEGER NOT NULL DEFAULT 1
);

-- 3. 厩舎テーブル (Trainers: 美浦30場、栗東30場、計60厩舎、50歳開業〜80歳定年引退)
CREATE TABLE IF NOT EXISTS trainers (
    trainer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    location TEXT NOT NULL CHECK (location IN ('美浦', '栗東')),
    age INTEGER NOT NULL DEFAULT 50,             -- 調教師年齢 (50〜80歳)
    trainer_years INTEGER NOT NULL DEFAULT 1,    -- 調教師歴 (1〜30年)
    specialty TEXT NOT NULL,                     -- 得意分野 ('turf', 'dirt', 'distance_long', 'distance_sprint', 'early_growth', 'late_growth', 'durability_care', 'general')
    horse_capacity INTEGER NOT NULL DEFAULT 30,  -- 最大受入頭数 (初期30頭、最大50頭)
    reputation REAL NOT NULL DEFAULT 50.0,       -- 厩舎評価
    former_jockey_id INTEGER,                    -- 前身の引退騎手ID (引き継ぎ元)
    current_year_starts INTEGER NOT NULL DEFAULT 0, -- 今年の出走数
    current_year_wins INTEGER NOT NULL DEFAULT 0,
    current_year_g1 INTEGER NOT NULL DEFAULT 0,
    current_year_g2 INTEGER NOT NULL DEFAULT 0,
    current_year_g3 INTEGER NOT NULL DEFAULT 0,
    current_year_earnings INTEGER NOT NULL DEFAULT 0,
    career_starts INTEGER NOT NULL DEFAULT 0,       -- 通算出走数
    career_wins INTEGER NOT NULL DEFAULT 0,
    g1_wins INTEGER NOT NULL DEFAULT 0,
    g2_wins INTEGER NOT NULL DEFAULT 0,
    g3_wins INTEGER NOT NULL DEFAULT 0,
    career_earnings INTEGER NOT NULL DEFAULT 0,
    created_year INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (former_jockey_id) REFERENCES jockeys(jockey_id)
);

-- 4. 騎手テーブル (Jockeys: 美浦30名、栗東30名、計60名、女性騎手含む、現役30年定員維持)
CREATE TABLE IF NOT EXISTS jockeys (
    jockey_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    gender TEXT NOT NULL DEFAULT 'male' CHECK (gender IN ('male', 'female')), -- 性別
    location TEXT NOT NULL CHECK (location IN ('美浦', '栗東')),
    age INTEGER NOT NULL,                        -- 年齢 (20〜50歳)
    debut_year INTEGER NOT NULL,                 -- デビュー年
    career_years INTEGER NOT NULL DEFAULT 1,     -- 騎手歴 (最大30年)
    is_active INTEGER NOT NULL DEFAULT 1,
    
    -- 能力値 (30.0〜90.0, 平均 50.0)
    skill REAL NOT NULL,                         -- 操縦技術・位置取り
    drive REAL NOT NULL,                         -- 直線の追い・推進力
    start_dash REAL NOT NULL,                    -- スタートダッシュ
    temperament_handling REAL NOT NULL,          -- 気性難カバー・折り合い
    
    -- 成績
    current_year_starts INTEGER NOT NULL DEFAULT 0,
    current_year_wins INTEGER NOT NULL DEFAULT 0,
    current_year_rides INTEGER NOT NULL DEFAULT 0,
    current_year_g1 INTEGER NOT NULL DEFAULT 0,
    current_year_g2 INTEGER NOT NULL DEFAULT 0,
    current_year_g3 INTEGER NOT NULL DEFAULT 0,
    current_year_earnings INTEGER NOT NULL DEFAULT 0,
    career_starts INTEGER NOT NULL DEFAULT 0,
    career_wins INTEGER NOT NULL DEFAULT 0,
    career_rides INTEGER NOT NULL DEFAULT 0,
    g1_wins INTEGER NOT NULL DEFAULT 0,
    g2_wins INTEGER NOT NULL DEFAULT 0,
    g3_wins INTEGER NOT NULL DEFAULT 0,
    career_earnings INTEGER NOT NULL DEFAULT 0
);

-- 5. 競走馬テーブル (Horses: 個体能力、遺伝情報、成績)
CREATE TABLE IF NOT EXISTS horses (
    horse_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,                   -- カタカナ
    sex TEXT NOT NULL CHECK (sex IN ('colt', 'filly', 'horse', 'mare', 'gelding')),
    birth_year INTEGER NOT NULL,
    age INTEGER NOT NULL,
    breeder_id INTEGER NOT NULL,
    owner_id INTEGER NOT NULL,
    trainer_id INTEGER,                          -- 所属厩舎 (現役時は必須)
    jockey_id INTEGER,                           -- 主戦騎手
    sire_id INTEGER,                             -- 父馬 ID (外部キー)
    dam_id INTEGER,                              -- 母馬 ID (外部キー)
    
    -- 状態フラグ
    is_active INTEGER NOT NULL DEFAULT 1,        -- 1:現役, 0:引退 (現役は最大8歳まで)
    is_sire INTEGER NOT NULL DEFAULT 0,          -- 1:種牡馬供用中
    is_dam INTEGER NOT NULL DEFAULT 0,           -- 1:繁殖牝馬供用中
    is_dead INTEGER NOT NULL DEFAULT 0,          -- 1:死亡・登録抹消 (※死亡ロジックは完全不使用)

    -- 遺伝特性 (3層構造)
    -- 1) 離散遺伝子 (ミオスタチン / MSTN)
    mstn_type TEXT NOT NULL CHECK (mstn_type IN ('C/C', 'C/T', 'T/T')),
    
    -- 2) ポリジーン (連続量 0.0〜100.0, 平均 50.0)
    speed REAL NOT NULL,                         -- 最高速度
    stamina REAL NOT NULL,                       -- 持久力
    acceleration REAL NOT NULL,                  -- 瞬発力
    temperament REAL NOT NULL,                   -- 気性
    durability REAL NOT NULL,                    -- 耐久力
    
    -- 3) 母系遺伝 (ミトコンドリアDNA / 母性効果)
    maternal_vitality REAL NOT NULL,             -- 心肺機能・底力補正 (0.0〜100.0)
    
    -- 成長・戦術
    growth_type TEXT NOT NULL CHECK (growth_type IN ('early', 'normal', 'late')),
    peak_age REAL NOT NULL,                      -- 能力ピーク年齢 (例: 3.0, 4.5, 5.5)
    current_ability_rate REAL NOT NULL DEFAULT 1.0, -- 現在の成長・加齢係数 (0.0〜1.0)
    running_style TEXT NOT NULL CHECK (running_style IN ('escape', 'leading', 'between', 'closing')),

    -- 競走成績
    prize_money INTEGER NOT NULL DEFAULT 0,           -- 生涯総賞金 (円)
    condition_prize_money INTEGER NOT NULL DEFAULT 0, -- 累積収得賞金 (出走順決定用)
    career_starts INTEGER NOT NULL DEFAULT 0,         -- 出走回数
    career_wins INTEGER NOT NULL DEFAULT 0,           -- 勝利数
    g1_wins INTEGER NOT NULL DEFAULT 0,               -- G1勝利数
    g2_wins INTEGER NOT NULL DEFAULT 0,               -- G2勝利数
    g3_wins INTEGER NOT NULL DEFAULT 0,               -- G3勝利数
    major_wins TEXT,                                  -- 主な勝ち鞍 (例: "東京優駿(G1), 皐月賞(G1)")

    FOREIGN KEY (breeder_id) REFERENCES breeders(breeder_id),
    FOREIGN KEY (owner_id) REFERENCES owners(owner_id),
    FOREIGN KEY (trainer_id) REFERENCES trainers(trainer_id),
    FOREIGN KEY (jockey_id) REFERENCES jockeys(jockey_id),
    FOREIGN KEY (sire_id) REFERENCES horses(horse_id),
    FOREIGN KEY (dam_id) REFERENCES horses(horse_id)
);


-- 4. 種牡馬管理テーブル (Sires)
CREATE TABLE IF NOT EXISTS sires (
    sire_id INTEGER PRIMARY KEY AUTOINCREMENT,
    horse_id INTEGER NOT NULL UNIQUE,
    breeder_id INTEGER NOT NULL,                 -- 繋養牧場
    sire_line TEXT NOT NULL,                     -- サイアーライン系統名 (保護判定用)
    annual_coverings INTEGER NOT NULL DEFAULT 0, -- 今年の種付け頭数
    max_coverings INTEGER NOT NULL DEFAULT 30,   -- 年間最大種付け頭数上限 (30頭)
    stud_fee INTEGER NOT NULL DEFAULT 1000000,   -- 種付け料 (円)
    is_active INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (horse_id) REFERENCES horses(horse_id),
    FOREIGN KEY (breeder_id) REFERENCES breeders(breeder_id)
);

-- 5. 繁殖牝馬管理テーブル (Dams)
CREATE TABLE IF NOT EXISTS dams (
    dam_id INTEGER PRIMARY KEY AUTOINCREMENT,
    horse_id INTEGER NOT NULL UNIQUE,
    breeder_id INTEGER NOT NULL,                 -- 繋養牧場
    consecutive_empty_years INTEGER NOT NULL DEFAULT 0, -- 連続不受胎年数
    is_active INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (horse_id) REFERENCES horses(horse_id),
    FOREIGN KEY (breeder_id) REFERENCES breeders(breeder_id)
);

-- 6. レース番組表テーブル (Races)
CREATE TABLE IF NOT EXISTS races (
    race_id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    week INTEGER NOT NULL,                       -- 1〜48週
    track_id TEXT NOT NULL CHECK (track_id IN ('A', 'B', 'C', 'D')),
    name TEXT NOT NULL,
    grade TEXT NOT NULL CHECK (grade IN ('G1', 'G2', 'G3', 'L', 'OP', 'COND_3W', 'COND_2W', 'COND_1W', 'MAIDEN', 'NEWCOMER')),
    surface TEXT NOT NULL CHECK (surface IN ('turf', 'dirt')),
    distance INTEGER NOT NULL,
    age_restriction TEXT NOT NULL,               -- '2yo', '3yo', '3yo_up', '4yo_up'
    sex_restriction TEXT NOT NULL,               -- 'mixed', 'filly_mare', 'colt_horse'
    condition TEXT NOT NULL DEFAULT 'good',      -- 'good' (良馬場固定)
    full_gate INTEGER NOT NULL DEFAULT 18,
    is_trial INTEGER NOT NULL DEFAULT 0,         -- トライアル競走フラグ
    target_g1_name TEXT                          -- トライアルの場合の対象G1名
);

-- 7. レース結果テーブル (Results)
CREATE TABLE IF NOT EXISTS results (
    result_id INTEGER PRIMARY KEY AUTOINCREMENT,
    race_id INTEGER NOT NULL,
    horse_id INTEGER NOT NULL,
    jockey_id INTEGER,                           -- 騎乗騎手
    trainer_id INTEGER,                          -- 所属厩舎
    finish_position INTEGER NOT NULL,
    finish_time REAL NOT NULL,                   -- 走破タイム (秒)
    margin TEXT,                                 -- 着差表現 (例: "1 1/4", "クビ", "ハナ")
    time_diff REAL NOT NULL DEFAULT 0.0,         -- 1着とのタイム差 (秒)
    prize_awarded INTEGER NOT NULL DEFAULT 0,    -- 獲得本賞金
    running_style_used TEXT,                     -- 実際のレース脚質
    replay_data_json TEXT,                       -- 0.1秒ごとの時系列位置データ (JSON)
    FOREIGN KEY (race_id) REFERENCES races(race_id),
    FOREIGN KEY (horse_id) REFERENCES horses(horse_id),
    FOREIGN KEY (jockey_id) REFERENCES jockeys(jockey_id),
    FOREIGN KEY (trainer_id) REFERENCES trainers(trainer_id)
);

-- インデックス作成 (検索・参照の高速化)
CREATE INDEX IF NOT EXISTS idx_horses_owner ON horses(owner_id);
CREATE INDEX IF NOT EXISTS idx_horses_breeder ON horses(breeder_id);
CREATE INDEX IF NOT EXISTS idx_horses_trainer ON horses(trainer_id);
CREATE INDEX IF NOT EXISTS idx_horses_jockey ON horses(jockey_id);
CREATE INDEX IF NOT EXISTS idx_horses_active ON horses(is_active);
CREATE INDEX IF NOT EXISTS idx_horses_sire ON horses(sire_id);
CREATE INDEX IF NOT EXISTS idx_horses_dam ON horses(dam_id);
CREATE INDEX IF NOT EXISTS idx_sires_horse ON sires(horse_id);
CREATE INDEX IF NOT EXISTS idx_sires_breeder ON sires(breeder_id);
CREATE INDEX IF NOT EXISTS idx_dams_horse ON dams(horse_id);
CREATE INDEX IF NOT EXISTS idx_dams_breeder ON dams(breeder_id);
CREATE INDEX IF NOT EXISTS idx_results_race ON results(race_id);
CREATE INDEX IF NOT EXISTS idx_results_horse ON results(horse_id);
CREATE INDEX IF NOT EXISTS idx_results_jockey ON results(jockey_id);
CREATE INDEX IF NOT EXISTS idx_results_trainer ON results(trainer_id);
"""
