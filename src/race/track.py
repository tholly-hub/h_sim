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
        name='競馬場A（阪神/京都型）',
        turn='right',
        size_type='large',
        straight_length=400.0,
        has_slope=False,
        slope_type='flat',
        description='右回り・大箱 / 直線 400m / 平坦。スピードと持続力が要求される王道コース。',
    ),
    'B': TrackInfo(
        track_id='B',
        name='競馬場B（東京型）',
        turn='left',
        size_type='large',
        straight_length=520.0,
        has_slope=True,
        slope_type='gentle_slope',
        description='左回り・大箱 / 直線 520m / 坂あり。長い直線とだらだら坂により、瞬発力とスタミナが問われる。',
    ),
    'C': TrackInfo(
        track_id='C',
        name='競馬場C（中山型）',
        turn='right',
        size_type='small',
        straight_length=310.0,
        has_slope=True,
        slope_type='steep_slope',
        description='右回り・小箱 / 直線 310m / 急坂あり。小回り適性とゴール前急坂を乗り越えるパワー・耐久力が必須。',
    ),
    'D': TrackInfo(
        track_id='D',
        name='競馬場D（ローカル型）',
        turn='right',
        size_type='small',
        straight_length=300.0,
        has_slope=False,
        slope_type='flat',
        description='右回り・小箱 / 直線 300m / 平坦。先行力と器用さ、小回り立ち回りが重視される。',
    ),
}


def get_track_info(track_id: str) -> TrackInfo:
    """指定IDの競馬場情報を取得"""
    return TRACK_CONFIGS.get(track_id, TRACK_CONFIGS['A'])
