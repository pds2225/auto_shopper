# -*- coding: utf-8 -*-
"""매물카드 파싱·가격추출(parse_listing / parse_price_won) 테스트.

네트워크 0 — daangn_parsers 순수함수만 호출. 계획 §3 test_daangn_listing_parse.py.
필수: "35만원"->350000, "1.5만원"->15000, 콤마/원 표기, 실패->None.
"""
import daangn_parsers as P


# --- parse_price_won ---

def test_price_comma_won():
    """천단위 콤마 + 원."""
    assert P.parse_price_won("350,000원") == 350000
    assert P.parse_price_won("1,234,000원") == 1234000


def test_price_no_comma():
    """콤마 없는 원 표기."""
    assert P.parse_price_won("9800원") == 9800


def test_price_man_won():
    """만원 표기 "35만원"->350000."""
    assert P.parse_price_won("35만원") == 350000


def test_price_decimal_man_won():
    """소수 만원 표기 "1.5만원"->15000."""
    assert P.parse_price_won("1.5만원") == 15000


def test_price_man_with_space():
    """공백 변형 "35 만 원"."""
    assert P.parse_price_won("35 만 원") == 350000


def test_price_failures_return_none():
    """추출 실패 -> None (예외 없음)."""
    assert P.parse_price_won("") is None
    assert P.parse_price_won(None) is None
    assert P.parse_price_won("가격문의") is None
    assert P.parse_price_won("원") is None


# --- parse_listing ---

def test_parse_listing_basic():
    """정상 카드 제목+가격+상태태그."""
    card = "에어팟 프로 2세대 S급\n290,000원\n역삼동\n3분 전"
    out = P.parse_listing(card)
    assert out["title"] == "에어팟 프로 2세대 S급"
    assert out["price"] == 290000
    assert "s급" in out["tags"]
    assert out["condition"] == "상급"
    assert out["traded"] is False
    assert out["link"] is None


def test_parse_listing_man_won_card():
    """만원 표기 카드."""
    card = "갤럭시 버즈\n3만원\n삼성동"
    out = P.parse_listing(card)
    assert out["price"] == 30000


def test_parse_listing_traded_complete():
    """"거래완료" -> traded=True."""
    out = P.parse_listing("아이폰 14\n700,000원\n거래완료")
    assert out["traded"] is True


def test_parse_listing_reserved():
    """"예약중" -> traded=True."""
    out = P.parse_listing("닌텐도 스위치\n250,000원\n예약중")
    assert out["traded"] is True


def test_parse_listing_no_price():
    """가격 줄 없는 카드 -> price=None (예외 없음)."""
    out = P.parse_listing("에어팟 프로 가격 문의\n역삼동")
    assert out["price"] is None
    assert out["title"] is not None


def test_parse_listing_strips_ad_and_jjim_labels():
    """찜수/광고 라벨 섞인 카드 -> 제목만 정제."""
    card = "광고\n에어팟 프로 2세대\n290,000원\n찜"
    out = P.parse_listing(card)
    assert out["title"] == "에어팟 프로 2세대"
