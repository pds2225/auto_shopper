# -*- coding: utf-8 -*-
r"""
run_naver.py — 네이버 쇼핑 파이프라인 단일 진입점

검색어 하나로 01_candidates → 03_prices → 04_reviews → 04_review_risk → 05_final
까지 돌린다. 결제 버튼은 누르지 않는다.

모드:
  (기본)  검색어 주면 naver_poc.py 로 후보를 모은 뒤,
          브라우저 단계(상세·리뷰)를 시도하고 실패하면 참고가로 강등한 채 완주.
  --skip-browser  브라우저는 건너뛰고 표시가(참고가)만으로 05까지.
  --offline       네트워크/브라우저 0. tests/fixtures 후보로 동일 흐름 검증.

사용:
  python scripts/run_naver.py "무선청소기"
  python scripts/run_naver.py "무선청소기" --top 3 --skip-browser
  python scripts/run_naver.py --offline
"""
import os
import sys
import json
import argparse
import subprocess

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_SCRIPTS_DIR)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from naver_common import save_with_alias, save, OUT_DIR, ensure_candidates_alias
from naver_parsers import (
    build_prices_schema,
    build_reviews_schema,
    offers_from_candidates,
    assess_reviews_document,
    validate_schema,
)
import build_final as BF
import review_risk as RR


_FIXTURES = os.path.join(_ROOT, "tests", "fixtures")


def _load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _run_script(script_name, extra_args, check=True):
    """같은 인터프리터로 scripts/<name> 을 실행한다."""
    cmd = [sys.executable, os.path.join(_SCRIPTS_DIR, script_name), *extra_args]
    print(f"[실행] {' '.join(cmd)}")
    return subprocess.run(cmd, check=check)


def build_reference_prices(candidates, top=3):
    """브라우저 없이 01 → 03 (참고가). 순수 + 스키마 조립."""
    query = (candidates or {}).get("query") or "unknown"
    offers = offers_from_candidates(candidates, top=top)
    return build_prices_schema(query, offers)


def build_pipeline_result(candidates, reviews=None, top=3):
    """01 dict + 선택 04 dict → 05 dict. 파일 I/O 없음 (테스트 대상).

    브라우저도 LLM도 없이 참고가 + 휴리스틱 리뷰판정으로 완주한다.
    """
    prices = build_reference_prices(candidates, top=top)
    risk = assess_reviews_document(reviews) if reviews else None
    return {
        "prices": prices,
        "reviews": reviews,
        "risk": risk,
        "final": BF.build(prices, reviews, risk),
    }


def _offline_reviews_for(candidates, top=3):
    """픽스처 리뷰 블록을 후보 상품에 붙인 04_reviews dict."""
    from naver_parsers import parse_review_block, dedup_reviews

    blocks_path = os.path.join(_FIXTURES, "review_blocks.txt")
    raw = ""
    if os.path.exists(blocks_path):
        with open(blocks_path, "r", encoding="utf-8") as f:
            raw = f.read()
    blocks = [b.strip() for b in raw.split("===") if b.strip()]
    parsed = dedup_reviews([parse_review_block(b) for b in blocks])

    products = []
    offers = offers_from_candidates(candidates, top=top)
    for i, offer in enumerate(offers):
        # 1순위 후보는 부정 리뷰를 섞어 제외/주의 경로를 오프라인에서도 검증
        if i == 0:
            reviews = list(parsed) + [{
                "text": "가품 의심됩니다. 환불 거부당했어요.",
                "rating": 1.0,
                "date": None,
            }]
        else:
            reviews = [r for r in parsed if (r.get("rating") or 5) >= 4] or parsed[:1]
        ratings = [r["rating"] for r in reviews if r.get("rating") is not None]
        avg = round(sum(ratings) / len(ratings), 2) if ratings else None
        products.append({
            "rank": offer.get("rank") or (i + 1),
            "title": offer.get("title"),
            "link": offer.get("link"),
            "rating_avg": avg,
            "review_count_seen": len(reviews),
            "reviews": reviews,
        })
    query = (candidates or {}).get("query") or "unknown"
    return build_reviews_schema(query, products)


