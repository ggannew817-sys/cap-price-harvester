#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""배출권(KAU) 일별 시세 수집 — 금융위 일반상품시세정보 / 배출권시세."""
import os, json, datetime, re
import requests

KEY = os.environ.get("PUBLIC_DATA_KEY", "").strip()
URL = ("https://apis.data.go.kr/1160100/service/GetGeneralProductInfoService"
       "/getCertifiedEmissionReductionPriceInfo")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "prices_daily.json")


def fetch():
    items, page = [], 1
    end = datetime.date.today()
    start = (end - datetime.timedelta(days=400)).strftime("%Y%m%d")
    while True:
        params = {"serviceKey": KEY, "resultType": "json", "numOfRows": 1000,
                  "pageNo": page, "beginBasDt": start, "endBasDt": end.strftime("%Y%m%d")}
        r = requests.get(URL, params=params, timeout=30)
        print(f"HTTP {r.status_code} (page {page})")
        if r.status_code != 200:
            print(r.text[:400]); break
        it = r.json().get("response", {}).get("body", {}).get("items", {})
        it = it.get("item") if isinstance(it, dict) else it
        if isinstance(it, dict): it = [it]
        if not it: break
        if page == 1:
            print("첫 item:", json.dumps(it[0], ensure_ascii=False))
        items += it
        if len(it) < 1000: break
        page += 1
        if page > 50: break
    return items


def main():
    if not KEY:
        print("!! PUBLIC_DATA_KEY 없음"); return
    print("KEY 길이:", len(KEY))
    items = fetch()
    print("총 item:", len(items))
    best = {}  # 날짜 -> (vintage, close)  최신 빈티지 우선
    for it in items:
        nm = str(it.get("itmsNm") or it.get("prdtNm") or "").upper()
        if "KAU" not in nm: continue
        d = str(it.get("basDt") or "")
        clpr = it.get("clpr") or it.get("clsprc") or it.get("tdd_clsprc")
        if not (d and clpr): continue
        m = re.search(r"KAU(\d+)", nm); vint = int(m.group(1)) if m else 0
        iso = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
        try: v = round(float(str(clpr).replace(",", "")))
        except ValueError: continue
        if iso not in best or vint >= best[iso][0]:
            best[iso] = (vint, v)
    kau = {d: v for d, (vint, v) in best.items()}
    print("KAU 일수:", len(kau))
    if kau:
        last = sorted(kau)[-3:]
        print("최근:", {d: kau[d] for d in last})
    data = {"단위": {"KAU": "원/톤", "EUA": "€/톤"}, "주기": "daily",
            "series": {"KAU": kau}, "보간": False,
            "_수집": {"실행": datetime.date.today().isoformat(), "건수": len(kau)}}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("수집 완료:", len(kau), "일 → prices_daily.json")


if __name__ == "__main__":
    main()

