# -*- coding: utf-8 -*-
r"""
네이버 쇼핑 PoC - 1단계 작동 증명 스크립트

목적: "검색 -> 상품정보 추출"이 실제로 되는지 증명한다.
 - 모드 api     : 네이버 공식 검색 API(쇼핑). 안정적. NAVER_CLIENT_ID/SECRET 환경변수 필요.
 - 모드 browser : Playwright로 실제 네이버쇼핑 화면을 띄워 상품 카드 추출. 봇 차단 가능.
 - 모드 both    : 둘 다 시도 (기본값)

결과는 _workspace/poc_result.json 에 저장된다.

사용 (Windows PowerShell):
  python scripts\naver_poc.py "무선청소기"
  python scripts\naver_poc.py "무선청소기" --mode api
  python scripts\naver_poc.py "무선청소기" --mode browser --headless
"""
import os
import re
import json
import argparse
import datetime
import urllib.request
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "_workspace")
SESSION_FILE = os.path.join(ROOT, "data", "naver_session.json")

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"))


def now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def strip_tags(s):
    return re.sub("<.*?>", "", s or "")


def save(obj, name):
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    return path


def run_api(query, display=10):
    """네이버 공식 검색 API(쇼핑). 키 없으면 건너뛴다."""
    cid = os.environ.get("NAVER_CLIENT_ID")
    secret = os.environ.get("NAVER_CLIENT_SECRET")
    if not cid or not secret:
        return {"ok": False, "reason": "NAVER_CLIENT_ID/SECRET 환경변수 없음 -> API 모드 건너뜀"}
    url = "https://openapi.naver.com/v1/search/shop.json?" + urllib.parse.urlencode(
        {"query": query, "display": display, "sort": "asc"}
    )
    req = urllib.request.Request(
        url,
        headers={"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": secret},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"ok": False, "reason": f"API 호출 실패: {e}"}
    items = []
    for it in data.get("items", []):
        items.append({
            "title": strip_tags(it.get("title", "")),
            "lprice": it.get("lprice"),       # 최저가(표시가, 참고용)
            "hprice": it.get("hprice"),
            "mall": it.get("mallName"),
            "link": it.get("link"),
            "productId": it.get("productId"),
            "brand": it.get("brand"),
            "maker": it.get("maker"),
            "category": it.get("category3") or it.get("category2"),
        })
    return {"ok": len(items) > 0, "count": len(items), "items": items}


def run_browser(query, limit=10, headful=True):
    """Playwright로 네이버쇼핑 검색결과에서 상품 카드를 추출한다."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        return {"ok": False, "reason": f"playwright 미설치: {e}"}

    result = {"ok": False, "items": [], "notes": []}
    search_url = "https://search.shopping.naver.com/search/all?query=" + urllib.parse.quote(query)
    with sync_playwright() as p:
        # 1순위: playwright 내장 chromium. 없으면 시스템에 설치된 크롬(channel="chrome")으로 폴백.
        try:
            browser = p.chromium.launch(headless=not headful)
        except Exception:
            try:
                browser = p.chromium.launch(headless=not headful, channel="chrome")
                result["notes"].append("내장 chromium 없음 -> 시스템 Chrome 사용")
            except Exception as e:
                return {"ok": False, "reason": f"브라우저 실행 불가(내장/시스템 크롬 모두 실패): {e}"}
        storage_state = SESSION_FILE if os.path.exists(SESSION_FILE) else None
        ctx = browser.new_context(
            storage_state=storage_state,
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"),
            locale="ko-KR",
            viewport={"width": 1366, "height": 900},
        )
        if storage_state:
            result["notes"].append("세션 파일 로드됨 (로그인 유지)")
        page = ctx.new_page()
        try:
            page.goto(search_url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(3500)
            title = page.title()
            result["notes"].append(f"page_title: {title}")
            body = (page.inner_text("body") or "")[:800]

            # 봇 차단/캡차/보안확인 감지 -> 사람 개입(반자동) 신호
            block_signals = [
                "보안 확인", "실제 사용자임을 확인", "스팸을 방지",
                "자동화된", "captcha", "blocked", "비정상적인 접근", "비정상 접근",
            ]
            blob = (body + " " + (title or "")).lower()
            if any(sig.lower() in blob for sig in block_signals):
                result["reason"] = "네이버 봇 차단/보안확인 화면 -> 사람 개입(반자동) 필요"
                result["needs_human"] = True
                result["sample_body"] = body
                browser.close()
                return result

            # 상품 카드 추출 (셀렉터는 네이버 개편 시 수선 필요)
            selectors = [
                'div[class*=product_item]',
                'div[class*=basicList_item]',
                'div[class*=adProduct_item]',
                'li[class*=product]',
            ]
            cards = []
            for sel in selectors:
                cards = page.query_selector_all(sel)
                if cards:
                    result["notes"].append(f"matched_selector: {sel} ({len(cards)})")
                    break

            for c in cards[:limit]:
                txt = (c.inner_text() or "")[:300]
                link_el = c.query_selector("a")
                href = link_el.get_attribute("href") if link_el else None
                # 가격으로 보이는 숫자 추출 시도
                price = None
                m = re.search(r"([0-9][0-9,]{3,})\s*원", txt)
                if m:
                    price = m.group(1).replace(",", "")
                result["items"].append({"text": txt, "price_guess": price, "link": href})

            result["ok"] = len(result["items"]) > 0
            if not result["ok"]:
                result["reason"] = "상품 카드 셀렉터 매칭 0개 -> 셀렉터 수선 필요"
                result["sample_body"] = body
        except Exception as e:
            result["reason"] = f"브라우저 실행/이동 실패: {e}"
        finally:
            browser.close()
    return result


def main():
    ap = argparse.ArgumentParser(description="네이버 쇼핑 PoC")
    ap.add_argument("query", help="검색어 (예: 무선청소기)")
    ap.add_argument("--mode", choices=["browser", "api", "both"], default="both")
    ap.add_argument("--headless", action="store_true", help="브라우저 창 숨김")
    args = ap.parse_args()

    out = {"query": args.query, "ts": now(), "mode": args.mode}
    if args.mode in ("api", "both"):
        out["api"] = run_api(args.query)
    if args.mode in ("browser", "both"):
        out["browser"] = run_browser(args.query, headful=not args.headless)

    path = save(out, "poc_result.json")

    # 01_candidates.json 저장 (상품 상세 크롤러 입력용)
    items_for_cands = []
    if "browser" in out and out["browser"].get("ok"):
        items_for_cands = out["browser"].get("items", [])
        src = "browser"
    elif "api" in out and out["api"].get("ok"):
        items_for_cands = out["api"].get("items", [])
        src = "api"
    if items_for_cands:
        cands = {
            "query": out["query"],
            "ts": out["ts"],
            "source": src,
            "items": [dict(it, rank=i + 1) for i, it in enumerate(items_for_cands)],
        }
        cands_path = save(cands, "01_candidates.json")
        print(f"[후보 저장] {cands_path}  ({len(items_for_cands)}건)")

    # 콘솔 요약
    print("=" * 50)
    print(f"검색어: {args.query}  ({out['ts']})")
    if "api" in out:
        a = out["api"]
        print(f"[API]     ok={a.get('ok')}  count={a.get('count')}  {a.get('reason','')}")
    if "browser" in out:
        b = out["browser"]
        print(f"[BROWSER] ok={b.get('ok')}  items={len(b.get('items', []))}  {b.get('reason','')}")
        for note in b.get("notes", []):
            print(f"          - {note}")
    print(f"[저장됨] {path}")
    print("=" * 50)


if __name__ == "__main__":
    main()
