# auto_shopper 2단계 구현 계획 (autopilot-impl)

> 권위 순서: `.omc/specs/deep-interview-auto-shopper-stage2.md`(최상위) → 에이전트 입출력 계약 → 기존 `naver_poc.py` 패턴. 모든 경로는 절대경로/리포 상대경로 명시. 실행은 Windows PowerShell + `python -m ...`.

---

## 0. 핵심 의사결정 (구현 전 반드시 합의)

### 0.1 파일명 계약 충돌 해소 (BLOCKER — 먼저 확정)

스펙과 에이전트 정의가 **서로 다른 파일명**을 쓴다. 이대로 두면 AC-4(에이전트 연결)에서 dead link가 생긴다.

| 단계 | 스펙/RESUME 표기 | 에이전트 `.md` 기대 | 오케스트레이터 SKILL 표기 | **채택 (정본)** |
|------|------------------|---------------------|--------------------------|-----------------|
| 01 후보 | `01_candidates.json` (PoC 실제 생성) | `01_decision_candidates.json` (browser-agent L20) | `01_decision_candidates.json` | **둘 다 생성** — 정본 `01_candidates.json` + 별칭 복사 `01_decision_candidates.json` |
| 02 원문 | `02_browser_raw.json` | `02_browser_raw.json` | `02_browser_raw.json` | `02_browser_raw.json` (일치) |
| 03 가격 | `03_prices.json` | `03_price_compare.json` (price-hunter L21) | `03_price_compare.json` | **`03_prices.json`이 정본** — 단 price-hunter가 읽는 `03_price_compare.json`도 동시 출력(별칭) |
| 04 리뷰 | `04_reviews.json` | `04_review_risk.json` (review-risk-analyst L24, **판정 결과물**) | `04_review_risk.json` | **분리**: `04_reviews.json`=수집 원문(스크립트 산출), `04_review_risk.json`=판정(에이전트 산출). 둘은 다른 파일이며 충돌 아님 |
| 05 최종 | `05_final.json` | `05_final_recommendation.json` | `05_final_recommendation.json` | **`05_final.json`이 정본** + 별칭 `05_final_recommendation.json` 복사 |

**결정 원칙(스펙 우선):** 스크립트가 생성하는 파일의 **정본 이름은 스펙(`03_prices.json`/`04_reviews.json`/`05_final.json`)**을 따른다. 에이전트는 `~/.claude`에 있어 대규모 개편 금지(Non-Goals)이므로, **스크립트가 에이전트 기대 파일명으로 "별칭 복사본"을 추가 생성**해 양쪽을 모두 만족시킨다. 이 별칭 복사는 공통 유틸 `save_with_alias()` 한 곳에 모은다.

> 04는 충돌이 아니라 **역할 분리**다: `04_reviews.json`은 스크립트가 만드는 **수집 원문**(deal-breaker 분석 입력), `04_review_risk.json`은 review-risk-analyst가 만드는 **판정 결과**. 계획 전반에서 이 둘을 혼동하지 않는다.

### 0.2 모듈 구조 결정 (테스트 가능성의 핵심)

AC-7(네트워크 없는 단위테스트)을 만족하려면 **파싱·정규화·가격추출·스키마검증 로직을 브라우저 I/O와 물리적으로 분리**해야 한다. 따라서:

- `scripts/naver_product_detail.py` = **브라우저 오케스트레이션만** (Playwright goto/click/scroll, 세션로드, 봇차단감지). 순수 로직 호출만 한다.
- `scripts/naver_parsers.py` (**신규 순수 함수 모듈**) = DOM 텍스트 문자열 → 구조화 데이터. Playwright 객체를 import하지 않는다. 입력은 `str`/`dict`, 출력은 `dict`. → tests가 이 모듈만 호출하면 네트워크/브라우저 0.
- `scripts/naver_common.py` (**신규 공통 유틸**) = 경로 상수, `save()`, `save_with_alias()`, `now()`, `human_delay()`, 봇차단 시그널 리스트, 브라우저 런처 폴백 1곳.

