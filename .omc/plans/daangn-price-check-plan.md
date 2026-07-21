# 당근 가격비교 (시세 점검) — 구현 계획 (ralplan)

> 상태: pending approval (ralplan)
> 작성 2026-06-18. 개정 2026-06-18 (Critic 1차: B1·B2 + R/정합성 7건 / 3회차 최종봉합: B-NEW 라벨통일·R-1 경계부등호·R-2 군별필터·R-3 마커앵커).
> 기반 설계: `.omc/specs/daangn-price-check-design.md` (확정본).
> 임무: 확정 설계를 **구현 가능한 단계별 계획**으로 분해. 새 설계 금지(단, Critic 지적된 판단로직은 test-first 신규설계로 명기).
> 미러링 원본: `scripts/naver_common.py`, `scripts/naver_parsers.py`.

---

## 0. RALPLAN-DR 요약 (리뷰 전 필수)

### Principles (불변 원칙)
1. **순수/부수 분리** — 파싱·판단은 `daangn_parsers`(브라우저·네트워크 무import)에 격리한다. 모든 단위테스트는 이 모듈만 호출 → 네트워크 0 (AC-6).
2. **스캐폴딩은 미러링, 판단로직은 test-first 신규설계** — `parse_price_won`(확장)·`validate_schema`·경로상수·`save`·`detect_block` 같은 **스캐폴딩은 naver_* 에서 미러링**한다. 그러나 `classify_condition`·`compute_price_stats`·`verdict`·`detect_cheap_warnings`·`parse_search_listings_from_text`·`filter_listings` 같은 **판단/분할 로직은 naver에 선례가 없는 신규설계**이므로 **테스트를 먼저 작성(test-first)** 해 계약을 못박은 뒤 구현한다. (정직성: 미러링으로 신뢰를 빌려오지 않는다)
3. **안전 우선, 우회 없음** — 봇차단/로그인유도/지역인증 시 `needs_human`으로 정지. 거래 행동(구매·결제·채팅·문의·찜·연락처·전화·거래) 자동화 코드는 **셀렉터조차 작성하지 않는다** (AC-5).
4. **멈춤 없는 완주** — 셀렉터 0매칭이면 텍스트 폴백, 그래도 0이면 그 단계를 비우고 파이프라인 계속 (AC-4).
5. **시크릿 격리** — `data/daangn_session.json`은 `.gitignore`. 토큰/쿠키 출력·커밋 금지.

### Decision Drivers (top 3)
1. **신뢰도** — 판정의 근거(상태군 분류·호가분포·입력정합)가 틀리면 도구 가치 0(혹은 마이너스). 신규 판단로직은 test-first로 계약을 먼저 고정한다.
2. **재사용 비용 최소화** — 기존 스캐폴딩은 검증·동작 완료. 발명 대신 미러링.
3. **DOM·표본 불확실성 흡수** — 당근 셀렉터 미확정 + 실표본이 흔히 소량(n<8). 텍스트 폴백을 순수함수로 승격하고, 소표본을 예외가 아닌 **정상 경로**로 설계한다.

### Viable Options (>=2)

**옵션 A — 모듈 4분할 미러링 + 판단로직 test-first** (채택)
`daangn_parsers / daangn_common / daangn_collect / build_report` + 세션저장 + 스킬. 스캐폴딩은 미러링, 판단·분할 로직은 순수함수로 격리해 test-first.
- Pros: 순수/부수 분리로 AC-6(네트워크 0) 보장, 텍스트 폴백·판단을 모두 단위테스트로 검증, 셀렉터 격리로 DOM 변화 흡수, 전부 신규 daangn_* 라 동시세션 충돌 0.
- Cons: 파일 6개 보일러플레이트, 신규 판단로직 test-first로 초기 공수 증가(단, 신뢰도 드라이버상 필수 비용).

**옵션 B — 경량 단일 스크립트**
한 파일에 파싱+브라우저+리포트 전부.
- Pros: 착수 빠름.
- Cons: 순수/부수 혼재 → 단위테스트가 브라우저를 끌고 들어와 **AC-6 위반**, 텍스트 폴백·판단로직을 네트워크 없이 검증 불가, 셀렉터·통계 한 파일에 뒤섞여 유지보수 악화. **드라이버 1·3과 정면 충돌 → 기각.**

**선택: 옵션 A.** 옵션 B는 텍스트 폴백·판단로직의 네트워크 0 검증 불가로 무효화.

---

## 1. 구현 단계 (Task) 분해 — 의존 순서대로

