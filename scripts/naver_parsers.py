# -*- coding: utf-8 -*-
r"""
네이버 쇼핑 순수 파싱 모듈 (2단계)

브라우저/네트워크를 절대 import 하지 않는다. 전부 str/dict in -> dict out.
AC-7(네트워크 없는 단위테스트)의 핵심 타깃. tests 가 이 모듈만 호출하면
네트워크/브라우저 0.

스키마는 계획 섹션 2와 정확히 일치한다.
"""
import re

# 가격 정규식 (naver_poc.py L155 일반화). "39,800원" / "9800원"
_PRICE_RE = re.compile(r"([0-9][0-9,]*)\s*원")


def parse_price_won(text):
    """가격 문자열 -> int. "39,800원" -> 39800. 실패 시 None.

    천단위 콤마/공백 변형 처리. 콤마 없는 "9800원" 도 허용.
    """
    if not text:
        return None
    m = _PRICE_RE.search(text)
    if not m:
        return None
    digits = m.group(1).replace(",", "")
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _find_price_after(text, labels, allow_newline=False):
    """라벨(쿠폰적용가 등) 뒤 근접 위치의 가격을 찾는다. 못 찾으면 None.

    라벨과 가격 사이 간격을 좁게(비숫자 0~20자) 제한해 엉뚱한 가격을 막는다.
    allow_newline=True 면 "상품 가격\n49,900원"처럼 다음 줄의 가격도 허용한다
    (네이버 상세는 라벨/가격이 다른 줄에 오는 경우가 흔하다).
    """
    if not text:
        return None
    gap = r"[^0-9]{0,20}?" if allow_newline else r"[^0-9\n]{0,20}?"
    for label in labels:
        pat = re.compile(re.escape(label) + gap + r"([0-9][0-9,]*)\s*원")
        m = pat.search(text)
        if m:
            return int(m.group(1).replace(",", ""))
    return None


def _find_price_near(text, labels):
    """라벨이 가격 앞/뒤 어디에 있어도 근접 가격을 찾는다.

    네이버 상세는 "쿠폰적용가 142,000원"(라벨->가격)도 있고
    "49,400원나의 할인가"(가격->라벨)도 있다. 둘 다 잡는다.
    """
    if not text:
        return None
    for label in labels:
        esc = re.escape(label)
        # 라벨 -> 가격 (같은 줄, 비숫자 0~20자)
        m = re.search(esc + r"[^0-9\n]{0,20}?([0-9][0-9,]*)\s*원", text)
        if m:
            return int(m.group(1).replace(",", ""))
        # 가격 -> 라벨 (가격 바로 뒤에 라벨이 붙는 형태)
        m = re.search(r"([0-9][0-9,]*)\s*원[^0-9\n]{0,8}?" + esc, text)
        if m:
            return int(m.group(1).replace(",", ""))
    return None


def extract_coupon_price(detail_text):
    """상세 텍스트에서 쿠폰적용가/할인가 + 판매가 추출.

    반환: {"coupon_price": int|None, "list_price": int|None}

    주의: "할인 전 가격"(취소선 정가)은 절대 판매가로 쓰지 않는다.
    실제 결제가는 "나의 할인가"/"쿠폰적용가"를, 판매가는 "상품 가격"을 우선한다.
    """
    coupon = _find_price_near(
        detail_text,
        ["나의 할인가", "내 할인가", "쿠폰적용가", "쿠폰 적용가",
         "즉시할인가", "할인적용가"],
    )
    # 판매가: '상품 가격'/'판매가' 우선. '할인 전 가격'(취소선)은 라벨에 넣지 않는다.
    # 네이버는 "상품 가격\n49,900원"처럼 다음 줄에 가격이 오므로 줄바꿈 허용.
    listp = _find_price_after(
        detail_text,
        ["상품 가격", "상품가격", "판매가", "판매 가격", "정가", "상품금액", "최저"],
        allow_newline=True,
    )
    if listp is None:
        # 라벨 없이 첫 가격을 표시가로 폴백
        listp = parse_price_won(detail_text)
    return {"coupon_price": coupon, "list_price": listp}


