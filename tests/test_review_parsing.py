# -*- coding: utf-8 -*-
"""리뷰 파싱 테스트 (계획 4.3) — 네트워크 0."""
import naver_parsers as P


def test_parse_review_block_full():
    block = "별점 5.0\n2026.05.20\n흡입력 정말 좋아요. 강력 추천합니다."
    out = P.parse_review_block(block)
    assert out["rating"] == 5.0
    assert out["date"] == "2026-05-20"
    assert "흡입력" in out["text"]


def test_parse_review_block_low_rating_dotted_date():
    block = "평점 1.0\n2026. 5. 1\n한 달 만에 흡입력 떨어져요."
    out = P.parse_review_block(block)
    assert out["rating"] == 1.0
    assert out["date"] == "2026-05-01"  # zero-pad


def test_parse_review_block_jeom_format():
    block = "4.0점\n2026-04-15\n무난해요."
    out = P.parse_review_block(block)
    assert out["rating"] == 4.0
    assert out["date"] == "2026-04-15"


def test_parse_review_block_no_rating():
    block = "좋아요 잘 쓰고 있습니다 별점 없는 리뷰"
    out = P.parse_review_block(block)
    assert out["rating"] is None


def test_parse_review_block_empty():
    out = P.parse_review_block("")
    assert out["rating"] is None
    assert out["date"] is None
    assert out["text"] == ""


def test_dedup_reviews_exact():
    reviews = [
        {"text": "흡입력 좋아요", "rating": 5.0},
        {"text": "흡입력 좋아요", "rating": 5.0},
        {"text": "배터리 약해요", "rating": 2.0},
    ]
    out = P.dedup_reviews(reviews)
    assert len(out) == 2


def test_dedup_reviews_whitespace():
    # 공백차이만 있는 중복 -> 1개
    reviews = [
        {"text": "흡입력  좋아요"},
        {"text": "흡입력 좋아요"},
    ]
    out = P.dedup_reviews(reviews)
    assert len(out) == 1


def test_review_pipeline_from_fixture(review_blocks):
    parsed = [P.parse_review_block(b) for b in review_blocks]
    deduped = P.dedup_reviews(parsed)
    # 픽스처에 동일 5.0 리뷰 2개 -> dedup 후 1개 줄어듦
    assert len(deduped) == len(review_blocks) - 1
    # 낮은 평점(1.0) 리뷰가 포함돼야 한다 (AC-3 낮은평점 포함)
    assert any(r["rating"] == 1.0 for r in deduped)
