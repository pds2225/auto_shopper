# -*- coding: utf-8 -*-
r"""
당근마켓 세션 쿠키 저장 스크립트 (최초 1회 실행)

사용:
  python scripts\daangn_session_save.py

동작:
  1. headful 크롬이 열립니다.
  2. 당근마켓에 직접 로그인하세요.
  3. 내 동네(지역)를 설정하세요 — 검색 결과·시세가 동네 기준이라 정확도가 올라갑니다.
  4. 로그인 + 동네 설정 완료 후 터미널에서 Enter를 누르세요.
  5. 세션 쿠키가 data\daangn_session.json 에 저장됩니다.
  6. 이후 daangn_collect.py 가 이 파일을 자동 로드합니다.

주의:
  - 비밀번호는 저장되지 않습니다. 쿠키(로그인 토큰)만 저장됩니다.
  - 세션이 만료되면(로그인유도가 뜨면) 이 스크립트를 다시 실행하세요.
  - data\ 폴더는 .gitignore 에 포함되어 있어 절대 커밋되지 않습니다.
"""
import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
SESSION_FILE = os.path.join(DATA_DIR, "daangn_session.json")

DAANGN_URL = "https://www.daangn.com"


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[오류] playwright 미설치. 아래 명령을 먼저 실행하세요:")
        print("  python -m pip install playwright")
        sys.exit(1)

    os.makedirs(DATA_DIR, exist_ok=True)

    already_exists = os.path.exists(SESSION_FILE)
    if already_exists:
        print(f"[참고] 기존 세션 파일 있음: {SESSION_FILE}")
        print("       로그인 상태가 유지되면 바로 Enter 눌러도 됩니다.")

    print()
    print("=" * 60)
    print("[안내] 브라우저 창이 곧 열립니다.")
    print("  1. 당근마켓에 로그인해 주세요 (브라우저 창에서).")
    print("  2. 내 동네(지역)를 설정해 주세요 — 시세가 동네 기준이라 정확해집니다.")
    print("  3. 로그인 + 동네 설정 완료 후 이 터미널로 돌아와 Enter를 누르세요.")
    print("  (이미 로그인된 상태라면 바로 Enter)")
    print("=" * 60)

    with sync_playwright() as p:
        # 시스템 Chrome 우선 시도 (내장 chromium 다운로드 불가 환경 대응)
        browser = None
        for launch_kwargs in [
            {"headless": False},
            {"headless": False, "channel": "chrome"},
        ]:
            try:
                browser = p.chromium.launch(**launch_kwargs)
                break
            except Exception as e:
                last_err = e
        if browser is None:
            print(f"[오류] 브라우저 실행 실패: {last_err}")
            sys.exit(1)

        # 기존 세션이 있으면 로드해 로그인 상태 이어받기
        ctx_kwargs = dict(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="ko-KR",
            viewport={"width": 1366, "height": 900},
        )
        if already_exists:
            ctx_kwargs["storage_state"] = SESSION_FILE

        ctx = browser.new_context(**ctx_kwargs)
        page = ctx.new_page()
        page.goto(DAANGN_URL, timeout=30000)

        input("\n  ▶ 로그인 + 동네 설정 완료 후 Enter: ")

        # 쿠키 + localStorage 저장 (비밀번호는 포함되지 않음)
        ctx.storage_state(path=SESSION_FILE)
        browser.close()

    print()
    print(f"[저장됨] {SESSION_FILE}")
    print("[완료] 이제 수집 스크립트가 이 세션을 자동으로 재사용합니다.")
    print("       세션 만료 시 이 스크립트를 다시 실행하세요.")


if __name__ == "__main__":
    main()
