# -*- coding: utf-8 -*-
"""결제/구매확정 클릭 코드가 스크립트에 없음을 고정 (AC-5)."""
import os
import re

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
_CLICK_RE = re.compile(r"\.click\s*\(")
_PAY_RE = re.compile(r"결제하기|구매확정|paymentBtn")


def test_no_payment_click_calls():
    offenders = []
    for name in os.listdir(_SCRIPTS):
        if not name.endswith(".py"):
            continue
        path = os.path.join(_SCRIPTS, name)
        with open(path, encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                if line.lstrip().startswith("#"):
                    continue
                if _CLICK_RE.search(line) and _PAY_RE.search(line):
                    offenders.append(f"{name}:{i}:{line.strip()}")
    assert offenders == []
