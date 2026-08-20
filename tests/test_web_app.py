# -*- coding: utf-8 -*-
"""웹앱 파일이 폰/한글 요구를 포함하는지 확인 — 네트워크 0."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def test_layout_korean_font_and_phone_viewport():
    layout = (WEB / "app" / "layout.tsx").read_text(encoding="utf-8")
    assert 'lang="ko"' in layout
    assert "Noto_Sans_KR" in layout
    assert "device-width" in layout
    assert "viewportFit" in layout


def test_css_phone_font_stack():
    css = (WEB / "app" / "globals.css").read_text(encoding="utf-8")
    assert "Apple SD Gothic Neo" in css
    assert "Malgun Gothic" in css
    assert "safe-area-inset" in css
    assert "font-size: 16px" in css


def test_pwa_manifest_and_icon():
    manifest = (WEB / "app" / "manifest.ts").read_text(encoding="utf-8")
    assert 'display: "standalone"' in manifest
    assert (WEB / "public" / "icon.svg").exists()


def test_no_pay_click_in_web():
    src = (WEB / "app" / "SearchApp.tsx").read_text(encoding="utf-8")
    assert "결제" in src
    assert "clickPay" not in src
    assert "구매하기 최종" not in src
