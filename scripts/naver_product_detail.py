# -*- coding: utf-8 -*-
r"""
네이버 쇼핑 상세 크롤러 (2단계, AC-2/AC-5)

목적: 상위 N개 상품에 대해 상품페이지 -> 쿠폰가 -> 장바구니 -> 주문서(결제 직전)
까지만 진입해 "실제 결제가"를 캡처하고 03_prices.json 으로 저장한다.

안전 불변 (위반 금지):
 - 결제/구매확정 버튼은 절대 클릭하지 않는다 (셀렉터 자체를 두지 않음).
   진입 상한 = 주문서(order/checkout) URL 의 텍스트만 읽고 정지.
 - 쿠폰 "받기" 버튼도 클릭하지 않는다 (계정 상태 변경 방지) — 표시된 쿠폰가 텍스트만 읽음.
 - 봇차단/캡차 감지 시 우회하지 않고 needs_human 기록 후 즉시 전체 중단.
 - headful 고정(naver_common.launch_browser 만 사용), 비번/키 출력·하드코딩 금지.

파싱(가격/쿠폰/주문서 분해)은 전부 naver_parsers(순수 모듈)에 위임한다.
브라우저 I/O·세션·봇차단·저장은 naver_common 헬퍼를 재사용한다.

사용 (Windows PowerShell):
  python scripts\naver_product_detail.py
  python scripts\naver_product_detail.py --top 3
"""
import os
import sys
import argparse

from naver_common import (
    launch_browser, new_naver_context, human_delay, detect_block,
    save_with_alias, merge_into_browser_raw, ensure_candidates_alias,
    SESSION_FILE,
)
from naver_parsers import (
    normalize_candidate, extract_coupon_price, extract_checkout_breakdown,
    compute_final_price, build_prices_schema,
)

# ──────────────────────────────────────────────────────────────────────────
# 셀렉터 상수 (네이버 개편 시 여기만 수선)
# 각 단계별 폴백 후보 2~4개. 매칭 0개면 reason 기록 후 해당 단계 스킵(참고가 강등).
# ──────────────────────────────────────────────────────────────────────────
SELECTORS = {
    # 장바구니 담기 버튼
    "add_to_cart": [
        'button[class*=cart]',
        'a[class*=cart]',
        'button:has-text("장바구니")',
        'a:has-text("장바구니담기")',
    ],
    # 장바구니 페이지의 상품 행(원상복구 시 삭제 대상 식별용)
    "cart_row": [
        'li[class*=cartItem]',
        'div[class*=cartItem]',
        'tr[class*=cart]',
        'li[class*=item]',
    ],
    # 장바구니에서 주문서로 진입하는 "주문하기" 버튼
    "order_button": [
        'button:has-text("주문하기")',
        'a:has-text("주문하기")',
        'button[class*=order]',
        'a[class*=order]',
    ],
    # 장바구니 항목 삭제 버튼(원상복구)
    "cart_delete": [
        'button:has-text("삭제")',
        'a:has-text("삭제")',
        'button[class*=delete]',
        'button[class*=remove]',
    ],
}

# 주문서(결제 직전) 페이지로 인정하는 URL 토큰 — 이 너머로는 어떤 클릭도 하지 않는다.
CHECKOUT_URL_TOKENS = ("order", "checkout", "pay/order")


def _first_match(page, selector_list):
    """폴백 셀렉터 리스트에서 처음 매칭되는 요소 핸들 반환. 없으면 None."""
    for sel in (selector_list or []):
        try:
            el = page.query_selector(sel)
        except Exception:
            el = None
        if el:
            return el
    return None


def _safe_inner_text(page):
    """body inner_text 안전 추출. 실패 시 빈 문자열."""
    try:
        return page.inner_text("body") or ""
    except Exception:
        return ""


def _count_cart_rows(page):
    """장바구니 상품 행 개수 추정 (원상복구 검증용). 셀 수 없으면 None."""
    for sel in SELECTORS["cart_row"]:
        try:
            els = page.query_selector_all(sel)
        except Exception:
            els = None
        if els:
            return len(els)
    return None


def _clamp_top(top):
    """top 인자 클램프: 1~5 (기본 3)."""
    try:
        t = int(top)
    except (TypeError, ValueError):
        t = 3
    if t < 1:
        t = 1
    if t > 5:
        t = 5
    return t


