# -*- coding: utf-8 -*-
r"""
네이버 쇼핑 리뷰 수집 스크립트 (2단계, AC-3)

입력: _workspace/01_candidates.json
출력:
  - _workspace/04_reviews.json   (정제 리뷰 원문, 스크립트 산출)
  - _workspace/02_browser_raw.json  (원문 누적 — append-merge, 덮어쓰기 금지)

사용법:
  python scripts\naver_reviews.py [--top 3]

안전 불변:
  - 결제/구매 관련 클릭 코드 없음
  - 캡차 우회 없음
  - headless=False 고정 (launch_browser 사용)
  - 리뷰 텍스트·별점·날짜만 저장, 작성자 개인정보 저장 안 함

셀렉터 관리:
  상단 SELECTORS 상수 블록에 집중. 네이버 개편 시 여기만 수선.
"""

import argparse
import sys

from naver_common import (
    ensure_candidates_alias,
    launch_browser,
    new_naver_context,
    human_delay,
    gradual_scroll,
    detect_block,
    save,
    merge_into_browser_raw,
    now,
)
from naver_parsers import (
    normalize_candidate,
    parse_review_block,
    dedup_reviews,
    build_reviews_schema,
)

# ---------------------------------------------------------------------------
# 셀렉터 상수 블록 — 네이버 개편 시 여기만 수선
# ---------------------------------------------------------------------------
SELECTORS = {
    # 리뷰 탭 클릭 후보 (우선순위 순)
    "review_tab": [
        "a[href*='review']",
        "li[data-tab='review'] a",
        ".tab__item--review",
        "a:has-text('리뷰')",
    ],
    # 리뷰 블록 (개별 리뷰 컨테이너)
    "review_block": [
        ".reviewItems__review",
        ".review_list .review_item",
        "[class*='reviewItem']",
        ".sdp-review__article__list__item",
    ],
    # "평점 낮은순" 정렬 옵션
    "low_rating_sort": [
        "a:has-text('낮은순')",
        "button:has-text('낮은순')",
        "[data-sort='reviewScore_asc']",
        "option[value='reviewScore_asc']",
    ],
    # 별점 평균 텍스트
    "rating_avg": [
        ".reviewSummary__score",
        ".review_summary .score",
        "[class*='avgScore']",
        ".sdp-review__summary__score",
    ],
}

# 리뷰 원문 최대 길이 (바이트 절단 방지, 문자 기준 절단)
_MAX_REVIEW_TEXT = 500
# 상품당 목표 리뷰 수
_REVIEW_TARGET_MIN = 10
_REVIEW_TARGET_MAX = 40


def _try_click_selector(page, candidates, timeout=3000):
    """후보 셀렉터 리스트를 순서대로 시도해 첫 성공 반환.

    반환: 성공한 셀렉터 str, 없으면 None.
    """
    for sel in candidates:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=timeout):
                loc.click(timeout=timeout)
                return sel
        except Exception:
            continue
    return None


def _extract_rating_avg(page):
    """페이지에서 평균 별점 텍스트 추출 시도. 실패 시 None."""
    for sel in SELECTORS["rating_avg"]:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=2000):
                text = loc.inner_text(timeout=2000).strip()
                # 숫자만 추출 (예: "4.5점" → 4.5)
                import re
                m = re.search(r"[0-5](?:\.[0-9])?", text)
                if m:
                    return float(m.group(0))
        except Exception:
            continue
    return None


def _collect_review_texts(page):
    """현재 페이지에서 리뷰 블록 텍스트 목록 수집.

    반환: list[str] (각 500자 절단).
    """
    texts = []
    for sel in SELECTORS["review_block"]:
        try:
            locs = page.locator(sel).all()
            if locs:
                for loc in locs:
                    try:
                        t = loc.inner_text(timeout=2000).strip()
                        if t:
                            texts.append(t[:_MAX_REVIEW_TEXT])
                    except Exception:
                        continue
                if texts:
                    break
        except Exception:
            continue
    return texts


def crawl_reviews(page, product):
    """단일 상품 리뷰 수집.

    반환:
        result dict:
          {
            "rank", "title", "link",
            "rating_avg", "review_count_seen",
            "reviews": [{text, rating, date}, ...],
            "raw_review_blocks": [원문 str, ...],
            "needs_human": bool,
            "reasons": [str, ...]
          }
        blocked: bool — True면 호출측에서 전체 중단.
    """
    link = product.get("link") or ""
    title = product.get("title") or ""
    rank = product.get("rank")
    reasons = []

    # 상품 페이지 이동
    page.goto(link, wait_until="domcontentloaded", timeout=30000)
    human_delay(page)

    # 봇차단 감지 — True 면 즉시 전체 중단
    body_text = ""
    page_title = ""
    try:
        body_text = page.inner_text("body", timeout=5000)
        page_title = page.title()
    except Exception:
        pass

    if detect_block(body_text, page_title):
        return {
            "rank": rank, "title": title, "link": link,
            "rating_avg": None, "review_count_seen": 0,
            "reviews": [], "raw_review_blocks": [],
            "needs_human": True, "reasons": ["봇차단 감지"],
        }, True  # blocked=True

    # 평균 별점 추출 (리뷰 탭 클릭 전)
    rating_avg = _extract_rating_avg(page)

    # 리뷰 탭 클릭
    tab_sel = _try_click_selector(page, SELECTORS["review_tab"])
    if tab_sel is None:
        reasons.append("리뷰 탭 셀렉터 매칭 0 — 셀렉터 수선 필요")
    else:
        human_delay(page)

    # 점진 스크롤로 리뷰 로딩 유도
    gradual_scroll(page)

    # 기본 정렬 리뷰 수집
    raw_blocks_all = _collect_review_texts(page)

    if not raw_blocks_all:
        reasons.append("리뷰 블록 셀렉터 매칭 0 — 셀렉터 수선 필요")

    # 낮은 평점 포함: "낮은순" 정렬 시도 (있으면 한 번 더 수집)
    low_sort_sel = _try_click_selector(page, SELECTORS["low_rating_sort"])
    if low_sort_sel:
        human_delay(page)
        gradual_scroll(page)
        low_blocks = _collect_review_texts(page)
        raw_blocks_all = raw_blocks_all + low_blocks
    else:
        reasons.append("낮은순 정렬 옵션 없음 — 스킵")

    # 리뷰 파싱 및 중복 제거
    parsed = [parse_review_block(t) for t in raw_blocks_all]
    parsed = dedup_reviews(parsed)

    # 목표 범위 클램프 (있는 만큼, 최대 40개)
    parsed = parsed[:_REVIEW_TARGET_MAX]

    return {
        "rank": rank,
        "title": title,
        "link": link,
        "rating_avg": rating_avg,
        "review_count_seen": len(parsed),
        "reviews": parsed,
        "raw_review_blocks": raw_blocks_all[:_REVIEW_TARGET_MAX],
        "needs_human": False,
        "reasons": reasons,
    }, False  # blocked=False


