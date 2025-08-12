from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class ParticipantPref:
    """Preferences collected from each participant."""

    user_id: str
    spicy_ok: Optional[bool] = None
    seafood_ok: Optional[bool] = None
    allergies: List[str] = field(default_factory=list)
    budget_upper: Optional[int] = None
    notes: str = ""


@dataclass
class EventContext:
    """Context information for a single planning session."""

    channel: str
    thread_ts: str
    organizer: str
    date_candidates: List[str]
    start_time_range: str
    area_text: str
    genre_candidates: List[str]
    must_haves: Dict[str, bool]
    budget_min: Optional[int]
    budget_max: Optional[int]
    participants: List[str]
    prefs_by_user: Dict[str, ParticipantPref] = field(default_factory=dict)
    shortlist: List[Dict] = field(default_factory=list)
