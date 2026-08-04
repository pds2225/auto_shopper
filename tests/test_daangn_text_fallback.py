# -*- coding: utf-8 -*-
"""텍스트 폴백 분할(parse_search_listings_from_text) 테스트 — [B1 신규, AC-4 단위].

네트워크 0 — daangn_parsers 순수함수만 호출. 계획 §3 test_daangn_text_fallback.py.
필수 4: 멀티카드 blob->N개, 쓰레기->[], 가격없는 카드 price=None 보존,
거래완료 마커로 분할.
"""
import daangn_parsers as P


def test_multi_card_blob_splits_to_n():
    """멀티카드 blob(3개 카드 연결) -> 3개 dict."""
    blob = (
        "에어팟 프로 2세대 S급\n290,000원\n역삼동\n3분 전\n"
        "에어팟 프로 2세대 미개봉\n330,000원\n삼성동\n10분 전\n"
        "에어팟 프로 1세대\n150,000원\n논현동\n1시간 전\n"
    )
    out = P.parse_search_listings_from_text(blob)
    assert isinstance(out, list)
    assert len(out) == 3
    prices = [x["price"] for x in out]
    assert 290000 in prices
    assert 330000 in prices
    assert 150000 in prices


def test_garbage_blob_returns_empty():
    """쓰레기/빈 blob -> []."""
    assert P.parse_search_listings_from_text("") == []
    assert P.parse_search_listings_from_text(None) == []
    assert P.parse_search_listings_from_text("메뉴 홈 검색 내 동네 채팅 마이페이지") == []


def test_card_without_price_preserved():
    """가격 없는 카드 포함 blob -> 해당 카드 price=None (드롭 안 함)."""
    blob = (
        "에어팟 프로 2세대 S급\n290,000원\n역삼동\n3분 전\n"
        "에어팟 프로 가격문의\n거래완료\n삼성동\n"
    )
    out = P.parse_search_listings_from_text(blob)
    # 거래완료 마커로 두 번째 카드가 분할되어 보존돼야 한다.
    assert len(out) >= 2
    assert any(x["price"] is None for x in out)


def test_traded_marker_splits_cards():
    """거래완료 마커로 카드 경계 분할 확인."""
    blob = (
        "닌텐도 스위치\n250,000원\n거래완료\n"
        "닌텐도 스위치 OLED\n300,000원\n역삼동\n5분 전\n"
    )
    out = P.parse_search_listings_from_text(blob)
    assert len(out) == 2
    # 첫 카드는 거래완료 표시.
    assert any(x["traded"] for x in out)
    assert any(x["price"] == 300000 for x in out)