> 이렇게 하면 `naver_poc.py`의 인라인 정규식(L155 `r"([0-9][0-9,]{3,})\s*원"`)·봇차단 리스트(L123-126)·브라우저 폴백(L95-102)이 **중복 구현되지 않고** `naver_common`/`naver_parsers`로 수렴한다. (단, naver_poc.py 회귀 금지를 위해 naver_poc.py 자체는 건드리지 않고 신규 모듈만 추가 — 6.2 참조)

---

## 1. 파일 단위 작업 목록

### 1.1 신규: `scripts/naver_common.py` (공통 유틸) — complexity: simple

**구현 내용**
- 경로 상수: `ROOT`, `OUT_DIR=_workspace`, `SESSION_FILE=data/naver_session.json` (naver_poc.py L25-27 패턴 그대로 복사).
- `now()` — naver_poc.py L34-35 재사용.
- `save(obj, name)` — naver_poc.py L42-47 재사용.
- `save_with_alias(obj, primary_name, alias_names: list)` — 정본 저장 후 동일 내용을 별칭 파일명으로도 저장 (0.1 충돌 해소용).
- `human_delay(page, lo=0.8, hi=2.5)` — `page.wait_for_timeout(random.uniform(lo,hi)*1000)`. "사람처럼 천천히" 제약 구현.
- `gradual_scroll(page, steps=6)` — 점진 스크롤(리뷰/상세 로딩 유도). 각 스텝 사이 `human_delay`.
- `launch_browser(p, headful=True)` — naver_poc.py L95-102 폴백 로직(내장 chromium → `channel="chrome"`)을 함수로 추출. headful 강제(headless 인자 없음 — 안전상 headful 고정).
- `new_naver_context(browser)` — UA/locale/viewport + `storage_state=SESSION_FILE if exists`. naver_poc.py L104-111 패턴.
- `BLOCK_SIGNALS` 상수 — naver_poc.py L123-126 리스트.
- `detect_block(body_text, title) -> bool` — naver_poc.py L127-128 판정 로직을 순수 함수로. **tests에서 검증 가능.**

**재사용 패턴:** 폴백(L95-102), 세션로드(L103-113), 봇차단감지(L122-133) 전부 이 파일로 추출.

### 1.2 신규: `scripts/naver_parsers.py` (순수 파싱 모듈) — complexity: standard

브라우저를 절대 import하지 않는다. 전부 `str`/`dict` in → `dict` out. **AC-7 테스트의 핵심 타깃.**

함수 목록:
- `parse_price_won(text: str) -> int | None` — naver_poc.py L155 정규식 일반화. "39,800원" → 39800. 천단위 콤마/원 단위/공백 변형 처리. 실패 시 None.
- `extract_coupon_price(detail_text: str) -> dict` — 상세 텍스트에서 "쿠폰적용가/즉시할인가" 후보 추출. `{"coupon_price": int|None, "list_price": int|None}`.
- `extract_checkout_breakdown(checkout_text: str) -> dict` — 주문서 직전 텍스트에서 카드할인/포인트/배송비/최종결제금액 분해. `{"card_discount":int, "point":int, "shipping":int, "final_price":int|None}`. 못 찾은 항목은 0 또는 None.
- `compute_final_price(breakdown: dict) -> tuple[int|None, bool]` — 최종가 계산 + `is_reference`(참고가 여부) 플래그. 주문서값 있으면 confidence=실결제가, 없으면 참고가. **AC-2 "참고가 표기" 로직.**
- `normalize_candidate(raw_item: dict) -> dict` — 01_candidates의 browser 모드 항목(`{text, price_guess, link}`)과 api 모드 항목(`{title, lprice, link, productId}`)을 **단일 스키마**로 정규화. 03/리뷰 입력 통일.
- `parse_review_block(block_text: str) -> dict` — 리뷰 한 덩어리 텍스트 → `{"text", "rating": float|None, "date": str|None}`. 별점/날짜 정규식.
- `dedup_reviews(reviews: list[dict]) -> list[dict]` — 중복 리뷰 텍스트 제거.
- `build_prices_schema(...)`, `build_reviews_schema(...)` — 섹션 2 스키마대로 dict 조립(스키마 일관성 1곳).
- `validate_schema(obj: dict, required_keys: list) -> list[str]` — 누락 키 리스트 반환(빈 리스트=통과). tests에서 스키마 검증에 사용.
- `score_offer(price_norm, rating, penalty)` — 통합추천 점수 순수 함수 (T5에서 사용, tests 대상).

