"""CAP intel harvester — public 제도/시장 동향 수집 (RSS 우선, 실패시 스킵).
Runs on GitHub Actions (internet open). Never run on the offline VDI.

Output: intel_daily.json — {"updated": "YYYY-MM-DD", "source": "collected", "items": [...]}
Existing intel_daily.json items are kept if a source fails (no data loss).

DIAG=1 env var: print HTTP status + first 300 chars for every candidate URL, do not write output.
"""
import json
import os
import re
import sys
import datetime
import xml.etree.ElementTree as ET
import urllib.request
import urllib.error
import urllib.parse

OUT_FILE = "intel_daily.json"
TIMEOUT = 15
UA = "Mozilla/5.0 (compatible; CAP-intel-harvester/1.0; +https://github.com/ggannew817-sys/cap-price-harvester)"

# 소스 정의: 각 소스마다 후보 RSS/피드 URL 여러 개 시도 (정확한 경로 미확인 → 첫 성공 사용)
SOURCES = [
    {
        "name": "기후에너지환경부 보도자료",
        "region": "국내",
        "tag": ["제도", "행정"],
        "candidates": [
            "https://me.go.kr/home/web/board/rss.do?menuId=10525&boardMasterId=1",
            "https://www.me.go.kr/home/web/board/rss.do?menuId=10525&boardMasterId=1",
        ],
    },
    {
        "name": "온실가스종합정보센터(GIR)",
        "region": "국내",
        "tag": ["배출량", "통계"],
        "candidates": [
            "https://www.gir.go.kr/home/board/rss.do?menuId=36",
            "https://www.gir.go.kr/rss/board.xml",
        ],
    },
    {
        "name": "국가법령정보센터 - 배출권거래법",
        "region": "국내",
        "tag": ["법령"],
        "law_api": True,   # RSS 없음 -> law.go.kr Open API(OC=test 게스트키)로 수집
    },
    {
        "name": "KRX 배출권시장 시장동향",
        "region": "국내",
        "tag": ["시세", "거래량", "시장"],
        "candidates": [
            "https://ets.krx.co.kr/rss/ets_notice.xml",
        ],
    },
    {
        "name": "법률신문 배출권 뉴스",
        "region": "국내",
        "tag": ["법률", "판례"],
        "candidates": [
            "https://www.lawtimes.co.kr/rss/allArticle.xml",
            "https://www.lawtimes.co.kr/rss/S1N7.xml",
        ],
    },
    {
        "name": "EU ETS (European Commission)",
        "region": "해외",
        "tag": ["EU-ETS", "EUA", "CBAM"],
        "candidates": [
            "https://climate.ec.europa.eu/news-your-voice/news_en.rss",
            "https://ec.europa.eu/commission/presscorner/api/rss?text=emissions+trading",
        ],
    },
    {
        "name": "ICAP (International Carbon Action Partnership)",
        "region": "해외",
        "tag": ["글로벌", "제도동향"],
        "candidates": [
            "https://icapcarbonaction.com/en/rss.xml",
            "https://icapcarbonaction.com/en/feed",
        ],
    },
]

NS_STRIP = re.compile(r"\{[^}]*\}")


def _tag(el):
    return NS_STRIP.sub("", el.tag)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.status, r.read()


def parse_rss(xml_bytes, limit=5):
    """Minimal RSS 2.0 / Atom parser -> list of {title, url, date}."""
    root = ET.fromstring(xml_bytes)
    items = []
    # RSS 2.0: channel/item
    for item in root.iter():
        if _tag(item) not in ("item", "entry"):
            continue
        title = link = date = ""
        for child in item:
            t = _tag(child)
            if t == "title":
                title = (child.text or "").strip()
            elif t == "link":
                link = (child.get("href") or child.text or "").strip()
            elif t in ("pubDate", "published", "updated", "date"):
                date = (child.text or "").strip()
        if title:
            items.append({"title": title, "url": link, "date": date})
        if len(items) >= limit:
            break
    return items


def normalize_date(raw):
    if not raw:
        return "2026"
    if re.fullmatch(r"\d{8}", raw):
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(raw[:len(fmt) + 5], fmt).strftime("%Y-%m-%d")
        except Exception:
            continue
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        return m.group(0)
    return raw[:10] if len(raw) >= 10 else "2026"


