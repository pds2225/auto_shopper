# 당근 시세점검 v2 확장: 조건 기반 최저가 N개 — 설계

> 작성 2026-06-19. brainstorming 승인본(사용자: 5개 기본 / A안 이대로 구현).
> 기존 당근 시세점검 도구(`.omc/specs/daangn-price-check-design.md`)의 확장.

## 1. 목적
사용자가 **원하는 조건을 설정**하면, 그 조건을 통과한 매물 중 **가격이 가장 싼 순으로 3~5개**를 추려 보여준다. 기존 `cheap_picks`(상태군 median 대비 상대적으로 싼 Top3)와 달리, **사용자 조건 필터 + 절대 최저가순**이다.

## 2. 조건 항목 (사용자 선택 확정)
- **상태 최소등급(min_condition)**: 새것>상급>보통>하자 순위. "상급" 지정 시 상급·새것 통과(이상).
- **판매중만(on_sale_only)**: 거래완료·예약중(`traded=True`) 제외.
- **키워드 포함(include)**: 제목+태그에 지정 단어가 **모두** 포함(AND).
- **키워드 제외(exclude)**: 제목+태그에 지정 단어가 **하나라도** 있으면 제외(OR).
- **개수(top)**: 기본 5(있는 만큼, 부족하면 그 수만). (가격 상한은 미채택 — 최저가순이라 불필요)

## 3. 접근 (A안)
- `build_report.py` 확장 + `daangn_parsers.py`에 순수함수 2개 추가. 수집(`daangn_collect`)은 그대로.
- 입력: 비개발자는 스킬에 자연어로("에어팟 상급 이상, 케이스 빼고 최저가 5개") → 스킬이 `build_report.py` CLI 인자로 변환.

## 4. 순수함수 시그니처 (daangn_parsers, 네트워크 0)
```
_CONDITION_RANK = {"하자":0, "보통":1, "상급":2, "새것":3}

filter_by_conditions(listings, conditions) -> list
  conditions = {min_condition: str|None, on_sale_only: bool,
                include: [str], exclude: [str]}
  - on_sale_only=True 면 traded 제외
  - min_condition 지정 시 rank(condition) >= rank(min_condition) 만 통과
  - include 모두 포함(AND), exclude 하나라도 포함 시 제외(OR) — 검색 대상 = title + " " + tags
  - 빈 조건이면 전부 통과

select_lowest(listings, n=5) -> list[dict]
  - 살 수 있는 매물만(traded 제외) + price int — 가격 오름차순 n개
  - n 부족 시 있는 만큼. 항목: {price, condition, title, link}
```

## 5. build_report 변경
- `build(listings_obj, conditions=None)`: 기존 흐름(filter_listings→classify→stats→verdict→cheap_picks→warnings) 유지.
  conditions 주어지면: `filter_by_conditions(분류된 listings, conditions)` → `select_lowest(..., top)` → `condition_deals` 생성.
- `build_report_schema(..., condition_deals=None)`: 02_price_report.json에 `condition_deals` 필드 추가.
  ```
  condition_deals = { "conditions": {...echo...}, "matched_count": int, "deals": [{price,condition,title,link}...] }
  ```
- `render_markdown`: condition_deals 있으면 "## 조건 맞는 최저가 N개" 섹션(조건 요약 + 매물 목록).
- `main`: `--min-condition {새것,상급,보통,하자}` `--on-sale-only` `--include`(반복) `--exclude`(반복) `--top N`. 조건 인자가 하나라도 있으면 conditions 조립해 build에 전달.

## 6. 테스트 (test_daangn_deals.py, 네트워크 0)
- filter_by_conditions: on_sale_only(traded 제외)/min_condition(상급→상급·새것, 보통·하자 제외)/include(AND)/exclude(OR)/빈 조건 전부 통과.
- select_lowest: 가격 오름차순 n개 / traded 제외 / price None 제외 / n 부족 시 있는 만큼.

## 7. 수용 기준
- AC-D1: 조건(상태·판매중·키워드) 필터가 정확히 동작(단위테스트).
- AC-D2: 통과 매물을 가격 오름차순 최저가 N개(기본 5)로 반환.
- AC-D3: 리포트(md/json)에 조건 요약 + 최저가 목록 표시.
- AC-D4: 안전 불변 유지(거래행동 코드 없음, 순수함수 네트워크 0).
