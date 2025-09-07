# app/services/shops.py
import os
import requests
from typing import Dict, List, Optional

HP_API = "https://webservice.recruit.co.jp/hotpepper/gourmet/v1/"
HP_KEY = os.environ.get("HOTPEPPER_API_KEY")
DEBUG = os.environ.get("HOTPEPPER_DEBUG") == "1"

# 最低限のエリアコード（必要に応じて拡張）
# large_area: 東京 Z011, 神奈川 Z014, 埼玉 Z012, 千葉 Z013
LARGE_AREA_MAP = {
    "東京": "Z011", "東京都": "Z011", "tokyo": "Z011",
    "神奈川": "Z014", "横浜": "Z014", "kanagawa": "Z014",
    "埼玉": "Z012", "saitama": "Z012",
    "千葉": "Z013", "chiba": "Z013",
}
# middle_area（例）：新宿 Y005 / 渋谷 Y006 / 品川 Y010 / 池袋 Y004 / 銀座・有楽町・新橋 Y009
MIDDLE_AREA_MAP = {
    "新宿": "Y005", "shinjuku": "Y005",
    "渋谷": "Y006", "shibuya": "Y006",
    "池袋": "Y004", "ikebukuro": "Y004",
    "品川": "Y010", "shinagawa": "Y010",
    "銀座": "Y009", "有楽町": "Y009", "新橋": "Y009", "ginza": "Y009",
}

# 主なジャンルコード（十分でなければ拡張）
GENRE_MAP = {
    "居酒屋": "G001",
    "ダイニング": "G002",
    "創作": "G003",
    "和食": "G004",
    "洋食": "G005",
    "イタリアン": "G006", "フレンチ": "G006",
    "中華": "G007",
    "焼肉": "G008", "ホルモン": "G008", "韓国料理": "G008",
    "アジア": "G009", "エスニック": "G009",
    "各国料理": "G010",
    "カラオケ": "G011", "パーティ": "G011",
    "バー": "G012", "バル": "G012", "ダーツ": "G012", "スポーツバー": "G012",
    "ラーメン": "G013", "つけ麺": "G013",
    "カフェ": "G014", "スイーツ": "G014",
    "お好み焼き": "G015", "もんじゃ": "G015", "鉄板焼き": "G015",
    "居酒屋（英語）": "G001", "izakaya": "G001",
    "焼き鳥": "G012",  # 近いカテゴリ（実際は細かいサブカテゴリあり）
}

def _pick_area_codes(area_text: Optional[str]) -> Dict[str, str]:
    """入力されたエリア文字列から large_area / middle_area を推定。なければ空。"""
    if not area_text:
        return {}
    a = area_text.strip().lower()
    # middle優先で見つけ、なければlarge
    for k, code in MIDDLE_AREA_MAP.items():
        if k in area_text or k in a:
            return {"middle_area": code}
    for k, code in LARGE_AREA_MAP.items():
        if k in area_text or k in a:
            return {"large_area": code}
    return {}  # 見つからない場合は keyword に任せる

def _pick_genre_code(cuisine_text: Optional[str]) -> Optional[str]:
    if not cuisine_text:
        return None
    for token in [t.strip().lower() for t in cuisine_text.split(",") if t.strip()]:
        for k, code in GENRE_MAP.items():
            if k in token:
                return code
    # 日本語そのままの一致も試す
    for k, code in GENRE_MAP.items():
        if cuisine_text.find(k) >= 0:
            return code
    return None

def _build_params(
    area: Optional[str], budget_min: Optional[int], budget_max: Optional[int],
    cuisine: Optional[str], size: int
) -> List[Dict]:
    """検索パターンを“徐々にゆるめる”順で返す（複数回試行）。"""
    area_codes = _pick_area_codes(area)
    genre = _pick_genre_code(cuisine)
    keywords = []
    if area and not area_codes:
        keywords.append(area)
    if cuisine and not genre:
        keywords.append(cuisine.replace(",", " "))

    patterns = []

    # 1) コード優先（当たれば精度◎）
    p1 = {"count": size, "format": "json"}
    p1.update(area_codes)
    if genre:
        p1["genre"] = genre
    if keywords:
        p1["keyword"] = " ".join(keywords)
    patterns.append(p1)

    # 2) コードのない場合 or 0件だった場合：keyword 中心
    p2 = {"count": size, "format": "json"}
    if keywords:
        p2["keyword"] = " ".join(keywords)
    patterns.append(p2)

    # 3) 最後の手段：cuisine/area どちらかだけ（より緩い）
    if cuisine:
        patterns.append({"count": size, "format": "json", "keyword": cuisine})
    if area:
        patterns.append({"count": size, "format": "json", "keyword": area})

    # 予算は本来 budget コードが必要。ここでは keyword へ添えるだけに留める。
    # （将来: min/max を hotpepper の budget コードへマッピング可能）
    if budget_min and budget_max:
        for p in patterns:
            p["keyword"] = (p.get("keyword", "") + f" {budget_min}-{budget_max}").strip()

    return patterns

def _extract_shops(json_data: Dict) -> List[Dict]:
    shops = json_data.get("results", {}).get("shop", []) or []
    out = []
    for s in shops:
        url = (s.get("urls", {}) or {}).get("pc") or (s.get("coupon_urls", {}) or {}).get("pc")
        name = s.get("name")
        if not url or not name:
            continue
        out.append(
            {
                "name": name,
                "url": url,
                "budget_label": (s.get("budget") or {}).get("name") or "-",
            }
        )
    return out

def _query(params: Dict) -> List[Dict]:
    try:
        r = requests.get(HP_API, params={"key": HP_KEY, **params}, timeout=10)
        r.raise_for_status()
        data = r.json()
        out = _extract_shops(data)
        if DEBUG:
            print("[HOTPEPPER] params=", params, "hit=", len(out))
        return out
    except Exception as e:
        if DEBUG:
            print("[HOTPEPPER][ERROR]", type(e).__name__, str(e))
        return []

def search_shops_api(
    area: Optional[str],
    budget_min: Optional[int],
    budget_max: Optional[int],
    cuisine: Optional[str],
    size: int = 5,
) -> List[Dict]:
    """
    段階的に検索を緩めてヒット率を高める。
    APIキー未設定時はダミー候補を返す。
    """
    if not HP_KEY:
        return [
            {"name": "サンプル居酒屋A", "url": "https://example.com/a", "budget_label": "¥3000〜¥4000"},
            {"name": "サンプル焼き鳥B", "url": "https://example.com/b", "budget_label": "¥3500〜¥4500"},
            {"name": "サンプル酒場C", "url": "https://example.com/c", "budget_label": "¥2500〜¥3500"},
            {"name": "サンプルダイニングD", "url": "https://example.com/d", "budget_label": "¥4000〜¥5000"},
            {"name": "サンプル居酒屋E", "url": "https://example.com/e", "budget_label": "¥3000〜¥4500"},
        ][:size]

    for params in _build_params(area, budget_min, budget_max, cuisine, size):
        results = _query(params)
        if results:
            return results[:size]

    # すべて空だった場合は最後にダミー
    return [
        {"name": "候補（API 0件のためサンプル）", "url": "https://example.com", "budget_label": "-"}
    ]
