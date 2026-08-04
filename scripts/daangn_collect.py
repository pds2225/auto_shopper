# -*- coding: utf-8 -*-
r"""
당근마켓 매물 수집기 (시세 점검 1단계, AC-1/AC-3/AC-4/AC-5)

목적: 물건명(검색) 또는 당근 매물 링크를 입력받아 "같은 물건" 매물 카드를
수집하고 _workspace/01_listings.json 으로 저장한다. 수집된 매물은
build_report.py 가 상태군별 호가분포·판정에 사용한다.

입력 2종 (엔진은 1개 공유 — 설계 §2):
  - link 모드  : 매물 상세 페이지에서 제목/가격/상태를 먼저 추출(target)한 뒤,
                 그 제목으로 검색해 같은 물건 매물 카드를 수집한다.
  - search 모드: 물건명으로 바로 검색해 매물 카드를 수집한다.

안전 불변 (위반 금지):
 - 거래 행동(구매/결제/주문/채팅/문의/찜/연락처/전화/거래하기) 자동화 코드를
   일절 작성하지 않는다. 읽기(텍스트 수집)만 한다 — 거래 버튼 셀렉터조차 두지 않음 (AC-5).
 - 봇차단/로그인유도/지역인증 감지 시 우회하지 않고 needs_human=True 후 즉시 정지 (AC-3).
 - 매물카드 셀렉터가 0매칭이면 페이지 inner_text 에서 직접 추출하는 순수 폴백
   (parse_search_listings_from_text)으로 완주한다. 그래도 0이면 빈 채로 완주(멈춤 없음, AC-4).
 - headful 고정(daangn_common.launch_browser 만 사용), 비번/세션토큰/쿠키 출력·하드코딩 금지.

파싱(가격/상태/카드분해/텍스트폴백)은 전부 daangn_parsers(순수 모듈)에 위임한다.
브라우저 I/O·세션·봇차단·저장은 daangn_common 헬퍼를 재사용한다.

사용 (Windows PowerShell):
  python scripts\daangn_collect.py --query "에어팟 프로 2세대"
  python scripts\daangn_collect.py --url "https://www.daangn.com/articles/..."
"""
import sys
import argparse
import urllib.parse

from daangn_common import (
    launch_browser, new_daangn_context, human_delay, gradual_scroll,
    detect_block, save,
)
from daangn_parsers import (
    parse_listing, parse_search_listings_from_text, build_listings_schema,
)

# ──────────────────────────────────────────────────────────────────────────
# 셀렉터 상수 (당근 개편 시 여기만 수선)
# 각 항목 폴백 후보 2~4개. 매칭 0개면 텍스트 폴백으로 강등(멈춤 없음, AC-4).
# 실 DOM 확정은 T8(사람) 실측에 위임 — 여기는 합리적 추정 셀렉터 + 텍스트 폴백.
#
# ※ 안전(AC-5): 거래 행동(구매/채팅/찜/연락처/거래하기 등) 버튼 셀렉터는
#   의도적으로 두지 않는다. 아래는 "읽기 전용" 카드/제목/가격 셀렉터뿐이다.
# ──────────────────────────────────────────────────────────────────────────
SELECTORS = {
    # 검색결과 매물 카드(컨테이너) — inner_text 를 그대로 parse_listing 에 넘긴다.
    "search_card": [
        "a[data-gtm='search_article']",
        "a[href*='/articles/']",
        "article[class*=article]",
        "div[class*=card]",
    ],
    # (link 모드) 매물 상세 — 제목
    "detail_title": [
        "h1",
        "[class*=article-title]",
        "[class*=title] h1",
        "meta[property='og:title']",
    ],
    # (link 모드) 매물 상세 — 가격
    "detail_price": [
        "[class*=price]",
        "[data-testid*=price]",
        "p[class*=Price]",
        "span[class*=price]",
    ],
    # (link 모드) 매물 상세 — 본문/상태키워드가 들어있는 영역
    "detail_body": [
        "[class*=article-detail]",
        "[class*=description]",
        "article",
        "main",
    ],
}

