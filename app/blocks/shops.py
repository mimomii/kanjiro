"""Utilities to build Slack Block Kit structures for shops."""

from __future__ import annotations

from typing import Dict, List


def shop_to_blocks(shop: Dict) -> List[Dict]:
    """Convert a shop dict to a list of Block Kit blocks."""

    name = shop.get("name", "")
    url = shop.get("urls")
    if isinstance(url, dict):
        url = url.get("pc", "")
    budget = shop.get("budget", "")
    access = shop.get("access", "")
    photo = shop.get("photo")

    blocks: List[Dict] = []
    if photo:
        blocks.append({"type": "image", "image_url": photo, "alt_text": name})
    blocks.append(
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*<{url}|{name}>*\n{budget}｜{access}"},
        }
    )
    blocks.append(
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "候補に追加"},
                    "style": "primary",
                    "action_id": "add_candidate",
                    "value": shop.get("id", ""),
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "除外"},
                    "style": "danger",
                    "action_id": "exclude_candidate",
                    "value": shop.get("id", ""),
                },
            ],
        }
    )
    return blocks


def shortlist_blocks(shops: List[Dict]) -> List[Dict]:
    """Build blocks that list current shortlist."""

    if not shops:
        return [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "候補はまだありません。"},
            }
        ]

    lines = []
    for i, s in enumerate(shops, 1):
        url = s.get("urls")
        if isinstance(url, dict):
            url = url.get("pc", "")
        lines.append(f"{i}. <{url}|{s.get('name','')}> - {s.get('budget','')}")
    text = "\n".join(lines)
    return [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*現在の候補一覧:*\n{text}"},
        }
    ]
