# -*- coding: utf-8 -*-
"""build_final.build 순수함수 — 제외 강등·휴리스틱 폴백. 네트워크 0."""
import build_final as BF
import naver_parsers as P


def _prices(offers):
    return P.build_prices_schema("무선청소기", offers)


def _offer(title, price, link):
    return {
        "mall": title, "title": title, "link": link, "url": link,
        "list_price": price, "coupon": 0, "card_discount": 0, "point": 0,
        "shipping": 0, "final_price": price, "confidence": "실결제가",
        "is_reference": False, "cart_cleanup": "removed", "needs_human": False,
    }


def test_excluded_cheapest_is_not_first():
    prices = _prices([
        _offer("위험최저가", 10000, "https://x/cheap"),
        _offer("안전중간", 20000, "https://x/mid"),
    ])
    risk = {
        "products": [
            {"title": "위험최저가", "link": "https://x/cheap", "verdict": "제외"},
            {"title": "안전중간", "link": "https://x/mid", "verdict": "안전"},
        ]
    }
    final = BF.build(prices, None, risk)
    assert final["rank"][0]["name"] == "안전중간"
    assert final["rank"][-1]["name"] == "위험최저가"
    assert final["rank"][-1]["review_verdict"] == "제외"


def test_heuristic_used_when_risk_file_missing():
    prices = _prices([
        _offer("짝퉁청소기", 10000, "https://x/fake"),
        _offer("정품청소기", 20000, "https://x/ok"),
    ])
    reviews = P.build_reviews_schema("무선청소기", [
        {"title": "짝퉁청소기", "link": "https://x/fake", "rating_avg": 1.0,
         "reviews": [{"text": "가품입니다", "rating": 1.0, "date": None}]},
        {"title": "정품청소기", "link": "https://x/ok", "rating_avg": 4.8,
         "reviews": [{"text": "좋아요", "rating": 5.0, "date": None}]},
    ])
    risk = P.assess_reviews_document(reviews)
    final = BF.build(prices, reviews, risk)
    assert final["rank"][0]["name"] == "정품청소기"
    fake = [r for r in final["rank"] if r["name"] == "짝퉁청소기"][0]
    assert fake["review_verdict"] == "제외"


def test_no_reviews_no_risk_is_unknown():
    prices = _prices([_offer("상품", 30000, "https://x/1")])
    final = BF.build(prices, None, None)
    assert final["rank"][0]["review_verdict"] == "미상"
    assert "note" in final
