# -*- coding: utf-8 -*-
r"""
build_report.py — 당근 시세 점검 통합 리포트 생성기 (Task5)

입력:
  _workspace/01_listings.json  (필수 — daangn_collect.py 산출)

출력:
  _workspace/02_price_report.json                       (정본 JSON)
  _saved/daangn_<물건명>_<날짜>/report.md               (사람용 마크다운)

흐름(설계 §2 공유 엔진):
  01_listings -> filter_listings(query) -> 매물별 classify_condition
  -> compute_price_stats(상태군별) -> (link 모드면) target 상태군 분포로 verdict
  -> detect_cheap_warnings -> build_report_schema -> 02 구조.

네트워크/브라우저 일절 없음 — 순수 파일 처리(build_final.py 미러).
build()·render_markdown() 은 파일 I/O 없는 순수 함수(테스트 대상).

판정의 한계(호가 분포 기준)는 note 와 리포트에 항상 명시한다(AC-7).
"""
import os
import re
import sys
import json
import datetime

# scripts/ 디렉터리가 패키지 경로에 없을 때를 대비한 경로 주입 (build_final.py 미러)
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from daangn_common import save_with_alias, SAVED_DIR, OUT_DIR
from daangn_parsers import (
    filter_listings,
    filter_by_conditions,
    select_lowest,
    classify_condition,
    compute_price_stats,
    verdict,
    detect_cheap_warnings,
    build_report_schema,
    validate_schema,
    _priced_listings,
)

# 같은 상태군에서 "지금 싼 매물" 으로 추려 보여줄 최대 개수(설계 §5 cheap_picks).
_CHEAP_PICKS_TOP_N = 3
# (v2) 사용자 조건 기반 최저가 기본 개수(설계 v2 §2).
_DEALS_TOP_N = 5
# 상태군 표 출력 순서(없는 군은 생략).
_COND_ORDER = ("새것", "상급", "보통", "하자")


