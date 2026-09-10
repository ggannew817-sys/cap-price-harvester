# CAP Intel Harvester — 제도·시장 동향 수집기

배출권거래제 **제도·시장 동향(공개 뉴스/보도자료)**을 RSS로 수집해 `intel_daily.json`을 만든다.
민감 데이터 없음 — 회계·배출 데이터는 CAP 본체(로컬)에만 있고 여기엔 없다.
(cap-price-harvester와 동일한 오프라인망 대응 패턴)

## 소스 (config/sources.yaml 대응)
국내_제도(환경부 보도자료·GIR·법령정보센터), 국내_시장(KRX 배출권시장),
해외(EU-ETS EC·ICAP), 전문(법률신문). RSS 후보 URL을 여러 개 시도해 첫 성공을 사용한다.
**RSS 경로가 정확한지 미확인** — 첫 실행 로그로 확정 필요(아래 진단 참고).

## 배포 (기존 cap-price-harvester Public 레포에 추가)
1. https://github.com/ggannew817-sys/cap-price-harvester 웹 UI에서
   **Add file → Create new file** 로 아래 3개 경로/내용을 그대로 붙여넣기:
   - `fetch_intel.py`
   - `requirements.txt` (내용 없어도 무방, 표준 라이브러리만 사용)
   - `.github/workflows/collect_intel.yml`
2. **Actions → CAP Intel Harvester → Run workflow** 로 수동 첫 실행.
3. 로그 확인 — 소스별로 `[OK]` / `[SKIP]` / `[FAIL]` / `[MISS]` 가 찍힌다.
   - `[MISS]`인 소스는 후보 RSS URL이 다 실패한 것 → 실제 RSS 주소를 확인해 `fetch_intel.py`의
     `candidates` 리스트를 교체해야 한다(브라우저로 해당 기관 사이트에서 RSS 아이콘/링크 확인).
   - 진단만 하려면 워크플로 env에 `DIAG=1`을 추가해 재실행 → 각 URL의 HTTP 상태+본문 일부 출력.
4. 성공하면 `intel_daily.json`이 레포에 커밋됨(+ 아티팩트).

## 로컬 CAP에 반영
```powershell
cd "D:\클로드 코드\CAP\intel-harvester"
.\pull_intel.ps1                     # intel_daily.json 다운로드
copy intel_daily.json "..\cap\data\intel_daily.json"
cd ..\cap
python run.py sync-intel             # intel_cache.json에 병합(기존 수동 항목 유지)
python run.py dashboard 2026-XX      # 대시보드 재생성(정적 빌드라 재생성 필요)
```
`run.py serve`는 파일을 실시간 로드하지 않으므로(단가 API와 달리) **대시보드 재생성이 필요**하다.

## 자동화하려면
단가와 같은 패턴으로 로컬 작업스케줄러에 `pull_intel.ps1`을 등록하고,
VDI 스케줄러에서 `sync-intel` + `dashboard` 재생성을 잇는 배치를 만들면 된다
(price-harvester의 `CAP_단가_갱신.bat` / 작업스케줄러 등록 참고). 지금은 수동 실행 기준으로만 구성.

## 주의
- RSS가 없는 사이트는 계속 `[MISS]`로 남는다 — 그런 소스는 HTML 파싱으로 바꿔야 하는데,
  페이지 구조가 바뀌면 깨지기 쉬우니 우선 RSS 가능한 소스부터 확정하고 나머지는 수동 유지.
- 기존 `intel_cache.json`의 수동 입력 항목(제4차 계획기간 등)은 `sync-intel`이 지우지 않고 유지한다.
