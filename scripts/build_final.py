# -*- coding: utf-8 -*-
r"""
build_final.py — 통합추천 폴백 생성기 (AC-4)

입력:
  _workspace/03_prices.json   (필수)
  _workspace/04_reviews.json  (선택)
  _workspace/04_review_risk.json (선택 — review-risk-analyst 산출)

출력:
  _workspace/05_final.json  (정본)
  _workspace/05_final_recommendation.json (별칭)

네트워크/브라우저 일절 없음 — 순수 파일 처리.
"""
import os
import sys
import json

# scripts/ 디렉터리가 패키지 경로에 없을 때를 대비한 경로 주입
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from naver_common import save_with_alias, now, OUT_DIR
from naver_parsers import score_offer, validate_schema


# ---------------------------------------------------------------------------
# 페널티 상수
# ---------------------------------------------------------------------------
_PENALTY_EXCLUDE = 1.5   # verdict == "제외" → 랭크 최하위로
_PENALTY_CAUTION = 0.3   # verdict == "주의"
_PENALTY_NONE    = 0.0   # verdict == "안전" / "미상" / 없음


def _load_json(path):
    """JSON 파일 로드. 없거나 깨지면 None."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[경고] {path} 읽기 실패: {e}")
        return None


def _build_review_index(reviews_data):
    """04_reviews.json products 를 link/title 기준 dict 로 인덱싱.

    반환: {link_or_title: {"rating_avg": float|None, "reviews": list}}
    """
    idx = {}
    if not reviews_data:
        return idx
    for p in reviews_data.get("products") or []:
        key_link  = (p.get("link") or "").strip()
        key_title = (p.get("title") or "").strip()
        entry = {
            "rating_avg": p.get("rating_avg"),
            "reviews": p.get("reviews") or [],
        }
        if key_link:
            idx[key_link] = entry
        if key_title:
            idx[key_title] = entry
    return idx


def _build_risk_index(risk_data):
    """04_review_risk.json 의 판정 결과를 link/title 기준 dict 로 인덱싱.

    review-risk-analyst 가 산출하는 스키마를 관대하게 수용한다.
    반환: {link_or_title: verdict_str}  (없으면 "미상")
    """
    idx = {}
    if not risk_data:
        return idx
    # 상품별 판정 목록이 있는 경우
    for item in risk_data.get("products") or risk_data.get("results") or []:
        verdict = (item.get("verdict") or item.get("risk_verdict") or "미상").strip()
        key_link  = (item.get("link") or "").strip()
        key_title = (item.get("title") or item.get("name") or "").strip()
        if key_link:
            idx[key_link] = verdict
        if key_title:
            idx[key_title] = verdict
    # 전체 단일 verdict 만 있는 경우 (단일 상품 리포트)
    if not idx:
        top_verdict = risk_data.get("verdict") or risk_data.get("risk_verdict")
        if top_verdict:
            idx["__global__"] = top_verdict.strip()
    return idx


def _lookup_verdict(risk_idx, link, title):
    """risk 인덱스에서 verdict 조회. link 우선, 없으면 title, 그것도 없으면 "미상"."""
    if not risk_idx:
        return "미상"
    if link and link.strip() in risk_idx:
        return risk_idx[link.strip()]
    if title and title.strip() in risk_idx:
        return risk_idx[title.strip()]
    if "__global__" in risk_idx:
        return risk_idx["__global__"]
    return "미상"


def _lookup_rating(rev_idx, link, title):
    """review 인덱스에서 rating 조회.

    rating_avg 우선, 없으면 reviews 내 rating 평균, 그것도 없으면 None.
    """
    entry = None
    if link and link.strip() in rev_idx:
        entry = rev_idx[link.strip()]
    elif title and title.strip() in rev_idx:
        entry = rev_idx[title.strip()]
    if entry is None:
        return None
    avg = entry.get("rating_avg")
    if avg is not None:
        try:
            return float(avg)
        except (TypeError, ValueError):
            pass
    # reviews 내 rating 평균
    ratings = [
        float(r["rating"]) for r in (entry.get("reviews") or [])
        if r.get("rating") is not None
    ]
    if ratings:
        return round(sum(ratings) / len(ratings), 2)
    return None


def _penalty_for(verdict):
    """verdict 문자열 → 페널티 값."""
    v = (verdict or "").strip()
    if v == "제외":
        return _PENALTY_EXCLUDE
    if v == "주의":
        return _PENALTY_CAUTION
    return _PENALTY_NONE


def _make_why(name, final_price, verdict, rating, confidence):
    """한국어 한 문장 why 생성."""
    parts = []
    if confidence == "실결제가":
        parts.append("최저 실결제가")
    else:
        parts.append("참고가")
    if rating is not None:
        parts.append(f"평점 {rating:.1f}")
    if verdict == "안전":
        parts.append("deal-breaker 없음")
    elif verdict == "주의":
        parts.append("리뷰 주의 필요")
    elif verdict == "제외":
        parts.append("리뷰 위험 제외 대상")
    else:
        parts.append("리뷰 미확인")
    return " + ".join(parts)


# ---------------------------------------------------------------------------
# 핵심 순수 함수 (파일 I/O 없음 — 테스트 대상)
# ---------------------------------------------------------------------------

def build(prices: dict, reviews: dict | None, risk: dict | None) -> dict:
    """03/04 dict 를 받아 05_final 구조를 반환하는 순수 함수.

    파일 I/O 없음. main() 과 외부 테스트 양쪽에서 호출 가능.
    """
    query = (prices or {}).get("query") or "unknown"
    offers = (prices or {}).get("offers") or []

    rev_idx  = _build_review_index(reviews)
    risk_idx = _build_risk_index(risk)

    # 가격 정규화를 위한 그룹 내 최저 final_price
    priced_offers = [
        o for o in offers
        if isinstance(o.get("final_price"), (int, float))
    ]
    min_price = min((o["final_price"] for o in priced_offers), default=None)

    ranked = []
    for offer in offers:
        title      = (offer.get("title") or offer.get("mall") or "").strip()
        link       = (offer.get("link") or offer.get("url") or "").strip()
        final      = offer.get("final_price")
        confidence = offer.get("confidence") or "참고가"
        is_ref     = offer.get("is_reference", confidence == "참고가")

        verdict = _lookup_verdict(risk_idx, link, title)
        rating  = _lookup_rating(rev_idx, link, title)
        penalty = _penalty_for(verdict)

        # price_norm: 그룹 내 최저 / 해당가 (0~1, 낮은 가격일수록 1.0)
        if min_price and isinstance(final, (int, float)) and final > 0:
            price_norm = min_price / final
        else:
            price_norm = 0.0

        # rating None → 중립 0.5 가중치 적용 (5점 척도 기준 2.5점)
        effective_rating = rating if rating is not None else 2.5

        sc = score_offer(price_norm, effective_rating, penalty)

        # confidence == "참고가" 는 is_ref_flag 으로 별도 표기 (정렬 시 활용)
        ranked.append({
            "name":           title,
            "final_price":    final,
            "review_verdict": verdict,
            "score":          sc,
            "buy_url":        link or offer.get("url") or "",
            "confidence":     confidence,
            "why":            _make_why(title, final, verdict, rating, confidence),
            "_is_ref":        is_ref,   # 정렬용 내부 플래그 (출력 제외)
        })

    # 정렬:
    #  1) 점수 내림차순
    #  2) 동점 시 참고가(is_ref=True) 후순위
    ranked.sort(key=lambda x: (-x["score"], x["_is_ref"]))

    # 내부 플래그 제거 후 출력 리스트
    rank_out = []
    for item in ranked:
        out = {k: v for k, v in item.items() if k != "_is_ref"}
        rank_out.append(out)

    return {
        "query": query,
        "ts":    now(),
        "rank":  rank_out,
        "note":  "결제 직전까지 차려둠. 결제 버튼은 직접 눌러주세요.",
    }


# ---------------------------------------------------------------------------
# main — 파일 I/O
# ---------------------------------------------------------------------------

def main():
    prices_path = os.path.join(OUT_DIR, "03_prices.json")
    reviews_path = os.path.join(OUT_DIR, "04_reviews.json")
    risk_path    = os.path.join(OUT_DIR, "04_review_risk.json")

    # 03 필수
    if not os.path.exists(prices_path):
        print("[오류] 먼저 naver_product_detail.py 실행")
        sys.exit(1)

    prices  = _load_json(prices_path)
    reviews = _load_json(reviews_path)   # 없으면 None
    risk    = _load_json(risk_path)      # 없으면 None

    if reviews is None:
        print("[안내] 04_reviews.json 없음 - 평점 없이 진행")
    if risk is None and reviews:
        from naver_parsers import assess_reviews_document
        risk = assess_reviews_document(reviews)
        print("[안내] 04_review_risk.json 없음 - 휴리스틱 판정 사용")
    elif risk is None:
        print("[안내] 04_review_risk.json 없음 - verdict='미상'으로 진행")

    result = build(prices, reviews, risk)

    # 자가 검증
    required = [
        "rank.name", "rank.final_price", "rank.review_verdict",
        "rank.score", "rank.buy_url", "note",
    ]
    missing = validate_schema(result, required)
    if missing:
        print(f"[오류] 스키마 검증 실패 - 누락 키: {missing}")
        sys.exit(1)

    paths = save_with_alias(result, "05_final.json", ["05_final_recommendation.json"])
    print(f"[저장] {', '.join(paths)}")

    # 콘솔 요약 (1~N순위)
    print()
    print(f"{'순위':>3}  {'이름':<30}  {'최종가':>8}  {'verdict':<6}  {'score':>6}")
    print("-" * 65)
    for i, item in enumerate(result["rank"], 1):
        name     = (item["name"] or "")[:30]
        price    = item["final_price"]
        price_s  = f"{price:,}원" if isinstance(price, int) else str(price)
        verdict  = item["review_verdict"] or "미상"
        score    = item["score"]
        print(f"{i:>3}. {name:<30}  {price_s:>8}  {verdict:<6}  {score:>6.4f}")
    print()
    print(f"[note] {result['note']}")


if __name__ == "__main__":
    main()
