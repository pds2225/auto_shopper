# 당근 가격비교 (시세 점검) — 설계 문서

> 작성 2026-06-18. brainstorming(/brainstorming) 결과 확정본. 다음 단계: ralplan 계획 합의 → 구현.
> 기반: 기존 auto_shopper(네이버 쇼핑 대행) 2단계 자산을 미러링한다.

## 1. 목적 / 범위

- **목적:** 당근마켓에서 중고 매물을 **살 때**, "이 가격이 싼편/적정/비쌈"인지 같은 물건 매물들과 비교해 알려주는 **구매자 보호 시세 점검 도구**.
- **배포:** 나만 쓰는 개인 도구. 내 PC에서 돌리는 Python + Claude 스킬. 서버·가입·결제 없음.
- **범위 한정(불변):**
  - 구매 직전(시세 판정)까지만. **구매·채팅·연락처 등 거래 행동 자동화 금지.**
  - 차단/캡차/로그인유도/지역인증 시 우회 금지 → 사람 인계(`needs_human`).
  - 비번·세션토큰 하드코딩/출력/커밋 금지.

## 2. 사용 흐름 (입력 2종, 엔진 1개 공유)

### [A] 매물 링크 점검
1. 당근 매물 URL 입력
2. 매물 페이지에서 제목·가격·상태키워드 추출
3. 그 제목으로 당근 검색 → "같은 물건" 매물 수집
4. 상태 보정 호가분포 계산
5. 타깃 매물 가격이 같은 상태군 분포에서 어느 위치인지 → `싼편/적정/비쌈` 판정

### [B] 물건명 검색
1. 물건명 입력 (예: "에어팟 프로 2세대")
2. 당근 검색 → 매물 수집
3. 상태별 호가분포 + 지금 싼 매물 Top N 리포트

> 두 흐름 모두 내부 엔진은 동일: **물건명 → 매물 수집 → 상태 분류 → 호가분포 통계**. 링크 점검은 여기에 "타깃 매물 위치 판정"만 더한다.

## 3. 핵심 판정 로직 (신뢰도 핵심)

1. **상태 키워드 추출** — 매물 제목·본문에서 사전 기반 태그 추출
   - 새것군: `미개봉`, `미사용`, `새상품`, `풀박스`, `정품박스`
   - 상급: `S급`, `A급`, `거의새것`, `생활기스`
   - 하자군: `하자`, `고장`, `파손`, `부품용`, `잔상`, `액정깨짐`
2. **상태군 분류** — 태그 조합으로 4등급(새것 / 상급 / 보통 / 하자). 키워드 없으면 "보통".
3. **상태군별 호가분포 통계** — 각 군에서 최저·25%·중앙값(median)·75%·최고. 중앙값 기준(극단값 내성).
4. **판정** — (링크 점검 시) 타깃 매물이 속한 상태군 분포에서 백분위 계산 → `싼편(하위 33%)` / `적정(중간)` / `비쌈(상위 33%)`.
5. **부산물 경고** — 같은 상태군 최저가보다 비정상적으로 싼 매물은 "확인 권장" 한 줄. (별도 사기분석 모듈 없음 — 분포에서 자연 도출)

### 한계 (리포트에 명시)
- 당근은 **위치 기반 + 거래완료가 비노출**이라 표시되는 값은 대부분 "팔린 가격"이 아닌 **호가**.
- 따라서 판정은 "실거래 시세"가 아닌 **"현재 호가 분포 기준 상대 위치"**. (사용자 확정: 호가분포 기준이 더 좋음)

## 4. 모듈 구조 (auto_shopper 미러)

| 새 파일 | 미러 원본 | 책임 |
|---|---|---|
| `scripts/daangn_common.py` | naver_common.py | 브라우저 실행(headful, 시스템 Chrome 폴백)·세션로드·봇차단/로그인유도 감지·`save`/`save_with_alias`·경로상수 |
| `scripts/daangn_parsers.py` | naver_parsers.py | **순수 파싱**(브라우저/네트워크 무import): `parse_price_won`(재사용), `extract_status_tags`, `classify_condition`, `parse_listing`, `compute_price_stats`, `verdict`, `build_*_schema`, `validate_schema` |
| `scripts/daangn_collect.py` | naver_product_detail.py / naver_reviews.py | 링크/물건명 → 당근 검색 → 매물카드 inner_text 수집 → `01_listings.json`. 봇차단/로그인유도 시 `needs_human` 정지 |
| `scripts/build_report.py` | build_final.py | `01_listings` → 분류 → 통계 → 판정 → `02_price_report.json` + `_saved/.../report.md` |
| `scripts/daangn_session_save.py` | naver_session_save.py | 최초 1회 로그인 세션 저장(`data/daangn_session.json`) |
| `~/.claude/skills/daangn-price-check/SKILL.md` | shopping-concierge | 오케스트레이션(입력 분기·단계 호출·리포트 안내) |