def _load_json(path):
    """JSON 파일 로드. 없거나 깨지면 None (build_final._load_json 미러)."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[경고] {path} 읽기 실패: {e}")
        return None


def _stats_for_condition(stats_by_condition, condition, listings):
    """verdict 호출용 단일 상태군 분포 dict 를 조립한다.

    compute_price_stats 결과(stats_by_condition)에 condition 을 주입하고,
    n>=8 백분위 정밀 계산을 위해 그 상태군의 원본 가격 리스트(_sorted)를 함께 넘긴다.
    해당 군이 없으면 condition 만 담은 빈 분포(n=0) 를 돌려 verdict 가 판정보류하도록 한다.
    """
    base = dict((stats_by_condition or {}).get(condition) or {})
    base["condition"] = condition
    if condition:
        prices = sorted(
            lst["price"] for lst in _priced_listings(listings)
            if (lst.get("condition") or "보통") == condition
        )
        if prices:
            base["_sorted"] = prices
    return base


def _collect_cheap_picks(listings, stats_by_condition):
    """같은 상태군 median 대비 싼 매물 Top N (설계 §5 cheap_picks).

    각 매물의 (median 대비 비율) 오름차순으로 정렬해 가장 싼 순으로 추린다.
    traded/price None 매물은 제외. 반환 항목은 {price, condition, link}.
    """
    scored = []
    for lst in _priced_listings(listings):
        cond = lst.get("condition") or "보통"
        s = (stats_by_condition or {}).get(cond)
        if not s:
            continue
        median = s.get("median")
        if not median:
            continue
        ratio = lst["price"] / median
        scored.append((ratio, {
            "price": lst["price"],
            "condition": cond,
            "link": lst.get("link"),
        }))
    scored.sort(key=lambda x: x[0])
    return [item for _, item in scored[:_CHEAP_PICKS_TOP_N]]


# ---------------------------------------------------------------------------
# 핵심 순수 함수 (파일 I/O 없음 — 테스트 대상)
# ---------------------------------------------------------------------------

def build(listings_obj, conditions=None):
    """01_listings dict 를 받아 02_price_report 구조를 반환하는 순수 함수.

    파일 I/O 없음. main() 과 외부 테스트 양쪽에서 호출 가능.

    흐름:
      filter_listings(입력정합) -> 매물별 classify_condition(태그->등급 재확정)
      -> compute_price_stats(상태군별) -> (link 모드) target 상태군 분포로 verdict
      -> detect_cheap_warnings -> (conditions 있으면) 조건 최저가 -> build_report_schema.
    needs_human 이 True 여도 진행분으로 리포트를 만든다(멈춤 없음, AC-4).

    conditions: 사용자 조건 dict(설계 v2). 주어지면 조건 통과 매물 중
      가격 오름차순 최저가 N개를 condition_deals 로 추가한다(없으면 None).
    """
    obj = listings_obj or {}
    query = obj.get("query") or "unknown"
    mode = obj.get("mode") or "search"
    raw_listings = obj.get("listings") or []
    target = obj.get("target")

    # ① 입력정합 가드(검색어 토큰 + 가격 이상치) — 통계/판정 전에 적용(R1).
    listings = filter_listings(raw_listings, query)

    # ② 매물별 상태등급 재확정(태그 기준 — 수집 단계 분류를 신뢰하지 않고 재계산).
    for lst in listings:
        lst["condition"] = classify_condition(lst.get("tags") or [])

    # ③ 상태군별 호가분포.
    stats_by_condition = compute_price_stats(listings)

    # ④ (link 모드) 타깃 매물 판정 — 타깃 상태군 분포 기준.
    verdict_obj = None
    if mode == "link" and target:
        t_cond = classify_condition(target.get("tags") or [])
        t_price = target.get("price")
        if isinstance(t_price, int):
            t_stats = _stats_for_condition(stats_by_condition, t_cond, listings)
            verdict_obj = verdict(t_price, t_stats)

    # ⑤ 비정상 저가 경고 + 싼 매물 Top N.
    warnings = detect_cheap_warnings(listings, stats_by_condition)
    cheap_picks = _collect_cheap_picks(listings, stats_by_condition)

    # ⑥ (v2) 사용자 조건 기반 최저가 — conditions 주어졌을 때만.
    condition_deals = None
    if conditions is not None:
        matched = filter_by_conditions(listings, conditions)
        buyable = [
            l for l in matched
            if not l.get("traded") and isinstance(l.get("price"), int)
        ]
        top_n = conditions.get("top") or _DEALS_TOP_N
        condition_deals = {
            "conditions": conditions,
            "matched_count": len(buyable),
            "deals": select_lowest(matched, top_n),
        }

    return build_report_schema(
        query, mode, verdict_obj, stats_by_condition, cheap_picks, warnings,
        condition_deals,
    )


def _fmt_won(val):
    """정수면 "1,234원", 아니면 안전 문자열."""
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return f"{int(round(val)):,}원"
    return str(val)


def _verdict_korean(verdict_obj):
    """verdict dict -> 사람용 한 줄 설명."""
    if not verdict_obj:
        return None
    label = verdict_obj.get("label") or "판정보류"
    conf = verdict_obj.get("confidence") or "low"
    cond = verdict_obj.get("condition") or "미상"
    tp = verdict_obj.get("target_price")
    pct = verdict_obj.get("percentile")
    line = f"이 매물은 **{label}** (상태군: {cond}, 가격 {_fmt_won(tp)}, 신뢰도 {conf})"
    if isinstance(pct, (int, float)) and not isinstance(pct, bool):
        line += f" — 같은 상태군에서 하위 {pct * 100:.0f}% 위치(참고)"
    if conf == "low" or label == "판정보류":
        line += "\n> 표본이 적어 추정 신뢰도가 낮습니다. 참고용으로만 보세요."
    return line


def _conditions_korean(c):
    """조건 dict -> 사람용 한 줄 요약 (v2 condition_deals)."""
    c = c or {}
    parts = []
    if c.get("min_condition"):
        parts.append(f"{c['min_condition']} 이상")
    if c.get("on_sale_only"):
        parts.append("판매중만")
    if c.get("include"):
        parts.append("포함: " + ", ".join(c["include"]))
    if c.get("exclude"):
        parts.append("제외: " + ", ".join(c["exclude"]))
    return " · ".join(parts) if parts else "조건 없음(전체 최저가)"


def render_markdown(report):
    """02_price_report dict -> 사람용 마크다운 (순수 함수).

    구성: 제목/요약 -> (link 모드) 판정 -> 상태군별 호가분포표(소표본은 분위 생략)
    -> 싼 매물 -> 경고 -> 호가분포 한계 note(AC-7 고정).
    """
    report = report or {}
    query = report.get("query") or "unknown"
    mode = report.get("mode") or "search"
    ts = report.get("ts") or ""
    verdict_obj = report.get("verdict")
    stats = report.get("stats_by_condition") or {}
    cheap_picks = report.get("cheap_picks") or []
    warnings = report.get("warnings") or []
    note = report.get("note") or ""

    lines = []
    lines.append(f"# 당근 시세 점검 — {query}")
    lines.append("")
    lines.append(f"- 모드: {'매물 링크 판정' if mode == 'link' else '물건명 검색'}")
    lines.append(f"- 생성: {ts}")
    lines.append("")

    # 판정 (link 모드)
    if mode == "link":
        lines.append("## 판정")
        vk = _verdict_korean(verdict_obj)
        lines.append(vk if vk else "판정 불가(타깃 매물 가격/표본 부족).")
        lines.append("")

    # 상태군별 호가분포표
    lines.append("## 상태군별 호가 분포")
    if not stats:
        lines.append("수집된 매물이 없어 분포를 계산할 수 없습니다.")
    else:
        has_quartile = any("p25" in s for s in stats.values())
        if has_quartile:
            lines.append("| 상태군 | 건수 | 최저 | 25% | 중앙값 | 75% | 최고 |")
            lines.append("|---|---:|---:|---:|---:|---:|---:|")
        else:
            lines.append("| 상태군 | 건수 | 최저 | 중앙값 | 최고 |")
            lines.append("|---|---:|---:|---:|---:|")
        ordered = [c for c in _COND_ORDER if c in stats]
        ordered += [c for c in stats if c not in _COND_ORDER]
        for cond in ordered:
            s = stats[cond]
            if has_quartile:
                p25 = _fmt_won(s["p25"]) if "p25" in s else "-"
                p75 = _fmt_won(s["p75"]) if "p75" in s else "-"
                lines.append(
                    f"| {cond} | {s.get('n')} | {_fmt_won(s.get('min'))} | {p25} | "
                    f"{_fmt_won(s.get('median'))} | {p75} | {_fmt_won(s.get('max'))} |"
                )
            else:
                lines.append(
                    f"| {cond} | {s.get('n')} | {_fmt_won(s.get('min'))} | "
                    f"{_fmt_won(s.get('median'))} | {_fmt_won(s.get('max'))} |"
                )
        if not has_quartile:
            lines.append("")
            lines.append("> 표본이 8건 미만인 상태군은 25%/75% 분위를 생략했습니다(과신 방지).")
    lines.append("")

    # 조건 맞는 최저가 (v2 — condition_deals 있을 때만)
    cdeals = report.get("condition_deals")
    if cdeals and cdeals.get("deals"):
        lines.append("## 조건 맞는 최저가")
        lines.append(f"- 조건: {_conditions_korean(cdeals.get('conditions') or {})}")
        lines.append(f"- 조건 통과 매물 {cdeals.get('matched_count', 0)}건 중 최저가순")
        lines.append("")
        for i, d in enumerate(cdeals["deals"], 1):
            link = d.get("link") or "(링크 없음)"
            title = d.get("title") or "(제목 없음)"
            lines.append(
                f"{i}. {_fmt_won(d.get('price'))} · [{d.get('condition')}] {title} — {link}"
            )
        lines.append("")

    # 싼 매물
    if cheap_picks:
        lines.append("## 지금 싼 매물")
        for pick in cheap_picks:
            link = pick.get("link") or "(링크 없음)"
            lines.append(
                f"- [{pick.get('condition')}] {_fmt_won(pick.get('price'))} — {link}"
            )
        lines.append("")

    # 경고
    if warnings:
        lines.append("## 확인 권장")
        for w in warnings:
            lines.append(f"- {w}")
        lines.append("")

    # 호가분포 한계 note (AC-7 고정)
    lines.append("## 한계 (꼭 읽어주세요)")
    lines.append(note)
    lines.append("")
    lines.append("> 이 도구는 시세 참고용입니다. 구매·연락·결제는 직접 판단하세요.")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# main — 파일 I/O
# ---------------------------------------------------------------------------

def _safe_name(text):
    """폴더명에 안전하게 — 한글/영숫자/일부 기호만 남기고 공백은 _ 로."""
    text = (text or "unknown").strip()
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^0-9A-Za-z가-힣_\-]", "", text)
    return text[:60] or "unknown"


def _save_report_md(report):
    """report.md 를 _saved/daangn_<물건명>_<날짜>/ 에 저장. 반환: 저장 경로.

    날짜는 datetime.now()(스크립트 실행 시점).
    """
    query = report.get("query") or "unknown"
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    folder = os.path.join(SAVED_DIR, f"daangn_{_safe_name(query)}_{date_str}")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "report.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(render_markdown(report))
    return path


def _parse_conditions(argv=None):
    """CLI 인자 -> conditions dict (조건 인자가 하나라도 있을 때만, 아니면 None)."""
    import argparse
    ap = argparse.ArgumentParser(
        description="당근 시세 점검 리포트 (+조건 기반 최저가)"
    )
    ap.add_argument("--min-condition", choices=["새것", "상급", "보통", "하자"],
                    help="최소 상태등급(이상). 예: 상급 -> 상급·새것만")
    ap.add_argument("--on-sale-only", action="store_true",
                    help="거래완료/예약중 제외(판매중만)")
    ap.add_argument("--include", action="append", default=[], metavar="단어",
                    help="제목/태그에 모두 포함(AND). 반복 지정 가능")
    ap.add_argument("--exclude", action="append", default=[], metavar="단어",
                    help="제목/태그에 하나라도 있으면 제외(OR). 반복 지정 가능")
    ap.add_argument("--top", type=int, default=None,
                    help=f"최저가 표시 개수(기본 {_DEALS_TOP_N})")
    args = ap.parse_args(argv)

    if (args.min_condition or args.on_sale_only or args.include
            or args.exclude or args.top is not None):
        return {
            "min_condition": args.min_condition,
            "on_sale_only": bool(args.on_sale_only),
            "include": args.include,
            "exclude": args.exclude,
            "top": args.top or _DEALS_TOP_N,
        }
    return None


def main():
    conditions = _parse_conditions()

    listings_path = os.path.join(OUT_DIR, "01_listings.json")

    if not os.path.exists(listings_path):
        print("[오류] 먼저 daangn_collect.py 실행 (01_listings.json 없음)")
        sys.exit(1)

    listings_obj = _load_json(listings_path)
    if listings_obj is None:
        print("[오류] 01_listings.json 읽기 실패")
        sys.exit(1)

    result = build(listings_obj, conditions)

    # 자가 검증 (02 스키마 필수키)
    required = [
        "query", "ts", "mode",
        "stats_by_condition", "cheap_picks", "warnings", "note",
    ]
    missing = validate_schema(result, required)
    if missing:
        print(f"[오류] 스키마 검증 실패 - 누락 키: {missing}")
        sys.exit(1)

    # 02 JSON 저장
    json_paths = save_with_alias(result, "02_price_report.json", [])
    md_path = _save_report_md(result)
    print(f"[저장] {', '.join(json_paths)}")
    print(f"[저장] {md_path}")

    # 콘솔 요약
    print()
    print(f"[질의] {result.get('query')}  (모드: {result.get('mode')})")
    if listings_obj.get("needs_human"):
        print("[주의] 봇차단/로그인유도 감지 → needs_human (진행분만 리포트)")
    vobj = result.get("verdict")
    if vobj:
        print(f"[판정] {vobj.get('label')}  "
              f"(신뢰도 {vobj.get('confidence')}, 상태군 {vobj.get('condition')})")
    print()
    print(f"{'상태군':<6} {'건수':>4} {'최저':>10} {'중앙값':>10} {'최고':>10}")
    print("-" * 46)
    for cond, s in (result.get("stats_by_condition") or {}).items():
        print(f"{cond:<6} {s.get('n'):>4} {_fmt_won(s.get('min')):>10} "
              f"{_fmt_won(s.get('median')):>10} {_fmt_won(s.get('max')):>10}")
    for w in (result.get("warnings") or []):
        print(f"[경고] {w}")
    # (v2) 조건 기반 최저가 콘솔 출력
    cdeals = result.get("condition_deals")
    if cdeals and cdeals.get("deals"):
        print()
        print(f"[조건 최저가] {_conditions_korean(cdeals.get('conditions') or {})}"
              f"  — 통과 {cdeals.get('matched_count', 0)}건")
        for i, d in enumerate(cdeals["deals"], 1):
            print(f"  {i}. {_fmt_won(d.get('price')):>12}  [{d.get('condition')}]  "
                  f"{d.get('title') or ''}")
    print()
    print(f"[note] {result.get('note')}")


if __name__ == "__main__":
    main()
