#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""배출권 시세 수집 — 오퍼레이션 자동탐색 + 키 개행 제거 + 파싱/저장."""
import os, json, datetime
import requests

KEY = os.environ.get("PUBLIC_DATA_KEY", "").strip()   # ← 끝 개행/공백 제거
SVC = "https://apis.data.go.kr/1160100/service/GetGeneralProductInfoService"
OPS = ["getEmissionsInfo", "getEmissionInfo", "getEmissionsPriceInfo",
       "getGeneralProduct", "getGoldPriceInfo", "getOilPriceInfo"]
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "prices_daily.json")


def try_op(op, params):
    url = SVC + "/" + op
    try:
        r = requests.get(url, params=params, timeout=30)
        print(f"[{op}] HTTP {r.status_code}")
        if r.status_code != 200:
            print("   ", r.text[:200].replace("\n", " ")); return None
        j = r.json()
        body = j.get("response", {}).get("body", {})
        it = body.get("items", {})
        it = it.get("item") if isinstance(it, dict) else it
        if isinstance(it, dict): it = [it]
        print(f"    items={len(it) if it else 0}")
        if it:
            print("    첫 item:", json.dumps(it[0], ensure_ascii=False)[:300])
            return it
    except Exception as e:
        print(f"[{op}] 실패: {e}")
    return None


def main():
    if not KEY:
        print("!! PUBLIC_DATA_KEY 없음"); return
    print("KEY 길이:", len(KEY))
    end = datetime.date.today()
    start = (end - datetime.timedelta(days=200)).strftime("%Y%m%d")
    params = {"serviceKey": KEY, "resultType": "json", "numOfRows": 1000, "pageNo": 1,
              "beginBasDt": start, "endBasDt": end.strftime("%Y%m%d")}
    items = None
    for op in OPS:
        items = try_op(op, params)
        if items:
            print(">>> 사용 오퍼레이션:", op); break
    if not items:
        print("⚠️ 모든 오퍼레이션 실패 — 위 로그의 HTTP/응답 확인"); return

    # 배출권(KAU) 파싱: 날짜별로 최신 빈티지(KAU숫자 최대) 종가
    import re
    best = {}
    for it in items:
        nm = str(it.get("itmsNm") or "")
        if "KAU" not in nm.upper(): continue
        d = str(it.get("basDt") or ""); clpr = it.get("clpr")
        if not (d and clpr): continue
        m = re.search(r"KAU(\d+)", nm.upper()); vint = int(m.group(1)) if m else 0
        iso = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
        try: v = round(float(str(clpr).replace(",", "")))
        except: continue
        if iso not in best or vint >= best[iso][0]:
            best[iso] = (vint, v)
    kau = {d: v for d, (vint, v) in best.items()}
    print(f"KAU 파싱: {len(kau)}일치")
    if kau:
        sample = sorted(kau)[-3:]
        print("   최근:", {d: kau[d] for d in sample})

    data = {"단위": {"KAU": "원/톤", "EUA": "€/톤"}, "주기": "daily",
            "series": {"KAU": kau}, "보간": False,
            "_수집": {"실행": end.isoformat(), "건수": len(kau)}}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("수집 완료:", len(kau), "일")


if __name__ == "__main__":
    main()

