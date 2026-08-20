# -*- coding: utf-8 -*-
"""리뷰 위험 휴리스틱 (assess_product_reviews / assess_reviews_document) — 네트워크 0."""
import naver_parsers as P


def test_no_reviews_is_unknown():
    out = P.assess_product_reviews([])
    assert out["verdict"] == "미상"


def test_counterfeit_is_exclude():
    out = P.assess_product_reviews([
        {"text": "가품입니다. 정품이 아니에요.", "rating": 1.0},
    ])
    assert out["verdict"] == "제외"
    assert any("가품" in r for r in out["reasons"])


def test_fraud_keyword_is_exclude():
    out = P.assess_product_reviews([{"text": "사기 당했어요 환불 거부", "rating": 1.0}])
    assert out["verdict"] == "제외"


def test_one_star_with_caution_is_caution():
    out = P.assess_product_reviews([
        {"text": "한 달 만에 흡입력 떨어져요. 배터리도 금방 닳고 AS도 느려요. 비추천.",
         "rating": 1.0},
        {"text": "무난해요", "rating": 4.0},
    ])
    assert out["verdict"] == "주의"


def test_all_positive_is_safe():
    out = P.assess_product_reviews([
        {"text": "흡입력 정말 좋아요. 가성비 최고입니다.", "rating": 5.0},
        {"text": "잘 쓰고 있습니다", "rating": 4.0},
    ])
    assert out["verdict"] == "안전"


def test_low_average_many_reviews_is_caution():
    reviews = [{"text": "그저 그래요", "rating": 2.0} for _ in range(3)]
    out = P.assess_product_reviews(reviews, rating_avg=2.0)
    assert out["verdict"] == "주의"


def test_assess_document_fills_products():
    doc = {
        "query": "무선청소기",
        "products": [
            {"title": "위험상품", "link": "https://x/bad",
             "reviews": [{"text": "짝퉁 가품이에요", "rating": 1.0}]},
            {"title": "좋은상품", "link": "https://x/good",
             "reviews": [{"text": "최고예요", "rating": 5.0}]},
            {"title": "리뷰없음", "link": "https://x/none", "reviews": []},
        ],
    }
    out = P.assess_reviews_document(doc)
    assert out["source"] == "heuristic"
    by_title = {p["title"]: p["verdict"] for p in out["products"]}
    assert by_title["위험상품"] == "제외"
    assert by_title["좋은상품"] == "안전"
    assert by_title["리뷰없음"] == "미상"
