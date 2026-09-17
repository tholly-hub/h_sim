"""
競馬場モデル (Track Models)
JRA 8場（東京・中山・阪神・京都・中京・福島・新潟・小倉）
地方 4場（大井・川崎・船橋・盛岡）の構造・コース特性・枝線/引き込み線情報
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class TrackInfo:
    """競馬場のコース特性"""
    track_id: str                      # 識別ID ('TOKYO', 'NAKAYAMA', 'HANSHIN', etc.)
    name: str                          # 表示名
    org: str                           # 'JRA' / 'NAR' (地方)
    turn: str                          # 'right' (右回り) / 'left' (左回り) / 'straight'
    size_type: str                     # 'large' (大箱) / 'small' (小回り) / 'medium'
    straight_length: float             # 主要コース直線距離 (m)
    has_slope: bool                    # 坂の有無
    slope_type: str                    # 'flat', 'gentle_slope', 'steep_slope'
    has_turf: bool                     # 芝コースの有無
    has_dirt: bool                     # ダートコースの有無
    description: str                   # コース概要
    chutes: Dict[int, str] = field(default_factory=dict)  # 距離別スタート地点・引き込み線/枝線情報


TRACK_CONFIGS: Dict[str, TrackInfo] = {
    # -------------------------------------------------------------------------
    # JRA 8場
    # -------------------------------------------------------------------------
    'TOKYO': TrackInfo(
        track_id='TOKYO',
        name='東京競馬場',
        org='JRA',
        turn='left',
        size_type='large',
        straight_length=525.9,
        has_slope=True,
        slope_type='gentle_slope',
        has_turf=True,
        has_dirt=True,
        description='左回り・大箱 / 直線 525.9m / だらだら坂あり。日本屈指の雄大な大箱コース。長い直線と高低差2mの上り坂で真の地力が問われる。',
        chutes={
            1400: '向正面奥引き込み線（芝スタート）',
            1600: '向正面奥引き込み線（ダート・芝ともに直線スタート）',
            1800: '1〜2コーナー中間奥の引き込み線（直線スタート）',
            2000: '1〜2コーナー奥ポケット（大欅の向こう、直線スタートから本線合流）',
            2400: 'スタンド前直線のホームストレッチ奥（直線スタート）',
        },
    ),
    'NAKAYAMA': TrackInfo(
        track_id='NAKAYAMA',
        name='中山競馬場',
        org='JRA',
        turn='right',
        size_type='large',
        straight_length=310.0,
        has_slope=True,
        slope_type='steep_slope',
        has_turf=True,
        has_dirt=True,
        description='右回り・大箱 / 直線 310.0m / 急坂あり。ゴール前に高低差2.2mの急坂。おにぎり型のトリッキーな起伏と小回りで先行力・持続力が必須。',
        chutes={
            1200: '向正面奥引き込み線（下り坂直線スタート）',
            1600: '1コーナー奥ポケット（外回り専用枝線からスタート）',
            1800: 'スタンド前直線坂下（直線スタート）',
            2000: 'スタンド前直線の急坂手前（直線スタート）',
            2500: '外回り向正面奥引き込み線（有馬記念の舞台）',
        },
    ),
    'HANSHIN': TrackInfo(
        track_id='HANSHIN',
        name='阪神競馬場',
        org='JRA',
        turn='right',
        size_type='large',
        straight_length=473.6,
        has_slope=True,
        slope_type='steep_slope',
        has_turf=True,
        has_dirt=True,
        description='右回り・大箱外回り(473.6m)/内回り(356.5m) / ゴール前急坂。雄大な外回りとタフな内回り、直線の急坂が激闘を生む。',
        chutes={
            1400: '向正面奥引き込み線（内回り直線スタート）',
            1600: '向正面奥引き込み線（外回り専用枝線直線スタート）',
            1800: 'スタンド前直線（内回り）',
            2000: 'スタンド前直線坂下（内回り直線スタート）',
            2200: 'スタンド前直線正面（外回り）',
        },
    ),
    'KYOTO': TrackInfo(
        track_id='KYOTO',
        name='京都競馬場',
        org='JRA',
        turn='right',
        size_type='large',
        straight_length=404.0,
        has_slope=True,
        slope_type='gentle_slope',
        has_turf=True,
        has_dirt=True,
        description='右回り・外回り(404m)/内回り(328m) / 淀の坂あり・直線平坦。3コーナーの淀の坂（登り降り）の立ち回りと平坦直線の末脚勝負。',
        chutes={
            1200: '向正面直線（平坦スタート）',
            1400: '向正面奥引き込み線（外回り）',
            1600: '向正面奥引き込み線（外回り専用枝線スタート）',
            1800: '2コーナー奥引き込み線（直線スタート）',
            2000: 'スタンド前直線（内回り）',
            3000: '向正面直線奥（菊花賞の舞台、坂を2度越える）',
            3200: '向正面奥引き込み線（天皇賞・春の舞台）',
        },
    ),
    'CHUKYO': TrackInfo(
        track_id='CHUKYO',
        name='中京競馬場',
        org='JRA',
        turn='left',
        size_type='medium',
        straight_length=412.5,
        has_slope=True,
        slope_type='steep_slope',
        has_turf=True,
        has_dirt=True,
        description='左回り・中箱 / 直線 412.5m / 急坂あり。小回りから改装され長い直線とゴール前2.0mの急坂を備えたタフなコース。',
        chutes={
            1200: '向正面奥引き込み線（直線スタート）',
            1600: '向正面奥引き込み線（直線スタート）',
            2000: 'スタンド前直線坂下（直線スタート）',
            2200: 'スタンド前直線（直線スタート）',
        },
    ),
    'FUKUSHIMA': TrackInfo(
        track_id='FUKUSHIMA',
        name='福島競馬場',
        org='JRA',
        turn='right',
        size_type='small',
        straight_length=292.0,
        has_slope=True,
        slope_type='gentle_slope',
        has_turf=True,
        has_dirt=True,
        description='右回り・小回り / 直線 292.0m / 起伏・スパイラルカーブ。小回りながら高低差があり、トリッキーな立ち回りが要求される。',
        chutes={
            1200: '向正面奥引き込み線（下り坂直線スタート）',
            1800: 'スタンド前直線坂上（直線スタート）',
            2000: 'スタンド前直線坂下（直線スタート）',
        },
    ),
    'NIIGATA': TrackInfo(
        track_id='NIIGATA',
        name='新潟競馬場',
        org='JRA',
        turn='left',
        size_type='large',
        straight_length=659.0,
        has_slope=False,
        slope_type='flat',
        has_turf=True,
        has_dirt=True,
        description='左回り・日本最長直線 659.0m(外回り) / 平坦。日本唯一の芝1000m完全直線コースと、雄大な外回りコースを誇る。',
        chutes={
            1000: '第4コーナー奥からゴールまで一直線の専用直線枝線（アイビスSDの舞台）',
            1600: '向正面奥引き込み線（外回り直線スタート）',
            1800: '向正面直線（内回り）',
            2000: '向正面奥引き込み線（外回り直線スタート）',
        },
    ),
    'KOKURA': TrackInfo(
        track_id='KOKURA',
        name='小倉競馬場',
        org='JRA',
        turn='right',
        size_type='small',
        straight_length=293.0,
        has_slope=False,
        slope_type='flat',
        has_turf=True,
        has_dirt=True,
        description='右回り・平坦小回り / 直線 293.0m / スパイラルカーブ。スピードが乗りやすい平坦スピーディな競馬場。',
        chutes={
            1200: '2コーナー奥引き込み線（直線スタート）',
            1800: 'スタンド前直線（直線スタート）',
            2000: 'スタンド前直線（直線スタート）',
        },
    ),

    # -------------------------------------------------------------------------
    # 地方 (NAR) 4場
    # -------------------------------------------------------------------------
    'OI': TrackInfo(
        track_id='OI',
        name='大井競馬場',
        org='NAR',
        turn='right',
        size_type='large',
        straight_length=386.0,
        has_slope=False,
        slope_type='flat',
        has_turf=False,
        has_dirt=True,
        description='右回り・外回り(386m)/内回り(286m) / ダート専門。地方ダートの総本山。ダート三冠・東京大賞典など数多くの名勝負が行われる。',
        chutes={
            1200: '向正面奥引き込み線（直線スタート）',
            1400: '向正面奥引き込み線（直線スタート）',
            1800: 'スタンド前直線（外回り・羽田盃の舞台）',
            2000: 'スタンド前直線奥（東京ダービー・JDC・東京大賞典の舞台）',
        },
    ),
    'KAWASAKI': TrackInfo(
        track_id='KAWASAKI',
        name='川崎競馬場',
        org='NAR',
        turn='left',
        size_type='small',
        straight_length=300.0,
        has_slope=False,
        slope_type='flat',
        has_turf=False,
        has_dirt=True,
        description='左回り・小回り / 直線 300.0m / ダート専門。きついコーナーとスリリングなナイター競馬。川崎記念や全日本2歳優駿の舞台。',
        chutes={
            900: '向正面奥引き込み線（ワンターンスプリント）',
            1500: '4コーナー奥引き込み線（直線スタート）',
            1600: '4コーナー奥引き込み線（全日本2歳優駿の舞台）',
            2100: 'スタンド前直線奥（川崎記念の舞台）',
        },
    ),
    'FUNABASHI': TrackInfo(
        track_id='FUNABASHI',
        name='船橋競馬場',
        org='NAR',
        turn='left',
        size_type='medium',
        straight_length=308.0,
        has_slope=False,
        slope_type='flat',
        has_turf=False,
        has_dirt=True,
        description='左回り・外回り/内回り / 直線 308.0m / ダート専門・スパイラルカーブ。かしわ記念や日本テレビ盃が行われる交流ダートの名舞台。',
        chutes={
            1000: '向正面奥引き込み線（直線スタート）',
            1600: '4コーナー奥引き込み線（かしわ記念の舞台）',
            1800: 'スタンド前直線（日本テレビ盃の舞台）',
        },
    ),
    'MORIOKA': TrackInfo(
        track_id='MORIOKA',
        name='盛岡競馬場',
        org='NAR',
        turn='left',
        size_type='large',
        straight_length=300.0,
        has_slope=True,
        slope_type='steep_slope',
        has_turf=True,
        has_dirt=True,
        description='左回り・大箱 / 直線 300.0m / 地方競馬で唯一の芝コース併設（高低差4.4m）。マイルCS南部杯や不来方賞の舞台。',
        chutes={
            1000: '向正面奥引き込み線（ダート短距離）',
            1600: '向正面奥引き込み線（マイルCS南部杯・不来方賞芝/ダートスタート）',
            2000: 'スタンド前直線（芝・ダート中距離）',
        },
    ),
}

# 過去の4大コードエイリアス対応 (A:中京, B:東京, C:中山, D:小倉)
TRACK_ALIASES: Dict[str, str] = {
    'A': 'CHUKYO',
    'B': 'TOKYO',
    'C': 'NAKAYAMA',
    'D': 'KOKURA',
}


def get_track_info(track_id: str) -> TrackInfo:
    """指定ID（英字または旧コード）の競馬場情報を取得"""
    resolved_id = TRACK_ALIASES.get(track_id, track_id)
    return TRACK_CONFIGS.get(resolved_id, TRACK_CONFIGS['TOKYO'])
