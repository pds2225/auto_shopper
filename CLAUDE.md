# auto_shopper — 네이버 쇼핑 대행 하네스

> 하네스 트리거·운영 지침과 변경 이력은 전역 `C:\Users\ekth3\.claude\CLAUDE.md`로 이전됨 (2026-06-08).
> 스킬·에이전트도 사용자 단위 `C:\Users\ekth3\.claude\skills\` · `C:\Users\ekth3\.claude\agents\`에 있어 어느 폴더에서나 자동 트리거·호출된다.
> 쇼핑 데이터는 실행 폴더의 `_workspace/`(상대경로)에 저장. 기존 PoC 데이터: `D:\auto_shopper\_workspace\`.

**트리거:** 쇼핑 검색·추천은 기존 하네스. 휴대폰/웹에서 쓰게 해달라는 요청은 `web/` 앱을 사용·수정하라.

**변경 이력:**
| 날짜 | 변경 내용 | 대상 | 사유 |
|------|----------|------|------|
| 2026-08-20 | 휴대폰·어디서나 웹앱 추가 | web/, scripts/naver_shop_api.py | 아무 데서나(폰 포함) 쓰게 해달라는 요청 |