### 1.3 신규: `scripts/naver_product_detail.py` (상세 크롤러, AC-2/AC-5/AC-7 핵심) — complexity: complex

**입력:** `_workspace/01_candidates.json` (없으면 에러 메시지 + 종료).
**출력:** `_workspace/03_prices.json` (정본) + `03_price_compare.json` (별칭, price-hunter용).

**처리 흐름 (상위 3~5개 상품 루프):**
1. 01_candidates 로드 → `normalize_candidate`로 정규화 → 상위 N개(기본 3, 인자 `--top`)만.
2. `naver_common.launch_browser`(headful) + `new_naver_context`(세션로드).
3. 각 상품:
   - a. 상품 링크로 `page.goto(..., wait_until="domcontentloaded")` + `human_delay`.
   - b. **봇차단 감지** (`detect_block(inner_text, title)`) → True면 그 상품 `needs_human:true` 기록하고 **즉시 전체 중단**(우회 금지, AC-5).
   - c. 쿠폰 영역 텍스트 추출 → `extract_coupon_price`. (쿠폰 "받기" 버튼이 있으면 클릭은 **선택**; 클릭해도 결제 아님 → 허용. 단 실패해도 진행.)
   - d. **장바구니 담기** 클릭 → `human_delay`. (담기 성공 여부 플래그 기록.)
   - e. 장바구니 → "주문하기"로 **주문서(결제 직전) 페이지까지만** 진입. `wait_until="domcontentloaded"`.
   - f. 주문서 텍스트 추출 → `extract_checkout_breakdown` → `compute_final_price`.
   - g. **결제 버튼은 절대 클릭하지 않는다** (코드 자체에 결제 클릭 셀렉터/호출 부재 — AC-5/불변).
   - h. **장바구니 원상복구**: 담았던 항목 삭제. try/finally로 보장. 삭제 실패 시 `cart_cleanup:"failed"` 기록 + 콘솔 경고(사람이 수동 정리하도록).
   - i. 주문서 진입 실패 → `compute_final_price`가 참고가로 강등(쿠폰가/표시가 confidence=참고가).
4. `build_prices_schema`로 조립 → `save_with_alias`로 03_prices.json + 03_price_compare.json 저장.

**재사용:** 봇차단감지/세션로드/폴백 모두 `naver_common`. 가격 파싱은 `naver_parsers`(브라우저 코드와 분리).

**셀렉터:** 상세/장바구니/주문서/리뷰 셀렉터는 **상단 상수 블록 `SELECTORS`**에 모으고 "네이버 개편 시 여기만 수선" 주석(naver_poc.py L135 패턴). 각 항목 폴백 후보 2~4개 리스트.

**안전 가드(코드 레벨):** 파일 어디에도 "결제"/"구매하기 최종"/"pay" 클릭이 없도록. 주문서 진입은 URL이 `order`/`checkout`까지만.

### 1.4 신규: `scripts/naver_reviews.py` (리뷰 수집, AC-3) — complexity: standard

**입력:** `01_candidates.json`. **출력:** `02_browser_raw.json`(원문 누적) + `04_reviews.json`(정제 리뷰).

**처리:**
1. 상위 N개 상품 각각 상품페이지 → 리뷰 탭 클릭 → `gradual_scroll`로 리뷰 로딩.
2. **낮은 평점 포함 수집**: 평점 정렬(낮은순) 탭이 있으면 한 번 더 수집(AC-3 "낮은 평점 포함").
3. 리뷰 블록 텍스트 수집 → `parse_review_block` → `dedup_reviews`.
4. 봇차단 감지 동일(`detect_block`) → `needs_human`.
5. `02_browser_raw.json`: 상품별 원문(표시가/쿠폰가 자리 + reviews 원문). `04_reviews.json`: `{product, reviews:[{text,rating,date}]}`.

