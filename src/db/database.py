"""
SQLite データベース接続・トランザクション管理モジュール
WAL モード対応、外部キー制約有効化、安全なファイルパス管理
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

from src.core.config import get_config
from src.db.schema import DDL_STATEMENTS


class Database:
    """SQLite データベース管理クラス"""

    def __init__(self, db_path: Optional[Path | str] = None):
        self.is_memory = False
        self._keepalive_conn: Optional[sqlite3.Connection] = None
        self._mem_uri: Optional[str] = None
        self._migrated = False

        if db_path is None:
            self.db_path = get_config().get_db_path()
        elif str(db_path).startswith(":memory:"):
            self.is_memory = True
            import uuid
            self._mem_uri = f"file:mem_{uuid.uuid4().hex}?mode=memory&cache=shared"
            self.db_path = ":memory:"
            # 共有メモリが破棄されないようキープアライブ接続を保持
            self._keepalive_conn = sqlite3.connect(self._mem_uri, uri=True)
            self._keepalive_conn.execute("PRAGMA foreign_keys = ON;")
        else:
            self.db_path = Path(db_path).resolve()
            # ディレクトリが存在しない場合は自動作成
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def get_connection(self) -> sqlite3.Connection:
        """
        SQLite 接続を生成して基本設定を適用
        Row オブジェクトでカラム名アクセス可能
        """
        if self.is_memory and self._mem_uri:
            conn = sqlite3.connect(self._mem_uri, uri=True, timeout=30.0)
        else:
            conn = sqlite3.connect(str(self.db_path), timeout=60.0)
            # ビジータムアウトを設定（ファイルロック競合防止）
            conn.execute("PRAGMA busy_timeout = 60000;")
            
            # クラウド同期ドライブ（Google Drive等）での WAL エラー防止・安全なフォールバック
            try:
                conn.execute("PRAGMA journal_mode = DELETE;")
                conn.execute("PRAGMA synchronous = NORMAL;")
            except sqlite3.OperationalError:
                pass

        conn.row_factory = sqlite3.Row
        
        # 外部キー制約の有効化
        try:
            conn.execute("PRAGMA foreign_keys = ON;")
        except sqlite3.OperationalError:
            pass

        if not self._migrated:
            self._migrate_schema(conn)
            self._migrated = True
        return conn

    def _migrate_schema(self, conn: sqlite3.Connection) -> None:
        """既存DBに対するカラム追加などの自動マイグレーション"""
        try:
            # resultsテーブルが存在するか確認
            table_check = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='results'"
            ).fetchone()
            if table_check:
                # results カラムが存在するか確認
                cols = [col["name"] for col in conn.execute("PRAGMA table_info(results)").fetchall()]
                if "gate_number" not in cols:
                    conn.execute("ALTER TABLE results ADD COLUMN gate_number INTEGER NOT NULL DEFAULT 1;")
                if "last_3f" not in cols:
                    conn.execute("ALTER TABLE results ADD COLUMN last_3f REAL DEFAULT 0.0;")
                if "odds" not in cols:
                    conn.execute("ALTER TABLE results ADD COLUMN odds REAL DEFAULT 0.0;")
                if "carried_weight" not in cols:
                    conn.execute("ALTER TABLE results ADD COLUMN carried_weight REAL NOT NULL DEFAULT 55.0;")
                if "running_style_used" not in cols:
                    conn.execute("ALTER TABLE results ADD COLUMN running_style_used TEXT;")
                if "replay_data_json" not in cols:
                    conn.execute("ALTER TABLE results ADD COLUMN replay_data_json TEXT;")

                # sires テーブルのマイグレーション
                sires_check = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='sires'"
                ).fetchone()
                if sires_check:
                    s_cols = [col["name"] for col in conn.execute("PRAGMA table_info(sires)").fetchall()]
                    if "start_year" not in s_cols:
                        conn.execute("ALTER TABLE sires ADD COLUMN start_year INTEGER NOT NULL DEFAULT 1;")
                    if "is_imported" not in s_cols:
                        conn.execute("ALTER TABLE sires ADD COLUMN is_imported INTEGER NOT NULL DEFAULT 0;")
                    if "debut_year" not in s_cols:
                        conn.execute("ALTER TABLE sires ADD COLUMN debut_year INTEGER;")

                # dams テーブルのマイグレーション
                dams_check = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='dams'"
                ).fetchone()
                if dams_check:
                    d_cols = [col["name"] for col in conn.execute("PRAGMA table_info(dams)").fetchall()]
                    if "start_year" not in d_cols:
                        conn.execute("ALTER TABLE dams ADD COLUMN start_year INTEGER NOT NULL DEFAULT 1;")
                    if "debut_year" not in d_cols:
                        conn.execute("ALTER TABLE dams ADD COLUMN debut_year INTEGER;")

                # races テーブルのマイグレーション
                races_check = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='races'"
                ).fetchone()
                if races_check:
                    r_cols = [col["name"] for col in conn.execute("PRAGMA table_info(races)").fetchall()]
                    if "weight_type" not in r_cols:
                        conn.execute("ALTER TABLE races ADD COLUMN weight_type TEXT NOT NULL DEFAULT '定量';")

                # gate_number が全頭 1 に固定化されているレースの自動修復
                stuck_races = conn.execute(
                    """
                    SELECT race_id, COUNT(*) as cnt 
                    FROM results 
                    GROUP BY race_id 
                    HAVING COUNT(*) > 1 AND MAX(gate_number) = 1
                    """
                ).fetchall()

                if stuck_races:
                    import random
                    for r in stuck_races:
                        race_id = r["race_id"]
                        horse_rows = conn.execute(
                            "SELECT horse_id FROM results WHERE race_id = ? ORDER BY horse_id ASC",
                            (race_id,),
                        ).fetchall()
                        total = len(horse_rows)
                        rng = random.Random(race_id)
                        gates = list(range(1, total + 1))
                        rng.shuffle(gates)

                        for idx, h_row in enumerate(horse_rows):
                            conn.execute(
                                "UPDATE results SET gate_number = ? WHERE race_id = ? AND horse_id = ?",
                                (gates[idx], race_id, h_row["horse_id"]),
                            )
                # jockeysテーブルのカラム補完
                j_check = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='jockeys'"
                ).fetchone()
                if j_check:
                    j_cols = [col["name"] for col in conn.execute("PRAGMA table_info(jockeys)").fetchall()]
                    if "is_free" not in j_cols:
                        conn.execute("ALTER TABLE jockeys ADD COLUMN is_free INTEGER NOT NULL DEFAULT 0;")
                    if "growth_type" not in j_cols:
                        conn.execute("ALTER TABLE jockeys ADD COLUMN growth_type TEXT NOT NULL DEFAULT 'standard';")
                    if "trainer_id" not in j_cols:
                        conn.execute("ALTER TABLE jockeys ADD COLUMN trainer_id INTEGER;")
                    if "experience" not in j_cols:
                        conn.execute("ALTER TABLE jockeys ADD COLUMN experience REAL NOT NULL DEFAULT 0.0;")
                    if "stamina" not in j_cols:
                        conn.execute("ALTER TABLE jockeys ADD COLUMN stamina REAL NOT NULL DEFAULT 50.0;")

                # trainersテーブルのカラム補完
                t_check = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='trainers'"
                ).fetchone()
                if t_check:
                    t_cols = [col["name"] for col in conn.execute("PRAGMA table_info(trainers)").fetchall()]
                    if "skill_level" not in t_cols:
                        conn.execute("ALTER TABLE trainers ADD COLUMN skill_level REAL NOT NULL DEFAULT 50.0;")

                # horsesテーブルのカラム補完
                h_check = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='horses'"
                ).fetchone()
                if h_check:
                    h_cols = [col["name"] for col in conn.execute("PRAGMA table_info(horses)").fetchall()]
                    if "coat_color" not in h_cols:
                        conn.execute("ALTER TABLE horses ADD COLUMN coat_color TEXT NOT NULL DEFAULT '鹿毛';")
                    if "coat_genotype" not in h_cols:
                        conn.execute("ALTER TABLE horses ADD COLUMN coat_genotype TEXT NOT NULL DEFAULT 'E/E A/A G/g W/w Cr/cr';")
                    if "retired_year" not in h_cols:
                        conn.execute("ALTER TABLE horses ADD COLUMN retired_year INTEGER;")
                        conn.execute("CREATE INDEX IF NOT EXISTS idx_horses_retired_year ON horses(retired_year);")

                # siresテーブルのカラム補完
                s_check = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='sires'"
                ).fetchone()
                if s_check:
                    s_cols = [col["name"] for col in conn.execute("PRAGMA table_info(sires)").fetchall()]
                    if "is_foreign" not in s_cols:
                        conn.execute("ALTER TABLE sires ADD COLUMN is_foreign INTEGER NOT NULL DEFAULT 0;")
                    if "is_new" not in s_cols:
                        conn.execute("ALTER TABLE sires ADD COLUMN is_new INTEGER NOT NULL DEFAULT 0;")
                    if "consecutive_zero_win_years" not in s_cols:
                        conn.execute("ALTER TABLE sires ADD COLUMN consecutive_zero_win_years INTEGER NOT NULL DEFAULT 0;")

                # assistant_trainersテーブルの自動作成
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS assistant_trainers (
                        assistant_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        jockey_id INTEGER NOT NULL UNIQUE,
                        trainer_id INTEGER NOT NULL,
                        name TEXT NOT NULL,
                        age INTEGER NOT NULL,
                        career_wins INTEGER NOT NULL DEFAULT 0,
                        g1_wins INTEGER NOT NULL DEFAULT 0,
                        is_active INTEGER NOT NULL DEFAULT 1,
                        FOREIGN KEY (jockey_id) REFERENCES jockeys(jockey_id),
                        FOREIGN KEY (trainer_id) REFERENCES trainers(trainer_id)
                    );
                """)

                # system_statusテーブルの自動作成 & 初期レコード補完
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS system_status (
                        key TEXT PRIMARY KEY,
                        value_int INTEGER,
                        value_text TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                cur_y = conn.execute("SELECT value_int FROM system_status WHERE key = 'current_year'").fetchone()
                if not cur_y or cur_y[0] is None:
                    # resultsテーブルから最新年・週を推測
                    res_row = None
                    try:
                        res_row = conn.execute("""
                            SELECT rc.year, rc.week
                            FROM results r
                            JOIN races rc ON r.race_id = rc.race_id
                            ORDER BY rc.year DESC, rc.week DESC
                            LIMIT 1
                        """).fetchone()
                    except Exception:
                        pass
                    init_y = res_row["year"] if res_row else 1
                    init_w = res_row["week"] if res_row else 1
                    conn.execute(
                        "INSERT INTO system_status (key, value_int) VALUES ('current_year', ?), ('current_week', ?) "
                        "ON CONFLICT(key) DO UPDATE SET value_int = excluded.value_int",
                        (init_y, init_w),
                    )
                # 既存アクティブ海外種牡馬の能力・世代補正（新仕様への同期）
                try:
                    active_dom_sires = conn.execute("""
                        SELECT h.speed, h.stamina, h.acceleration, h.maternal_vitality, h.temperament, h.durability, h.generation
                        FROM sires s
                        JOIN horses h ON s.horse_id = h.horse_id
                        WHERE s.is_active = 1 AND s.is_foreign = 0
                        ORDER BY (h.speed + h.stamina + h.acceleration) DESC
                        LIMIT 10
                    """).fetchall()
                    if active_dom_sires:
                        avg_spd = sum(r["speed"] for r in active_dom_sires) / len(active_dom_sires)
                        avg_sta = sum(r["stamina"] for r in active_dom_sires) / len(active_dom_sires)
                        avg_acc = sum(r["acceleration"] for r in active_dom_sires) / len(active_dom_sires)
                        avg_vit = sum(r["maternal_vitality"] for r in active_dom_sires) / len(active_dom_sires)
                        avg_temp = sum(r["temperament"] for r in active_dom_sires) / len(active_dom_sires)
                        avg_dura = sum(r["durability"] for r in active_dom_sires) / len(active_dom_sires)
                        cur_max_gen = max((r["generation"] for r in active_dom_sires if r["generation"]), default=1)

                        # アクティブな海外種牡馬で世代が古い、または能力値が国内平均未満のものを補正
                        foreign_sires = conn.execute("""
                            SELECT s.sire_id, s.horse_id, s.generation as s_gen, h.speed, h.stamina, h.acceleration, h.generation as h_gen
                            FROM sires s
                            JOIN horses h ON s.horse_id = h.horse_id
                            WHERE s.is_foreign = 1 AND s.is_active = 1
                        """).fetchall()
                        for fs in foreign_sires:
                            new_gen = max(fs["s_gen"] or 1, cur_max_gen)
                            new_spd = max(fs["speed"], round(avg_spd * 1.10, 1))
                            new_sta = max(fs["stamina"], round(avg_sta * 1.10, 1))
                            new_acc = max(fs["acceleration"], round(avg_acc * 1.10, 1))
                            new_vit = round(max(20.0, avg_vit * 1.10), 1)
                            new_temp = round(max(20.0, avg_temp * 1.10), 1)
                            new_dura = round(max(20.0, avg_dura * 1.10), 1)

                            conn.execute("""
                                UPDATE horses
                                SET generation = ?, speed = ?, stamina = ?, acceleration = ?,
                                    maternal_vitality = ?, temperament = ?, durability = ?
                                WHERE horse_id = ?
                            """, (new_gen, new_spd, new_sta, new_acc, new_vit, new_temp, new_dura, fs["horse_id"]))
                            conn.execute("UPDATE sires SET generation = ? WHERE sire_id = ?", (new_gen, fs["sire_id"]))
                except Exception:
                    pass

                # 過去に出走した引退馬の trainer_id / jockey_id がクリアされている場合の自動復元
                try:
                    conn.execute("""
                        UPDATE horses
                        SET trainer_id = (
                            SELECT res.trainer_id 
                            FROM results res 
                            WHERE res.horse_id = horses.horse_id 
                              AND res.trainer_id IS NOT NULL 
                            ORDER BY res.result_id DESC 
                            LIMIT 1
                        ),
                        jockey_id = (
                            SELECT res.jockey_id 
                            FROM results res 
                            WHERE res.horse_id = horses.horse_id 
                              AND res.jockey_id IS NOT NULL 
                            ORDER BY res.result_id DESC 
                            LIMIT 1
                        )
                        WHERE trainer_id IS NULL AND career_starts > 0;
                    """)
                except Exception:
                    pass

                # 検索高速化インデックスの作成
                try:
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_races_year_week ON races(year, week);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_races_track ON races(track_id);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_races_grade ON races(grade);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_results_race_gate ON results(race_id, gate_number);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_results_finish ON results(race_id, finish_position);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_results_race ON results(race_id);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_results_horse ON results(horse_id);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_results_jockey ON results(jockey_id);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_results_trainer ON results(trainer_id);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_horses_name ON horses(name);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_horses_active ON horses(is_active);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_horses_sire ON horses(sire_id);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_horses_dam ON horses(dam_id);")
                except Exception:
                    pass
        except Exception as e:
            pass

    @contextmanager
    def session(self) -> Generator[sqlite3.Connection, None, None]:
        """トランザクション管理を行うコンテキストマネージャ"""
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize_schema(self, force_recreate: bool = False) -> None:
        """
        データベーススキーマ（DDL）を実行
        force_recreate が True の場合、既存テーブルを全削除して再作成
        """
        conn = self.get_connection()
        try:
            if force_recreate:
                conn.isolation_level = None
                conn.execute("PRAGMA foreign_keys = OFF;")
                existing_tables = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ).fetchall()
                for t in existing_tables:
                    conn.execute(f"DROP TABLE IF EXISTS \"{t['name']}\";")
                conn.execute("PRAGMA foreign_keys = ON;")
            
            conn.executescript(DDL_STATEMENTS)
            conn.commit()
        finally:
            conn.close()


_global_db_instance: Optional[Database] = None


def get_db(db_path: Optional[Path | str] = None) -> Database:
    """グローバルまたは指定パスの Database インスタンスを取得"""
    global _global_db_instance
    if db_path is not None:
        return Database(db_path)
    if _global_db_instance is None:
        _global_db_instance = Database()
    return _global_db_instance
