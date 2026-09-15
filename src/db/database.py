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
        return conn

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