> 분리 이유: 03(가격)과 04(리뷰)를 다른 스크립트로 두면 한쪽 실패가 다른 쪽을 막지 않고, E2E에서 병렬 가능. 단 02_browser_raw는 두 스크립트가 모두 쓰므로 **append-merge**(기존 읽고 product별 병합)로 처리 — 덮어쓰기 금지.

### 1.5 신규: `scripts/build_final.py` (통합추천 폴백 생성기, AC-4) — complexity: standard

best-deal-finder는 에이전트(LLM)다. 하지만 **네트워크 없는 자동 완주(AC-6 보조)·테스트**를 위해 **결정론적 폴백 점수 계산기**를 스크립트로 둔다.

**입력:** `03_prices.json` + `04_reviews.json` (+ 있으면 `04_review_risk.json` 판정).
**출력:** `05_final.json` + 별칭 `05_final_recommendation.json`.

**로직:**
- 점수식(AC-4/RESUME): `score = 가성비(가격 역수 정규화) + 리뷰가중(평점) − deal_breaker_penalty`.
- `04_review_risk.json`의 `verdict=="제외"`면 해당 상품 1순위에서 강등(점수 대폭 감점 또는 rank 후순위).
- best-deal-finder가 나중에 덮어써도 되도록 동일 스키마(섹션 2.5) 출력.
- 순수 점수 함수 `score_offer(price_norm, rating, penalty)`는 `naver_parsers`에 두고 tests 대상으로.

> 역할: best-deal-finder(에이전트)가 최종 판단을 하되, 이 스크립트는 **데이터 흐름이 끝까지 완주**하도록(AC-6) 하는 보증 장치 + 테스트 가능한 점수 로직 제공.

### 1.6 `naver_poc.py` 무수정 + 01 별칭 보장 — complexity: simple

**원칙:** 회귀 금지. naver_poc.py를 손대지 않고, **`naver_product_detail.py`/`naver_reviews.py` 시작 시 01_candidates를 읽어 `01_decision_candidates.json` 별칭을 보장**한다. → 회귀 0. browser-agent(L20)·orchestrator가 기대하는 `01_decision_candidates.json` dead link 해소.

### 1.7 신규: `tests/` (단위테스트) — complexity: standard

- `tests/__init__.py`, `tests/conftest.py`(픽스처: 샘플 DOM 텍스트 문자열, 샘플 JSON).
- `tests/fixtures/` — 정적 텍스트 샘플(상세 텍스트, 주문서 텍스트, 리뷰 블록, 01_candidates 샘플). **네트워크 0**.
- 테스트 파일 4종(섹션 4).

### 1.8 `requirements.txt`에 `pytest` 추가 — complexity: simple

현재 `playwright`, `python-dotenv`만. `pytest>=8.0` 한 줄 추가(테스트 전용, 최소 의존성 원칙 유지).

---

## 2. JSON 데이터 계약 (스키마)

> 표기: `int|null`은 미확인 허용. 모든 파일 `ts`(생성시각) 포함. 인코딩 UTF-8, `ensure_ascii=false`.

### 2.1 `01_candidates.json` (기존, 변경 없음 — 참고용)
naver_poc.py L195-200이 생성. browser 모드 item: `{text, price_guess, link}`, api 모드 item: `{title, lprice, hprice, mall, link, productId, ...}`. 공통 래퍼 `{query, ts, source, items:[{... , rank}]}`.
→ `naver_parsers.normalize_candidate`가 두 형태를 흡수해 다음 스키마로 정규화:
```json
{"rank": 1, "title": "제품명", "list_price": 39800, "mall": "샵명|null",
 "link": "https://...", "product_id": "123|null"}
```

