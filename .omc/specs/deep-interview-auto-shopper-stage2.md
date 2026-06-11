# Deep Interview Spec: auto_shopper 2단계 — 실사용 수준 쇼핑 대행 파이프라인

## Metadata
- Interview ID: di-autoshopper-20260611
- Rounds: 4 (R1 아이디어, R0 토폴로지, R2 검증기준, R3 진입한계)
- Final Ambiguity Score: 15%
- Type: brownfield
- Generated: 2026-06-11
- Threshold: 0.2
- Threshold Source: default
- Initial Context Summarized: yes (RESUME.md 요약 사용)
- Status: PASSED

## Clarity Breakdown
| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Goal Clarity | 0.85 | 0.35 | 0.298 |
| Constraint Clarity | 0.85 | 0.25 | 0.213 |
| Success Criteria | 0.85 | 0.25 | 0.213 |
| Context Clarity | 0.85 | 0.15 | 0.128 |
| **Total Clarity** | | | **0.85** |
| **Ambiguity** | | | **0.15** |

## Topology
| Component | Status | Description | Coverage / Deferral Note |
|-----------|--------|-------------|--------------------------|
| 기반 검증(①②) | active | 기존 headful+세션재사용이 실제 봇차단 없이 동작하는지 점검·보강(사람처럼 천천히 포함) | AC-1, AC-6 |
| 상품상세 크롤러(③) | active | `scripts/naver_product_detail.py` 신규 — 상품페이지→쿠폰가→장바구니→주문서 직전 최종가 캡처 → `_workspace/03_prices.json` | AC-2, AC-5, AC-7 |
| 리뷰 수집기(④) | active | 상품 리뷰 텍스트 수집 → `_workspace/02_browser_raw.json` + `_workspace/04_reviews.json` | AC-3 |
| 에이전트 연결(⑤) | active | price-hunter·review-risk-analyst가 실데이터를 쓰고 best-deal-finder가 `_workspace/05_final.json` 통합추천 생성 | AC-4 |

## Goal
네이버 쇼핑 대행 하네스를 실사용 수준으로 끌어올린다. 기존 검색 PoC(`naver_poc.py`) 위에 (a) 상품상세→쿠폰 적용가→주문서 직전 **진짜 최종가**(카드할인·포인트·배송비 포함) 캡처, (b) 리뷰 자동수집, (c) 에이전트 데이터 연결을 구현해, 검색어 하나로 `01_candidates → 02_browser_raw → 03_prices → 04_reviews → 05_final` 데이터 흐름이 끝까지 완주하고 1순위 추천+구매 직전 링크가 나오게 한다. 결제 클릭만 사람이 한다.

## Constraints
- **결제/주문 실행 절대 금지** (불변). 주문서(결제) 페이지 진입까지만 허용, 결제 버튼 클릭 금지.
- 장바구니에 담은 상품은 최종가 확인 후 **장바구니에서 제거**해 계정을 원상복구한다.
- **headful 필수** — headless는 네이버 봇차단 실측됨. 사람처럼 천천히(랜덤 대기, 점진 스크롤).
- 봇차단/캡차/보안확인 감지 시 **우회 금지** → `needs_human` 신호 내고 중단(반자동 인계).
- 세션: `data/naver_session.json` 재사용(최초 1회 사람 로그인). 비밀번호·API키 저장/출력/하드코딩 금지.
- 브라우저: 내장 chromium 실패 시 시스템 Chrome(`channel="chrome"`) 폴백 유지 (이 환경서 내장 다운로드 차단 실측).
- 가격: 실결제가 기준. 주문서까지 확인 못한 값은 **"참고가"** 로 명시 표기.
- 기존 `naver_poc.py` 동작 회귀 금지 (01_candidates 생성 흐름 유지).
- Windows PowerShell 환경, 실행은 `python -m ...` 형식 안내. Python 3.14 / Playwright 1.60.
- `data/`, `.env` 커밋 금지 (.gitignore 유지).

## Non-Goals
- 결제/주문 자동 실행 (영구 금지)
- 네이버 외 쇼핑몰 지원
- 봇차단/캡차 우회 기술
- 대시보드·UI 개발
- 에이전트 정의 파일(~/.claude) 대규모 개편 — 데이터 연결에 필요한 최소 수정만

## Acceptance Criteria
- [ ] **AC-1 (기반)**: headful+세션 재사용으로 네이버쇼핑 검색이 봇차단 없이 동작, `_workspace/01_candidates.json` 생성 (회귀 확인)
- [ ] **AC-2 (최종가)**: `naver_product_detail.py`가 01의 상위 3~5개 상품에 대해 상품페이지 진입→쿠폰 적용가 캡처→장바구니 담기→주문서 직전 최종가(카드할인·포인트·배송비 포함) 캡처→`03_prices.json` 저장. 미확인 값은 "참고가" 표기. 담은 상품은 장바구니에서 제거됨.
- [ ] **AC-3 (리뷰)**: 각 상품의 리뷰 텍스트(낮은 평점 포함)를 수집해 `02_browser_raw.json`·`04_reviews.json` 생성 — deal-breaker 분석 입력으로 사용 가능한 형태.
- [ ] **AC-4 (통합추천)**: `05_final.json`에 "가성비 + 리뷰·평점 − deal-breaker 페널티" 기준 1순위 추천과 구매 직전 링크 생성. deal-breaker verdict=제외면 최저가여도 1순위에서 내림.
- [ ] **AC-5 (안전)**: 봇차단/캡차 감지 시 `needs_human` 신호 후 중단. 결제 버튼 클릭 코드 부재.
- [ ] **AC-6 (E2E)**: 실제 검색어 1개(기본 "무선청소기")로 검색→후보→최종가→리뷰→05_final까지 전 과정 1회 완주. 사람이 결과를 보고 합격 판정.
- [ ] **AC-7 (자동테스트)**: 네트워크 없이 도는 파싱/정규화 단위테스트가 `python -m pytest`로 통과. 모든 신규/수정 py 파일 `python -m py_compile` 통과.

