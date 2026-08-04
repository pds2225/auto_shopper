# -*- coding: utf-8 -*-
"""리포트 면책 note 회귀(build_report_schema / build / render_markdown) — [AC-7].

네트워크 0 — 순수함수만 호출. 계획 §3 test_daangn_report_note.py.
note 비어있지 않음 + (render_markdown 있으면) 출력에 "호가"/"거래완료" 한계 문구 포함.

build/render_markdown 은 build_report.py(Task5)에 위치한다 — 아직 없으면 그 케이스는 skip.
"""
import importlib

import pytest

import daangn_parsers as P


def test_report_schema_note_not_empty():
    """build_report_schema().note 가 비어있지 않고 호가분포 한계 문구를 담는다."""
    obj = P.build_report_schema(
        query="에어팟 프로",
        mode="link",
        verdict_obj={"label": "비쌈", "percentile": None, "condition": "상급",
                     "target_price": 350000, "confidence": "low"},
        stats_by_condition={},
        cheap_picks=[],
        warnings=[],
    )
    assert "note" in obj
    note = obj["note"]
    assert isinstance(note, str)
    assert note.strip() != ""
    # 호가분포 한계 핵심어 포함.
    assert "호가" in note


def _load_build_report():
    """build_report 모듈을 import 시도. 아직 없으면 None."""
    try:
        return importlib.import_module("build_report")
    except Exception:
        return None


def test_build_note_not_empty():
    """build(...) 결과 note 비어있지 않음 (build_report 있을 때만)."""
    mod = _load_build_report()
    if mod is None or not hasattr(mod, "build"):
        pytest.skip("build_report.build 미구현 (Task5)")
    listings_obj = P.build_listings_schema(
        query="에어팟 프로", mode="search", target=None,
        listings=[], needs_human=False,
    )
    report = mod.build(listings_obj)
    assert report.get("note", "").strip() != ""


def test_render_markdown_contains_limit_note():
    """render_markdown 출력에 "호가"/"거래완료" 한계 문구 포함 (있을 때만)."""
    mod = _load_build_report()
    if mod is None or not hasattr(mod, "render_markdown"):
        pytest.skip("build_report.render_markdown 미구현 (Task5)")
    report = P.build_report_schema(
        query="에어팟 프로", mode="search", verdict_obj=None,
        stats_by_condition={}, cheap_picks=[], warnings=[],
    )
    md = mod.render_markdown(report)
    assert "호가" in md or "거래완료" in md