### 2.2 `02_browser_raw.json` (원문, AC-3 입력)
```json
{
  "query": "무선청소기", "ts": "2026-06-11 15:20:00",
  "products": [
    {
      "rank": 1, "title": "...", "link": "https://...",
      "list_price": 39800, "coupon_price": 35800,
      "raw_detail_text": "...(상세 텍스트 일부)...",
      "raw_review_blocks": ["리뷰원문1", "리뷰원문2"],
      "needs_human": false
    }
  ]
}
```

### 2.3 `03_prices.json` (정본) + `03_price_compare.json` (별칭, price-hunter용)

price-hunter가 기대하는 `offers[]` 구조에 **맞춘다**:
```json
{
  "query": "무선청소기", "ts": "2026-06-11 15:25:00",
  "product": "무선청소기",
  "offers": [
    {
      "mall": "판매처", "title": "제품명", "link": "https://...",
      "list_price": 39800,
      "coupon": 4000, "card_discount": 1000, "point": 800, "shipping": 0,
      "final_price": 33000,
      "confidence": "실결제가",
      "is_reference": false,
      "cart_cleanup": "removed",
      "needs_human": false,
      "url": "https://...(구매직전링크)"
    }
  ],
  "best": {"mall": "...", "final_price": 33000, "url": "..."}
}
```
- `confidence`: `"실결제가"`(주문서 도달) | `"참고가"`(쿠폰가/표시가까지만).
- `is_reference`: 스펙 "참고가플래그" 명시 필드.
- `cart_cleanup`: `"removed"|"failed"|"not_added"` — 장바구니 원상복구 결과.
- 03_price_compare.json은 **동일 내용 복사**(price-hunter가 그대로 읽음).

### 2.4 `04_reviews.json` (수집 원문, 스크립트 산출 — `04_review_risk.json`과 별개)
```json
{
  "query": "무선청소기", "ts": "...",
  "products": [
    {"rank": 1, "title": "...", "link": "...",
     "rating_avg": 4.3, "review_count_seen": 40,
     "reviews": [
       {"text": "한 달 만에 흡입력 떨어져요", "rating": 1.0, "date": "2026-05-01"}
     ]}
  ]
}
```
→ review-risk-analyst가 이 파일(또는 02_browser_raw)을 읽어 **판정** `04_review_risk.json` 생성. **이 두 파일은 충돌이 아니라 입력/출력 관계.**

### 2.5 `05_final.json` (정본) + `05_final_recommendation.json` (별칭, best-deal-finder 계약)

best-deal-finder 스키마에 맞춘다:
```json
{
  "query": "무선청소기", "ts": "...",
  "rank": [
    {"name": "제품명", "final_price": 33000, "review_verdict": "안전|주의|제외|미상",
     "score": 0.82, "buy_url": "https://...(구매직전링크)",
     "confidence": "실결제가|참고가",
     "why": "최저 실결제가 + 평점 4.3 + deal-breaker 없음"}
  ],
  "note": "결제 직전까지 차려둠. 결제 버튼은 직접 눌러주세요."
}
```
- `review_verdict`: `04_review_risk.json` 없으면 `"미상"`.
- best-deal-finder가 나중에 LLM 판단으로 이 파일을 갱신해도 스키마 동일.

---

## 3. 태스크 분해와 의존성

```
T0 (공통 기반) ──┬─> T1 ──┬─> T3 ──┐
                 │        │        ├─> T5 ─> T6
                 └─> T2 ──┴─> T4 ──┘
T7(tests) 는 T0/T1 산출 함수에 의존하되 병렬 작성 가능
```

