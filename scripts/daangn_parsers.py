# -*- coding: utf-8 -*-
r"""
당근마켓 시세 점검 순수 파싱·판단 모듈 (1단계)

브라우저/네트워크를 절대 import 하지 않는다. 전부 str/dict/list in -> dict/list out.
AC-6(네트워크 없는 단위테스트)의 핵심 타깃. tests 가 이 모듈만 호출하면
네트워크/브라우저 0.

스캐폴딩(parse_price_won 포크·validate_schema·build_*_schema)은 naver_parsers.py 에서
미러링한다. 그러나 classify_condition / compute_price_stats / verdict /
detect_cheap_warnings / parse_search_listings_from_text / filter_listings 같은
판단·분할 로직은 naver 선례가 없는 신규설계(★)다.

스키마·경계 부등호는 계획 §2(시그니처)·§2 경계 부등호 단정 표와 정확히 일치한다.
"""
import re
import statistics

# 가격 정규식 — naver 판 포크 + 당근용 "만원" 표기 확장.
# 콤마/공백 변형 유지("350,000원" / "9800원"), 만원 표기 추가("35만원" / "1.5만원").
_PRICE_WON_RE = re.compile(r"([0-9][0-9,]*)\s*원")
_PRICE_MAN_RE = re.compile(r"(\d+(?:\.\d+)?)\s*만\s*원?")

# 상태 태그 사전 (설계 §3-1). 키워드 -> 정규화 태그.
# 변형 흡수: 대소문자(S급/s급), 공백("풀 박스"->"풀박스").
_STATUS_DICT = {
    "새것": ["미개봉", "미사용", "새상품", "풀박스", "정품박스"],
    "상급": ["s급", "a급", "거의새것", "생활기스"],
    "하자": ["하자", "고장", "파손", "부품용", "잔상", "액정깨짐"],
}
# 확실한 새것 태그(상급과 섞이지 않은 단독일 때만 "새것"으로 승격).
_SURE_NEW_TAGS = ("미개봉", "미사용", "새상품", "풀박스", "정품박스")

# 거래 상태 마커.
_TRADED_MARKERS = ("거래완료", "예약중")

# verdict 경계 비교용 부동소수 관용오차 (median*1.1/median*0.9 정확 경계 포함 보장).
_EPS = 1e-9


def parse_price_won(text):
    """가격 문자열 -> int. 실패 시 None. [당근 확장/포크]

    지원 형식:
      - "350,000원" -> 350000 (천단위 콤마)
      - "9800원"    -> 9800   (콤마 없음)
      - "35만원"    -> 350000 (만원 표기)
      - "1.5만원"   -> 15000  (소수 만원 표기)
    만원 표기를 일반 "원" 표기보다 먼저 본다("35만원"의 "35"만 잡지 않게).
    콤마/공백 변형 유지.
    """
    if not text:
        return None
    # 만원 표기 우선("35만원" -> 350000). 일반 원 패턴보다 먼저.
    m = _PRICE_MAN_RE.search(text)
    if m:
        try:
            return int(round(float(m.group(1)) * 10000))
        except ValueError:
            return None
    m = _PRICE_WON_RE.search(text)
    if not m:
        return None
    digits = m.group(1).replace(",", "")
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def extract_status_tags(text):  # ★ 신규설계
    """사전 기반 상태 태그 추출. 매칭 없으면 [].

    새것군(미개봉/미사용/새상품/풀박스/정품박스), 상급(S급/A급/거의새것/생활기스),
    하자군(하자/고장/파손/부품용/잔상/액정깨짐).

    변형 흡수: 대소문자(S급=s급), 내부 공백("풀 박스"->"풀박스", "S 급"->"S급").
    반환 태그는 사전의 정규형(소문자 키)으로 통일한다.
    """
    if not text:
        return []
    # 공백 제거 + 소문자화로 변형 흡수("풀 박스", "S 급", "s급").
    blob = re.sub(r"\s+", "", str(text)).lower()
    out = []
    for keywords in _STATUS_DICT.values():
        for kw in keywords:
            if kw in blob and kw not in out:
                out.append(kw)
    return out