def extract_checkout_breakdown(checkout_text):
    """주문서(결제 직전) 텍스트에서 카드할인/포인트/배송비/최종결제금액 분해.

    반환: {"card_discount": int, "point": int, "shipping": int, "final_price": int|None}
    못 찾은 할인/포인트/배송비는 0, 최종가는 None.
    """
    card = _find_price_after(checkout_text, ["카드할인", "카드 할인", "즉시할인"])
    point = _find_price_after(checkout_text, ["포인트", "적립", "네이버페이"])
    shipping = _find_price_after(checkout_text, ["배송비"])
    final = _find_price_after(
        checkout_text,
        ["최종결제금액", "최종 결제 금액", "총 결제금액", "총결제금액", "결제예정금액", "결제 예정 금액"],
    )
    # 배송비 "무료" 처리 ("무료배송" / "배송비 무료" / "배송 무료")
    if shipping is None and checkout_text:
        if "무료배송" in checkout_text or re.search(r"배송\S*\s*무료", checkout_text):
            shipping = 0
    return {
        "card_discount": card or 0,
        "point": point or 0,
        "shipping": shipping or 0,
        "final_price": final,
    }


def compute_final_price(breakdown):
    """최종가 + is_reference(참고가 여부) 계산. AC-2.

    주문서 final 있으면 (final, False)=실결제가.
    없으면 쿠폰가 -> 표시가 순 폴백 + is_reference=True(참고가).
    아무것도 없으면 (None, True).
    """
    breakdown = breakdown or {}
    final = breakdown.get("final_price")
    if final is not None:
        return final, False
    coupon = breakdown.get("coupon_price")
    if coupon is not None:
        return coupon, True
    listp = breakdown.get("list_price")
    if listp is not None:
        return listp, True
    return None, True


def _to_int(val):
    """문자열/숫자 -> int (콤마/원 제거). 실패 시 None."""
    if val is None:
        return None
    if isinstance(val, bool):
        return None
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        return int(val)
    s = str(val).replace(",", "").replace("원", "").strip()
    if not s:
        return None
    m = re.search(r"-?[0-9]+", s)
    return int(m.group(0)) if m else None


def _clean_title(raw):
    """카드 텍스트 블록에서 상품명 한 줄만 추출.

    browser형 text 는 "찜하기0\n\t\n신일 무선 핸디 청소기...\n49,900원\n배송비\n..."
    처럼 카드 전체가 담긴다. 찜하기/광고/가격/숫자 줄을 걷어내고 첫 상품명 줄을 고른다.
    """
    if not raw:
        return None
    for ln in str(raw).split("\n"):
        ln = ln.strip()
        # 줄 앞에 붙은 "찜하기N" 제거 후 재검사
        ln = re.sub(r"^찜하기\d*\s*", "", ln).strip()
        if not ln:
            continue
        if ln in ("찜", "찜하기", "광고", "AD", "ad", "구매", "리뷰", "배송비", "무료"):
            continue
        # 가격/숫자만 있는 줄 제외
        if re.fullmatch(r"[\d,]+\s*원?", ln):
            continue
        if re.fullmatch(r"[\d,]+", ln):
            continue
        return ln[:120]
    return None


def normalize_candidate(raw_item):
    """01_candidates 항목을 단일 스키마로 정규화.

    browser형 {text, price_guess, link} 과 api형 {title, lprice, mall, link,
    productId} 둘 다 흡수. 깨진 입력(빈 dict)도 예외 없이 None 채움.

    반환: {"rank", "title", "list_price", "mall", "link", "product_id"}
    """
    raw_item = raw_item or {}
    # 제목: api형 title 우선(이미 정제됨), 없으면 browser형 text 를 정제
    api_title = raw_item.get("title")
    if api_title:
        title = str(api_title).strip() or None
    else:
        title = _clean_title(raw_item.get("text"))
    # 가격: api형 lprice 우선, 없으면 browser형 price_guess
    list_price = _to_int(raw_item.get("lprice"))
    if list_price is None:
        list_price = _to_int(raw_item.get("price_guess"))
    mall = raw_item.get("mall") or None
    link = raw_item.get("link") or None
    product_id = raw_item.get("productId") or raw_item.get("product_id") or None
    if product_id is not None:
        product_id = str(product_id)
    rank = raw_item.get("rank")
    return {
        "rank": rank,
        "title": title,
        "list_price": list_price,
        "mall": mall,
        "link": link,
        "product_id": product_id,
    }


# 별점: "별점 4.0", "평점 4.5", "4.0점", "★★★★☆", "5점"
_RATING_RE = re.compile(r"(?:별점|평점)\s*([0-5](?:\.[0-9])?)|([0-5](?:\.[0-9])?)\s*점")
# 날짜: 2026.05.01 / 2026-05-01 / 2026. 5. 1
_DATE_RE = re.compile(r"(20[0-9]{2})[.\-\s]+([0-9]{1,2})[.\-\s]+([0-9]{1,2})")