LAW_API = "https://www.law.go.kr/DRF/lawSearch.do?OC=test&target=law&query={q}&type=JSON"


def collect_law_api(src, query="배출권거래법", limit=3):
    """국가법령정보센터 Open API (게스트키 OC=test, 무료/무등록). RSS가 없어 API로 대체."""
    url = LAW_API.format(q=urllib.parse.quote(query))
    try:
        status, body = fetch(url)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(f"  [FAIL] {url} -> {e}")
        return None
    if status != 200:
        print(f"  [SKIP] {url} -> HTTP {status}")
        return None
    try:
        data = json.loads(body)
        laws = data.get("LawSearch", {}).get("law", [])
        if isinstance(laws, dict):
            laws = [laws]
    except Exception as e:
        print(f"  [SKIP] {url} -> JSON parse error ({e})")
        return None
    if not laws:
        print(f"  [SKIP] {url} -> 0 results")
        return None
    print(f"  [OK] law.go.kr API -> {len(laws)} laws")
    out = []
    for law in laws[:limit]:
        name = law.get("법령명한글", "").strip()
        promul = law.get("공포일자", "")
        effective = law.get("시행일자", "")
        revision = law.get("제개정구분명", "")
        mst = law.get("법령일련번호", "")
        out.append({
            "date": normalize_date(promul) if promul else "2026",
            "region": src["region"],
            "title": f"{name} — {revision} (공포 {promul}, 시행 {effective})",
            "summary": "",
            "tag": src["tag"],
            "url": f"https://www.law.go.kr/DRF/lawService.do?OC=test&target=law&MST={mst}&type=HTML" if mst else "https://www.law.go.kr",
        })
    return out


def collect_source(src):
    if src.get("law_api"):
        return collect_law_api(src)
    for url in src["candidates"]:
        try:
            status, body = fetch(url)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            print(f"  [FAIL] {url} -> {e}")
            continue
        if status != 200:
            print(f"  [SKIP] {url} -> HTTP {status}")
            continue
        try:
            parsed = parse_rss(body, limit=3)
        except ET.ParseError as e:
            print(f"  [SKIP] {url} -> not valid XML/RSS ({e})")
            continue
        if not parsed:
            print(f"  [SKIP] {url} -> 200 OK but no <item>/<entry> found")
            continue
        print(f"  [OK] {url} -> {len(parsed)} items")
        out = []
        for it in parsed:
            out.append({
                "date": normalize_date(it["date"]),
                "region": src["region"],
                "title": it["title"],
                "summary": "",
                "tag": src["tag"],
                "url": it["url"],
            })
        return out
    print(f"  [MISS] {src['name']} -> no candidate URL worked, source skipped")
    return None


def diag():
    for src in SOURCES:
        print(f"== {src['name']} ==")
        if src.get("law_api"):
            print(f"  (law.go.kr API) {LAW_API.format(q='배출권거래법')}")
            continue
        for url in src["candidates"]:
            try:
                status, body = fetch(url)
                print(f"  {url}\n    HTTP {status} | {body[:300]!r}")
            except Exception as e:
                print(f"  {url}\n    ERROR {e}")


def main():
    if os.environ.get("DIAG") == "1":
        diag()
        return

    existing = {}
    if os.path.exists(OUT_FILE):
        try:
            existing = json.load(open(OUT_FILE, encoding="utf-8"))
        except Exception:
            existing = {}
    existing_items = existing.get("items", [])
    # 소스명(URL) 기준으로 기존 항목 보존(실패한 소스는 이전 값 유지)
    kept_by_source_tag = {}
    for it in existing_items:
        key = tuple(sorted(it.get("tag", [])))
        kept_by_source_tag.setdefault(key, []).append(it)

    all_items = []
    any_success = False
    for src in SOURCES:
        print(f"수집: {src['name']}")
        got = collect_source(src)
        key = tuple(sorted(src["tag"]))
        if got is not None:
            any_success = True
            all_items.extend(got)
        else:
            all_items.extend(kept_by_source_tag.get(key, []))

    if not any_success and existing_items:
        print("모든 소스 실패 — 기존 캐시 그대로 유지 (파일 미변경)")
        return

    result = {
        "updated": datetime.date.today().isoformat(),
        "source": "collected",
        "items": all_items,
    }
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(f"저장 완료: {OUT_FILE} ({len(all_items)}건)")


if __name__ == "__main__":
    sys.exit(main())