# 당근 검색 URL (search 모드) — 검색어만 채워 진입한다(읽기 전용).
_SEARCH_URL = "https://www.daangn.com/search/{q}/"

# 카드 1건에서 inner_text 가 너무 길면 절단(파싱 안정).
_MAX_CARD_TEXT = 600
# 수집 상한(과수집 방지).
_MAX_CARDS = 60


def _safe_inner_text(page, selector="body"):
    """selector inner_text 안전 추출. 실패 시 빈 문자열."""
    try:
        return page.inner_text(selector) or ""
    except Exception:
        return ""


def _safe_title(page):
    """page.title() 안전 추출. 실패 시 빈 문자열."""
    try:
        return page.title() or ""
    except Exception:
        return ""


def _first_text(page, selector_list):
    """폴백 셀렉터 리스트에서 처음 매칭되는 요소의 inner_text 반환. 없으면 ""."""
    for sel in (selector_list or []):
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible(timeout=2000):
                t = (loc.inner_text(timeout=2000) or "").strip()
                if t:
                    return t
        except Exception:
            continue
    return ""


def _collect_card_texts(page):
    """검색결과 매물 카드들의 inner_text 목록 수집(읽기 전용).

    셀렉터 폴백 후보를 순서대로 시도해 처음으로 카드가 잡히는 셀렉터를 쓴다.
    반환: list[str] (각 _MAX_CARD_TEXT 자 절단), 0매칭이면 [].
    """
    for sel in SELECTORS["search_card"]:
        try:
            locs = page.locator(sel).all()
        except Exception:
            locs = []
        texts = []
        for loc in locs:
            try:
                t = (loc.inner_text(timeout=2000) or "").strip()
            except Exception:
                t = ""
            if t:
                texts.append(t[:_MAX_CARD_TEXT])
            if len(texts) >= _MAX_CARDS:
                break
        if texts:
            return texts
    return []


def _collect_listings(page, query):
    """검색결과 페이지에서 매물 dict 목록 수집.

    1) 카드 셀렉터로 inner_text 수집 -> parse_listing.
    2) 카드 셀렉터 0매칭이면 페이지 inner_text 에서 parse_search_listings_from_text 폴백.
    3) 그래도 0이면 빈 리스트로 완주(멈춤 없음, AC-4).

    반환: (listings: list[dict], used_fallback: bool)
    """
    card_texts = _collect_card_texts(page)
    if card_texts:
        listings = [parse_listing(t) for t in card_texts]
        return listings, False

    # 셀렉터 0매칭 -> 순수 텍스트 폴백 (네트워크 0 함수, daangn_parsers)
    page_text = _safe_inner_text(page, "body")
    listings = parse_search_listings_from_text(page_text)
    return (listings[:_MAX_CARDS], True)


def _goto(page, url):
    """페이지 이동(읽기 전용). 실패해도 예외를 삼키고 흐름 유지."""
    try:
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        human_delay(page)
        return True
    except Exception as e:
        print(f"  [경고] 페이지 이동 실패: {e}")
        return False


def _blocked_here(page):
    """현재 페이지가 봇차단/로그인유도/지역인증 화면인지 (순수 detect_block 위임)."""
    body = _safe_inner_text(page, "body")
    title = _safe_title(page)
    return detect_block(body, title)


def extract_target_from_detail(page, url):
    """(link 모드) 매물 상세 페이지에서 target 매물 dict 추출.

    제목/가격/본문 셀렉터로 텍스트를 모아 한 덩어리로 parse_listing 에 위임한다
    (가격·상태태그·거래상태를 순수 파서가 일관되게 뽑게 한다). link 는 입력 URL 로 채운다.
    셀렉터가 비면 페이지 전체 inner_text 로 폴백.

    반환: (target: dict|None, blocked: bool)
    """
    if not _goto(page, url):
        return None, False
    if _blocked_here(page):
        return None, True

    title_text = _first_text(page, SELECTORS["detail_title"])
    price_text = _first_text(page, SELECTORS["detail_price"])
    body_text = _first_text(page, SELECTORS["detail_body"])

    blob = "\n".join([t for t in (title_text, price_text, body_text) if t]).strip()
    if not blob:
        # 셀렉터 0매칭 -> 페이지 전체 텍스트 폴백
        blob = _safe_inner_text(page, "body")
    if not blob.strip():
        return None, False

    target = parse_listing(blob)
    target["link"] = url
    return target, False


