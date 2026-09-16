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
        if db_path is None:
            self.db_path = get_config().get_db_path()
        else:
            self.db_path = Path(db_path).resolve()

        # ディレクトリが存在しない場合は自動作成
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def get_connection(self) -> sqlite3.Connection:
        """
        SQLite 接続を生成して基本設定を適用
        Row オブジェクトでカラム名アクセス可能
        """
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        
        # 外部キー制約の有効化
        conn.execute("PRAGMA foreign_keys = ON;")
        # パフォーマンス向上のための WAL モード (Write-Ahead Logging)
        conn.execute("PRAGMA journal_mode = WAL;")
        # 通常の同期モード (安全性と速度のバランス)
        conn.execute("PRAGMA synchronous = NORMAL;")

        self._migrate_schema(conn)
        return conn

    def _migrate_schema(self, conn: sqlite3.Connection) -> None:
        """既存DBに対するカラム追加などの自動マイグレーション"""
        try:
            # resultsテーブルが存在するか確認
            table_check = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='results'"
            ).fetchone()
            if table_check:
                # gate_number カラムが存在するか確認
                cols = [col["name"] for col in conn.execute("PRAGMA table_info(results)").fetchall()]
                if "gate_number" not in cols:
                    conn.execute("ALTER TABLE results ADD COLUMN gate_number INTEGER NOT NULL DEFAULT 1;")
                if "last_3f" not in cols:
                    conn.execute("ALTER TABLE results ADD COLUMN last_3f REAL DEFAULT 0.0;")
                if "odds" not in cols:
                    conn.execute("ALTER TABLE results ADD COLUMN odds REAL DEFAULT 0.0;")

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
        with self.session() as conn:
            if force_recreate:
                # 外部キーを一時無効化して既存の全テーブルを確実に削除
                conn.execute("PRAGMA foreign_keys = OFF;")
                existing_tables = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ).fetchall()
                for t in existing_tables:
                    conn.execute(f"DROP TABLE IF EXISTS \"{t['name']}\";")
                conn.execute("PRAGMA foreign_keys = ON;")
            
            # スキーマ DDL スクリプトの一括実行
            conn.executescript(DDL_STATEMENTS)


_global_db_instance: Optional[Database] = None


def get_db(db_path: Optional[Path | str] = None) -> Database:
    """グローバルまたは指定パスの Database インスタンスを取得"""
    global _global_db_instance
    if db_path is not None:
        return Database(db_path)
    if _global_db_instance is None:
        _global_db_instance = Database()
    return _global_db_instance