def parse_review_block(block_text):
    """리뷰 한 덩어리 텍스트 -> {"text", "rating": float|None, "date": str|None}."""
    text = (block_text or "").strip()
    rating = None
    m = _RATING_RE.search(text)
    if m:
        val = m.group(1) or m.group(2)
        if val is not None:
            try:
                rating = float(val)
            except ValueError:
                rating = None
    date = None
    dm = _DATE_RE.search(text)
    if dm:
        y, mo, d = dm.group(1), int(dm.group(2)), int(dm.group(3))
        date = f"{y}-{mo:02d}-{d:02d}"
    return {"text": text, "rating": rating, "date": date}


def extract_reviews_from_text(page_text, max_n=40):
    """페이지 inner_text 에서 "평점 N ... 본문" 패턴으로 리뷰 추출 (셀렉터 폴백).

    네이버 상세는 리뷰가 "평점\n5소음좋아요\n본문..." 형태로 인라인 노출되는데,
    리뷰 블록 셀렉터가 0개 매칭일 때 텍스트에서 직접 긁는 안전망이다.

    반환: [{"text", "rating": float|None, "date": str|None}, ...]
    """
    if not page_text:
        return []
    out = []
    for seg in re.split(r"평점", page_text)[1:]:
        m = re.match(r"\s*([0-5])(?:\.[0-9])?", seg)
        if not m:
            continue
        rating = float(m.group(1))
        rest = seg[m.end():]
        lines = [ln.strip() for ln in rest.split("\n") if ln.strip()]
        if not lines:
            continue
        body = max(lines, key=len)  # 본문은 가장 긴 줄(속성 라벨 '소음좋아요'는 짧음)
        if len(body) < 12:
            continue  # 너무 짧으면 리뷰 아님(요약/정렬 라벨 등)
        date = None
        dm = _DATE_RE.search(rest)
        if dm:
            y, mo, d = dm.group(1), int(dm.group(2)), int(dm.group(3))
            date = f"{y}-{mo:02d}-{d:02d}"
        out.append({"text": body[:500], "rating": rating, "date": date})
        if len(out) >= max_n:
            break
    return out


def dedup_reviews(reviews):
    """중복 리뷰 제거. text 의 공백을 정규화해 동일 본문이면 1개만 남긴다."""
    seen = set()
    out = []
    for r in (reviews or []):
        if not isinstance(r, dict):
            continue
        key = re.sub(r"\s+", " ", (r.get("text") or "")).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def build_prices_schema(query, offers, best=None):
    """03_prices.json 스키마 조립 (계획 2.3). price-hunter offers[] 계약."""
    from naver_common import now  # 지연 import (datetime 의존만)
    if best is None and offers:
        priced = [o for o in offers if isinstance(o.get("final_price"), int)]
        if priced:
            b = min(priced, key=lambda o: o["final_price"])
            best = {"mall": b.get("mall"), "final_price": b.get("final_price"), "url": b.get("url")}
    return {
        "query": query,
        "ts": now(),
        "product": query,
        "offers": offers or [],
        "best": best,
    }


def build_reviews_schema(query, products):
    """04_reviews.json 스키마 조립 (계획 2.4)."""
    from naver_common import now
    return {
        "query": query,
        "ts": now(),
        "products": products or [],
    }


def validate_schema(obj, required_keys):
    """obj 에서 누락된 필수키 리스트 반환. 빈 리스트 = 통과.

    required_keys 항목에 "a.b" 점표기는 obj["a"][0]["b"] 형태의
    리스트 첫 원소 키 검증을 의미한다(offers[].mall 같은 계약 회귀 검증용).
    """
    missing = []
    obj = obj or {}
    for key in (required_keys or []):
        if "." in key:
            parent, child = key.split(".", 1)
            seq = obj.get(parent)
            if not isinstance(seq, list) or not seq:
                missing.append(key)
                continue
            first = seq[0] if isinstance(seq[0], dict) else {}
            if child not in first:
                missing.append(key)
        else:
            if key not in obj:
                missing.append(key)
    return missing


def score_offer(price_norm, rating, penalty):
    """통합추천 점수 (계획 1.5 / 2.5). 가성비 + 리뷰가중 - deal_breaker_penalty.

    - price_norm: 정규화 가성비 점수(가격 낮을수록 1.0에 가깝게, 0~1 권장).
      가격이 낮을수록 점수 단조 증가.
    - rating: 평점(0~5). 높을수록 점수 단조 증가.
    - penalty: deal-breaker 페널티(>=0). verdict=="제외" 시 부과 -> 점수 하락.

    반환: float (가독성 위해 소수 4자리 반올림).
    """
    pn = float(price_norm or 0.0)
    rt = float(rating or 0.0)
    pen = float(penalty or 0.0)
    score = pn + (rt / 5.0) - pen
    return round(score, 4)