> 순서: 판단/파싱 순수모듈(test-first 가능) → 테스트 → 브라우저 헬퍼 → 수집 → 리포트 → 세션 → 스킬 → E2E 실측. T1~T7 네트워크 0으로 완성·검증, T8만 실측 의존.
> **판단·분할 로직은 test-first**: Task2의 해당 테스트를 Task1 구현 전/병행으로 먼저 작성한다.

### Task 1 — `scripts/daangn_parsers.py` (순수 파싱·판단 모듈) — [AC-1, AC-2, AC-4, AC-6, AC-7]
- **대상 파일:** 신규 `scripts/daangn_parsers.py`
- **미러(스캐폴딩):** `naver_parsers.py` 구조 + `validate_schema` 재사용.
- **신규설계(test-first):** 아래 ★ 표시 함수. naver 선례 없음.
- **핵심 함수·책임:**
  - `parse_price_won(text) -> int|None` — **naver 재사용이 아닌 당근용 확장/포크**(R4). 기존 "350,000원" + **만원 표기** `(\d+(?:\.\d+)?)\s*만\s*원?` 추가("35만원"→350000, "1.5만원"→15000). 콤마/공백 변형 유지.
  - ★ `extract_status_tags(text) -> list[str]` — 사전 기반 상태 태그(새것군/상급/하자군, 설계 §3-1). 매칭 없으면 [].
  - ★ `classify_condition(tags) -> str` — 4등급. **충돌 시 보수적 다운그레이드**(R3①): 하자군 있으면 "하자" > (상급 태그 없이 확실한 새것 태그 `미개봉`/`미사용`만) "새것" > 상급 태그가 섞이면 "상급" > 그 외/빈 "보통". 즉 "상급+새것" 동시 출현 → **"상급"으로 강등**(높은 등급 오분류가 구매자에게 더 위험).
  - ★ `parse_listing(card_text) -> dict` — 카드 텍스트 한 덩어리 → `{title, price, tags, condition, traded, link:None}`. traded: "거래완료"/"예약중" 감지. link는 수집기가 채움.
  - ★ `parse_search_listings_from_text(page_text) -> list[dict]` — **[B1 신규설계, naver 선례 없음]** 검색결과 페이지 `inner_text` blob → 매물 dict 리스트. 셀렉터 0매칭 시 순수 폴백. **분할 경계 가설**(T8 이전 문서화, §4-A): 가격 토큰(`...원`)을 1차 앵커로 보되, **[R-3]** 가격 미표기 카드(거래완료 등)가 누락되지 않도록 반복 마커("거래완료"/"예약중"/"N분 전"/"N시간 전"/동네명)도 **보조 경계 앵커**로 함께 사용한다. 각 조각을 `parse_listing`에 위임. (실측 검증은 §8 T8 대상)
  - ★ `filter_listings(listings, query) -> list[dict]` — **[R1/D3 입력정합 가드, 1차 포함]** ① 제목에 검색어 핵심토큰(공백분리 후 1글자 초과 토큰) 하나도 없으면 제외 ② 가격 이상치 제거: **1차는 전체 median 기준** 5배 초과 또는 1/5 미만 제외(`> median*5` 또는 `< median/5`). 통계·판정 전에 적용. **[R-2 결정]** 새것/하자 가격차로 정상 새것 매물이 오제거될 수 있어 **"상태군 분류 후 군별 median 기준 정밀화"는 §8 후속과제로 명기**(1차는 전체 median 유지 — 분류 전 단계라 군 정보가 없어 단순·안전 우선).
  - ★ `compute_price_stats(listings) -> dict` — 상태군별 분포. **소표본 가드(B2②)**: n<8이면 p25/p75 키 자체를 **출력하지 않음**(`min`/`median`/`max`만). traded/price None 매물 제외.
  - ★ `verdict(target_price, stats) -> dict` — 타깃 상태군 분포 → `{label, percentile, condition, target_price, confidence}`. **라벨 통일(B-NEW, Architect 권장#1)**: 싼편/적정/비쌈 라벨은 **모든 n에서 median 비율 규칙 하나로 통일** — `target <= median*0.9` 싼편 / `target >= median*1.1` 비쌈 / 그 외 적정(±10%). 표본 1건 차이로 라벨이 역전되는 불연속을 제거한다. **백분위(percentile)는 n>=8일 때만 부가 참고정보로 채워 표기**(`float`), 라벨 결정에는 사용하지 않는다. n<8이면 `percentile=None`. **confidence(B2①, n 기반 유지)**: n>=8 `"mid"`, 3<=n<8 `"low"`, n<3 `label="판정보류"`+`confidence="low"`. (라벨 체계는 n에 무관, confidence·percentile 표기만 n에 의존)
  - ★ `detect_cheap_warnings(listings, stats) -> list[str]` — **수치 규칙 확정(R2/D5)**: 같은 상태군에서 `price < median*0.5` **또는** (n>=8) `price < p25 - 1.5*IQR`(IQR=p75-p25) 이면 "확인 권장" 경고. 둘 다 미해당이면 경고 없음.
  - `build_listings_schema(query, mode, target, listings, needs_human) -> dict` — 01 스키마(설계 §5).
  - `build_report_schema(query, mode, verdict_obj, stats_by_condition, cheap_picks, warnings) -> dict` — 02 스키마(설계 §5). **verdict 객체에 `confidence` 포함**(B2①). note에 호가분포 한계 고정.
  - `validate_schema(obj, required_keys)` — naver_parsers 재사용.
- **AC 충족:** AC-1(분포), AC-2(판정), AC-4(텍스트 폴백 순수함수 ★`parse_search_listings_from_text`), AC-6/AC-7(순수→테스트·스키마).

### Task 2 — 순수함수 단위테스트 (판단로직 test-first) — [AC-4(단위), AC-6, AC-7]
- **대상 파일:** 신규 `tests/test_daangn_status.py`, `tests/test_daangn_stats.py`, `tests/test_daangn_listing_parse.py`, `tests/test_daangn_text_fallback.py`, `tests/test_daangn_filter.py`, `tests/test_daangn_cheap_warning.py`, `tests/test_daangn_block.py`, `tests/test_daangn_report_note.py`
- **미러:** 기존 `tests/` 패턴(순수함수만, 네트워크 0)
- **핵심 책임:** Task1의 ★ 신규 판단·분할 함수 + Task3의 `detect_block`을 경계 케이스 포함 검증. **판단로직 테스트는 Task1 구현 전/병행으로 먼저 작성(test-first).** 목록은 §3.
- **실행:** `python -m pytest -q` (네트워크/브라우저 0)
- **AC 충족:** AC-4(텍스트 폴백 **단위** 검증 — E2E와 병행), AC-6, AC-7(note 회귀).

### Task 3 — `scripts/daangn_common.py` (브라우저/세션/봇차단 헬퍼) — [AC-3]
- **대상 파일:** 신규 `scripts/daangn_common.py`
- **미러:** `naver_common.py`
- **핵심 함수·책임:**
  - 경로상수: `ROOT`, `OUT_DIR`(=`_workspace`), `SESSION_FILE`(=`data/daangn_session.json`), `SAVED_DIR`(=`_saved`).
  - `now()`, `save(obj, name)`, `save_with_alias(...)` — 동일.
  - `BLOCK_SIGNALS` — 당근 시그널 사전(차단/로그인유도/지역인증 변종). 1차안, T8 보강.
  - `detect_block(body_text, title) -> bool` — **순수함수**(Task2 직접 검증).
  - `human_delay`, `gradual_scroll`.
  - `launch_browser(p)` — **headful 고정**, 시스템 Chrome 폴백.
  - `new_daangn_context(browser)` — UA/locale/viewport + 세션로드.
- **AC 충족:** AC-3, AC-5(헬퍼에 거래 행동 코드 없음).

### Task 4 — `scripts/daangn_collect.py` (수집기) — [AC-1, AC-3, AC-4, AC-5]
- **대상 파일:** 신규 `scripts/daangn_collect.py`
- **미러:** `naver_product_detail.py`(구조), `naver_reviews.py`(텍스트 폴백 호출 패턴)
- **핵심 책임:**
  - CLI: `--url <매물링크>`(link 모드) 또는 `--query "<물건명>"`(search 모드).
  - `SELECTORS` 상수 — 검색결과 카드 / (link) 매물상세. 폴백 후보 2~4개씩, 실측 전 placeholder. 0매칭 → **`parse_search_listings_from_text` 순수 폴백 호출**(B1).
  - link 모드: 상세 진입 → `parse_listing`으로 target 추출 → 그 제목으로 검색 → 카드 수집.
  - search 모드: 물건명으로 검색 → 카드 수집.
  - 각 진입마다 `detect_block` → True면 `needs_human=True` 후 **즉시 중단**(진행분 저장).
  - 출력: `build_listings_schema(...)` → `_workspace/01_listings.json`.
  - **거래 행동 셀렉터·클릭 코드 일절 없음.**
- **AC 충족:** AC-1, AC-3, AC-4, AC-5.

### Task 5 — `scripts/build_report.py` (정합필터·분류·통계·판정·리포트) — [AC-1, AC-2, AC-7]
- **대상 파일:** 신규 `scripts/build_report.py`
- **미러:** `build_final.py`(순수 `build()` + main I/O 분리, `validate_schema` 자가검증)
- **핵심 함수·책임:**
  - `build(listings_obj) -> dict` (순수) — 01 dict → **`filter_listings`(입력정합)** → 매물별 `classify_condition` → `compute_price_stats` → (link 모드면) target에 `verdict`(confidence 포함) → `detect_cheap_warnings`로 `warnings`/`cheap_picks` → 02 구조 반환. **파일 I/O 없음.**
  - `render_markdown(report) -> str` (순수) — 상태군별 분포표(소표본은 분위 생략 표기) + 판정(+confidence) + **호가분포 한계 note 고정 출력**.
  - `main()` — 01 로드 → `build()` → `validate_schema` 자가검증 → `_workspace/02_price_report.json` + `_saved/daangn_<물건명>_<날짜>/report.md` 저장 + 콘솔 요약.
- **AC 충족:** AC-1, AC-2, AC-7.

### Task 6 — `scripts/daangn_session_save.py` (최초 1회 세션 저장)
- **대상 파일:** 신규 `scripts/daangn_session_save.py`
- **미러:** `naver_session_save.py`(URL·파일경로만 당근으로)
- **핵심 책임:** headful 크롬 → 사용자 당근 로그인 + **내 동네 지역 설정** → Enter → `ctx.storage_state(path=data/daangn_session.json)`. **비밀번호 저장·출력 금지**(쿠키만). `data/`는 `.gitignore`.
- **AC 충족:** (안전) AC-3 전제(로그인유도·지역인증 회피용 세션 확보).

### Task 7 — `~/.claude/skills/daangn-price-check/SKILL.md` (오케스트레이션 스킬)
- **대상 파일:** 신규 `C:\Users\ekth3\.claude\skills\daangn-price-check\SKILL.md`
- **미러:** `shopping-concierge` 구조
- **핵심 책임:** 입력 분기(URL→link / 물건명→search) → `daangn_collect` → `build_report` → `needs_human`이면 사람 인계 안내 → 최종 `report.md` 경로·요약. confidence가 low/판정보류면 그 한계를 사용자에게 명시. 트리거: "당근 시세", "당근 얼마", "당근 이 가격 적당해?" 등. **구매·연락 자동화 안내 금지.**
- **AC 충족:** 전 흐름 오케스트레이션. (~/.claude 직접 작성 허용, 동시세션 무관)

### Task 8 — E2E 실측 · 셀렉터·분할경계 확정 — [AC-1~AC-4, AC-7]
- **대상 파일:** Task3·4 `SELECTORS`/`BLOCK_SIGNALS` 갱신, 필요 시 `parse_search_listings_from_text` 분할 경계 정규식 보정.
- **핵심 책임:** 실제 당근에서 search/link 1건씩 + 봇차단·로그인유도 정지 확인 + 셀렉터 0매칭 강제 시 **텍스트 폴백 동작 확인**(단위는 §3에서 이미 검증, E2E는 실 blob 확인) + 지역 범위 관찰. 실 DOM·실 blob 보고 셀렉터·분할 경계 확정. 절차 §4-B.
- **AC 충족:** 전 AC 실측 마무리.

---

## 2. 순수함수 시그니처 초안 (입출력 계약 — 설계 §5 스키마 일치)

```python
# daangn_parsers.py  (브라우저/네트워크 무import)
# ★ = naver 선례 없는 신규설계 → test-first

def parse_price_won(text: str) -> int | None:
    """ [당근 확장/포크] "350,000원"->350000 + "35만원"->350000 + "1.5만원"->15000.
        만원 정규식: (\\d+(?:\\.\\d+)?)\\s*만\\s*원?. 콤마/공백 변형 유지. 실패 None. """

def extract_status_tags(text: str) -> list[str]:  # ★
    """ 사전 기반 상태 태그. 새것군(미개봉/미사용/새상품/풀박스/정품박스),
        상급(S급/A급/거의새것/생활기스), 하자군(하자/고장/파손/부품용/잔상/액정깨짐).
        매칭 없으면 []. """

def classify_condition(tags: list[str]) -> str:  # ★ 보수적 다운그레이드
    """ 우선순위: 하자군 > 새것 > 상급 > 보통, 단 충돌 시 낮은 등급으로.
        - 하자군 태그 하나라도 있으면 "하자".
        - 상급 태그가 섞여 있으면 "상급"(새것 태그와 공존해도 강등).
        - 상급 태그 없이 확실한 새것 태그(미개봉/미사용 등)만 있으면 "새것".
        - 아무 태그 없으면 "보통".
        (구매자 보호: 등급 과대평가가 더 위험 → 충돌 시 낮은 등급) """

def parse_listing(card_text: str) -> dict:  # ★
    """ 카드 텍스트 -> {"title":str|None,"price":int|None,"tags":list,
        "condition":str,"traded":bool,"link":None}.
        traded: "거래완료"/"예약중" 감지. """

def parse_search_listings_from_text(page_text: str) -> list[dict]:  # ★ [B1 신규, naver 선례 無]
    """ 검색결과 inner_text blob -> [parse_listing(...) , ...].
        분할 경계: 가격 토큰(...원) 또는 반복 마커(거래완료/예약중/N분 전/N시간 전/동네명).
        빈/쓰레기 blob -> []. (T8 이전 분할경계 가설 §4-A 문서화) """

def filter_listings(listings: list[dict], query: str) -> list[dict]:  # ★ [R1 입력정합]
    """ ① 제목에 query 핵심토큰(1글자 초과) 하나도 없으면 제외.
        ② 가격 이상치 제거: 전체 median*5 초과 또는 median/5 미만 제외.
        통계/판정 전에 적용. """

def compute_price_stats(listings: list[dict]) -> dict:  # ★ 소표본 가드
    """ 상태군별 {"n","min","median","max", (n>=8이면)"p25","p75"}.
        n<8이면 p25/p75 키 자체를 출력하지 않음. traded/price None 제외. n=0 군 생략. """

def verdict(target_price: int, stats: dict) -> dict:  # ★ 라벨 통일 + confidence 바인딩
    """ {"label":"싼편"|"적정"|"비쌈"|"판정보류","percentile":float|None,
        "condition":str,"target_price":int,"confidence":"low"|"mid"}.
        [라벨 통일 — 모든 n에서 median 비율 단일 규칙 (B-NEW)]:
          target <= median*0.9  -> "싼편"   (이하 포함, <=)
          target >= median*1.1  -> "비쌈"   (이상 포함, >=)
          그 외(median*0.9 초과 ~ median*1.1 미만) -> "적정"
        [percentile — 라벨에 미사용, 참고정보만]:
          n>=8 이면 백분위(float) 채워 표기, n<8 이면 None.
        [confidence — n 기반]:
          n>=8 "mid" / 3<=n<8 "low" / n<3 label="판정보류" + "low". """

def detect_cheap_warnings(listings, stats) -> list[str]:  # ★ 수치 규칙 확정
    """ 같은 상태군에서 price < median*0.5 (미만, <) 또는
        (n>=8) price < p25-1.5*IQR (미만, <) 이면 "확인 권장" 경고. IQR=p75-p25. """

def build_listings_schema(query, mode, target, listings, needs_human) -> dict: ...
def build_report_schema(query, mode, verdict_obj, stats_by_condition,
                        cheap_picks, warnings) -> dict:
    """ verdict_obj에 confidence 포함. note에 호가분포 한계 고정. """
```

```python
# daangn_common.py
def detect_block(body_text: str, title: str) -> bool:
    """ BLOCK_SIGNALS(차단/로그인유도/지역인증) 포함 시 True. 순수. """
```

```python
# build_report.py
def build(listings_obj: dict) -> dict:    # filter_listings -> classify -> stats -> verdict -> 02. 순수.
def render_markdown(report: dict) -> str: # 분포표+판정(confidence)+호가한계 note. 순수.
```

### 경계 부등호 단정 표 (R-1 — 포함/미포함 방향 명문화)
모든 경계 함수의 부등호를 아래대로 고정한다. §3 경계 테스트는 정확히 이 방향(포함/미포함)을 assert한다.

| 함수 | 조건 | 부등호 | 포함 여부 | 결과 |
|---|---|---|---|---|
| `verdict` | `target` vs `median*0.9` | `<=` | **이하 포함** | "싼편" |
| `verdict` | `target` vs `median*1.1` | `>=` | **이상 포함** | "비쌈" |
| `verdict` | 그 사이(0.9 초과 ~ 1.1 미만) | `<` 양끝 | 양끝 미포함 | "적정" |
| `compute_price_stats` | `n` vs `8` (분위 출력) | `>=` | **8 포함** 시 p25/p75 출력 | — |
| `verdict`/`compute_price_stats` | `n` vs `3` (판정보류) | `<` | **3 미만**(0,1,2) 보류 | "판정보류" |
| `verdict` confidence | `n` vs `8` (mid) | `>=` | 8 포함 "mid", 그 미만 "low" | — |
| `detect_cheap_warnings` | `price` vs `median*0.5` | `<` | **미만**(0.5배 정확히 같으면 경고 아님) | "확인 권장" |
| `detect_cheap_warnings` | `price` vs `p25-1.5*IQR` (n>=8) | `<` | **미만** | "확인 권장" |
| `filter_listings` 이상치 | `price` vs `median*5` / `median/5` | `>` / `<` | 초과/미만(경계값은 보존) | 제외 |

> 정확한 경계값(예: `median*0.9`와 같은 값)은 위 표대로 처리: 싼편은 `<=`라 **경계값 포함=싼편**, cheap_warning은 `<`라 **경계값=경고 아님**, filter 이상치는 `>`/`<`라 **경계값=보존**.

### 설계 §5 스키마 보강 (이 개정으로 추가/변경되는 필드)
```jsonc
// 02_price_report.json -> verdict 에 confidence 추가 (B2①)
// percentile 은 n>=8 일 때만 채우고(참고정보), 라벨 결정엔 미사용 (B-NEW)
"verdict": { "label":"비쌈","percentile":0.8,"condition":"상급",
             "target_price":350000, "confidence":"mid" }   // percentile=참고, n<8이면 null
// stats_by_condition 의 각 군: n<8 이면 p25/p75 키 없음 (B2②)
"상급": { "n":5,"min":280000,"median":310000,"max":340000 }  // p25/p75 생략 예시
```

---

## 3. 테스트 케이스 목록 (경계 포함, 네트워크 0)

**test_daangn_status.py** (`extract_status_tags`, `classify_condition`)
- 태그 없음 → `[]` → "보통".
- "미개봉" → "새것". "S급" → "상급".
- **"S급 풀박스"(상급+새것군) → "상급"** (보수적 다운그레이드, R3① — 모호성 제거·결과 단정).
- "거의새것 액정깨짐"(상급+하자군) → "하자"(하자 최우선).
- 대소문자/공백 변형 "s급","풀 박스" 처리.

**test_daangn_stats.py** (`compute_price_stats`, `verdict`)
- 홀수/짝수 n 중앙값 경계.
- **n=7 → p25/p75 키 없음 / n=8 → 분위 표시** (B2③ 통계 출력 경계, 유지).
- **라벨 통일(B-NEW): 모든 n에서 median 비율로 라벨.** 경계 부등호 방향 단정(R-1): `target==median*0.9` → "싼편"(<=, 포함) / `target==median*1.1` → "비쌈"(>=, 포함) / 그 사이 → "적정".
- **불연속 회귀(B-NEW 필수): 동일 분포에서 n=7과 n=8의 `label`이 동일하다** — 표본 1건 차이로 적정↔비쌈 역전 없음을 assert(같은 target_price·같은 median).
- **percentile 표기: n>=8 → percentile=float(참고정보) / n<8 → percentile=None.** (라벨은 두 경우 모두 median 비율로 동일)
- confidence: n>=8 "mid" / 3<=n<8 "low" / n<3 "판정보류"+"low" (n 기반).
- n<3 → label="판정보류".
- 극단값 있어도 median 안정.
- traded/price None 제외 / 빈 listings → 빈 stats(예외 없음).

**test_daangn_listing_parse.py** (`parse_listing`, `parse_price_won`)
- 정상 카드 제목+가격+상태태그.
- 가격 변형: "350,000원", **"35만원"→350000, "1.5만원"→15000**(R3②), 콤마 없는 "9800원".
- "거래완료"/"예약중" → traded=True.
- 가격 줄 없는 카드 → price=None(예외 없음).
- 찜수/광고 라벨 섞인 카드 → 제목만 정제.

**test_daangn_text_fallback.py** (`parse_search_listings_from_text`) — **[B1 신규, AC-4 단위 검증]**
- 멀티카드 blob(2~3개 카드 연결) → N개 dict.
- 쓰레기/빈 blob → `[]`.
- 가격 없는 카드 포함 blob → 해당 카드 price=None(드롭 안 함).
- 거래완료 마커로 카드 경계 분할 확인.

**test_daangn_filter.py** (`filter_listings`) — **[R1/D3 입력정합]**
- 검색어 토큰 없는 매물 제외("에어팟" 검색에 "갤럭시버즈" 제외).
- 가격 이상치(`> median*5` 초과 / `< median/5` 미만) 제외.
- **경계 방향 단정(R-1): `price == median*5` 또는 `== median/5` → 보존**(`>`/`<` 이므로 경계값 미제외).
- 정상 매물 보존 / 빈 입력 → [].

**test_daangn_cheap_warning.py** (`detect_cheap_warnings`) — **[R2/D5, 기존 테스트 0 해소]**
- 같은 군 median*0.5 미만 1건 → 경고 1개.
- IQR 규칙: n>=8에서 p25-1.5*IQR 미만 → 경고.
- 정상가만 있으면 경고 [].
- **경계 방향 단정(R-1): `price == median*0.5` → 경고 아님**(`<` 미만이므로 경계값 미포함).

**test_daangn_block.py** (`detect_block`)
- 정상 텍스트 → False.
- 봇차단("보안 확인","비정상적인 접근") → True.
- 로그인유도("로그인이 필요","로그인 후 이용") → True.
- 지역인증("동네 인증","위치 인증") → True.
- 빈/None → False.

**test_daangn_report_note.py** (`build`, `render_markdown`) — **[AC-7 면책 회귀]**
- `build(...)` 결과 `note` 비어있지 않음(호가분포 한계 문구 포함).
- `render_markdown(...)` 출력에 호가 한계 문구("호가","거래완료가 비노출" 등 핵심어) 포함 assert.

---

## 4. 텍스트 폴백 분할경계 가설 + E2E 검증 절차

### §4-A 분할경계 가설 (T8 이전 문서화 — B1 요구)
`parse_search_listings_from_text`의 카드 경계 후보:
1. **가격 토큰**(1차 앵커) `[0-9][0-9,]*\s*원` 또는 만원 토큰 — 카드당 보통 가격 1개.
2. **반복 상태 마커**(보조 앵커, R-3 필수) — "거래완료" / "예약중" / "N분 전" / "N시간 전" / "N일 전" / 동네명(지역 텍스트). **가격 미표기 카드(거래완료 등)는 가격 앵커만으로는 누락되므로, 마커를 보조 경계로 반드시 함께 사용한다.**
3. 두 신호를 OR로 조합해 조각 분리 → 각 조각을 `parse_listing`에 위임.
> 실제 blob 구조 및 가격없는 카드 분할 정확도는 **T8 실측 검증 대상**(§8 기록). **이 함수는 naver에 선례 없는 신규설계**임을 명기.

### §4-B E2E 검증 절차 (Task 8)
> 전제: headful 고정. `daangn_session_save.py`로 사전 로그인(내 동네 설정 포함).
1. **search 모드** — `python -m scripts.daangn_collect --query "에어팟 프로 2세대"`(또는 `python scripts\daangn_collect.py --query ...`). 검색결과 DOM → 카드 셀렉터 확정. `01_listings.json` N건 → `build_report.py` 분포 확인.
2. **link 모드** — 실제 매물 URL `--url`. target 추출 → 검색 수집 → `verdict` 라벨+confidence 확인.
3. **봇차단/로그인유도** — 차단/비로그인 유발 시 `needs_human=True` 정지, 우회 없음 확인.
4. **텍스트 폴백(실 blob)** — `SELECTORS` 카드 셀렉터를 무효화해 0매칭 강제 → `parse_search_listings_from_text` 폴백으로 수집되는지 확인 → 실 blob으로 §4-A 경계 정규식 보정 → 원복. (단위는 §3에서 이미 검증)
5. **지역 범위** — 결과가 내 동네 한정인지 전국인지 관찰 → 리포트 note·§9 반영.
6. **저장 확인** — 01/02 JSON + `_saved/.../report.md` 생성(AC-7).
> E2E는 실 네트워크/로그인 필요 → 단위(§3)와 분리. 시크릿 출력 금지.

---

## 5. 수용조건 AC-1~7 → Task 매핑표

| AC | 내용 | 충족 Task | 검증 방법 |
|---|---|---|---|
| AC-1 | 물건명 검색 → 상태군별 호가분포 | T1(`compute_price_stats`/`filter_listings`), T4, T5 | 단위(§3 stats/filter) + E2E search |
| AC-2 | 매물 링크 → `싼편/적정/비쌈` 판정 | T1(`verdict`), T4(target), T5 | 단위(§3 stats/verdict) + E2E link |
| AC-3 | 봇차단/로그인유도 시 `needs_human` 정지 | T3(`detect_block`/시그널), T4 | 단위(§3 block) + E2E 차단 |
| AC-4 | 셀렉터 실패 시 텍스트 폴백 완주 | T1(`parse_search_listings_from_text`), T4 | **단위(§3 text_fallback) + E2E 폴백** (B1: E2E only 폐기) |
| AC-5 | 거래 행동 자동화 코드 부재 | T3·T4(셀렉터·클릭 미작성), T7 | 코드 리뷰 grep(§6 토큰 목록) |
| AC-6 | 순수파싱 단위테스트 네트워크 0 통과 | T1(순수), T2(테스트) | `python -m pytest -q` |
| AC-7 | 결과 MD + JSON 저장 + 한계 note | T5(저장/note), T1(`build_report_schema` note) | 단위(§3 report_note) + E2E 저장 |

---

## 6. AC-5 검증 grep 토큰 목록 (재현 가능)

코드 리뷰 시 `daangn_*.py` 전체에서 아래 토큰이 **셀렉터/클릭 코드로 등장하지 않음**을 확인(주석·안내 문구 제외):
```
구매  결제  주문  채팅  대화  문의  찜  관심  연락처  전화  통화  거래하기  보내기  send  buy  pay  chat  contact
```
(`detect_block` 등에서 차단 시그널 **문자열**로만 등장하는 것은 허용 — 버튼 클릭·`.click()` 대상이 아님을 확인.)

---

## 7. 미해결 / 리스크 + 완화책

| 리스크 | 영향 | 완화책 |
|---|---|---|
| **당근 DOM 셀렉터·분할경계 미확정** | 수집 0건 가능 | `SELECTORS` 격리 + 폴백 후보 2~4개 + **`parse_search_listings_from_text` 순수 폴백**(§4-A 경계 가설). 실측(T8) 확정. |
| **소표본(n<8) 흔함** | 분위 불가·판정 약화 | **정상 경로로 설계**: 라벨은 모든 n에서 median 비율 단일 규칙(B-NEW, 불연속 없음) + n<8 분위/percentile 숨김 + confidence="low" + n<3 "판정보류"(§9 명시). |
| **지역 의존성** | 표본·시세 왜곡 | 세션 로그인 시 지역 설정(T6) + T8 범위 관찰 + 리포트 note "지역 한정 시세". |
| **"같은 물건" 식별 정밀도** | 오탐 분포 오염 | **1차에 `filter_listings` 입력정합 가드 포함**(검색어 토큰 + 가격 이상치). 잔여 오탐은 후속 검색어 정규화(§8). |
| **거래완료가 비노출(호가만)** | 실거래 아님 | 호가분포 기준(설계 확정) + 모든 리포트 한계 note 고정(§3 회귀 테스트). |
| **동시세션 git 경합** | 파일 충돌 | 전부 신규 `daangn_*`·신규 테스트만. **기존 naver_* 수정 0.** 스킬은 `~/.claude`(repo 밖). |
| **세션 만료/시크릿 노출** | 로그인유도·유출 | `data/daangn_session.json` `.gitignore`(T6). 토큰/쿠키 출력 금지. 만료 시 재실행 안내. |

---

## 8. 후속(1차 범위 밖) 과제
- 검색어 정규화/동의어 사전("에어팟프로2"="에어팟 프로 2세대") — `filter_listings` 잔여 오탐 시.
- **[R-2] `filter_listings` 이상치 제거의 군별 median 정밀화** — 1차는 전체 median 기준(분류 전 단계라 군 정보 없음). 새것/하자 가격차로 정상 새것 매물이 오제거되는 사례가 관찰되면, 상태군 분류 후 군별 median 기준으로 재필터링하는 2-pass 구조로 정밀화.
- **[R-3] 가격없는 카드(거래완료 등) 분할 정확도 실측** — `parse_search_listings_from_text`의 보조 마커 앵커가 가격 미표기 카드를 실제로 누락 없이 분할하는지 T8 실 blob으로 검증·보정(§4-A·§4-B 4).
- "네고가능" 등 비정형 가격 표기 추가 확장.
- 멀티 지역 비교(내 동네 vs 인접).

---

## 9. 사용자 결정 대기 / 명시 항목

- **소표본은 예외가 아닌 흔한 경로다.** 당근 실표본은 자주 n<8 → `confidence="low"` / `n<3` "판정보류"가 **정상 동작**이지 엣지케이스가 아니다. 리포트·스킬 안내가 이를 솔직히 표기한다(과신 금지). 사용자가 "그래도 추정치라도 달라(라벨 표시)" vs "보류만 명확히" 중 무엇을 선호하는지는 운영하며 조정 — **사용자 결정 대기 1건**.
- **입력정합 필터(R1) 1차 포함 확정.** `filter_listings`(검색어 토큰 + 가격 이상치)를 MVP에 넣는다(오염 입력이면 통계가 정확해도 판정이 틀리므로).
- **본문 채택 확정 항목**: 만원 표기 지원(R3②), classify 충돌 시 상급 강등(R3①), cheap_warning 수치 규칙 median*0.5·IQR(R2/D5), **라벨은 모든 n에서 median 비율 ±10% 단일 규칙(B-NEW — percentile은 n>=8 참고정보만, 라벨 불연속 제거)**, 경계 부등호 방향 단정(R-1, §2 표). 운영 중 임계값(0.9·1.1·0.5·1.5·5배·n=8/3) 튜닝 여지만 남김.

> open-questions: `.omc/plans/open-questions.md` 에 위 결정대기 1건(소표본 추정치 표기 선호)을 기록한다.
