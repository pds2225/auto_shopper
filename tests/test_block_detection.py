# -*- coding: utf-8 -*-
"""봇차단/접속불가 화면 감지(detect_block) 회귀 테스트 — 네트워크 0."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from naver_common import detect_block  # noqa: E402


# E2E 2026-06-11 실측: 리뷰 수집 중 뜬 네이버 접속 차단 화면 전문
ACCESS_BLOCK_SCREEN = (
    "현재 서비스 접속이 불가합니다. "
    "동시에 접속하는 이용자 수가 많거나 인터넷 네트워크 상태가 불안정하여 접속이 불가합니다. "
    "이용에 불편을 드린 점 진심으로 사과 드리며, 잠시 후 다시 접속해 주시기 바랍니다. "
    "관련 문의사항은 고객센터에 문의해주시면 친절히 안내해드리겠습니다."
)


def test_detects_access_block_screen():
    """접속 차단 변종을 needs_human 으로 잡아야 한다 (이전엔 놓쳤던 케이스)."""
    assert detect_block(ACCESS_BLOCK_SCREEN, "네이버쇼핑") is True


def test_detects_access_block_from_title_only():
    assert detect_block("", "현재 서비스 접속이 불가합니다") is True


def test_detects_classic_security_screen():
    assert detect_block("보안 확인이 필요합니다", "네이버") is True


def test_detects_captcha():
    assert detect_block("Please complete the CAPTCHA", "") is True


def test_normal_page_is_not_blocked():
    """정상 상품/리뷰 페이지는 차단으로 오인하지 않는다."""
    normal = "무선청소기 39,800원 쿠폰적용가 35,800원 리뷰 1,240개 평점 4.5"
    assert detect_block(normal, "무선청소기 : 네이버쇼핑") is False


def test_empty_inputs_are_safe():
    assert detect_block("", "") is False
    assert detect_block(None, None) is False
