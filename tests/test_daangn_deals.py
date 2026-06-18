# -*- coding: utf-8 -*-
"""조건 기반 최저가 (filter_by_conditions / select_lowest) 테스트.

네트워크 0 — daangn_parsers 순수함수만 호출.
설계: .omc/specs/daangn-condition-deals-design.md §6.
"""
import daangn_parsers as P


def _mk(title, price, condition="보통", tags=None, traded=False, link=None):
    return {
        "title": title, "price": price, "condition": condition,
        "tags": tags or [], "traded": traded, "link": link,
    }


# ───────────────────────── filter_by_conditions ─────────────────────────

def test_empty_conditions_pass_all():
    items = [_mk("에어팟 A", 100), _mk("에어팟 B", 200)]
    assert P.filter_by_conditions(items, {}) == items
    assert P.filter_by_conditions(items, None) == items


def test_on_sale_only_excludes_traded():
    items = [_mk("판매중", 100, traded=False), _mk("거래완료건", 90, traded=True)]
    out = P.filter_by_conditions(items, {"on_sale_only": True})
    titles = [x["title"] for x in out]
    assert "판매중" in titles
    assert "거래완료건" not in titles


def test_on_sale_off_keeps_traded():
    items = [_mk("판매중", 100), _mk("거래완료건", 90, traded=True)]
    out = P.filter_by_conditions(items, {"on_sale_only": False})
    assert len(out) == 2


def test_min_condition_includes_higher_grades():
    """min_condition=상급 -> 상급·새것 통과, 보통·하자 제외."""
    items = [
        _mk("새것", 400, condition="새것"),
        _mk("상급", 310, condition="상급"),
        _mk("보통", 240, condition="보통"),
        _mk("하자", 160, condition="하자"),
    ]
    out = P.filter_by_conditions(items, {"min_condition": "상급"})
    conds = set(x["condition"] for x in out)
    assert conds == {"새것", "상급"}


def test_min_condition_normal_keeps_normal_and_above():
    items = [
        _mk("새것", 400, condition="새것"),
        _mk("보통", 240, condition="보통"),
        _mk("하자", 160, condition="하자"),
    ]
    out = P.filter_by_conditions(items, {"min_condition": "보통"})
    conds = set(x["condition"] for x in out)
    assert "하자" not in conds
    assert "보통" in conds and "새것" in conds


def test_include_keywords_and():
    """include 는 모두 포함(AND). title+tags 에서 검색."""
    items = [
        _mk("에어팟 풀박스 미개봉", 400, tags=["풀박스"]),
        _mk("에어팟 본체만", 300),
    ]
    out = P.filter_by_conditions(items, {"include": ["풀박스"]})
    assert len(out) == 1 and out[0]["title"].startswith("에어팟 풀박스")
    # 두 키워드 모두 있어야(AND) — "본체"는 첫 매물에 없음
    out2 = P.filter_by_conditions(items, {"include": ["풀박스", "본체"]})
    assert out2 == []


def test_include_matches_tags():
    """include 키워드가 제목엔 없고 태그에만 있어도 통과."""
    items = [_mk("에어팟 프로", 400, tags=["풀박스"])]
    out = P.filter_by_conditions(items, {"include": ["풀박스"]})
    assert len(out) == 1


def test_exclude_keywords_or():
    """exclude 는 하나라도 있으면 제외(OR)."""
    items = [
        _mk("에어팟 케이스 포함", 400),
        _mk("에어팟 본체", 300),
    ]
    out = P.filter_by_conditions(items, {"exclude": ["케이스"]})
    titles = [x["title"] for x in out]
    assert "에어팟 케이스 포함" not in titles
    assert "에어팟 본체" in titles


def test_combined_conditions():
    items = [
        _mk("에어팟 풀박스", 400, condition="새것", tags=["풀박스"]),
        _mk("에어팟 케이스 풀박스", 350, condition="새것", tags=["풀박스"]),
        _mk("에어팟 보통", 300, condition="보통"),
        _mk("에어팟 거래완료 풀박스", 250, condition="새것", tags=["풀박스"], traded=True),
    ]
    cond = {"min_condition": "상급", "on_sale_only": True,
            "include": ["풀박스"], "exclude": ["케이스"]}
    out = P.filter_by_conditions(items, cond)
    titles = [x["title"] for x in out]
    assert titles == ["에어팟 풀박스"]


