# -*- coding: utf-8 -*-
"""봇차단/로그인유도/지역인증 감지(detect_block) 테스트.

네트워크 0 — daangn_common 순수함수만 호출. 계획 §3 test_daangn_block.py.
BLOCK_SIGNALS 각 시그널 True / 정상 텍스트 False / 빈입력 False.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from daangn_common import detect_block, BLOCK_SIGNALS  # noqa: E402


def test_normal_text_not_blocked():
    """정상 검색/매물 텍스트는 차단으로 오인하지 않는다."""
    normal = "에어팟 프로 2세대 290,000원 역삼동 3분 전 채팅 1"
    assert detect_block(normal, "당근마켓") is False


def test_bot_block_signals():
    """봇차단 시그널 -> True."""
    assert detect_block("보안 확인이 필요합니다", "당근") is True
    assert detect_block("비정상적인 접근이 감지되었습니다", "") is True


def test_login_prompt_signals():
    """로그인 유도 시그널 -> True."""
    assert detect_block("로그인이 필요해요", "당근마켓") is True
    assert detect_block("로그인 후 이용해 주세요", "") is True


def test_region_auth_signals():
    """지역(동네) 인증 시그널 -> True."""
    assert detect_block("동네 인증이 필요해요", "당근") is True
    assert detect_block("위치 인증을 진행해 주세요", "") is True


def test_empty_and_none_inputs_safe():
    """빈/None 입력 -> False."""
    assert detect_block("", "") is False
    assert detect_block(None, None) is False


def test_every_block_signal_detected():
    """BLOCK_SIGNALS 의 모든 시그널이 각각 단독으로 True 를 만든다."""
    for sig in BLOCK_SIGNALS:
        assert detect_block(sig, "") is True, f"미감지 시그널: {sig}"


def test_signal_in_title_only():
    """body 가 비어도 title 에 시그널 있으면 True."""
    assert detect_block("", "로그인이 필요") is True
