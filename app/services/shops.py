# app/services/shops.py
import os
import requests
from typing import Dict, List, Optional

HP_API = "https://webservice.recruit.co.jp/hotpepper/gourmet/v1/"
HP_KEY = os.environ.get("HOTPEPPER_API_KEY")


def search_shops_api(
    area: Optional[str],
    budget_min: Optional[int],
    budget_max: Optional[int],
    cuisine: Optional[str],
    size: int = 5,
) -> List[Dict]:
    """
    ざっくり検索。area/cuisine を keyword にまとめてANDっぽく検索。
    予算はHotPepper特有のコードがあるが、簡易化のためkeywordで代替。
    """
    keywords = []
    if area:
        keywords.append(area)
    if cuisine:
        keywords.append(cuisine.replace(",", " "))
    if budget_min and budget_max:
        keywords.append(f"{budget_min}-{budget_max}")

    if not HP_KEY:
        # ダミー（APIキー未設定時）
        return [
            {"name": "サンプル居酒屋A", "url": "https://example.com/a", "budget_label": "¥3000〜¥4000"},
            {"name": "サンプル焼き鳥B", "url": "https://example.com/b", "budget_label": "¥3500〜¥4500"},
            {"name": "サンプル酒場C", "url": "https://example.com/c", "budget_label": "¥2500〜¥3500"},
        ][:size]

    params = {
        "key": HP_KEY,
        "format": "json",
        "count": size,
        "keyword": " ".join(keywords) if keywords else "",
    }
    try:
        r = requests.get(HP_API, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        shops = data.get("results", {}).get("shop", []) or []
        out = []
        for s in shops:
            out.append(
                {
                    "name": s.get("name"),
                    "url": s.get("urls", {}).get("pc") or s.get("coupon_urls", {}).get("pc"),
                    "budget_label": s.get("budget", {}).get("name"),
                }
            )
        return out
    except Exception:
        # エラー時はダミー
        return [
            {"name": "候補（取得失敗のためサンプル）", "url": "https://example.com", "budget_label": "-"}
        ]
