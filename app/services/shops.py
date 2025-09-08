# app/services/shops.py
import json
import os
from typing import Dict, List, Optional

from langchain_google_genai import ChatGoogleGenerativeAI

PREF_DOMAINS = ("tabelog.com", "hotpepper.jp", "gnavi.co.jp", "ikkyu.com", "retty.me")

def _mk_query(area: Optional[str], cuisine: Optional[str], budget_min: Optional[int], budget_max: Optional[int], extra: Optional[str]) -> str:
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
    応答から JSON 配列部分だけを抜き出して parse。失敗時は空配列。
    """
    try:
        # コードブロックで返る場合にも対応
        if "```" in text:
            text = text.split("```", 2)[-1]
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

def search_shops_api(
    area: Optional[str],
    budget_min: Optional[int],
    budget_max: Optional[int],
    cuisine: Optional[str],
    size: int = 5,
    extra_keywords: Optional[str] = None,
) -> List[Dict]:
    """
    Gemini の Google 検索グラウンディングを使い、信頼できるグルメサイトの店舗URLを取得する。
    - APIキーは GEMINI_API_KEY_MAIN を利用
    - 返り値: [{name, url, budget_label}]
    """
    api_key = os.environ.get("GEMINI_API_KEY_MAIN")
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")

    # 検索ツール有効な LLM（温度低めで安定化）
    llm = ChatGoogleGenerativeAI(
        model=model,
        google_api_key=api_key,
        temperature=float(os.environ.get("GEMINI_TEMPERATURE_SEARCH", "0.2")),
        tools=[{"google_search_retrieval": {}}],  # ★ ここがポイント
    )

    q = _mk_query(area, cuisine, budget_min, budget_max, extra_keywords)
    system = (
        "あなたはグルメ店探しのアシスタントです。Google 検索ツールで最新の情報を確認し、"
        "以下の条件を満たす JSON 配列のみを返してください（前後の説明文は不要）：\n"
        "- 要素は最大で {size} 件\n"
        "- 各要素は {name, url, budget_label} をキーに持つオブジェクト\n"
        "- url は以下のドメインのいずれかに限定: " + ", ".join(PREF_DOMAINS) + "\n"
        "- 同じ店の重複は除外\n"
    )
    user = f"検索クエリ: {q}\n上の条件に従って JSON 配列だけを返してください。"

    try:
        # LangChain の .invoke で 1ショット実行
        resp = llm.invoke([("system", system), ("human", user)])
        text = resp.content if hasattr(resp, "content") else str(resp)
        items = _extract_json(text)

        # 正規化 & ドメイン優先でフィルタ
        out: List[Dict] = []
        seen = set()
        for it in items:
            name = (it.get("name") or "").strip()
            url = (it.get("url") or "").strip()
            if not name or not url:
                continue
            if not any(d in url for d in PREF_DOMAINS):
                continue
            if url in seen:
                continue
            seen.add(url)
            out.append(
                {
                    "name": name,
                    "url": url,
                    "budget_label": (it.get("budget_label") or "-"),
                }
            )
            if len(out) >= size:
                break

        if out:
            return out

    except Exception as e:
        # 失敗しても動作を止めない（ダミーにフォールバック）
        pass

    # 最終フォールバック（ゼロ件や失敗時）
    return [
        {"name": "サンプル居酒屋A", "url": "https://tabelog.com/", "budget_label": "-"},
        {"name": "サンプル居酒屋B", "url": "https://www.hotpepper.jp/", "budget_label": "-"},
        {"name": "サンプル居酒屋C", "url": "https://r.gnavi.co.jp/", "budget_label": "-"},
    ][:size]
