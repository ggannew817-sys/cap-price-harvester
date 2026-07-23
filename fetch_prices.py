#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""배출권 시세 수집기 (공개데이터 전용) — GitHub Actions에서 실행.

공공데이터포털 「금융위 일반상품시세정보」(data.go.kr, publicDataPk=15094805)에서
KAU/KCU/KOC 일별 종가를 받아 prices_daily.json 을 갱신한다.
※ 민감 데이터(회계·배출) 없음. 이 레포는 공개 시세만 다룬다(weather-harvester와 동일 패턴).

환경변수:
  PUBLIC_DATA_KEY   공공데이터포털 인증키(필수, Actions Secret)
  PRICE_BASE_URL    (선택) 기본 엔드포인트 오버라이드
  START             (선택) 수집 시작일 YYYYMMDD (기본: 최근 400일)

사내망 오프라인에선 실행 불가(문법검증만). Actions(requests 설치)에서 동작.
첫 실행 시 응답 필드명(itmsNm/clpr/basDt)이 실제와 다르면 _parse 매핑만 조정.
"""
import json, os, datetime, sys
try:
    import requests
except ImportError:
    requests = None

BASE = os.environ.get("PRICE_BASE_URL",
                      "https://apis.data.go.kr/1160100/service/GetGeneralProductInfoService/getGeneralProductInfo")
KEY = os.environ.get("PUBLIC_DATA_KEY", "")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "prices_daily.json")
# 배출권 품목 매핑: 응답 itmsNm 에 아래 키워드가 들어가면 해당 시장으로
MARKETS = {"KAU": "KAU"}  # KCU/KOC 필요 시 추가


def _load():
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            return json.load(f)
    return {"단위": {"KAU": "원/톤", "EUA": "€/톤"}, "주기": "daily", "series": {}, "보간": False,
            "_주": "GitHub Actions 자동수집(공공데이터 일반상품시세정보). EUA는 별도(EEX/ICE) 미수집."}


def _fetch(start, end):
    if not requests:
        print("requests 미설치 — Actions에서 실행 필요"); return []
    if not KEY:
        print("PUBLIC_DATA_KEY 미설정 — Actions Secret 등록 필요"); return []
    items, page = [], 1
    while True:
        params = {"serviceKey": KEY, "resultType": "json", "numOfRows": 1000, "pageNo": page,
                  "beginBasDt": start, "endBasDt": end}
        r = requests.get(BASE, params=params, timeout=30)
        r.raise_for_status()
        body = r.json().get("response", {}).get("body", {})
        got = body.get("items", {}).get("item", []) or []
        if isinstance(got, dict):
            got = [got]
        items += got
        if len(got) < 1000:
            break
        page += 1
        if page > 50:
            break
    return items


def _parse(items):
    """응답 → {market: {date: close}}. 필드명은 표준 상품시세(basDt,itmsNm,clpr) 가정."""
    out = {}
    for it in items:
        nm = str(it.get("itmsNm") or it.get("prdlstNm") or "")
        d = str(it.get("basDt") or "")
        clpr = it.get("clpr") or it.get("clsPrc")
        if not (nm and d and clpr):
            continue
        for mk, kw in MARKETS.items():
            if kw in nm.upper():
                iso = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
                try:
                    out.setdefault(mk, {})[iso] = round(float(str(clpr).replace(",", "")))
                except ValueError:
                    pass
    return out


def main():
    end = datetime.date.today()
    start = os.environ.get("START") or (end - datetime.timedelta(days=400)).strftime("%Y%m%d")
    items = _fetch(start, end.strftime("%Y%m%d"))
    fetched = _parse(items)
    data = _load()
    data.setdefault("series", {})
    n = 0
    for mk, series in fetched.items():
        tgt = data["series"].setdefault(mk, {})
        for d, v in series.items():
            tgt[d] = v; n += 1
    data["보간"] = False
    data["_수집"] = {"실행": end.isoformat(), "반영건": n,
                   "market": {k: len(v) for k, v in data["series"].items()}}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"수집 완료: {n}건 반영, market={ {k: len(v) for k,v in data['series'].items()} }")
    if n == 0:
        print("⚠️ 0건 — 인증키/엔드포인트/필드명(_parse) 점검 필요")


if __name__ == "__main__":
    main()