def collect_by_query(page, query):
    """(공유 엔진) 물건명으로 검색 -> 매물 카드 수집.

    반환: (listings: list[dict], blocked: bool, used_fallback: bool)
    """
    q = urllib.parse.quote(query or "")
    if not _goto(page, _SEARCH_URL.format(q=q)):
        return [], False, False
    if _blocked_here(page):
        return [], True, False

    # 지연 로딩 유도(읽기 전용 스크롤)
    gradual_scroll(page)
    # 스크롤 후 차단 화면이 떴는지 한 번 더 확인
    if _blocked_here(page):
        return [], True, False

    listings, used_fallback = _collect_listings(page, query)
    return listings, False, used_fallback


def main():
    ap = argparse.ArgumentParser(
        description="당근마켓 매물 수집기 (물건명 검색 또는 매물 링크)"
    )
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--query", type=str, help="물건명 (search 모드)")
    g.add_argument("--url", type=str, help="당근 매물 링크 (link 모드)")
    args = ap.parse_args()

    mode = "link" if args.url else "search"
    target = None
    listings = []
    needs_human = False
    used_fallback = False
    query = args.query or ""

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = launch_browser(p)
        ctx = new_daangn_context(browser)
        page = ctx.new_page()
        try:
            if mode == "link":
                # 1) 매물 상세에서 target 추출
                target, blocked = extract_target_from_detail(page, args.url)
                if blocked:
                    needs_human = True
                else:
                    # 2) target 제목으로 검색 (제목 없으면 수집 생략하고 완주)
                    title = (target or {}).get("title") if target else None
                    query = title or ""
                    if query:
                        listings, blocked2, used_fallback = collect_by_query(page, query)
                        if blocked2:
                            needs_human = True
                    else:
                        print("[안내] 매물 제목을 못 읽어 검색을 건너뜁니다(빈 결과로 완주).")
            else:
                # search 모드: 물건명으로 바로 검색
                listings, blocked, used_fallback = collect_by_query(page, query)
                if blocked:
                    needs_human = True
        finally:
            browser.close()

    # 봇차단/로그인유도/지역인증이면 진행분(빈 결과 가능)까지만 저장하고 정지 안내
    obj = build_listings_schema(query, mode, target, listings, needs_human)
    path = save(obj, "01_listings.json")

    # 콘솔 요약
    print("=" * 50)
    print(f"모드: {mode}  | 검색어: {query!r}  | 매물 {len(listings)}건"
          + ("  | 텍스트폴백" if used_fallback else ""))
    if target:
        tp = target.get("price")
        tp_str = f"{tp:,}원" if isinstance(tp, int) else "가격불명"
        print(f"  [타깃] {target.get('title')}  | {tp_str}  | {target.get('condition')}")
    for lst in listings[:10]:
        lp = lst.get("price")
        lp_str = f"{lp:,}원" if isinstance(lp, int) else "가격불명"
        traded = "  | 거래완료/예약중" if lst.get("traded") else ""
        print(f"  - {lst.get('title')}  | {lp_str}  | {lst.get('condition')}{traded}")
    if needs_human:
        print("[중단] 봇차단/로그인유도/지역인증 감지 -> 우회 없이 정지. 사람 개입 필요.")
        print("       (세션 만료면 python scripts\\daangn_session_save.py 로 재로그인)")
    elif not listings:
        print("[안내] 수집된 매물이 0건입니다(셀렉터·검색어 점검 필요). 빈 결과로 완주.")
    print(f"[저장됨] {path}")
    print("=" * 50)

    # 봇차단으로 정지한 경우에도 진행분은 저장됐으므로 정상 종료(파이프라인이 needs_human 처리).
    if needs_human:
        sys.exit(0)


if __name__ == "__main__":
    main()
