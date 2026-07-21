# -*- coding: utf-8 -*-
"""상태 태그 추출·등급 분류(extract_status_tags / classify_condition) 테스트.

네트워크 0 — daangn_parsers 순수함수만 호출. 계획 §3 test_daangn_status.py 케이스.
계약: classify_condition 은 충돌 시 보수적 다운그레이드(구매자 보호) — 계획 §2.
"""
import daangn_parsers as P


def test_no_tags_empty_list():
    """태그 없는 텍스트 -> []."""
    assert P.extract_status_tags("그냥 평범한 매물입니다") == []


def test_no_tags_classify_normal():
    """태그 없음 -> "보통"."""
    assert P.classify_condition([]) == "보통"
    assert P.classify_condition(P.extract_status_tags("아무 키워드 없음")) == "보통"


def test_unboxed_is_new():
    """미개봉 -> "새것"."""
    tags = P.extract_status_tags("미개봉 새제품 팝니다")
    assert "미개봉" in tags
    assert P.classify_condition(tags) == "새것"


def test_s_grade_is_premium():
    """S급 -> "상급"."""
    tags = P.extract_status_tags("S급 상태 좋아요")
    assert "s급" in tags
    assert P.classify_condition(tags) == "상급"


def test_premium_plus_new_downgrades_to_premium():
    """"S급 풀박스"(상급+새것군) -> "상급" (보수적 다운그레이드, R3①)."""
    tags = P.extract_status_tags("S급 풀박스 미개봉급")
    # 상급 태그(s급)와 새것 태그(풀박스)가 함께 있으면 상급으로 강등.
    assert "s급" in tags
    assert "풀박스" in tags
    assert P.classify_condition(tags) == "상급"


def test_defect_takes_priority_over_premium():
    """"거의새것 액정깨짐"(상급+하자군) -> "하자" (하자 최우선)."""
    tags = P.extract_status_tags("거의새것인데 액정깨짐 있어요")
    assert "거의새것" in tags
    assert "액정깨짐" in tags
    assert P.classify_condition(tags) == "하자"


def test_defect_over_new():
    """하자 태그가 새것 태그와 섞여도 "하자"가 우선."""
    tags = P.extract_status_tags("미개봉이지만 고장 있음")
    assert P.classify_condition(tags) == "하자"


def test_case_and_space_variants():
    """대소문자/공백 변형 "s급","풀 박스" 처리."""
    assert "s급" in P.extract_status_tags("s급 입니다")
    assert "s급" in P.extract_status_tags("S 급 상품")
    assert "풀박스" in P.extract_status_tags("풀 박스 포함")
