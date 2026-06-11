# -*- coding: utf-8 -*-
r"""
네이버 쇼핑 공통 유틸 (2단계)

브라우저 I/O 헬퍼 + 경로상수 + 봇차단 감지를 한 곳에 모은다.
naver_poc.py의 검증된 패턴(경로상수 L25-27, save L42-47, 폴백 L95-102,
세션로드 L103-113, 봇차단 L122-133)을 추출했다.

- detect_block / BLOCK_SIGNALS 는 순수(브라우저 불필요) -> tests에서 직접 검증.
- Playwright import 는 함수 내부 지연 import (모듈 import 시점에 playwright
  없어도 순수 부분은 동작해야 한다).
"""
import os
import json
import random
import datetime

# 경로 상수 (naver_poc.py L25-27 동일)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "_workspace")
SESSION_FILE = os.path.join(ROOT, "data", "naver_session.json")

# 봇차단/캡차/보안확인 시그널 (naver_poc.py L123-126)
BLOCK_SIGNALS = [
    "보안 확인", "실제 사용자임을 확인", "스팸을 방지",
    "자동화된", "captcha", "blocked", "비정상적인 접근", "비정상 접근",
]


def now():
    """현재 시각 문자열 (naver_poc.py L34-35)."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def save(obj, name):
    """obj 를 _workspace/name 에 UTF-8 JSON 저장 (naver_poc.py L42-47)."""
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    return path


def save_with_alias(obj, primary_name, alias_names):
    """정본 저장 후 동일 내용을 별칭 파일명으로도 저장 (파일명 계약 충돌 해소).

    반환: [정본경로, 별칭경로...]
    """
    paths = [save(obj, primary_name)]
    for alias in (alias_names or []):
        paths.append(save(obj, alias))
    return paths


def _product_key(p):
    """02_browser_raw 병합 키 — link > product_id > title 순 (rank는 모드별로 흔들림)."""
    return p.get("link") or p.get("product_id") or p.get("title") or ""


def merge_into_browser_raw(query, products, name="02_browser_raw.json"):
    """02_browser_raw.json 에 상품별 append-merge (덮어쓰기 금지).

    상세 크롤러와 리뷰 수집기가 모두 02 를 쓰므로, 기존 파일을 읽어
    같은 상품(link 기준)이면 필드를 병합하고 아니면 추가한다.
    """
    path = os.path.join(OUT_DIR, name)
    existing = {"query": query, "ts": now(), "products": []}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            pass  # 깨진 파일이면 새로 시작
    by_key = {_product_key(p): p for p in existing.get("products", []) if _product_key(p)}
    for p in (products or []):
        k = _product_key(p)
        if k and k in by_key:
            prev = by_key[k]
            # needs_human=True 는 이후 병합이 False 로 덮지 못한다 (사람 개입 신호 보존)
            keep_needs_human = bool(prev.get("needs_human")) or bool(p.get("needs_human"))
            prev.update({kk: vv for kk, vv in p.items() if vv is not None})
            if keep_needs_human:
                prev["needs_human"] = True
        else:
            by_key[k or f"_anon_{len(by_key)}"] = p
    existing["query"] = query
    existing["ts"] = now()
    existing["products"] = list(by_key.values())
    return save(existing, name)


def ensure_candidates_alias():
    """01_candidates.json -> 01_decision_candidates.json 별칭 보장 (T6, naver_poc.py 무수정).

    01 이 없으면 None 반환 (호출측에서 에러 안내).
    """
    src = os.path.join(OUT_DIR, "01_candidates.json")
    if not os.path.exists(src):
        return None
    with open(src, "r", encoding="utf-8") as f:
        obj = json.load(f)
    save(obj, "01_decision_candidates.json")
    return obj


def detect_block(body_text, title):
    """봇차단/보안확인 화면 여부 (순수 함수, naver_poc.py L127-128).

    body_text + title 을 합쳐 BLOCK_SIGNALS 중 하나라도 들어있으면 True.
    """
    blob = ((body_text or "") + " " + (title or "")).lower()
    return any(sig.lower() in blob for sig in BLOCK_SIGNALS)


def human_delay(page, lo=0.8, hi=2.5):
    """사람처럼 천천히 — lo~hi초 무작위 대기."""
    page.wait_for_timeout(random.uniform(lo, hi) * 1000)


def gradual_scroll(page, steps=6):
    """점진 스크롤(리뷰/상세 지연 로딩 유도). 각 스텝 사이 human_delay."""
    for _ in range(steps):
        page.mouse.wheel(0, 900)
        human_delay(page)


def launch_browser(p):
    """브라우저 실행 (headful 고정).

    1순위: playwright 내장 chromium. 없으면 시스템 Chrome(channel="chrome") 폴백.
    (naver_poc.py L95-102 패턴). 안전상 headless 경로를 두지 않는다.
    """
    try:
        return p.chromium.launch(headless=False)
    except Exception:
        return p.chromium.launch(headless=False, channel="chrome")


def new_naver_context(browser):
    """네이버용 컨텍스트 생성 — UA/locale/viewport + 세션로드 (naver_poc.py L104-111)."""
    storage_state = SESSION_FILE if os.path.exists(SESSION_FILE) else None
    return browser.new_context(
        storage_state=storage_state,
        user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"),
        locale="ko-KR",
        viewport={"width": 1366, "height": 900},
    )
