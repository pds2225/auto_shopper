# -*- coding: utf-8 -*-
r"""
review_risk.py — 리뷰 위험 휴리스틱 판정 (AC-4 폴백)

입력:  _workspace/04_reviews.json
출력:  _workspace/04_review_risk.json

review-risk-analyst(LLM)가 없을 때도 05_final 이 deal-breaker 페널티를
적용하도록, 키워드·저평점 규칙으로 안전/주의/제외/미상을 붙인다.
LLM 판정 파일이 이미 있으면 기본적으로 덮어쓰지 않는다 (--force 로만 교체).

네트워크/브라우저 없음. 순수 파일 처리.
"""
import os
import sys
import json
import argparse

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from naver_common import save, OUT_DIR
from naver_parsers import assess_reviews_document, validate_schema


def _load_json(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[경고] {path} 읽기 실패: {e}")
        return None


def build(reviews_data):
    """04_reviews dict → 04_review_risk dict. 파일 I/O 없음."""
    return assess_reviews_document(reviews_data)


def main(argv=None):
    ap = argparse.ArgumentParser(description="리뷰 위험 휴리스틱 판정 (LLM 폴백)")
    ap.add_argument("--force", action="store_true",
                    help="기존 04_review_risk.json 이 있어도 휴리스틱으로 덮어쓴다")
    args = ap.parse_args(argv)

    reviews_path = os.path.join(OUT_DIR, "04_reviews.json")
    risk_path = os.path.join(OUT_DIR, "04_review_risk.json")

    if not os.path.exists(reviews_path):
        print("[오류] 먼저 naver_reviews.py 실행 (04_reviews.json 없음)")
        return 1

    if os.path.exists(risk_path) and not args.force:
        print("[안내] 04_review_risk.json 이미 있음 — 유지 (--force 로 교체)")
        return 0

    reviews = _load_json(reviews_path)
    if reviews is None:
        print("[오류] 04_reviews.json 을 읽지 못함")
        return 1

    result = build(reviews)
    missing = validate_schema(result, ["products.verdict"])
    if missing and (result.get("products") or []):
        print(f"[오류] 스키마 검증 실패 - 누락 키: {missing}")
        return 1

    path = save(result, "04_review_risk.json")
    print(f"[저장] {path}  (source={result.get('source')})")
    for p in result.get("products") or []:
        title = (p.get("title") or "")[:40]
        print(f"  - {title:<40}  {p.get('verdict')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
