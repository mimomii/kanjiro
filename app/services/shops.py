# app/services/shops.py
from __future__ import annotations
import os
import json
import re
import time
from typing import Dict, List, Optional, Tuple, Any

import requests
from langchain_google_genai import ChatGoogleGenerativeAI

# ===================== 基本設定 =====================
HOTPEPPER_API_KEY_ENV = "HOTPEPPER_API_KEY"  # 必須: 環境変数から与える
ENDPOINT_HTTP = "http://webservice.recruit.co.jp/hotpepper/gourmet/v1/"   # 公式に合わせて http
ENDPOINT_HTTPS = "https://webservice.recruit.co.jp/hotpepper/gourmet/v1/" # 念のためフォールバック
MAX_API_COUNT = 50
DEFAULT_TIMEOUT = 8.0
DEBUG = os.environ.get("HOTPEPPER_DEBUG") == "1"

# ===================== マッピング（debug版に準拠/拡張可） =====================
GENRE_MAP: Dict[str, str] = {
    "居酒屋": "G001", "ダイニングバー": "G002", "ダイニング": "G002", "創作料理": "G003",
    "和食": "G004", "洋食": "G005", "イタリアン": "G006", "フレンチ": "G006",
    "中華": "G007", "焼肉": "G008", "韓国料理": "G017", "アジア": "G009",
    "各国料理": "G010", "カラオケ": "G011", "バー": "G012", "バル": "G012",
    "カフェ": "G013", "スイーツ": "G014", "ラーメン": "G015",
    "お好み焼き": "G016", "もんじゃ": "G016", "郷土料理": "G004", "海鮮": "G004",
    "寿司": "G004", "焼鳥": "G001",
}

BUDGET_BINS: List[Tuple[str, Tuple[int, int]]] = [
    ("B005", (2001, 3000)), ("B006", (3001, 4000)), ("B007", (4001, 5000)),
    ("B008", (5001, 7000)), ("B009", (7001, 10000)), ("B010", (10001, 9999999)),
    # 必要なら B001〜B004 も追加可能
]

def _pick_budget_code(bmin: Optional[int], bmax: Optional[int]) -> Optional[str]:
    vals = []
    if isinstance(bmin, int): vals.append(bmin)
    if isinstance(bmax, int): vals.append(bmax)
    if not vals:
        return None
    target = sum(vals) // len(vals)
    for code, (lo, hi) in BUDGET_BINS:
        if lo <= target <= hi:
            return code
    return None

def _parse_int_safe(s: Any) -> Optional[int]:
    try:
        if s is None: return None
        if isinstance(s, (int, float)): return int(s)
        return int(re.sub(r"[^\d]", "", str(s)))
    except Exception:
        return None

