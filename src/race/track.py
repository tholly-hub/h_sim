"""
競馬場モデル (Track Models)
仕様書準拠の4大競馬場 (A, B, C, D) の構造・コース特性
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class TrackInfo:
    """競馬場のコース特性"""
    track_id: str                      # 'A', 'B', 'C', 'D'
    name: str                          # 表示名
    turn: str                          # 'right' (右回り) / 'left' (左回り)
    size_type: str                     # 'large' (大箱) / 'small' (小箱)
    straight_length: float             # 直線距離 (m)
    has_slope: bool                    # 坂の有無
    slope_type: str                    # 'flat', 'gentle_slope', 'steep_slope'
    description: str                   # コース概要


TRACK_CONFIGS: Dict[str, TrackInfo] = {
    'A': TrackInfo(
        track_id='A',
        name='中京競馬場',
        turn='left',
        size_type='small',
        straight_length=412.5,
        has_slope=True,
        slope_type='gentle_slope',
        description='左回り・小回り / 直線 412.5m / 坂あり。小回りながら直線に上り坂があり、タフな末脚が求められる。',
    ),
    'B': TrackInfo(
        track_id='B',
        name='東京競馬場',
        turn='left',
        size_type='large',
        straight_length=525.9,
        has_slope=True,
        slope_type='gentle_slope',
        description='左回り・大箱 / 直線 525.9m / 坂あり。日本屈指の雄大な大箱コース。長い直線とだらだら坂で底力が問われる。',
    ),
    'C': TrackInfo(
        track_id='C',
        name='中山競馬場',
        turn='right',
        size_type='large',
        straight_length=310.0,
        has_slope=True,
        slope_type='steep_slope',
        description='右回り・大箱 / 直線 310.0m / 急坂あり。ゴール前の急坂とトリッキーなコース形態で、パワーと持続力が必須。',
    ),
    'D': TrackInfo(
        track_id='D',
        name='小倉競馬場',
        turn='right',
        size_type='small',
        straight_length=293.0,
        has_slope=False,
        slope_type='flat',
        description='右回り・平坦 / 直線 293.0m / 平坦。平坦で小回りのスピードコース。先行力と立ち回りの器用さが重視される。',
    ),
}


def get_track_info(track_id: str) -> TrackInfo:
    """指定IDの競馬場情報を取得"""
    return TRACK_CONFIGS.get(track_id, TRACK_CONFIGS['A'])