def _process_one(page, cand, rank):
    """상품 1개 처리 (계획 1.3의 a~i).

    반환: (offer dict, blocked: bool, raw_product dict)
    blocked=True 면 호출측에서 즉시 전체 중단.
    """
    link = cand.get("link")
    title = cand.get("title")
    list_price = cand.get("list_price")
    mall = cand.get("mall")

    offer = {
        "mall": mall,
        "title": title,
        "link": link,
        "list_price": list_price,
        "coupon": None,
        "card_discount": 0,
        "point": 0,
        "shipping": 0,
        "final_price": None,
        "confidence": "참고가",
        "is_reference": True,
        "cart_cleanup": "not_added",
        "needs_human": False,
        "url": link,  # 구매직전링크 — 주문서 도달 시에도 상품링크를 유지
    }
    raw_product = {
        "rank": rank,
        "title": title,
        "link": link,
        "list_price": list_price,
        "coupon_price": None,
        "raw_detail_text": "",
        "needs_human": False,
    }

    # link 없으면 진행 불가 — 참고가(표시가)로 강등하고 흐름 유지
    if not link:
        fp, is_ref = compute_final_price({"list_price": list_price})
        offer["final_price"] = fp
        offer["is_reference"] = is_ref
        offer["reason"] = "상품 링크 없음 -> 표시가 참고"
        return offer, False, raw_product

    breakdown = {"coupon_price": None, "list_price": list_price}
    cart_added = False

    try:
        # a. 상품 상세 진입
        page.goto(link, timeout=30000, wait_until="domcontentloaded")
        human_delay(page)

        # b. 봇차단 감지 -> 즉시 전체 중단
        detail_text = _safe_inner_text(page)
        try:
            page_title = page.title()
        except Exception:
            page_title = ""
        if detect_block(detail_text, page_title):
            offer["needs_human"] = True
            offer["reason"] = "봇차단/보안확인 화면 -> 사람 개입 필요"
            raw_product["needs_human"] = True
            raw_product["raw_detail_text"] = detail_text[:1500]
            return offer, True, raw_product

        raw_product["raw_detail_text"] = detail_text[:1500]

        # c. 쿠폰가 텍스트만 읽는다 ("받기" 버튼 클릭 금지)
        cp = extract_coupon_price(detail_text)
        breakdown["coupon_price"] = cp.get("coupon_price")
        if cp.get("list_price") is not None:
            breakdown["list_price"] = cp.get("list_price")
            if offer["list_price"] is None:
                offer["list_price"] = cp.get("list_price")
        offer["coupon"] = cp.get("coupon_price")
        raw_product["coupon_price"] = cp.get("coupon_price")

        # d. 장바구니 담기
        add_btn = _first_match(page, SELECTORS["add_to_cart"])
        if add_btn is None:
            offer["reason"] = "장바구니 버튼 셀렉터 매칭 0개 -> 참고가 강등"
        else:
            try:
                add_btn.click()
                human_delay(page)
                cart_added = True
                offer["cart_cleanup"] = "failed"  # 담긴 상태 — finally에서 removed로 갱신 시도
            except Exception as e:
                offer["reason"] = f"장바구니 담기 실패: {e}"

        # e. 주문서(결제 직전) 진입 — 장바구니 담기 성공 시에만
        if cart_added:
            order_btn = _first_match(page, SELECTORS["order_button"])
            if order_btn is None:
                offer["reason"] = "주문하기 버튼 셀렉터 매칭 0개 -> 참고가 강등"
            else:
                try:
                    order_btn.click()
                    human_delay(page)
                    cur_url = (page.url or "").lower()
                    # URL에 order/checkout 포함 확인 후에만 주문서로 인정
                    if any(tok in cur_url for tok in CHECKOUT_URL_TOKENS):
                        # f. 주문서 텍스트만 읽고 정지 — 이 너머로 어떤 클릭도 하지 않는다
                        checkout_text = _safe_inner_text(page)
                        if detect_block(checkout_text, ""):
                            offer["needs_human"] = True
                            offer["reason"] = "주문서 봇차단 -> 사람 개입 필요"
                            raw_product["needs_human"] = True
                            return offer, True, raw_product
                        cb = extract_checkout_breakdown(checkout_text)
                        breakdown.update(cb)
                    else:
                        offer["reason"] = "주문서 URL(order/checkout) 미도달 -> 참고가 강등"
                except Exception as e:
                    offer["reason"] = f"주문서 진입 실패: {e}"

    except Exception as e:
        offer["reason"] = f"상세/주문 흐름 실패: {e}"

    finally:
        # h. 장바구니 원상복구 — 담았으면 삭제 시도
        if cart_added:
            try:
                # 장바구니에 담은 직후 주문서로 이동했을 수 있으니 장바구니로 복귀
                try:
                    page.goto("https://shopping.naver.com/cart",
                              timeout=20000, wait_until="domcontentloaded")
                    human_delay(page)
                except Exception:
                    pass
                before = _count_cart_rows(page)
                del_btn = _first_match(page, SELECTORS["cart_delete"])
                if del_btn is not None:
                    # 삭제 확인 팝업(JS dialog)이 뜨면 1회 수락 — 삭제 확정용(결제와 무관)
                    page.once("dialog", lambda d: d.accept())
                    del_btn.click()
                    human_delay(page)
                    after = _count_cart_rows(page)
                    # 행 수가 실제로 줄었을 때만 removed. 검증 못 하면 거짓 보고 대신 failed+경고.
                    if before is not None and after is not None and after < before:
                        offer["cart_cleanup"] = "removed"
                    else:
                        offer["cart_cleanup"] = "failed"
                        print(f"  [경고] 장바구니 삭제 미검증 → 직접 확인 권장: {title}")
                else:
                    offer["cart_cleanup"] = "failed"
                    print(f"  [경고] 장바구니 수동 정리 필요 (삭제 버튼 매칭 0개): {title}")
            except Exception as e:
                offer["cart_cleanup"] = "failed"
                print(f"  [경고] 장바구니 수동 정리 필요 ({e}): {title}")

    # g. 최종가 계산 (주문서값 있으면 실결제가, 없으면 쿠폰가->표시가 참고가 강등)
    final, is_ref = compute_final_price(breakdown)
    offer["final_price"] = final
    offer["is_reference"] = is_ref
    offer["confidence"] = "참고가" if is_ref else "실결제가"
    offer["card_discount"] = breakdown.get("card_discount", 0) or 0
    offer["point"] = breakdown.get("point", 0) or 0
    offer["shipping"] = breakdown.get("shipping", 0) or 0
    return offer, False, raw_product


