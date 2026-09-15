"""
クロスプラットフォーム対応 パスおよびシステム設定管理モジュール
Mac / Windows 両対応 (pathlib.Path 使用)
Google Drive や OneDrive 等のクラウド同期フォルダへの DB 配置・変更に対応
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass
class AppConfig:
    """アプリケーション設定データクラス"""

    # データベースファイルのパス (文字列形式で保持し、利用時に Path 化)
    db_path: str
    # シミュレーション年数・速度等の基本設定
    random_seed: Optional[int] = 42
    auto_vacuum: bool = True

    def get_db_path(self) -> Path:
        """プラットフォームに応じた pathlib.Path オブジェクトを取得"""
        return Path(self.db_path).resolve()


class ConfigManager:
    """設定ファイルのロード・更新・保存を管理するクラス"""

    DEFAULT_CONFIG_DIR_NAME = "config"
    DEFAULT_CONFIG_FILE_NAME = "settings.json"
    DEFAULT_DATA_DIR_NAME = "data"
    DEFAULT_DB_FILE_NAME = "horse_racing_sim.db"

    def __init__(self, base_dir: Optional[Path | str] = None, config_file: Optional[Path | str] = None):
        """
        Args:
            base_dir: プロジェクトのルートディレクトリ。未指定の場合はこのファイルの2階層上。
            config_file: 設定JSONファイルのパス。未指定の場合は base_dir/config/settings.json
        """
        if base_dir is None:
            # src/core/config.py -> 3つ上がプロジェクトルート
            self.base_dir = Path(__file__).resolve().parent.parent.parent
        else:
            self.base_dir = Path(base_dir).resolve()

        if config_file is None:
            self.config_path = self.base_dir / self.DEFAULT_CONFIG_DIR_NAME / self.DEFAULT_CONFIG_FILE_NAME
        else:
            self.config_path = Path(config_file).resolve()

        self._config: Optional[AppConfig] = None
        self.load()

    def get_default_db_path(self) -> Path:
        """デフォルトのSQLiteデータベースファイル配置パスを返却"""
        return self.base_dir / self.DEFAULT_DATA_DIR_NAME / self.DEFAULT_DB_FILE_NAME

    def load(self) -> AppConfig:
        """設定ファイルを読み込み。存在しない場合はデフォルトを作成して保存"""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._config = AppConfig(**data)
                return self._config
            except Exception as e:
                # 破損や互換性問題がある場合はデフォルトにフォールバック
                print(f"[警告] 設定ファイルの読み込みに失敗しました ({e})。デフォルト設定を使用します。")

        default_db = self.get_default_db_path()
        self._config = AppConfig(db_path=str(default_db))
        self.save()
        return self._config

    def save(self) -> None:
        """現在の設定をJSONファイルへ保存"""
        if self._config is None:
            return

        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(asdict(self._config), f, indent=4, ensure_ascii=False)

    @property
    def config(self) -> AppConfig:
        """現在の設定インスタンスを取得"""
        if self._config is None:
            self.load()
        return self._config  # type: ignore

    def get_db_path(self) -> Path:
        """設定されている SQLite データベースの Path を取得"""
        return self.config.get_db_path()

    def set_db_path(self, new_path: Path | str) -> None:
        """
        データベースファイルの保存先を変更し、設定ファイルに即座に反映
        Google Drive や外部ストレージ等のフォルダパスを指定可能
        """
        p = Path(new_path).resolve()
        # 保存先ディレクトリが存在しない場合は作成
        p.parent.mkdir(parents=True, exist_ok=True)
        self.config.db_path = str(p)
        self.save()


# グローバルシングルトンインスタンス
_global_config_manager: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """共通 ConfigManager インスタンスを取得"""
    global _global_config_manager
    if _global_config_manager is None:
        _global_config_manager = ConfigManager()
    return _global_config_manager
