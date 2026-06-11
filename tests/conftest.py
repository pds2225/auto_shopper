# -*- coding: utf-8 -*-
"""pytest 공통 설정 — scripts/ 를 import 경로에 추가하고 픽스처 로더 제공."""
import os
import sys
import json
import pytest

# scripts/ 를 sys.path 에 추가 (naver_parsers/naver_common import 가능하게)
_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.join(os.path.dirname(_HERE), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

FIXTURES = os.path.join(_HERE, "fixtures")


def _read(name):
    with open(os.path.join(FIXTURES, name), "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def detail_text():
    return _read("detail_sample.txt")


@pytest.fixture
def checkout_text():
    return _read("checkout_sample.txt")


@pytest.fixture
def checkout_partial_text():
    return _read("checkout_partial.txt")


@pytest.fixture
def review_blocks():
    """=== 구분자로 나눈 리뷰 블록 리스트 (빈 블록 제거)."""
    raw = _read("review_blocks.txt")
    return [b.strip() for b in raw.split("===") if b.strip()]


@pytest.fixture
def candidates_sample():
    with open(os.path.join(FIXTURES, "candidates_sample.json"), "r", encoding="utf-8") as f:
        return json.load(f)