def main():
    ap = argparse.ArgumentParser(description="네이버 쇼핑 상세 크롤러 (실결제가 캡처)")
    ap.add_argument("--top", type=int, default=3, help="상위 N개 상품 (기본 3, 최대 5)")
    args = ap.parse_args()
    top = _clamp_top(args.top)

    # 시작: 01_candidates 확인 + 별칭 보장
    cands = ensure_candidates_alias()
    if cands is None:
        print('[오류] _workspace\\01_candidates.json 없음 -> 먼저 '
              'python scripts\\naver_poc.py "검색어" 실행')
        sys.exit(1)

    # 세션 파일 경고(비로그인이면 최종가 캡처 실패 가능)
    if not os.path.exists(SESSION_FILE):
        print("[안내] 세션 없음 -> python scripts\\naver_session_save.py 먼저 실행 권장"
              "(비로그인이면 최종가 캡처 실패 가능)")

    query = cands.get("query") or "검색어"
    items = [it for it in (cands.get("items", []) or []) if isinstance(it, dict)]
    norm = [normalize_candidate(it) for it in items][:top]

    if not norm:
        print("[안내] 01_candidates 에 처리할 상품이 없습니다.")
        sys.exit(1)

    offers = []
    raw_products = []
    blocked = False

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = launch_browser(p)
        ctx = new_naver_context(browser)
        page = ctx.new_page()
        try:
            for i, cand in enumerate(norm):
                rank = cand.get("rank") or (i + 1)
                offer, was_blocked, raw_product = _process_one(page, cand, rank)
                offers.append(offer)
                raw_products.append(raw_product)
                if was_blocked:
                    blocked = True
                    # 봇차단 -> 즉시 전체 중단(진행분까지만 저장)
                    break
        finally:
            browser.close()

    # 저장: 03_prices.json(정본) + 03_price_compare.json(별칭)
    prices = build_prices_schema(query, offers)
    paths = save_with_alias(prices, "03_prices.json", ["03_price_compare.json"])
    # 상품별 원문을 02_browser_raw 에 병합(append-merge)
    merge_into_browser_raw(query, raw_products)

    # 콘솔 요약 (naver_poc.py 스타일)
    print("=" * 50)
    print(f"검색어: {query}  (상위 {len(offers)}개 처리)")
    for o in offers:
        fp = o.get("final_price")
        fp_str = f"{fp:,}원" if isinstance(fp, int) else "미확인"
        print(f"  - {o.get('title')}  | {fp_str}  "
              f"| {o.get('confidence')}  | cart_cleanup={o.get('cart_cleanup')}"
              + ("  | needs_human" if o.get("needs_human") else ""))
    best = prices.get("best")
    if best:
        bp = best.get("final_price")
        bp_str = f"{bp:,}원" if isinstance(bp, int) else "미확인"
        print(f"[최저 실결제가 우선] {best.get('mall')}  {bp_str}")
    if blocked:
        print("[중단] 봇차단/보안확인 감지 -> 진행분까지만 저장. 사람 개입 필요.")
    print(f"[저장됨] {paths[0]}")
    print("=" * 50)


if __name__ == "__main__":
    main()
