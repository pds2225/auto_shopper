# auto_shopper

네이버 기반 **쇼핑 대행 하네스**. 제품 추천부터 실제 결제가 최저가, 리뷰 위험 점검, 구매 직전까지 대신 차려줍니다. (결제 버튼만 직접)

## 폴더 구조
```
auto_shopper/
├─ .claude/
│  ├─ agents/    5종 (decision-advisor, browser-agent, price-hunter, review-risk-analyst, best-deal-finder)
│  └─ skills/    5종 (shopping-concierge=총괄, purchase-decision, naver-browser-automation, lowest-price-search, review-risk-scan)
├─ scripts/
│  └─ naver_poc.py   네이버 검색 작동 증명(PoC)
├─ _workspace/   중간 산출물(JSON)
├─ data/         세션 쿠키 등(비밀 정보, 커밋 금지)
├─ requirements.txt
├─ .env.example  네이버 API 키 템플릿(선택)
└─ CLAUDE.md     하네스 포인터
```

## 설치 (최초 1회)
```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
```

## 작동 확인 (PoC)
```powershell
# 네이버쇼핑 검색이 실제로 긁히는지 증명
python scripts\naver_poc.py "무선청소기"

# 브라우저만 / API만
python scripts\naver_poc.py "무선청소기" --mode browser
python scripts\naver_poc.py "무선청소기" --mode api
```
결과는 `_workspace/poc_result.json` 에 저장됩니다.

## 네이버 API 키(선택, 보조용)
브라우저 모드만 쓸 때는 키 없이도 PoC가 동작합니다. API 모드(`--mode api`)는 Client ID/Secret이 필요합니다.

1. [네이버 개발자센터 앱 등록](https://developers.naver.com/apps/#/register)에서 애플리케이션을 만듭니다.
2. 등록한 앱에서 **검색** API를 사용 설정합니다. (쇼핑 검색 = `search/shop.json` — [쇼핑 검색 API 문서](https://developers.naver.com/docs/serviceapi/search/shopping/shopping.md))
3. [내 애플리케이션 목록](https://developers.naver.com/apps/#/list)에서 **Client Secret**을 복사해 프로젝트 루트의 `.env`에 붙여넣습니다.
   - `NAVER_CLIENT_ID`는 이미 `pds2225`로 설정되어 있습니다.
   - `NAVER_CLIENT_SECRET=` 뒤에 발급받은 Secret만 입력하세요. (소스 코드에 Secret을 넣지 마세요.)
4. `.env`가 없다면 `.env.example`을 복사한 뒤 Secret만 채우면 됩니다.
5. PowerShell 환경변수로도 가능:
   ```powershell
   $env:NAVER_CLIENT_ID="pds2225"; $env:NAVER_CLIENT_SECRET="발급받은Secret"
   ```

## 사용 (Claude Code 대화에서)
- "30만원대 가성비 무선청소기 추천해줘" → 추천 + 최저가 + 리뷰
- "다이슨 V12 최저가 찾아줘" → 판매처별 실결제가 + 리뷰 위험 + 구매링크

## 안전
- 결제는 자동으로 누르지 않습니다(구매 직전까지). 비밀번호는 저장하지 않습니다(최초 로그인만 사람).
- 봇 차단·캡차가 뜨면 멈추고 사람에게 넘깁니다. 개인용 도구입니다.

## 로드맵
- [x] 1단계: 골격 + 검색 PoC
- [ ] 2단계: 상품상세·쿠폰 적용가 캡처
- [ ] 3단계: 결제 직전 최종가 + 리뷰 자동수집
- [ ] 4단계: 통합 추천(best-deal-finder) 완성