# ===================== LLM: 自然文 → 構造化（既存のまま） =====================
def interpret_preferences_with_llm(
    llm: ChatGoogleGenerativeAI,
    convo_text: str,
    current: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    current = current or {}
    sys_prompt = (
        "あなたは宴会・飲み会の幹事アシスタントです。"
        "入力テキストから次のJSON形式で情報を抽出して返してください。"
        "必ずJSONのみ、余分な文字は出力しないでください。\n"
        "schema:\n"
        "{"
        "  \"area\": string|null,"
        "  \"lat\": number|null, \"lng\": number|null, \"range_m\": number|null,"
        "  \"date\": string|null, \"people\": number|null,"
        "  \"budget_min\": number|null, \"budget_max\": number|null,"
        "  \"genres\": string[],"
        "  \"constraints\": {"
        "    \"private_room\": boolean, \"non_smoking\": boolean, \"card\": boolean, \"child\": boolean, \"free_drink\": boolean"
        "  }"
        "}"
        "注意: 不明な項目は null、genres は日本語の一般名詞で。"
    )
    user_prompt = (
        "入力:\n"
        f"{convo_text[:1200]}\n\n"
        "既知の現在値（無い場合は空）:\n"
        f"{json.dumps(current, ensure_ascii=False)}"
    )
    try:
        resp = llm.invoke([("system", sys_prompt), ("human", user_prompt)])
        text = getattr(resp, "content", str(resp))
        data = json.loads(text)
        return {
            "area": (data.get("area") or current.get("area")) or None,
            "lat": data.get("lat"),
            "lng": data.get("lng"),
            "range_m": _parse_int_safe(data.get("range_m")),
            "date": data.get("date"),
            "people": _parse_int_safe(data.get("people")),
            "budget_min": _parse_int_safe(data.get("budget_min") or current.get("budget_min")),
            "budget_max": _parse_int_safe(data.get("budget_max") or current.get("budget_max")),
            "genres": [str(g) for g in (data.get("genres") or []) if str(g).strip()],
            "constraints": {
                "private_room": bool((data.get("constraints") or {}).get("private_room")),
                "non_smoking": bool((data.get("constraints") or {}).get("non_smoking")),
                "card": bool((data.get("constraints") or {}).get("card")),
                "child": bool((data.get("constraints") or {}).get("child")),
                "free_drink": bool((data.get("constraints") or {}).get("free_drink")),
            },
        }
    except Exception:
        return {
            "area": current.get("area"),
            "lat": None, "lng": None, "range_m": None,
            "date": None, "people": None,
            "budget_min": _parse_int_safe(current.get("budget_min")),
            "budget_max": _parse_int_safe(current.get("budget_max")),
            "genres": [],
            "constraints": {
                "private_room": False, "non_smoking": False, "card": False, "child": False, "free_drink": False
            },
        }

# ===================== HTTP 呼び出し（debug版の芯） =====================
def _api_key() -> str:
    key = os.environ.get(HOTPEPPER_API_KEY_ENV, "").strip()
    if not key:
        raise RuntimeError(f"{HOTPEPPER_API_KEY_ENV} is not set")
    return key

def _call(params: Dict[str, Any], timeout_sec: float = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    """debug版の最小形：http を既定、必要なら https にフォールバック。results.error を検出。"""
    api_key = _api_key()
    base = {"key": api_key, "format": "json", "count": min(20, MAX_API_COUNT), "order": 4}
    p = {**base, **params}

    last_exc: Optional[Exception] = None
    for endpoint in (ENDPOINT_HTTP, ENDPOINT_HTTPS):
        try:
            r = requests.get(endpoint, params=p, timeout=timeout_sec)
            # デバッグURL（キーは伏せる）
            if DEBUG:
                try:
                    dbg_url = r.request.url.replace(api_key, "****")
                    print(f"[GET] {dbg_url}")
                except Exception:
                    pass
            r.raise_for_status()
            data = r.json()
            if "error" in (data.get("results") or {}):
                # 公式は results.error に詳細を載せる
                raise RuntimeError(f"HotPepper API error: {data['results']['error']}")
            return data
        except Exception as e:
            last_exc = e
            # https で再試行 → それでもダメなら例外
            continue
    raise last_exc or RuntimeError("HotPepper API call failed")

# ===================== パラメタ整形 & 検索 =====================
def _genre_codes_from_names(names: List[str]) -> List[str]:
    codes: List[str] = []
    for n in names:
        key = str(n).strip()
        if not key:
            continue
        if key in GENRE_MAP:
            codes.append(GENRE_MAP[key])
            continue
        for k, v in GENRE_MAP.items():
            if key.startswith(k) or k in key:
                codes.append(v)
                break
    # 重複排除
    uniq: List[str] = []
    for c in codes:
        if c not in uniq:
            uniq.append(c)
    return uniq

def search_hotpepper_api(
    area_text: Optional[str],
    budget_min: Optional[int],
    budget_max: Optional[int],
    genre_names: Optional[List[str]] = None,
    constraints: Optional[Dict[str, bool]] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    range_m: Optional[int] = None,
    count: int = 10,
) -> List[Dict]:
    """
    Hot Pepper 公式APIで検索し、最大MAX_API_COUNT件以内を返す。
    返却: [{ name, url, budget_label, address, access, photo_url }]
    """
    # debug版思想：まず最小条件で素直に叩く
    params: Dict[str, Any] = {"count": min(max(1, count), MAX_API_COUNT)}

    # 位置検索（lat/lng + range）優先。なければ keyword
    if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
        params.update({"lat": float(lat), "lng": float(lng)})
        rm = int(range_m or 1000)  # 既定1km
        params["range"] = 1 if rm <= 300 else 2 if rm <= 500 else 3 if rm <= 1000 else 4 if rm <= 2000 else 5
    elif area_text:
        params["keyword"] = str(area_text)

    # 予算（中央値近似→コード）
    b = _pick_budget_code(budget_min, budget_max)
    if b:
        params["budget"] = b

    # ジャンル（単一）
    if genre_names:
        codes = _genre_codes_from_names(genre_names)
        if codes:
            params["genre"] = codes[0]

    # 制約（付け過ぎると0件化しやすい）
    c = constraints or {}
    if c.get("private_room"): params["private_room"] = 1
    if c.get("non_smoking"): params["non_smoking"] = 1
    if c.get("card"): params["card"] = 1
    if c.get("child"): params["child"] = 1
    if c.get("free_drink"): params["free_drink"] = 1

    # 実行
    data = _call(params, timeout_sec=DEFAULT_TIMEOUT)

    shops = (data.get("results") or {}).get("shop") or []
    out: List[Dict] = []
    for s in shops:
        out.append({
            "name": s.get("name"),
            "url": (s.get("urls") or {}).get("pc"),
            "budget_label": (s.get("budget") or {}).get("name"),
            "address": s.get("address"),
            "access": s.get("access"),
            "photo_url": ((s.get("photo") or {}).get("pc") or {}).get("m"),
        })
    return out

# ===================== 上位：会話 → 正規化 → 検索 =====================
def find_shops(
    llm: ChatGoogleGenerativeAI,
    convo_text: str,
    form_inputs: Dict[str, Any],
    take: int = 3,
) -> List[Dict]:
    """
    1) LLMで意図理解し正規化
    2) Hot Pepper APIでフィルタ検索（最大MAX_API_COUNT件→上位take件）
    """
    normalized = interpret_preferences_with_llm(
        llm=llm,
        convo_text=convo_text,
        current={
            "area": form_inputs.get("area"),
            "budget_min": form_inputs.get("budget_min"),
            "budget_max": form_inputs.get("budget_max"),
            "genres": [g.strip() for g in (form_inputs.get("cuisine") or "").split(",") if g.strip()],
        },
    )

    shops = search_hotpepper_api(
        area_text=normalized.get("area"),
        budget_min=normalized.get("budget_min"),
        budget_max=normalized.get("budget_max"),
        genre_names=normalized.get("genres"),
        constraints=normalized.get("constraints"),
        lat=normalized.get("lat"),
        lng=normalized.get("lng"),
        range_m=normalized.get("range_m"),
        count=min(MAX_API_COUNT, max(take, 10)),
    )
    return shops[:take]
