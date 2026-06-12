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


# E2E 실측: 신일 상세 페이지에 인라인으로 노출된 리뷰 텍스트(셀렉터 폴백 대상)
NAVER_INLINE_REVIEWS = (
    "4점 이상 리뷰가 94%예요\n도움말\n"
    "평점\n5소음보통이에요\n드레스룸에서 머리를 말리는데 하도 머리카락이 많이 빠져서 샀어요. "
    "이건 당연히 부용도이고 그때그때 생기는 먼지 부스러기 쓰레기 정리하기엔 너무 좋아요\n"
    "평점\n4소음보통이에요\n바닥에 있는 머리카락 책상위 청소할려고 구입했어요 작은 사이즈로 딱 좋네요 만족합니다\n"
    "평점\n1소음시끄러워요\n한 달 만에 흡입력이 확 떨어졌어요. 배터리도 금방 닳고 별로입니다\n"
    "평점\n5소음보통이에요\n생각했던 것보다 훨씬 좋습니다 배송도 빠르고 포장도 꼼꼼해서 만족합니다"
)


def test_extract_reviews_from_text_inline():
    """셀렉터 0개일 때 페이지 텍스트에서 리뷰를 직접 추출해야 한다."""
    reviews = P.extract_reviews_from_text(NAVER_INLINE_REVIEWS)
    assert len(reviews) == 4
    ratings = [r["rating"] for r in reviews]
    assert ratings == [5.0, 4.0, 1.0, 5.0]          # 낮은 평점(1.0) 포함
    assert "머리카락" in reviews[0]["text"]
    assert "소음보통이에요" not in reviews[0]["text"]  # 속성 라벨은 본문에서 제외


def test_extract_reviews_from_text_empty():
    assert P.extract_reviews_from_text("") == []
    assert P.extract_reviews_from_text("리뷰 없음 평점 정보 없음") == []


def test_review_pipeline_from_fixture(review_blocks):
    parsed = [P.parse_review_block(b) for b in review_blocks]
    deduped = P.dedup_reviews(parsed)
    # 픽스처에 동일 5.0 리뷰 2개 -> dedup 후 1개 줄어듦
    assert len(deduped) == len(review_blocks) - 1
    # 낮은 평점(1.0) 리뷰가 포함돼야 한다 (AC-3 낮은평점 포함)
    assert any(r["rating"] == 1.0 for r in deduped)
