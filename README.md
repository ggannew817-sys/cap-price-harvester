# Carbon Price Harvester — CAP용 배출권 시세 수집기

배출권 **공개 시세(KAU 등)**를 공공데이터포털 「금융위 일반상품시세정보」에서 받아
`prices_daily.json`을 만든다. **민감 데이터(회계·배출)는 이 레포에 없다** — CAP 본체는 로컬에만.
(사용량예측모델의 weather-harvester와 동일 패턴: 공개데이터만 GitHub Actions로 수집)

## 배포 (최초 1회)
```bash
cd "D:/클로드 코드/CAP/price-harvester"
git init && git add . && git commit -m "init carbon price harvester"
git branch -M main
git remote add origin https://github.com/<계정>/cap-price-harvester.git   # ← PRIVATE 레포
git push -u origin main
```
그다음 GitHub에서:
1. **Settings → Secrets and variables → Actions → New secret**
   - 이름 `PUBLIC_DATA_KEY`, 값 = 공공데이터포털 인증키
2. **Actions → Carbon Price Harvester → Run workflow** (수동 첫 실행)
3. 성공하면 매일 평일 자동 수집 + `prices_daily.json` 커밋/아티팩트 생성

## 인증키 발급
공공데이터포털(data.go.kr) → "일반상품시세정보"(publicDataPk=15094805) → **활용신청** → 승인 후 인증키 발급.

## 로컬 CAP에 반영
Actions 아티팩트 `prices_daily`(또는 레포의 `prices_daily.json`)를 내려받아
`D:/클로드 코드/CAP/cap/data/prices_daily.json` 에 덮어쓰기 → 대시보드에 실 시세 반영.

## 주의
- 첫 실행에서 0건이면 `fetch_prices.py`의 `_parse` 필드명(itmsNm/clpr/basDt)을 실제 응답에 맞춰 조정.
- EUA(EU-ETS)는 공공데이터에 없음 → EEX/ICE 등 별도 소스 연동 필요(미포함).
- 사내망에서 GitHub 접근이 가능해야 push/Actions 사용 가능.
