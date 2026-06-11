# -*- coding: utf-8 -*-
"""가격추출 테스트 (계획 4.1) — 네트워크 0, naver_parsers 만 호출."""
import naver_parsers as P


def test_parse_price_won_basic():
    assert P.parse_price_won("39,800원") == 39800
    assert P.parse_price_won("1,234,000원") == 1234000
    assert P.parse_price_won("9800원") == 9800


def test_parse_price_won_failures():
    assert P.parse_price_won("원") is None
    assert P.parse_price_won("") is None
    assert P.parse_price_won(None) is None
    assert P.parse_price_won("무료배송") is None


def test_extract_coupon_price_present(detail_text):
    out = P.extract_coupon_price(detail_text)
    assert out["coupon_price"] == 142000
    assert out["list_price"] == 159000


def test_extract_coupon_price_absent():
    txt = "판매가 50,000원\n배송 무료배송"
    out = P.extract_coupon_price(txt)
    assert out["coupon_price"] is None
    assert out["list_price"] == 50000


def test_extract_checkout_breakdown_full(checkout_text):
    out = P.extract_checkout_breakdown(checkout_text)
    assert out["card_discount"] == 5000
    assert out["point"] == 2840
    assert out["shipping"] == 0  # "배송비 무료"
    assert out["final_price"] == 137000


def test_extract_checkout_breakdown_partial(checkout_partial_text):
    out = P.extract_checkout_breakdown(checkout_partial_text)
    # 카드할인/포인트 없음 -> 0, 배송비 3000, 최종가 미표기 -> None
    assert out["card_discount"] == 0
    assert out["point"] == 0
    assert out["shipping"] == 3000
    assert out["final_price"] is None


def test_compute_final_price_real():
    # 주문서값 있으면 실결제가 (is_reference=False)
    final, is_ref = P.compute_final_price({"final_price": 137000})
    assert final == 137000
    assert is_ref is False


def test_compute_final_price_reference_coupon():
    # 주문서 없음 -> 쿠폰가 폴백 (참고가)
    final, is_ref = P.compute_final_price({"final_price": None, "coupon_price": 142000})
    assert final == 142000
    assert is_ref is True


def test_compute_final_price_reference_list():
    # 쿠폰가도 없음 -> 표시가 폴백 (참고가)
    final, is_ref = P.compute_final_price({"final_price": None, "list_price": 159000})
    assert final == 159000
    assert is_ref is True


def test_compute_final_price_all_missing():
    final, is_ref = P.compute_final_price({})
    assert final is None
    assert is_ref is True