## 5. 데이터 흐름

- `_workspace/01_listings.json` — 수집된 매물 배열 + (링크 모드면) 타깃 매물
- `_workspace/02_price_report.json` — 상태군별 호가분포 통계 + 판정 결과
- `_saved/daangn_<물건명>_<날짜>/report.md` — 사람용 마크다운 리포트 (재열람용)

### 스키마(초안)
```jsonc
// 01_listings.json
{
  "query": "에어팟 프로 2세대",
  "mode": "link" | "search",
  "ts": "...",
  "target": { "title": "...", "price": 350000, "tags": ["S급"], "condition": "상급", "link": "..." } | null,
  "listings": [
    { "title": "...", "price": 290000, "tags": ["S급","풀박스"], "condition": "상급", "traded": false, "link": "..." }
  ],
  "needs_human": false
}

// 02_price_report.json
{
  "query": "...", "ts": "...", "mode": "link",
  "verdict": { "label": "비쌈", "percentile": 0.8, "condition": "상급", "target_price": 350000 } | null,
  "stats_by_condition": {
    "새것":   { "n": 5, "min": 380000, "p25": 390000, "median": 410000, "p75": 430000, "max": 450000 },
    "상급":   { "n": 9, "min": 280000, "p25": 295000, "median": 310000, "p75": 325000, "max": 340000 },
    "보통":   { "n": 7, "min": 220000, "p25": 235000, "median": 240000, "p75": 255000, "max": 270000 },
    "하자":   { "n": 2, "min": 150000, "p25": 150000, "median": 165000, "p75": 175000, "max": 180000 }
  },
  "cheap_picks": [ { "price": 290000, "condition": "상급", "link": "..." } ],
  "warnings": [ "시세보다 비정상적으로 싼 매물 1건 — 거래 시 직접 확인 권장" ],
  "note": "당근은 거래완료가 비노출 → 호가 분포 기준 상대 위치 판정"
}
```

## 6. 안전 · 에러 처리 (auto_shopper 원칙 승계)

- **headful 필수** — headless 자동접속은 봇차단. 실행은 headful 고정.
- **봇차단/로그인유도/지역인증 감지** → `needs_human=True`로 정지, 우회 시도 없음. (`daangn_common.detect_block` 순수함수 + 당근 시그널 사전)
- **셀렉터 0매칭 폴백** — 매물카드 셀렉터가 0이면 페이지 `inner_text`에서 직접 추출(naver `extract_*_from_text` 패턴). 그래도 0이면 그 단계를 비우고 파이프라인 계속(멈춤 없음).
- **거래 행동 자동화 코드 부재** — 구매/채팅/찜/연락처 클릭 코드를 아예 작성하지 않음.
- **시크릿 보호** — `data/daangn_session.json`은 `.gitignore`. 토큰/쿠키 출력·커밋 금지.

## 7. 테스트 전략 (네트워크 0)

전부 `daangn_parsers` / `daangn_common`의 순수함수만 호출 → 브라우저/네트워크 0.
- `tests/test_daangn_status.py` — 상태 키워드 추출·등급 분류(경계 케이스: 태그 없음→보통, 복합 태그)
- `tests/test_daangn_stats.py` — 호가분포 통계(중앙값/백분위)·판정(싼편/적정/비쌈 경계)
- `tests/test_daangn_listing_parse.py` — 매물카드 텍스트 파싱(가격/제목/거래완료)
- `tests/test_daangn_block.py` — 봇차단/로그인유도 감지 시그널
- 실행: `python -m pytest -q`

## 8. 검증 기준 (수용 조건)

- AC-1: 물건명 검색 시 같은 물건 매물을 모아 상태군별 호가분포를 산출한다.
- AC-2: 매물 링크 입력 시 타깃 매물의 `싼편/적정/비쌈`을 같은 상태군 기준으로 판정한다.
- AC-3: 봇차단/로그인유도 시 우회 없이 `needs_human`으로 정지한다.
- AC-4: 셀렉터 실패 시 텍스트 폴백으로 끝까지 완주(멈춤 없음).
- AC-5: 거래 행동(구매/채팅) 자동화 코드가 존재하지 않는다.
- AC-6: 순수파싱 단위테스트가 네트워크 0으로 통과한다.
- AC-7: 결과가 마크다운 리포트 + JSON으로 `_saved/`·`_workspace/`에 저장된다.

## 9. 미해결 / ralplan에서 확정할 항목

- 당근 웹 실제 DOM 구조(검색 결과 카드·매물 상세 셀렉터) — E2E 실측으로 셀렉터 확정 필요.
- 당근 검색의 지역 의존성 처리(전국 vs 내 동네) — 세션/지역 설정 영향.
- "같은 물건" 식별 정밀도(검색어 정규화·동의어) — 1차는 검색어 그대로, 오탐 많으면 보강.