def main():
    parser = argparse.ArgumentParser(description="네이버 상품 리뷰 수집")
    parser.add_argument("--top", type=int, default=3, help="수집할 상위 상품 수 (기본 3, 최대 5)")
    args = parser.parse_args()

    top_n = max(1, min(args.top, 5))  # 1~5 클램프

    # 01_candidates.json 로드 + 별칭 보장
    candidates_obj = ensure_candidates_alias()
    if candidates_obj is None:
        print("[오류] 01_candidates.json 없음 → 먼저 python scripts\\naver_poc.py \"검색어\" 실행")
        sys.exit(1)

    query = candidates_obj.get("query", "")
    raw_items = [it for it in candidates_obj.get("items", []) if isinstance(it, dict)]

    # rank 기준 정렬 → 상위 N개
    raw_items_sorted = sorted(raw_items, key=lambda x: x.get("rank") or 999)
    top_items = raw_items_sorted[:top_n]

    normalized = [normalize_candidate(item) for item in top_items]

    print(f"[리뷰 수집] 검색어: {query!r} | 상위 {top_n}개 상품")

    # Playwright 지연 import (모듈 레벨 import 시 playwright 없어도 순수 함수 동작)
    from playwright.sync_api import sync_playwright

    collected_products = []  # 04_reviews 용
    raw_products_for_02 = []  # 02_browser_raw 병합용

    with sync_playwright() as p:
        browser = launch_browser(p)
        context = new_naver_context(browser)
        page = context.new_page()

        blocked_early = False
        for product in normalized:
            rank = product.get("rank")
            title = product.get("title") or ""
            print(f"  [{rank}] {title[:40]} ... 리뷰 수집 중")

            try:
                result, blocked = crawl_reviews(page, product)
            except Exception as e:
                print(f"  [{rank}] 오류: {e}")
                result = {
                    "rank": rank, "title": title, "link": product.get("link") or "",
                    "rating_avg": None, "review_count_seen": 0,
                    "reviews": [], "raw_review_blocks": [],
                    "needs_human": True, "reasons": [f"예외: {e}"],
                }
                blocked = False

            # 04_reviews 용 상품 레코드 (리뷰어 개인정보 없이 text/rating/date만)
            product_entry = {
                "rank": result["rank"],
                "title": result["title"],
                "link": result["link"],
                "rating_avg": result["rating_avg"],
                "review_count_seen": result["review_count_seen"],
                "reviews": result["reviews"],
            }
            if result.get("needs_human"):
                product_entry["needs_human"] = True
            if result.get("reasons"):
                product_entry["reasons"] = result["reasons"]
            collected_products.append(product_entry)

            # 02_browser_raw 용 (raw_review_blocks 포함)
            raw_entry = {
                "rank": result["rank"],
                "title": result["title"],
                "link": result["link"],
                "raw_review_blocks": result["raw_review_blocks"],
                "needs_human": result.get("needs_human", False),
            }
            raw_products_for_02.append(raw_entry)

            # 콘솔 요약
            cnt = result["review_count_seen"]
            avg = result["rating_avg"]
            avg_str = f"{avg:.1f}점" if avg is not None else "평점불명"
            print(f"  [{rank}] {title[:30]} - 리뷰 {cnt}개, {avg_str}")

            if blocked:
                print(f"  [경고] 봇차단 감지 → 즉시 중단 (진행분 저장)")
                blocked_early = True
                break

        page.close()
        context.close()
        browser.close()

    # 저장
    reviews_obj = build_reviews_schema(query, collected_products)
    save_path = save(reviews_obj, "04_reviews.json")
    print(f"\n[저장] 04_reviews.json → {save_path}")

    merge_into_browser_raw(query, raw_products_for_02)
    print("[저장] 02_browser_raw.json 병합 완료")

    if blocked_early:
        print("[완료] 봇차단으로 일부만 수집. needs_human=true 항목 확인 필요.")
    else:
        print("[완료] 리뷰 수집 완료.")


if __name__ == "__main__":
    main()