| Task | 내용 | 의존 | 병렬 | 복잡도 |
|------|------|------|------|--------|
| **T0** | `naver_common.py` + `naver_parsers.py` (순수 모듈) | 없음 | — | standard |
| **T1** | `naver_parsers.py`의 가격/쿠폰/주문서/정규화 함수 완성 | T0(스켈레톤) | T2와 병렬 | standard |
| **T2** | `naver_parsers.py`의 리뷰 파싱(`parse_review_block`,`dedup_reviews`) | T0 | T1과 병렬 | simple |
| **T3** | `naver_product_detail.py` (브라우저 오케스트레이션, 03_prices) | T1, T0 | T4와 병렬 | complex |
| **T4** | `naver_reviews.py` (리뷰 수집, 02/04) | T2, T0 | T3와 병렬 | standard |
| **T5** | `build_final.py` (05 통합, 점수 폴백) | T1(점수함수) | — | standard |
| **T6** | 01 별칭 보장(naver_poc.py 무수정) + 에이전트 연결 검증(dead link 0) | T3,T4,T5 | — | simple |
| **T7** | `tests/` 4종 + fixtures + requirements pytest | T1,T2 함수 시그니처 | T3~T5와 병렬 | standard |

**권장 병렬 배치(executor 분배):**
- 워커A: T0→T1→T3 (가격 라인)
- 워커B: T2→T4 (리뷰 라인)
- 워커C: T7 (테스트) — T1/T2 함수 시그니처 확정 직후 시작
- 직렬 마무리: T5→T6 (한 사람이 통합)

---

## 4. 테스트 계획 (네트워크 0, `python -m pytest`)

