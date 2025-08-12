"""Hot Pepper Gourmet API client."""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional

import requests

API_URL = "https://webservice.recruit.co.jp/hotpepper/gourmet/v1/"
API_KEY = os.environ.get("HOTPEPPER_API_KEY", "")

log = logging.getLogger(__name__)


def budget_code_from_yen(y: Optional[int]) -> Optional[str]:
    """Convert budget in yen to Hot Pepper budget code.

    This mapping is intentionally coarse and can be refined later.
    """

    if y is None:
        return None
    if y <= 2000:
        return "B002"
    if y <= 3000:
        return "B003"
    if y <= 4000:
        return "B008"
    if y <= 5000:
        return "B001"
    return "B006"  # 5000円以上


def _extract(shop: Dict) -> Dict:
    return {
        "id": shop.get("id"),
        "name": shop.get("name"),
        "urls": shop.get("urls", {}).get("pc"),
        "budget": (shop.get("budget") or {}).get("name"),
        "access": shop.get("access"),
        "photo": (((shop.get("photo") or {}).get("pc") or {}).get("l")),
    }


def search_shops(
    area_text: str,
    genre_codes: List[str],
    budget_max: Optional[int],
    must: Dict[str, bool],
    start: int = 1,
    count: int = 20,
) -> List[Dict]:
    """Search shops using Hot Pepper Gourmet API.

    On error, an empty list is returned and the exception is logged.
    """

    params: Dict[str, object] = {
        "key": API_KEY,
        "format": "json",
        "keyword": area_text,
        "start": start,
        "count": count,
    }
    if genre_codes:
        params["genre"] = ",".join(genre_codes)
    bc = budget_code_from_yen(budget_max)
    if bc:
        params["budget"] = bc
    if must.get("private_room"):
        params["private_room"] = 1
    if must.get("non_smoking"):
        params["non_smoking"] = 1
    if must.get("free_drink"):
        params["free_drink"] = 1
    if must.get("course"):
        params["course"] = 1

    try:
        resp = requests.get(API_URL, params=params, timeout=10)
        resp.raise_for_status()
        results = resp.json().get("results", {})
        shops = results.get("shop", []) or []
        return [_extract(s) for s in shops]
    except Exception as e:  # pragma: no cover - best effort
        log.warning("Hot Pepper API error: %s", e)
        return []
