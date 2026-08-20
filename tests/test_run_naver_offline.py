# -*- coding: utf-8 -*-
"""run_naver 오프라인 파이프라인 (네트워크 0)."""
import json
import os

import run_naver as RN
import naver_parsers as P


def _candidates():
    path = os.path.join(os.path.dirname(__file__), "fixtures", "candidates_sample.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_offers_from_candidates_skips_broken():
    cands = _candidates()
    offers = P.offers_from_candidates(cands, top=5)
    assert len(offers) == 3  # rank 4 빈 dict 제외
    assert all(o.get("confidence") == "참고가" for o in offers)
    assert all(o.get("is_reference") is True for o in offers)


def test_offline_pipeline_ranks_exclude_last():
    cands = _candidates()
    reviews = RN._offline_reviews_for(cands, top=3)
    bundle = RN.build_pipeline_result(cands, reviews, top=3)
    final = bundle["final"]
    assert P.validate_schema(final, [
        "rank.name", "rank.final_price", "rank.review_verdict",
        "rank.score", "rank.buy_url", "note",
    ]) == []
    assert len(final["rank"]) >= 2
    # 1번 후보(최저 참고가)에 가품 리뷰를 붙였으므로 1순위가 되면 안 된다
    cheapest_title = P.normalize_candidate(cands["items"][0])["title"]
    assert final["rank"][0]["name"] != cheapest_title
    by_name = {r["name"]: r for r in final["rank"]}
    assert by_name[cheapest_title]["review_verdict"] == "제외"


def test_run_offline_writes_05(tmp_path, monkeypatch):
    monkeypatch.setattr(RN, "OUT_DIR", str(tmp_path))
    import naver_common as C
    import review_risk as RR
    monkeypatch.setattr(C, "OUT_DIR", str(tmp_path))
    monkeypatch.setattr(RR, "OUT_DIR", str(tmp_path))
    # save() uses naver_common.OUT_DIR
    rc = RN.run_offline(top=3)
    assert rc == 0
    assert os.path.exists(os.path.join(str(tmp_path), "05_final.json"))
    assert os.path.exists(os.path.join(str(tmp_path), "01_candidates.json"))
    assert os.path.exists(os.path.join(str(tmp_path), "04_review_risk.json"))
    with open(os.path.join(str(tmp_path), "05_final.json"), encoding="utf-8") as f:
        data = json.load(f)
    assert data["rank"]
    assert data["rank"][0]["review_verdict"] != "제외"
