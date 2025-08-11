"""Storage package exposing DAO helpers."""

from .dao import (
    init_db,
    get_latest_summary,
    save_new_summary,
    make_input_hash,
)

__all__ = [
    "init_db",
    "get_latest_summary",
    "save_new_summary",
    "make_input_hash",
]
