# -*- coding: utf-8 -*-
r"""
네이버 쇼핑 검색 API — 웹/CLI 공용 순수 로직.

브라우저를 import 하지 않는다. 네트워크 호출은 search_shop() 한 곳뿐이며
파싱·검증은 테스트가 네트워크 없이 호출한다.
"""
import os
import re
import json
import urllib.parse
import urllib.request

MAX_QUERY_LEN = 80
MIN_QUERY_LEN = 1
DEFAULT_DISPLAY = 20
NAVER_SHOP_URL = "https://openapi.naver.com/v1/search/shop.json"

_TAG_RE = re.compile(r"<[^>]+>")
_ALLOWED_SORT = ("sim", "date", "asc", "dsc")


def strip_tags(text):
    """네이버 제목에 섞인 <b> 태그 제거."""
    return _TAG_RE.sub("", text or "").replace("&quot;", '"').replace("&amp;", "&").strip()


def sanitize_query(raw):
    """검색어 정리. 유효하면 (query, None), 아니면 (None, error_message)."""
    query = (raw or "").strip()
    query = re.sub(r"\s+", " ", query)
    if len(query) < MIN_QUERY_LEN:
        return None, "검색어를 입력하세요"
    if len(query) > MAX_QUERY_LEN:
        return None, "검색어가 너무 깁니다 (80자 이내)"
    return query, None


def format_won(value):
    """정수 가격 -> '12,900원'. 없거나 숫자가 아니면 None."""
    if value is None or value == "":
        return None
    try:
        n = int(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
    if n < 0:
        return None
    return f"{n:,}원"


def normalize_item(raw):
    """네이버 shop.json 한 건 -> 웹/앱 공통 카드 스키마."""
    if not isinstance(raw, dict):
        return None
    title = strip_tags(raw.get("title") or raw.get("name") or "")
    if not title:
        return None
    lprice = raw.get("lprice")
    try:
        price = int(str(lprice).replace(",", "")) if lprice not in (None, "") else None
    except (TypeError, ValueError):
        price = None
    link = (raw.get("link") or raw.get("productUrl") or "").strip()
    image = (raw.get("image") or raw.get("imageUrl") or "").strip()
    return {
        "title": title,
        "price": price,
        "price_text": format_won(price) or "가격 미표시",
        "mall": (raw.get("mallName") or raw.get("mall") or "").strip() or "판매처 미표시",
        "link": link,
        "image": image,
        "brand": (raw.get("brand") or "").strip(),
        "category": (raw.get("category3") or raw.get("category2") or raw.get("category") or "").strip(),
        "product_id": str(raw.get("productId") or raw.get("product_id") or "").strip(),
    }


def parse_naver_response(payload):
    """API JSON(dict) -> {ok, items, count}."""
    if not isinstance(payload, dict):
        return {"ok": False, "reason": "응답 형식이 올바르지 않습니다", "items": []}
    items = []
    for raw in payload.get("items") or []:
        item = normalize_item(raw)
        if item:
            items.append(item)
    return {"ok": True, "count": len(items), "items": items}


def demo_items(query):
    """API 키 없을 때 화면이 비지 않도록 보여주는 샘플 카드.

    실결제가 아님을 호출측에서 source=demo 로 표시한다.
    """
    q = (query or "상품").strip() or "상품"
    samples = [
        {"title": f"{q} 인기 모델 (데모)", "lprice": "129000",
         "mallName": "데모스토어", "brand": "데모",
         "link": "https://search.shopping.naver.com/search/all?query=" + urllib.parse.quote(q),
         "image": "", "productId": "demo-1", "category3": "데모"},
        {"title": f"{q} 가성비형 (데모)", "lprice": "89000",
         "mallName": "데모마켓", "brand": "데모",
         "link": "https://search.shopping.naver.com/search/all?query=" + urllib.parse.quote(q),
         "image": "", "productId": "demo-2", "category3": "데모"},
        {"title": f"{q} 프리미엄 (데모)", "lprice": "219000",
         "mallName": "데모몰", "brand": "데모",
         "link": "https://search.shopping.naver.com/search/all?query=" + urllib.parse.quote(q),
         "image": "", "productId": "demo-3", "category3": "데모"},
    ]
    return [normalize_item(s) for s in samples]


def search_shop(query, display=DEFAULT_DISPLAY, sort="sim"):
    """공식 쇼핑 검색 API. 키 없으면 demo 결과를 돌려준다.

    반환 dict:
      ok, source ('naver'|'demo'), items, count, reason?, naver_mobile_url
    """
    cleaned, err = sanitize_query(query)
    if err:
        return {"ok": False, "reason": err, "items": [], "source": "error"}
    sort = sort if sort in _ALLOWED_SORT else "sim"
    try:
        display_n = int(display)
    except (TypeError, ValueError):
        display_n = DEFAULT_DISPLAY
    display_n = max(1, min(display_n, 40))

    mobile_url = "https://msearch.shopping.naver.com/search/all?query=" + urllib.parse.quote(cleaned)
    cid = (os.environ.get("NAVER_CLIENT_ID") or "").strip()
    secret = (os.environ.get("NAVER_CLIENT_SECRET") or "").strip()
    if not cid or not secret:
        items = demo_items(cleaned)
        return {
            "ok": True,
            "source": "demo",
            "count": len(items),
            "items": items,
            "reason": "네이버 API 키가 없어 데모 결과를 보여줍니다. .env 의 NAVER_CLIENT_SECRET 을 넣으면 실검색됩니다.",
            "naver_mobile_url": mobile_url,
            "query": cleaned,
        }

    url = NAVER_SHOP_URL + "?" + urllib.parse.urlencode(
        {"query": cleaned, "display": display_n, "sort": sort}
    )
    req = urllib.request.Request(
        url,
        headers={"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": secret},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        items = demo_items(cleaned)
        return {
            "ok": True,
            "source": "demo",
            "count": len(items),
            "items": items,
            "reason": f"네이버 API 호출 실패 → 데모로 대체: {exc}",
            "naver_mobile_url": mobile_url,
            "query": cleaned,
        }
    parsed = parse_naver_response(payload)
    parsed.update({
        "source": "naver",
        "query": cleaned,
        "naver_mobile_url": mobile_url,
    })
    return parsed