def classify_condition(tags):  # ★ 신규설계 — 보수적 다운그레이드
    """상태 태그 -> 4등급. 충돌 시 낮은 등급으로(구매자 보호).

    우선순위/규칙(계획 §2):
      - 하자군 태그 하나라도 있으면 "하자" (최우선).
      - 상급 태그가 섞여 있으면 "상급" (확실한 새것 태그와 공존해도 강등).
      - 상급 태그 없이 확실한 새것 태그(미개봉/미사용 등)만 있으면 "새것".
      - 아무 태그 없으면 "보통".
    (등급 과대평가가 구매자에게 더 위험 -> "상급+새것" 동시 출현은 "상급"으로 강등.)
    """
    tags = tags or []
    tagset = set(tags)
    if tagset & set(_STATUS_DICT["하자"]):
        return "하자"
    if tagset & set(_STATUS_DICT["상급"]):
        return "상급"
    if tagset & set(_SURE_NEW_TAGS):
        return "새것"
    return "보통"


def parse_listing(card_text):  # ★ 신규설계
    """카드 텍스트 한 덩어리 -> 매물 dict.

    반환: {"title": str|None, "price": int|None, "tags": list,
           "condition": str, "traded": bool, "link": None}
    - traded: "거래완료"/"예약중" 감지.
    - link 는 수집기가 채운다(여기선 None).
    """
    text = card_text or ""
    tags = extract_status_tags(text)
    return {
        "title": _clean_listing_title(text),
        "price": parse_price_won(text),
        "tags": tags,
        "condition": classify_condition(tags),
        "traded": any(mk in text for mk in _TRADED_MARKERS),
        "link": None,
    }


def _clean_listing_title(raw):
    """카드 텍스트 블록에서 제목 한 줄만 추출 (naver _clean_title 미러).

    카드 blob 은 "에어팟 프로 2세대 S급\n290,000원\n역삼동\n3분 전\n거래완료"
    처럼 여러 줄이 담긴다. 가격/거래마커/동네·시간 줄·광고 라벨을 걷어내고
    첫 상품명 줄을 고른다.
    """
    if not raw:
        return None
    for ln in str(raw).split("\n"):
        ln = ln.strip()
        if not ln:
            continue
        if ln in ("광고", "AD", "ad", "찜", "찜하기", "끌올", "Nego", "네고가능"):
            continue
        if ln in _TRADED_MARKERS:
            continue
        # 가격/숫자만 있는 줄 제외
        if re.fullmatch(r"[\d,]+\s*원?", ln):
            continue
        if re.fullmatch(r"\d+(?:\.\d+)?\s*만\s*원?", ln):
            continue
        if re.fullmatch(r"[\d,]+", ln):
            continue
        # "3분 전" / "2시간 전" / "1일 전" 같은 시간 표기 줄 제외
        if re.fullmatch(r"\d+\s*(?:분|시간|일|주|개월|달|초)\s*전", ln):
            continue
        return ln[:120]
    return None


# 텍스트 폴백 카드 경계 마커 (보조 앵커, R-3): 거래완료/예약중/N분 전/N시간 전/N일 전.
# 가격 미표기 카드(거래완료 등)가 가격 앵커만으로는 누락되므로 함께 쓴다(§4-A).
_CARD_MARKER_RE = re.compile(
    r"(?:거래완료|예약중|판매완료|\d+\s*(?:초|분|시간|일|주|개월|달)\s*전)"
)
# 가격 토큰(1차 앵커): "...원" 또는 "...만원".
_CARD_PRICE_RE = re.compile(r"(?:\d+(?:\.\d+)?\s*만\s*원?|[0-9][0-9,]*\s*원)")


