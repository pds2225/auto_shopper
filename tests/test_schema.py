# -*- coding: utf-8 -*-
"""스키마 검증 + 점수 단조성 테스트 (계획 4.4) — 네트워크 0."""
import naver_parsers as P


def _sample_offer():
    return {
        "mall": "샤오미스토어", "title": "G10 플러스", "link": "https://x/1",
        "list_price": 159000, "coupon": 17000, "card_discount": 5000,
        "point": 2840, "shipping": 0, "final_price": 137000,
        "confidence": "실결제가", "is_reference": False,
        "cart_cleanup": "removed", "needs_human": False, "url": "https://x/1",
    }


def test_build_prices_schema_keys():
    obj = P.build_prices_schema("무선청소기", [_sample_offer()])
    # 래퍼 필수키
    assert P.validate_schema(obj, ["query", "ts", "product", "offers", "best"]) == []
    # price-hunter 계약: offers[] 키 (에이전트 계약 회귀 테스트)
    contract = ["offers.mall", "offers.final_price", "offers.confidence", "offers.url"]
    assert P.validate_schema(obj, contract) == []
    # best 자동 산출
    assert obj["best"]["final_price"] == 137000


def test_build_reviews_schema_keys():
    products = [{"rank": 1, "title": "G10", "link": "https://x/1",
                 "rating_avg": 4.3, "review_count_seen": 40,
                 "reviews": [{"text": "좋아요", "rating": 5.0, "date": "2026-05-01"}]}]
    obj = P.build_reviews_schema("무선청소기", products)
    assert P.validate_schema(obj, ["query", "ts", "products"]) == []


def test_final_schema_contract():
    # best-deal-finder 기대키 회귀 테스트
    final_obj = {
        "query": "무선청소기", "ts": "2026-06-11 16:00:00",
        "rank": [
            {"name": "G10 플러스", "final_price": 137000, "review_verdict": "안전",
             "score": 0.82, "buy_url": "https://x/1", "confidence": "실결제가",
             "why": "최저 실결제가 + 평점 4.3"}
        ],
        "note": "결제 직전까지 차려둠.",
    }
    contract = ["rank.name", "rank.final_price", "rank.review_verdict",
                "rank.score", "rank.buy_url", "note"]
    assert P.validate_schema(final_obj, contract) == []


def test_validate_schema_detects_missing():
    obj = {"query": "x", "offers": [{"mall": "a"}]}
    missing = P.validate_schema(obj, ["query", "ts", "offers.final_price"])
    assert "ts" in missing
    assert "offers.final_price" in missing
    assert "query" not in missing


def test_validate_schema_empty_list_missing():
    # offers 가 빈 리스트면 offers.x 는 누락으로 판정
    obj = {"offers": []}
    assert "offers.mall" in P.validate_schema(obj, ["offers.mall"])


def test_score_offer_price_monotonic():
    # 가격 낮을수록(price_norm 클수록) 점수 단조 증가
    low_price = P.score_offer(0.9, 4.0, 0.0)   # 싼 제품 -> price_norm 큼
    high_price = P.score_offer(0.3, 4.0, 0.0)  # 비싼 제품 -> price_norm 작음
    assert low_price > high_price


def test_score_offer_rating_monotonic():
    # 평점 높을수록 점수 단조 증가
    high_rating = P.score_offer(0.5, 4.8, 0.0)
    low_rating = P.score_offer(0.5, 2.0, 0.0)
    assert high_rating > low_rating


def test_score_offer_penalty_drops():
    # verdict=="제외" penalty 적용 시 점수 하락
    no_penalty = P.score_offer(0.7, 4.5, 0.0)
    with_penalty = P.score_offer(0.7, 4.5, 1.0)
    assert with_penalty < no_penalty
