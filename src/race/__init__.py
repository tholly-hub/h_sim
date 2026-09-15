"""
レースシミュレーションパッケージ (Phase 3)
"""

from src.race.track import TrackInfo, get_track_info
from src.race.program import RaceProgramBuilder, GRADE_PRIZE_MAP
from src.race.entry import RaceEntryManager
from src.race.engine import RaceEngine, BASE_TIMES, get_base_time, calculate_margin
from src.race.calendar import CalendarController
from src.race.rankings import RankingManager

__all__ = [
    'TrackInfo',
    'get_track_info',
    'RaceProgramBuilder',
    'GRADE_PRIZE_MAP',
    'RaceEntryManager',
    'RaceEngine',
    'BASE_TIMES',
    'get_base_time',
    'calculate_margin',
    'CalendarController',
    'RankingManager',
]
