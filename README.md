# auto_shopper

네이버 기반 **쇼핑 대행 하네스**. 제품 추천부터 실제 결제가 최저가, 리뷰 위험 점검, 구매 직전까지 대신 차려줍니다. (결제 버튼만 직접)

당근마켓 **중고 시세 점검**(살 때 싼편/적정/비쌈)도 같은 레포에서 돌아갑니다. 채팅·구매 자동화는 하지 않습니다.

## 휴대폰·어디서나 (웹)

PC 없이 폰 브라우저에서도 씁니다. 한글은 `Noto Sans KR` + 아이폰/안드로이드 시스템 폰트 스택이라 깨지지 않습니다.

```powershell
cd web
npm install
npm run dev
```

같은 와이파이의 휴대폰에서 `http://(컴퓨터IP):3000` 으로 엽니다. 브라우저에서 홈 화면에 추가하면 앱처럼 열립니다.

- 검색 결과가 카드로 나오고, 상품을 누르면 네이버 쇼핑으로 이동합니다.
- `.env`에 `NAVER_CLIENT_SECRET`이 있으면 실검색, 없으면 데모 결과 + 네이버 모바일 검색 링크.
- Vercel에 올릴 때는 **Root Directory = `web`**. 시크릿은 Vercel 환경변수로만 넣으세요.

## 폴더 구조
```
auto_shopper/
├─ web/                        휴대폰·PC용 웹앱 (Next.js)
├─ scripts/
│  ├─ run_naver.py             네이버 파이프라인 단일 실행 (01→05)
│  ├─ naver_poc.py             검색 PoC (01_candidates)
│  ├─ naver_product_detail.py  상세·쿠폰·주문서 직전 실결제가 (03_prices)
│  ├─ naver_reviews.py         리뷰 수집 (04_reviews)
│  ├─ review_risk.py           리뷰 위험 휴리스틱 판정 (04_review_risk)
│  ├─ build_final.py           통합 추천 (05_final)
│  ├─ daangn_collect.py        당근 매물 수집
│  └─ build_report.py          당근 시세 리포트
├─ tests/                      네트워크 없는 단위테스트
├─ _workspace/                 중간 산출물(JSON, 커밋 금지)
├─ data/                       세션 쿠키 (비밀, 커밋 금지)
├─ requirements.txt
├─ .env.example
├─ AGENTS.md                   클라우드 에이전트 안내
└─ TASK.md                     AI 작업지시 (이 파일만)
```

## 설치 (최초 1회)
```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
```

## 한 번에 실행 (권장)
```powershell
# 네트워크 없이 픽스처로 01→05 완주 (테스트·클라우드용)
python scripts\run_naver.py --offline

# 검색만 하고 상세 브라우저는 건너뜀 (표시가=참고가 로 05까지)
python scripts\run_naver.py "무선청소기" --skip-browser

# 실검색 + 상세/리뷰 (headful, 세션 있으면 실결제가)
python scripts\run_naver.py "무선청소기" --top 3
```
결과는 `_workspace/05_final.json` 에 1순위 추천·구매 직전 링크가 저장됩니다. `04_review_risk.json` 이 없으면 리뷰 텍스트 휴리스틱으로 안전/주의/제외를 붙입니다.

## 단계별 실행
```powershell
python scripts\naver_poc.py "무선청소기"
python scripts\naver_product_detail.py --top 3
python scripts\naver_reviews.py --top 3
python scripts\review_risk.py
python scripts\build_final.py
```

브라우저만 / API만:
```powershell
python scripts\naver_poc.py "무선청소기" --mode browser
python scripts\naver_poc.py "무선청소기" --mode api
```

## 당근 시세
```powershell
python scripts\daangn_collect.py --query "에어팟 프로 2세대"
python scripts\build_report.py --min-condition 상급 --on-sale-only --top 5
```

## 테스트
```powershell
python -m pytest -q
```
브라우저·네트워크 없이 파싱/점수/리뷰위험/오프라인 파이프라인만 검증합니다.

## 네이버 API 키(선택, 보조용)
브라우저 모드만 쓸 때는 키 없이도 PoC가 동작합니다. API 모드(`--mode api`)는 Client ID/Secret이 필요합니다.

1. [네이버 개발자센터 앱 등록](https://developers.naver.com/apps/#/register)에서 애플리케이션을 만듭니다.
2. 등록한 앱에서 **검색** API를 사용 설정합니다. (쇼핑 검색 = `search/shop.json` — [쇼핑 검색 API 문서](https://developers.naver.com/docs/serviceapi/search/shopping/shopping.md))
3. [내 애플리케이션 목록](https://developers.naver.com/apps/#/list)에서 **Client Secret**을 복사해 프로젝트 루트의 `.env`에 붙여넣습니다.
   - `NAVER_CLIENT_ID`는 이미 `pds2225`로 설정되어 있습니다.
   - `NAVER_CLIENT_SECRET=` 뒤에 발급받은 Secret만 입력하세요. (소스 코드에 Secret을 넣지 마세요.)
4. `.env`가 없다면 `.env.example`을 복사한 뒤 Secret만 채우면 됩니다.

## 사용 (Claude Code 대화에서)
- "30만원대 가성비 무선청소기 추천해줘" → 추천 + 최저가 + 리뷰
- "다이슨 V12 최저가 찾아줘" → 판매처별 실결제가 + 리뷰 위험 + 구매링크
- "당근에서 에어팟 프로 시세 봐줘" → 호가분포 + 싼편/적정/비쌈

## 안전
- 결제는 자동으로 누르지 않습니다(구매 직전까지). 비밀번호는 저장하지 않습니다(최초 로그인만 사람).
- 봇 차단·캡차가 뜨면 멈추고 사람에게 넘깁니다. 개인용 도구입니다.
- 클라우드 VM에서는 네이버가 로그인 벽을 거는 경우가 많습니다. 그때는 `--offline` 또는 `--skip-browser`를 쓰세요.

## 로드맵
- [x] 1단계: 골격 + 검색 PoC
- [x] 2단계: 상품상세·쿠폰 적용가 캡처
- [x] 3단계: 결제 직전 최종가 + 리뷰 자동수집
- [x] 4단계: 통합 추천(휴리스틱 리뷰위험 폴백 포함)
- [x] 당근 시세 점검 + 조건 최저가 (실측 셀렉터 T8은 사람 세션 필요)
- [x] 휴대폰·어디서나 웹앱 (`web/`)