## Assumptions Exposed & Resolved
| Assumption | Challenge | Resolution |
|------------|-----------|------------|
| RESUME 5개 항목이 전부 미구현일 것 | 코드 탐색으로 검증 | ①headful ②세션재사용은 이미 구현됨 → "기반 검증"으로 축소, 신규 구현은 ③④⑤ |
| "완성"의 기준이 자명할 것 | R2에서 검증 장면 질문 | E2E 실전 1회 완주 + 네트워크 없는 자동테스트 둘 다 |
| "최종가 캡처"의 도달 한계가 자명할 것 | R3에서 계정 흔적 허용 한계 질문 | 주문서 직전까지 진입 허용(결제 버튼 금지, 장바구니 원상복구) |

## Technical Context
- `scripts/naver_poc.py` — 검색 PoC 구현됨: headful 기본, 세션 자동 로드(L103), 봇차단 감지(L122-133), 셀렉터 폴백 4종(L136-141), `01_candidates.json` 저장(L186-202). 셀렉터는 네이버 개편 시 수선 필요 주석 있음.
- `scripts/naver_session_save.py` — 세션 저장 구현됨(쿠키+localStorage, 비번 미저장). docstring이 `naver_product_detail.py`를 참조하나 **파일 미존재(핵심 갭)**.
- `_workspace/` 데이터 흐름: 01 후보 → 02 원문 → 03 가격 → 04 리뷰 → 05 최종추천 (01만 생성기 존재).
- 에이전트 5종(decision-advisor, browser-agent, price-hunter, review-risk-analyst, best-deal-finder)·스킬 5종은 `~/.claude`(사용자 단위)에 있음 — `_workspace/` 상대경로로 데이터 접근.
- 환경: Python 3.14.5, Playwright 1.60(내장 chromium 다운로드 차단 → 시스템 Chrome 폴백), Node 26.3, Windows 11 + PowerShell. D:\auto_shopper는 git repo (main).

## Ontology (Key Entities)
| Entity | Type | Fields | Relationships |
|--------|------|--------|---------------|
| 후보상품 | core domain | title, lprice(표시가), mall, link, productId, rank | 검색어 1 → 후보상품 N (01_candidates) |
| 네이버세션 | supporting | 쿠키, localStorage (비번 없음) | 모든 브라우저 작업이 세션을 재사용 |
| 상품상세 | core domain | 쿠폰적용가, 카드할인, 포인트, 배송비, 최종가, 참고가플래그 | 후보상품 1 → 상품상세 1 (03_prices) |
| 리뷰 | core domain | 텍스트, 평점, 날짜 | 후보상품 1 → 리뷰 N (02/04 json) |
| deal-breaker판정 | core domain | verdict(제외/경고/통과), 근거리뷰 | 리뷰 N → 판정 1 |
| 통합추천 | core domain | 1순위 상품, 실결제가, 구매직전링크, 근거 | 상품상세+판정 → 추천 (05_final) |
| 에이전트 | external system | price-hunter, review-risk-analyst, best-deal-finder | _workspace JSON을 읽고 씀 |
| 데이터파일01-05 | supporting | JSON 스키마 | 컴포넌트 간 계약(contract) |

## Ontology Convergence
| Round | Entity Count | New | Changed | Stable | Stability Ratio |
|-------|-------------|-----|---------|--------|----------------|
| 1 | 8 | 8 | - | - | N/A |
| 2 | 8 | 0 | 0 | 8 | 100% |
| 3 | 8 | 0 | 0 | 8 | 100% |

도메인 모델이 2라운드 연속 무변경으로 수렴함.

## Interview Transcript
<details>
<summary>Full Q&A (4 rounds)</summary>

### Round 1 (아이디어 수집)
**Q:** 이번 autopilot으로 무엇을 만들까요? (RESUME.md 2단계 5개 항목 제시)
**A:** RESUME 2단계 전체
**Ambiguity:** 미측정 → 측정 시작

### Round 0 (토폴로지 확인)
**Q:** 4개 컴포넌트(기반검증①②/상세크롤러③/리뷰수집④/에이전트연결⑤) 구도가 맞나? 코드 탐색 결과 ①②는 이미 구현됨을 명시.
**A:** 맞음, 이대로 진행
**Ambiguity:** 27% (Goal 0.80, Constraints 0.80→0.70(컴포넌트 최솟값), Criteria 0.50, Context 0.85)

### Round 2 (검증 기준)
**Q:** 완성됐다고 인정할 검증 기준은? (E2E 1회 완주 / 컴포넌트별 단독 / 둘 다)
**A:** E2E + 자동테스트 둘 다
**Ambiguity:** 21% (Criteria 0.50→0.85)

### Round 3 (진입 한계)
**Q:** 로그인 계정으로 자동화가 어디까지 진입 허용? (상품페이지만 / 장바구니까지 / 주문서 직전까지)
**A:** 주문서 직전까지 (결제 버튼 절대 금지, 담은 상품 제거)
**Ambiguity:** 15% (Goal 0.80→0.85, Constraints 0.70→0.85) — **임계값 20% 충족**

</details>