**위치:** `D:\auto_shopper\tests\`. 실행: `python -m pytest -q` (PowerShell). Playwright/네트워크 import 없음 — `naver_parsers`만 테스트.

### 4.1 `tests/test_price_parsing.py` (가격추출)
- `parse_price_won`: "39,800원"→39800, "1,234,000원"→1234000, "원"→None, ""→None, "무료배송"→None, 콤마없는 "9800원"→9800.
- `extract_coupon_price`: 쿠폰적용가 포함 텍스트 → coupon_price 정확, 쿠폰 없는 텍스트 → coupon_price=None+list_price만.
- `extract_checkout_breakdown`: 주문서 샘플 텍스트(fixtures) → card_discount/point/shipping/final_price 정확 분해. 일부 항목 누락 텍스트 → 0/None 처리.
- `compute_final_price`: 주문서값 있으면 `(final, False)`(실결제가), 없으면 `(None or 쿠폰가, True)`(참고가). **AC-2 참고가 강등 경로 검증.**

### 4.2 `tests/test_normalize.py` (정규화)
- `normalize_candidate`: browser모드 `{text,price_guess,link}` → 통일 스키마. api모드 `{title,lprice,...}` → 통일 스키마. price_guess 문자열("39800")이 int로.
- 깨진 입력(빈 dict, link 없음) → 예외 없이 안전 처리(None 채움).

### 4.3 `tests/test_review_parsing.py` (리뷰)
- `parse_review_block`: 별점/날짜/본문 포함 블록 → 정확 추출. 별점 없는 블록 → rating=None.
- `dedup_reviews`: 동일 text 2개 → 1개. 공백차이만 있는 중복 처리.

### 4.4 `tests/test_schema.py` (스키마 검증)
- `build_prices_schema`/`build_reviews_schema`/빌드 출력이 섹션 2 필수키 모두 포함(`validate_schema` 빈 리스트).
- `03_prices.json`이 price-hunter 기대키(`offers[].mall/final_price/confidence/url`, `best`) 보유 검증 — **에이전트 계약 회귀 테스트.**
- `05_final.json`이 best-deal-finder 기대키(`rank[].name/final_price/review_verdict/score/buy_url`, `note`) 보유 검증.
- `score_offer` 단조성: 가격↓일수록, 평점↑일수록 점수↑; verdict=제외 penalty 적용 시 점수 하락.

### 4.5 컴파일 게이트 (AC-7)
모든 신규/수정 py: `python -m py_compile scripts\naver_common.py scripts\naver_parsers.py scripts\naver_product_detail.py scripts\naver_reviews.py scripts\build_final.py`

---

## 5. 위험과 완화

| 위험 | 트리거 | 완화책 (코드 위치) |
|------|--------|--------------------|
| 네이버 셀렉터 변동 | 상세/장바구니/주문서/리뷰 DOM 개편 | 셀렉터를 `SELECTORS` 상수 블록에 집중 + 각 항목 폴백 후보 2~4개 리스트. 매칭 0개 시 `reason:"셀렉터 수선 필요"` 기록(naver_poc.py L161-162 패턴). 셀렉터 변동은 파싱 순수함수에 영향 없음(텍스트만 받으므로 tests 무중단). |
| 봇차단/캡차 | 상세/주문서 진입 시 보안확인 화면 | `detect_block` 매 페이지 호출 → True면 `needs_human:true` 기록 후 **즉시 전체 중단**(우회 금지). 진행된 상품까지만 저장. AC-5. |
| 주문서 진입 실패 | 품절/지역제한/장바구니 담기 실패/세션만료 | `compute_final_price`가 **"참고가" 강등**: 주문서값 없으면 쿠폰가→없으면 표시가, `confidence:"참고가"`, `is_reference:true`. 데이터 흐름은 끊기지 않음(AC-2/AC-6). |
| 장바구니 원상복구 실패 | 삭제 셀렉터 매칭 실패/네트워크 오류 | `try/finally`로 삭제 시도 보장. 실패 시 `cart_cleanup:"failed"` + 콘솔 경고("장바구니 N건 수동 정리 필요") + 03_prices에 기록. 계정 손상 없음(주문 아님). 다음 실행 시작 시 장바구니 잔여 경고. |
| 세션 만료 | 쿠키 만료로 로그인 풀림 | 세션 없거나 로그인페이지 리다이렉트 감지 → `needs_human:"세션 만료, naver_session_save.py 재실행"`. 비번 자동입력 금지. |
| 02_browser_raw 덮어쓰기 | 03/04 스크립트가 각각 씀 | append-merge(기존 product별 병합), 덮어쓰기 금지(1.4). |
| 결제 오클릭 | 셀렉터 오매칭으로 결제 버튼 클릭 | 코드에 결제 클릭 셀렉터 자체를 두지 않음 + 주문서 URL(`order/checkout`)에서 정지. grep로 결제 클릭 부재 확인(6.2). |
| Playwright 1.60 내장 chromium 차단 | launch 실패 | `naver_common.launch_browser`가 `channel="chrome"` 폴백(naver_poc.py L99 검증된 패턴). |

---

## 6. 불변 제약 체크리스트 (구현 완료 게이트)

### 6.1 안전 불변 (모두 PASS여야 완료)
- [ ] **결제 실행 금지**: 전체 코드에 결제/구매확정 버튼 클릭 부재. 진입 상한 = 주문서(order/checkout) URL. (검증: `Select-String -Path scripts\*.py -Pattern "결제하기|paymentBtn|\.pay\("` → 클릭 호출 0건)
- [ ] **캡차/봇차단 우회 금지**: 감지 시 `needs_human` 신호 + 중단. 캡차 입력/우회 코드 부재.
- [ ] **비번/키 출력·하드코딩 금지**: 코드·로그·JSON에 비밀번호/API키 부재. 세션은 쿠키만.
- [ ] **headful 필수**: `launch_browser`에 headless=True 경로 없음. `--headless` 옵션 미제공.
- [ ] **장바구니 원상복구**: 담은 항목 finally 삭제. 실패 시 명시 경고.
- [ ] **naver_poc.py 회귀 금지**: 무수정. `python scripts\naver_poc.py "무선청소기"` 동작 동일.

### 6.2 검증 명령 (PowerShell)
```powershell
# 컴파일
python -m py_compile scripts\naver_common.py scripts\naver_parsers.py scripts\naver_product_detail.py scripts\naver_reviews.py scripts\build_final.py
# 단위테스트 (네트워크 0)
python -m pytest -q
# 결제 클릭 부재 확인 (0건이어야 정상)
Select-String -Path scripts\*.py -Pattern "결제하기|paymentBtn|\.pay\("
# 회귀: PoC 검색 (headful 창 뜸)
python scripts\naver_poc.py "무선청소기"
# E2E (사람 관찰, AC-6) — 순서대로
python scripts\naver_product_detail.py --top 3
python scripts\naver_reviews.py --top 3
python scripts\build_final.py
```

### 6.3 AC 매핑 (완료 정의)
| AC | 충족 산출물 | 검증 |
|----|-------------|------|
| AC-1 | naver_poc.py 무수정 + 01 별칭 | `naver_poc.py "무선청소기"` 봇차단 없이 01 생성 |
| AC-2 | naver_product_detail.py → 03_prices.json | 상위3 상세→쿠폰→장바구니→주문서 최종가, 참고가 표기, cart_cleanup=removed |
| AC-3 | naver_reviews.py → 02/04 | 낮은평점 포함 리뷰 수집 |
| AC-4 | build_final.py → 05_final.json + 별칭 | 점수식, verdict=제외 강등, 에이전트 계약키 일치 |
| AC-5 | detect_block + 결제클릭 부재 | needs_human 신호, grep 0건 |
| AC-6 | 위 스크립트 순차 E2E | 사람 합격 판정 |
| AC-7 | tests/ + py_compile | `pytest` 통과, 컴파일 통과 |

---

## 7. 구현 순서 요약 (executor용 직렬 체크리스트)

1. T0: `naver_common.py`, `naver_parsers.py` 스켈레톤 + 함수 시그니처 확정 → `py_compile`.
2. T1/T2 병렬: 파싱 순수함수 구현 → 즉시 T7 tests 작성·통과(TDD).
3. T3/T4 병렬: 브라우저 스크립트(`SELECTORS` 상수 + 봇차단/세션/폴백은 common 호출).
4. T5: `build_final.py` + 점수함수 tests.
5. T6: 01 별칭 보장(naver_poc.py 무수정 대안), dead link 0 확인(`01_decision_candidates/03_price_compare/05_final_recommendation` 별칭 존재).
6. 게이트: 6.2 명령 전부 → 6.1 체크리스트 전부 PASS → AC 매핑 확인.
7. E2E(AC-6): headful로 "무선청소기" 1회 완주, 사람 합격.

---

## 8. 참고 (구현 시 열어볼 파일)
- `D:\auto_shopper\scripts\naver_poc.py:42-47` — `save()` 재사용
- `D:\auto_shopper\scripts\naver_poc.py:95-113` — 브라우저 폴백 + 세션로드 패턴
- `D:\auto_shopper\scripts\naver_poc.py:122-133` — 봇차단 감지 로직
- `D:\auto_shopper\scripts\naver_poc.py:155` — 가격 정규식 시드
- `D:\auto_shopper\scripts\naver_poc.py:186-202` — 01_candidates 생성(회귀 기준)
- `D:\auto_shopper\scripts\naver_session_save.py:88` — 쿠키만 저장(비번 미저장) 패턴
- `C:\Users\ekth3\.claude\agents\price-hunter.md:21-32` — 03 offers 계약
- `C:\Users\ekth3\.claude\agents\review-risk-analyst.md:24-33` — 04 판정 계약
- `C:\Users\ekth3\.claude\agents\best-deal-finder.md:23-31` — 05 rank 계약
- `C:\Users\ekth3\.claude\agents\browser-agent.md:20` — 01_decision_candidates/02 기대

---

**계획 작성자 노트(아키텍트):** 가장 큰 함정은 **파일명 계약 불일치**(섹션 0.1)다. 스펙은 `03_prices/04_reviews/05_final`을 쓰는데 에이전트는 `03_price_compare/04_review_risk/05_final_recommendation`을 읽는다. Non-Goals가 "에이전트 대규모 개편 금지"이므로 **스크립트가 별칭 복사본을 추가 생성**하는 방향(스펙 정본 + 에이전트 별칭)으로 양립시켰다. 두 번째 함정은 **테스트 가능성**으로, 파싱을 `naver_parsers.py` 순수 모듈로 물리 분리해야 AC-7(네트워크 0 pytest)이 성립한다 — 이게 모듈 구조의 존재 이유다.
