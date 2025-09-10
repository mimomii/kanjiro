# app/services/shops.py
import json
import os
import urllib.parse
from typing import Dict, List, Optional

from langchain_google_genai import ChatGoogleGenerativeAI

PREF_DOMAINS = ("tabelog.com", "hotpepper.jp", "gnavi.co.jp", "ikkyu.com", "retty.me")

# 各サイトの「安全な着地点」（モデルが不正URLを返した場合のフォールバック先）
SAFE_DOMAIN_HOMEPAGES = {
    "tabelog.com": "https://tabelog.com/",
    "hotpepper.jp": "https://www.hotpepper.jp/",
    "gnavi.co.jp": "https://www.gnavi.co.jp/",
    "ikkyu.com": "https://restaurant.ikyu.com/",
    "retty.me": "https://retty.me/",
}

def _mk_query(
    area: Optional[str],
    cuisine: Optional[str],
    budget_min: Optional[int],
    budget_max: Optional[int],
    extra: Optional[str],
) -> str:
    parts: List[str] = []
    if area: parts.append(str(area))
    if cuisine: parts.append(str(cuisine))
    if budget_min and budget_max: parts.append(f"予算 {budget_min}-{budget_max}円")
    parts += ["飲み会", "居酒屋", "予約"]
    if extra:
        parts.append(str(extra)[:200])  # 会話要約は短く
    return " ".join(p for p in parts if p)

def _extract_json(text: str) -> List[Dict]:
    """
    モデル応答から JSON 配列部分だけを抽出して parse。失敗時は空配列。
    """
    try:
        # ```json ... ``` にも対応
        if "```" in text:
            # 最後のコードブロックを優先
            chunks = text.split("```")
            # json指定が無いケースでも最後のブロックを拾う
            # 例: ... ```json [ ... ] ```
            text = chunks[-2] if len(chunks) >= 2 else text
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    # 緩い抽出（[ から最後の ] まで）
    try:
        s = text.find("[")
        e = text.rfind("]")
        if s != -1 and e != -1 and e > s:
            data = json.loads(text[s : e + 1])
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []

def _domain_of(url: str) -> str:
    try:
        from urllib.parse import urlparse
        netloc = urlparse(url).netloc.lower()
        # サブドメインを削って主要ドメインを返す
        parts = netloc.split(".")
        if len(parts) >= 2:
            return ".".join(parts[-2:])
        return netloc
    except Exception:
        return ""

def _sanitize_and_fill(items: List[Dict], size: int, fallback_query: str) -> List[Dict]:
    """
    生成結果をドメイン検証して正規化。
    - name/url の欠落や未知ドメイン → 安全なホーム/検索トップURLに補正
    - 既知ドメイン以外は除外し、足りない分は安全URLで補完
    """
    out: List[Dict] = []
    seen_urls = set()

    for it in items:
        name = (it.get("name") or "").strip()
        url = (it.get("url") or "").strip()
        budget_label = (it.get("budget_label") or "-").strip() or "-"

        if not name:
            continue

        dom = _domain_of(url) if url else ""
        if not url or dom not in PREF_DOMAINS:
            # モデルが不明/別ドメインURLを返した場合は安全URLに置換
            # 1) 可能なら name から想起されるドメインをあてる（軽いヒューリスティック）
            # 2) ダメなら順にローテーション
            preferred = None
            lower = name.lower()
            if "食べログ" in name or "tabelog" in lower:
                preferred = "tabelog.com"
            elif "ホットペッパー" in name or "hotpepper" in lower:
                preferred = "hotpepper.jp"
            elif "ぐるなび" in name or "gnavi" in lower:
                preferred = "gnavi.co.jp"
            elif "一休" in name or "ikyu" in lower:
                preferred = "ikkyu.com"
            elif "retty" in lower or "レッティ" in name:
                preferred = "retty.me"

            if not preferred:
                # 適当な既知ドメインを回す
                preferred = list(SAFE_DOMAIN_HOMEPAGES.keys())[len(out) % len(SAFE_DOMAIN_HOMEPAGES)]
            # 検索語をURLエンコードして（※サイト固有の検索URLは仕様変化が多いため、安全にトップへ）
            url = SAFE_DOMAIN_HOMEPAGES.get(preferred, "https://tabelog.com/")

        if url in seen_urls:
            continue
        seen_urls.add(url)

        out.append({"name": name, "url": url, "budget_label": budget_label})
        if len(out) >= size:
            break

    # 件数足りない場合は安全URLで埋める（UIが空にならないように）
    i = 0
    while len(out) < size:
        dom = list(SAFE_DOMAIN_HOMEPAGES.keys())[i % len(SAFE_DOMAIN_HOMEPAGES)]
        safe_url = SAFE_DOMAIN_HOMEPAGES[dom]
        label = f"検索の起点 / {dom}"
        candidate = {"name": f"{fallback_query}（{label}）", "url": safe_url, "budget_label": "-"}
        if candidate["url"] not in seen_urls:
            out.append(candidate)
            seen_urls.add(candidate["url"])
        i += 1

    return out[:size]

def search_shops_api(
    area: Optional[str],
    budget_min: Optional[int],
    budget_max: Optional[int],
    cuisine: Optional[str],
    size: int = 5,
    extra_keywords: Optional[str] = None,
) -> List[Dict]:
    """
    生成AIのみで候補JSONを作る版。
    - Google検索ツールは使わない（tools 無し）
    - 返り値: [{name, url, budget_label}]
    - URLは既知ドメインに限定・検証。不明/不正なら安全URLに補正。
    """
    api_key = os.environ.get("GEMINI_API_KEY_MAIN")
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")

    llm = ChatGoogleGenerativeAI(
        model=model,
        google_api_key=api_key,
        temperature=float(os.environ.get("GEMINI_TEMPERATURE_SEARCH", "0.2")),
        # ★ ツール指定を削除（純生成）
    )

    q = _mk_query(area, cuisine, budget_min, budget_max, extra_keywords)

    # 生成だけで完結させるため、厳密な出力制約を付与
    system = (
        "あなたはグルメ店候補を要件に沿って提案するアシスタントです。"
        "以下の制約で JSON 配列のみを返してください（前後の説明文は一切不要）。\n"
        f"- 配列要素は最大 {size} 件\n"
        "- 各要素は {name, url, budget_label} をキーに持つオブジェクト\n"
        "- url は次のいずれかのドメインに限定: " + ", ".join(PREF_DOMAINS) + "\n"
        "- 同一店舗の重複は除外\n"
        "- 不明な場合は、そのサイトのトップページURLを入れて構いません\n"
    )

    user = (
        "次の希望条件に合う飲食店の候補を返してください。\n"
        f"条件: {q}\n"
        "出力は JSON 配列のみ。余計な文章は出力しないでください。"
    )

    try:
        resp = llm.invoke([("system", system), ("human", user)])
        text = resp.content if hasattr(resp, "content") else str(resp)
        items = _extract_json(text)

        # 正規化＆既知ドメイン以外を弾きつつ補正
        return _sanitize_and_fill(items, size=size, fallback_query=q)

    except Exception:
        # 完全失敗時のフォールバック（安全URLで埋める）
        return _sanitize_and_fill([], size=size, fallback_query=q)
