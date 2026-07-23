#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""배출권(KAU·KCU·KOC) 일별 시세 + 종목 진단."""
import os, json, datetime, re
import requests

KEY = os.environ.get("PUBLIC_DATA_KEY", "").strip()
URL = ("https://apis.data.go.kr/1160100/service/GetGeneralProductInfoService"
       "/getCertifiedEmissionReductionPriceInfo")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "prices_daily.json")
MK = ("KAU", "KCU", "KOC")


def fetch():
    items, page = [], 1
    end = datetime.date.today()
    start = (end - datetime.timedelta(days=400)).strftime("%Y%m%d")
    while True:
        params = {"serviceKey": KEY, "resultType": "json", "numOfRows": 1000,
                  "pageNo": page, "beginBasDt": start, "endBasDt": end.strftime("%Y%m%d")}
        r = requests.get(URL, params=params, timeout=30)
        if r.status_code != 200:
            print("HTTP", r.status_code, r.text[:300]); break
        it = r.json().get("response", {}).get("body", {}).get("items", {})
        it = it.get("item") if isinstance(it, dict) else it
        if isinstance(it, dict): it = [it]
        if not it: break
        items += it
        if len(it) < 1000: break
        page += 1
        if page > 50: break
    return items


def main():
    if not KEY:
        print("!! PUBLIC_DATA_KEY 없음"); return
    items = fetch()
    print("총 item:", len(items))
    # 진단: 어떤 종목명이 들어오는지
    names = {}
    for it in items:
        nm = str(it.get("itmsNm") or "").upper()
        pre = nm[:3]
        names[pre] = names.get(pre, 0) + 1
    print("종목 접두어별 개수:", names)

    best = {mk: {} for mk in MK}
    for it in items:
        nm = str(it.get("itmsNm") or "").upper()
        d = str(it.get("basDt") or ""); clpr = it.get("clpr")
        if not (d and clpr): continue
        for mk in MK:
            if nm.startswith(mk):
                m = re.search(mk + r"(\d+)", nm); vint = int(m.group(1)) if m else 0
                iso = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
                try: v = round(float(str(clpr).replace(",", "")))
                except ValueError: break
                if iso not in best[mk] or vint >= best[mk][iso][0]:
                    best[mk][iso] = (vint, v)
                break
    series = {mk: {d: v for d, (vt, v) in best[mk].items()} for mk in MK if best[mk]}
    for mk in MK:
        print(f"{mk}: {len(best[mk])}일")
    data = {"단위": {"KAU": "원/톤", "KCU": "원/톤", "KOC": "원/톤", "EUA": "€/톤"},
            "주기": "daily", "series": series, "보간": False,
            "_수집": {"실행": datetime.date.today().isoformat()}}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("수집 완료 → prices_daily.json")


if __name__ == "__main__":
    main()