def parse_search_listings_from_text(page_text):  # ★ 신규설계 [B1, naver 선례 無]
    """검색결과 페이지 inner_text blob -> [매물 dict, ...] (셀렉터 0매칭 폴백).

    분할 경계 가설(§4-A):
      - 가격 토큰("...원"/"...만원")을 1차 앵커로 본다(카드당 보통 가격 1개).
      - 가격 미표기 카드(거래완료 등) 누락 방지를 위해 반복 마커
        (거래완료/예약중/N분 전/N시간 전/N일 전)도 보조 경계 앵커로 함께 쓴다(R-3).
      - 두 신호의 위치를 OR 로 모아 카드 경계로 삼고, 각 조각을 parse_listing 에 위임.

    빈/쓰레기 blob -> []. 가격 없는 카드도 누락 말고 price=None 으로 보존.
    (실측 분할 정확도는 §8 T8 검증 대상.)
    """
    if not page_text:
        return []
    text = str(page_text)

    # 가격 앵커 + 마커 앵커의 시작 위치를 모두 모아 카드 경계로 사용.
    anchors = sorted(set(
        [m.start() for m in _CARD_PRICE_RE.finditer(text)]
        + [m.start() for m in _CARD_MARKER_RE.finditer(text)]
    ))
    if not anchors:
        return []

    # 인접 앵커가 같은 카드(가격+마커가 한 카드에 함께)일 수 있으므로,
    # 각 앵커를 카드 "신호점"으로 보되 조각은 직전 신호점 직후 ~ 다음 신호점 직전까지.
    # 첫 카드는 첫 신호점 직전 텍스트(제목)부터 포함되게 0 을 경계 시작에 넣는다.
    bounds = [0] + anchors + [len(text)]
    # 중복/근접 경계 정리: 너무 가까운(같은 카드 내) 앵커는 하나로 합친다.
    seg_starts = []
    last = None
    for b in bounds:
        if last is None or b - last >= 1:
            seg_starts.append(b)
            last = b
    seg_starts = sorted(set(seg_starts))

    listings = []
    for i in range(len(seg_starts) - 1):
        chunk = text[seg_starts[i]:seg_starts[i + 1]]
        if not chunk.strip():
            continue
        # 가격 토큰도 마커도 없는 순수 잡음 조각은 건너뛴다(쓰레기 방지).
        if not (_CARD_PRICE_RE.search(chunk) or _CARD_MARKER_RE.search(chunk)):
            continue
        listing = parse_listing(chunk)
        # 제목·가격·마커가 모두 비어 있으면 카드로 보지 않는다.
        if listing["title"] is None and listing["price"] is None and not listing["traded"]:
            continue
        listings.append(listing)
    return _merge_partial_cards(listings)


def _merge_partial_cards(listings):
    """분할 과정에서 제목만/가격만 떨어진 인접 조각을 한 카드로 합친다.

    가격 앵커와 마커 앵커가 같은 카드를 두 조각으로 쪼갠 경우(제목+가격 조각 다음에
    마커만 있는 조각이 따라오는 식)를 보정한다. 보수적으로: 직전 카드가 가격은 있는데
    제목이 없고, 현재 조각이 제목만 있으면 합치는 식의 단순 병합은 하지 않고,
    "제목 없는 마커-only 조각"을 직전 카드의 traded 신호로만 흡수한다.
    """
    if not listings:
        return []
    merged = []
    for lst in listings:
        is_marker_only = (
            lst["title"] is None and lst["price"] is None and lst["traded"]
        )
        if is_marker_only and merged:
            # 직전 카드에 거래상태만 보강(중복 카드 생성 방지).
            merged[-1]["traded"] = True
            continue
        merged.append(lst)
    return merged


def filter_listings(listings, query):  # ★ 신규설계 [R1/D3 입력정합]
    """입력정합 가드: 검색어 무관 매물·가격 이상치 제거. 통계/판정 전에 적용.

    ① 제목에 query 핵심토큰(공백분리 후 1글자 초과 토큰) 하나도 없으면 제외.
       핵심토큰이 하나도 없는 query(예: 빈 문자열/1글자뿐)면 토큰 필터는 건너뛴다.
    ② 가격 이상치 제거(1차는 전체 median 기준 — 분류 전이라 군 정보 없음):
       price > median*5 (초과) 또는 price < median/5 (미만) 이면 제외.
       경계값(median*5, median/5 정확히 같음)은 보존(>/< 이므로).
       price=None 매물은 이상치 판정에서 제외하지 않고 보존(가격 없는 카드 누락 방지).

    [R-2] 군별 median 정밀화는 §8 후속과제(1차는 전체 median 단순·안전 우선).
    """
    listings = listings or []
    # ① 검색어 토큰 필터
    tokens = [t for t in re.split(r"\s+", (query or "").strip()) if len(t) > 1]
    if tokens:
        kept = []
        for lst in listings:
            title = (lst.get("title") or "")
            tl = title.lower()
            if any(tok.lower() in tl for tok in tokens):
                kept.append(lst)
        listings = kept
    # ② 가격 이상치 필터 (전체 median 기준)
    prices = [lst.get("price") for lst in listings if isinstance(lst.get("price"), int)]
    if len(prices) >= 1:
        med = statistics.median(prices)
        hi = med * 5
        lo = med / 5
        out = []
        for lst in listings:
            p = lst.get("price")
            if isinstance(p, int):
                # 경계값 보존: 초과(>)/미만(<) 만 제거.
                if p > hi or p < lo:
                    continue
            out.append(lst)
        listings = out
    return listings