# ───────────────────────────── select_lowest ────────────────────────────

def test_select_lowest_orders_ascending():
    items = [_mk("c", 300), _mk("a", 100), _mk("b", 200)]
    out = P.select_lowest(items, 5)
    assert [d["price"] for d in out] == [100, 200, 300]


def test_select_lowest_limits_n():
    items = [_mk(str(p), p) for p in (500, 100, 300, 200, 400, 600)]
    out = P.select_lowest(items, 3)
    assert [d["price"] for d in out] == [100, 200, 300]


def test_select_lowest_fewer_than_n():
    items = [_mk("a", 100), _mk("b", 200)]
    out = P.select_lowest(items, 5)
    assert len(out) == 2


def test_select_lowest_excludes_traded():
    items = [_mk("traded", 50, traded=True), _mk("ok", 100)]
    out = P.select_lowest(items, 5)
    prices = [d["price"] for d in out]
    assert 50 not in prices and 100 in prices


def test_select_lowest_excludes_priceless():
    items = [_mk("noprice", None), _mk("ok", 100)]
    out = P.select_lowest(items, 5)
    assert [d["price"] for d in out] == [100]


def test_select_lowest_item_shape():
    items = [_mk("타이틀", 100, condition="상급", link="http://x")]
    out = P.select_lowest(items, 5)
    assert out[0] == {"price": 100, "condition": "상급", "title": "타이틀", "link": "http://x"}


def test_select_lowest_empty():
    assert P.select_lowest([], 5) == []
    assert P.select_lowest(None, 5) == []


def test_select_lowest_default_n_is_5():
    items = [_mk(str(p), p) for p in range(1, 11)]  # 가격 1..10
    out = P.select_lowest(items)  # n 생략 -> 기본 5
    assert [d["price"] for d in out] == [1, 2, 3, 4, 5]


# ─────────────────── build_report 통합 (condition_deals) ───────────────────
import build_report as B


def test_build_includes_condition_deals():
    """conditions 주면 build 결과에 condition_deals(조건 통과 최저가)가 들어간다."""
    obj = {
        "query": "에어팟",
        "mode": "search",
        "listings": [
            _mk("에어팟 풀박스", 290000, condition="새것", tags=["풀박스"], link="a"),
            _mk("에어팟 보통", 250000, condition="보통", link="b"),
            _mk("에어팟 상급", 310000, condition="상급", tags=["s급"], link="c"),
        ],
        "target": None,
    }
    r = B.build(obj, {"min_condition": "상급", "on_sale_only": True,
                      "include": [], "exclude": [], "top": 5})
    cd = r["condition_deals"]
    assert cd is not None
    prices = [d["price"] for d in cd["deals"]]
    assert 250000 not in prices            # 보통은 "상급 이상"에서 제외
    assert prices == sorted(prices)        # 최저가순
    assert 290000 in prices and 310000 in prices


def test_build_no_conditions_no_deals():
    """conditions 없으면 condition_deals 는 None(기존 동작 보존)."""
    obj = {"query": "에어팟", "mode": "search",
           "listings": [_mk("에어팟", 100, link="a")], "target": None}
    r = B.build(obj, None)
    assert r["condition_deals"] is None


def test_parse_conditions_none_when_no_args():
    """조건 인자 0개면 None(condition_deals 미생성)."""
    assert B._parse_conditions([]) is None


def test_parse_conditions_builds_dict():
    c = B._parse_conditions(
        ["--min-condition", "상급", "--on-sale-only",
         "--exclude", "케이스", "--include", "풀박스", "--top", "3"]
    )
    assert c["min_condition"] == "상급"
    assert c["on_sale_only"] is True
    assert c["exclude"] == ["케이스"]
    assert c["include"] == ["풀박스"]
    assert c["top"] == 3


def test_render_markdown_has_condition_deals_section():
    """render_markdown 출력에 '조건 맞는 최저가' 섹션과 가격이 포함된다."""
    obj = {
        "query": "에어팟", "mode": "search",
        "listings": [
            _mk("에어팟 풀박스", 290000, condition="새것", tags=["풀박스"], link="a"),
        ],
        "target": None,
    }
    r = B.build(obj, {"min_condition": "상급", "on_sale_only": True,
                      "include": [], "exclude": [], "top": 5})
    md = B.render_markdown(r)
    assert "조건 맞는 최저가" in md
    assert "290,000원" in md