def run_offline(top=3):
    """네트워크 0 완주. fixtures/candidates_sample.json 사용."""
    cand_path = os.path.join(_FIXTURES, "candidates_sample.json")
    if not os.path.exists(cand_path):
        print(f"[오류] 픽스처 없음: {cand_path}")
        return 1
    candidates = _load_json(cand_path)
    os.makedirs(OUT_DIR, exist_ok=True)
    save(candidates, "01_candidates.json")
    ensure_candidates_alias()

    reviews = _offline_reviews_for(candidates, top=top)
    save(reviews, "04_reviews.json")

    bundle = build_pipeline_result(candidates, reviews, top=top)
    save_with_alias(bundle["prices"], "03_prices.json", ["03_price_compare.json"])
    save(bundle["risk"], "04_review_risk.json")
    missing = validate_schema(bundle["final"], [
        "rank.name", "rank.final_price", "rank.review_verdict",
        "rank.score", "rank.buy_url", "note",
    ])
    if missing:
        print(f"[오류] 05 스키마 누락: {missing}")
        return 1
    paths = save_with_alias(bundle["final"], "05_final.json",
                            ["05_final_recommendation.json"])
    print(f"[offline] {paths[0]}")
    _print_rank(bundle["final"])
    return 0


def run_live(query, top=3, skip_browser=False):
    """실검색. 브라우저는 선택. 실패해도 참고가로 05까지 완주."""
    poc = _run_script("naver_poc.py", [query], check=False)
    if poc.returncode != 0:
        print("[오류] naver_poc.py 실패")
        return poc.returncode or 1

    cands = ensure_candidates_alias()
    if cands is None:
        print("[오류] 01_candidates.json 없음")
        return 1

    used_browser = False
    if not skip_browser:
        detail = _run_script("naver_product_detail.py", ["--top", str(top)], check=False)
        reviews = _run_script("naver_reviews.py", ["--top", str(top)], check=False)
        used_browser = (detail.returncode == 0)
        if detail.returncode != 0:
            print("[안내] 상세 크롤 실패 — 표시가(참고가)로 강등하고 계속")
        if reviews.returncode != 0:
            print("[안내] 리뷰 수집 실패 — 리뷰 없이 계속")

    prices_path = os.path.join(OUT_DIR, "03_prices.json")
    if not os.path.exists(prices_path) or not used_browser:
        prices = build_reference_prices(cands, top=top)
        save_with_alias(prices, "03_prices.json", ["03_price_compare.json"])
        print("[안내] 03_prices 를 참고가로 저장")

    reviews_data = _load_json(os.path.join(OUT_DIR, "04_reviews.json"))
    risk_path = os.path.join(OUT_DIR, "04_review_risk.json")
    if reviews_data is not None and not os.path.exists(risk_path):
        RR.main([])

    prices = _load_json(os.path.join(OUT_DIR, "03_prices.json"))
    risk = _load_json(risk_path)
    if risk is None and reviews_data:
        risk = assess_reviews_document(reviews_data)
        save(risk, "04_review_risk.json")
    if prices is None:
        print("[오류] 03_prices.json 없음")
        return 1
    final = BF.build(prices, reviews_data, risk)
    missing = validate_schema(final, [
        "rank.name", "rank.final_price", "rank.review_verdict",
        "rank.score", "rank.buy_url", "note",
    ])
    if missing:
        print(f"[오류] 05 스키마 누락: {missing}")
        return 1
    paths = save_with_alias(final, "05_final.json", ["05_final_recommendation.json"])
    print(f"[저장] {paths[0]}")
    _print_rank(final)
    return 0


def _print_rank(final):
    print()
    print(f"{'순위':>3}  {'이름':<30}  {'최종가':>8}  {'verdict':<6}  {'score':>6}")
    print("-" * 65)
    for i, item in enumerate((final or {}).get("rank") or [], 1):
        name = (item.get("name") or "")[:30]
        price = item.get("final_price")
        price_s = f"{price:,}원" if isinstance(price, int) else str(price)
        verdict = item.get("review_verdict") or "미상"
        score = item.get("score") or 0.0
        print(f"{i:>3}. {name:<30}  {price_s:>8}  {verdict:<6}  {score:>6.4f}")
    print()
    print(f"[note] {(final or {}).get('note')}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="네이버 쇼핑 파이프라인 단일 실행")
    ap.add_argument("query", nargs="?", help="검색어 ( --offline 이면 생략 가능 )")
    ap.add_argument("--top", type=int, default=3, help="상위 N개 (기본 3)")
    ap.add_argument("--offline", action="store_true",
                    help="네트워크 없이 픽스처로 01→05 완주")
    ap.add_argument("--skip-browser", action="store_true",
                    help="상세/리뷰 브라우저를 건너뛰고 참고가로 완주")
    args = ap.parse_args(argv)

    top = max(1, min(int(args.top), 5))
    if args.offline:
        return run_offline(top=top)
    if not args.query:
        ap.error("검색어가 필요합니다 (또는 --offline)")
    return run_live(args.query, top=top, skip_browser=args.skip_browser) or 0


if __name__ == "__main__":
    sys.exit(main())