def _priced_listings(listings):
    """통계 대상 매물만: traded=False 이고 price 가 int 인 것."""
    out = []
    for lst in (listings or []):
        if lst.get("traded"):
            continue
        p = lst.get("price")
        if isinstance(p, int):
            out.append(lst)
    return out


def _percentile(sorted_vals, q):
    """정렬된 값 리스트에서 q(0~1) 백분위 (선형보간). 빈 리스트면 None."""
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    pos = q * (len(sorted_vals) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = pos - lo
    return float(sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * frac)


def compute_price_stats(listings):  # ★ 신규설계 — 소표본 가드
    """상태군별 호가분포 통계. traded/price None 제외. n=0 군 생략.

    각 군: {"n", "min", "median", "max", (n>=8 이면) "p25", "p75"}.
    [B2②] n<8 이면 p25/p75 키 자체를 출력하지 않는다(n>=8 일 때만 추가).
    빈 listings -> 빈 dict (예외 없음).
    """
    by_cond = {}
    for lst in _priced_listings(listings):
        cond = lst.get("condition") or "보통"
        by_cond.setdefault(cond, []).append(lst["price"])
    stats = {}
    for cond, prices in by_cond.items():
        if not prices:
            continue
        sp = sorted(prices)
        n = len(sp)
        entry = {
            "n": n,
            "min": sp[0],
            "median": _to_number(statistics.median(sp)),
            "max": sp[-1],
        }
        if n >= 8:  # 경계: 8 포함 시 분위 출력
            entry["p25"] = _to_number(_percentile(sp, 0.25))
            entry["p75"] = _to_number(_percentile(sp, 0.75))
        stats[cond] = entry
    return stats


def _to_number(val):
    """median/percentile 결과를 가능하면 int 로(정수면 int, 아니면 float)."""
    if val is None:
        return None
    if isinstance(val, float) and val.is_integer():
        return int(val)
    return val


def verdict(target_price, stats):  # ★ 신규설계 — 라벨 통일 + confidence 바인딩
    """타깃 매물 가격 -> 판정 dict (타깃 상태군 분포 기준).

    반환: {"label", "percentile": float|None, "condition", "target_price",
           "confidence"}.

    [라벨 통일 — 모든 n 에서 median 비율 단일 규칙 (B-NEW)]:
      target <= median*0.9 -> "싼편"   (이하 포함, <=)
      target >= median*1.1 -> "비쌈"   (이상 포함, >=)
      그 외(median*0.9 초과 ~ median*1.1 미만) -> "적정"
    표본 1건 차이로 라벨이 역전되는 불연속을 제거한다.

    [percentile — 라벨 결정엔 미사용, 참고정보만]:
      n>=8 이면 백분위(float) 채워 표기, n<8 이면 None.

    [confidence — n 기반]:
      n>=8 "mid" / 3<=n<8 "low" / n<3 label="판정보류" + "low".

    stats 는 {조건: {...}} 전체 또는 단일 군 dict 모두 허용한다. 단일 군으로 보고
    median/n 을 읽는다(타깃 상태군 분포를 호출측이 골라 넘긴다는 계약).
    """
    stats = stats or {}
    cond = stats.get("condition")
    median = stats.get("median")
    n = stats.get("n") or 0

    # n<3 -> 판정보류 (라벨 결정 불가)
    if n < 3 or median is None:
        return {
            "label": "판정보류",
            "percentile": None,
            "condition": cond,
            "target_price": target_price,
            "confidence": "low",
        }

    # 라벨: median 비율 단일 규칙 (모든 n 동일).
    # 부동소수 경계 보정: target/median 비율로 비교해 median*1.1·median*0.9
    # 정확 경계값이 "이상/이하 포함"되도록 한다(median*1.1 가 110.00000001 로
    # 떠서 정수 110 이 비쌈에서 누락되는 부동소수 오차 방지). _EPS 만큼 관용.
    ratio = target_price / median
    if ratio <= 0.9 + _EPS:
        label = "싼편"
    elif ratio >= 1.1 - _EPS:
        label = "비쌈"
    else:
        label = "적정"

    # confidence: n 기반
    confidence = "mid" if n >= 8 else "low"

    # percentile: n>=8 일 때만 참고정보로 (라벨 미사용)
    percentile = None
    if n >= 8:
        sorted_vals = stats.get("_sorted")
        if isinstance(sorted_vals, list) and sorted_vals:
            below = sum(1 for v in sorted_vals if v < target_price)
            percentile = round(below / len(sorted_vals), 4)
        else:
            # 분포 원본이 없으면 min/median/max 로 근사 위치 추정.
            mn = stats.get("min")
            mx = stats.get("max")
            if isinstance(mn, (int, float)) and isinstance(mx, (int, float)) and mx > mn:
                percentile = round(
                    min(1.0, max(0.0, (target_price - mn) / (mx - mn))), 4
                )

    return {
        "label": label,
        "percentile": percentile,
        "condition": cond,
        "target_price": target_price,
        "confidence": confidence,
    }


def detect_cheap_warnings(listings, stats):  # ★ 신규설계 — 수치 규칙 확정
    """비정상적으로 싼 매물 "확인 권장" 경고. 둘 다 미해당이면 [].

    수치 규칙(R2/D5):
      같은 상태군에서
        price < median*0.5 (미만, <)  또는
        (n>=8) price < p25 - 1.5*IQR (미만, <),  IQR = p75 - p25
      이면 경고. 경계값(== median*0.5)은 경고 아님(< 미만).

    stats 는 compute_price_stats 결과({조건: {...}}). traded/price None 제외.
    """
    warnings = []
    stats = stats or {}
    for lst in _priced_listings(listings):
        cond = lst.get("condition") or "보통"
        price = lst["price"]
        s = stats.get(cond)
        if not s:
            continue
        median = s.get("median")
        flagged = False
        if median is not None and price < median * 0.5:
            flagged = True
        if not flagged and s.get("n", 0) >= 8:
            p25 = s.get("p25")
            p75 = s.get("p75")
            if p25 is not None and p75 is not None:
                iqr = p75 - p25
                if price < p25 - 1.5 * iqr:
                    flagged = True
        if flagged:
            warnings.append(
                "시세보다 비정상적으로 싼 매물 1건 — 거래 시 직접 확인 권장"
            )
    return warnings


# 리포트 면책 note (AC-7 회귀 — 호가분포 한계 고정 문구).
_REPORT_NOTE = (
    "당근은 거래완료가 비노출 -> 표시값은 대부분 실거래가 아닌 호가입니다. "
    "판정은 실거래 시세가 아닌 현재 호가 분포 기준 상대 위치이며, "
    "지역·표본 수에 따라 달라질 수 있습니다."
)


def build_listings_schema(query, mode, target, listings, needs_human):
    """01_listings.json 스키마 조립 (설계 §5)."""
    from daangn_common import now  # 지연 import (datetime 의존만)
    return {
        "query": query,
        "mode": mode,
        "ts": now(),
        "target": target,
        "listings": listings or [],
        "needs_human": bool(needs_human),
    }


def build_report_schema(query, mode, verdict_obj, stats_by_condition,
                        cheap_picks, warnings):
    """02_price_report.json 스키마 조립 (설계 §5).

    verdict_obj 에 confidence 포함(B2①). note 에 호가분포 한계 고정.
    """
    from daangn_common import now
    return {
        "query": query,
        "ts": now(),
        "mode": mode,
        "verdict": verdict_obj,
        "stats_by_condition": stats_by_condition or {},
        "cheap_picks": cheap_picks or [],
        "warnings": warnings or [],
        "note": _REPORT_NOTE,
    }


def validate_schema(obj, required_keys):
    """obj 에서 누락된 필수키 리스트 반환. 빈 리스트 = 통과. (naver_parsers 재사용)

    required_keys 항목에 "a.b" 점표기는 obj["a"][0]["b"] 형태의
    리스트 첫 원소 키 검증을 의미한다(listings[].condition 같은 계약 회귀 검증용).
    """
    missing = []
    obj = obj or {}
    for key in (required_keys or []):
        if "." in key:
            parent, child = key.split(".", 1)
            seq = obj.get(parent)
            if not isinstance(seq, list) or not seq:
                missing.append(key)
                continue
            first = seq[0] if isinstance(seq[0], dict) else {}
            if child not in first:
                missing.append(key)
        else:
            if key not in obj:
                missing.append(key)
    return missing
