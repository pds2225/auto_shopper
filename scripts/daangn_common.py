# -*- coding: utf-8 -*-
r"""
당근마켓 시세 점검 공통 유틸 (브라우저 I/O 헬퍼)

브라우저 I/O 헬퍼 + 경로상수 + 봇차단/로그인유도/지역인증 감지를 한 곳에 모은다.
naver_common.py 의 검증된 패턴(경로상수 L18-21, save L37-43, save_with_alias L46-54,
봇차단 L108-114, 폴백 launch_browser L129-138, 세션로드 L141-151)을 미러링했다.

- detect_block / BLOCK_SIGNALS 는 순수(브라우저 불필요) -> tests 에서 직접 검증.
- Playwright import 는 함수 내부 지연 import (모듈 import 시점에 playwright
  없어도 순수 부분은 동작해야 한다).

안전 원칙(불변): 거래 행동(구매/결제/주문/채팅/문의/찜/연락처/전화) 자동화 코드는
이 헬퍼에 일절 두지 않는다. BLOCK_SIGNALS 의 문자열은 감지용일 뿐 클릭 대상이 아니다.
"""
import os
import json
import random
import datetime

# 경로 상수 (naver_common.py L18-21 미러, 당근용 경로로 교체)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "_workspace")
SESSION_FILE = os.path.join(ROOT, "data", "daangn_session.json")
SAVED_DIR = os.path.join(ROOT, "_saved")

# 봇차단/로그인유도/지역인증 시그널 (당근 변종, 1차안 — T8 실측 보강 대상)
# - 차단/보안확인 계열 + 로그인 유도 계열 + 지역(동네) 인증 계열을 모두 포함.
# - detect_block 에서 문자열 포함 검사로만 쓰인다(클릭 대상 아님, AC-5).
BLOCK_SIGNALS = [
    # 봇차단/보안확인 계열
    "보안 확인", "실제 사용자임을 확인", "스팸을 방지",
    "자동화", "captcha", "blocked", "비정상적인 접근", "비정상 접근",
    "접속이 불가", "접속 불가", "잠시 후 다시",
    # 로그인 유도 계열
    "로그인이 필요", "로그인 후 이용", "로그인 후 확인", "로그인해 주세요",
    "로그인하기", "로그인이 필요해요",
    # 지역(동네) 인증 계열
    "동네 인증", "동네 인증이 필요", "지역 인증", "위치 인증",
    "내 동네를 설정", "동네를 설정", "동네 설정이 필요",
]


def now():
    """현재 시각 문자열 (naver_common.py L32-34 동일)."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def save(obj, name):
    """obj 를 _workspace/name 에 UTF-8 JSON 저장 (naver_common.py L37-43 동일)."""
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    return path


def save_with_alias(obj, primary_name, alias_names):
    """정본 저장 후 동일 내용을 별칭 파일명으로도 저장 (naver_common.py L46-54 동일).

    반환: [정본경로, 별칭경로...]
    """
    paths = [save(obj, primary_name)]
    for alias in (alias_names or []):
        paths.append(save(obj, alias))
    return paths


def detect_block(body_text, title):
    """봇차단/로그인유도/지역인증 화면 여부 (순수 함수, naver_common.py L108-114 미러).

    body_text + title 을 합쳐 BLOCK_SIGNALS 중 하나라도 들어있으면 True.
    감지만 한다 — 우회/클릭 없음(AC-3, AC-5). 빈/None 입력은 False.
    """
    blob = ((body_text or "") + " " + (title or "")).lower()
    return any(sig.lower() in blob for sig in BLOCK_SIGNALS)


def human_delay(page, lo=0.8, hi=2.5):
    """사람처럼 천천히 — lo~hi초 무작위 대기 (naver_common.py L117-119 동일)."""
    page.wait_for_timeout(random.uniform(lo, hi) * 1000)


def gradual_scroll(page, steps=6):
    """점진 스크롤(검색결과/상세 지연 로딩 유도). 각 스텝 사이 human_delay (naver_common.py L122-126 동일)."""
    for _ in range(steps):
        page.mouse.wheel(0, 900)
        human_delay(page)


def launch_browser(p):
    """브라우저 실행 (headful 고정, naver_common.py L129-138 미러).

    1순위: playwright 내장 chromium. 없으면 시스템 Chrome(channel="chrome") 폴백.
    안전상 headless 경로를 두지 않는다.
    """
    try:
        return p.chromium.launch(headless=False)
    except Exception:
        return p.chromium.launch(headless=False, channel="chrome")


def new_daangn_context(browser):
    """당근용 컨텍스트 생성 — UA/locale/viewport + 세션로드 (naver_common.py L141-151 미러)."""
    storage_state = SESSION_FILE if os.path.exists(SESSION_FILE) else None
    return browser.new_context(
        storage_state=storage_state,
        user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"),
        locale="ko-KR",
        viewport={"width": 1366, "height": 900},
    )
