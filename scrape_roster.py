#!/usr/bin/env python3
"""Pass 1 (coarse): build the CAS physics-institute researcher roster.

Scrapes official faculty directories of:
  - 物理所 IPhy      (in.iphy.ac.cn list_json.php JSON API)
  - 高能所 IHEP      (ihep.cas.cn/kydw/{yjy,tpyjy}/index_N.html)
  - 理论所 ITP       (itp.cas.cn/rc/{yjtd,ys}/index_N.html)
  - 近物所 IMP       (imp.cas.cn/edu/zsyds/ds/dsyjzx/<center>/<disc>/ channelData)
  - 上海应物所 SINAP (sinap.cas.cn/rcdw/kjgg/ + yjsjynew advisor pages)
  - 精密测量院 APM   (apm.cas.cn/rcdw/{zgj,fgj}/ grouped by research division)

Writes data/roster_coarse.json with one record per person (confidence=coarse).
Polite: small delay between requests.
"""
import json
import re
import ssl
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DATA.mkdir(parents=True, exist_ok=True)

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
HDR = {"User-Agent": "Mozilla/5.0 (faculty-directory research; contact: local)"}

CACHE = HERE / "data" / "raw" / "cache"
CACHE.mkdir(parents=True, exist_ok=True)


def fetch(url, tries=3, cache_key=None):
    """Fetch a URL, cache raw bytes, return decoded text (utf-8)."""
    if cache_key is None:
        cache_key = re.sub(r"[^0-9A-Za-z]", "_", url)[-120:]
    cf = CACHE / f"{cache_key}.txt"
    if cf.exists() and cf.stat().st_size > 100:
        return cf.read_text(encoding="utf-8", errors="replace")
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=HDR)
            with urllib.request.urlopen(req, timeout=40, context=ctx) as r:
                b = r.read()
            m = re.search(rb"charset=[\"']?([\w-]+)", b[:3000], re.I)
            enc = m.group(1).decode() if m else "utf-8"
            if enc.lower() in ("gb2312", "gbk", "gb18030"):
                enc = "gb18030"
            text = b.decode(enc, "replace")
            cf.write_text(text, encoding="utf-8")
            time.sleep(0.5)
            return text
        except Exception as e:  # noqa
            last = e
            time.sleep(1.5 * (i + 1))
    print(f"  FAIL {url}: {repr(last)[:160]}", file=sys.stderr)
    return None


def strip_tags(html):
    html = re.sub(r"(?is)<script.*?</script>", " ", html)
    html = re.sub(r"(?is)<style.*?</style>", " ", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    html = html.replace("&nbsp;", " ").replace("&amp;", "&")
    html = html.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    return re.sub(r"\s+", " ", html).strip()


def slug(s):
    s = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", s).strip("-")
    return s or "x"


recs = []


# ---------------------------------------------------------------- IPhy
def scrape_iphy():
    sections = {"zgjgwry": "正高级", "tpyjy": "特聘研究员", "yjdwfgj": "副高级"}
    for t, label in sections.items():
        j = fetch(f"https://in.iphy.ac.cn/list_json.php?t={t}", cache_key=f"iphy_{t}")
        if not j:
            continue
        # content JSON -> extract <a href="?id=NNN">Name</a>
        try:
            content = json.loads(j).get("content", "")
        except Exception:
            content = j
        for m in re.finditer(r'href="\?id=(\d+)"[^>]*>([^<]+)</a>', content):
            pid, name = m.group(1), m.group(2).strip()
            if not name:
                continue
            recs.append({
                "id": f"iphy-{pid}",
                "name": name,
                "school": "中国科学院物理研究所",
                "department": "",
                "title": label,
                "profile_url": f"https://in.iphy.ac.cn/list_json.php?t={t}&id={pid}",
                "sources": ["http://www.iphy.ac.cn/rcjy/", f"https://in.iphy.ac.cn/list_json.php?t={t}"],
                "confidence": "coarse",
                "verified": False,
                "_detail_kind": "iphy",
                "_detail_arg": {"t": t, "id": pid},
            })
        print(f"  IPhy {label}: {len(recs)} total so far")


# ---------------------------------------------------------------- IHEP
def scrape_ihep():
    for sec, label in [("yjy", "研究员"), ("tpyjy", "特聘青年研究员")]:
        page = 0
        while True:
            url = f"https://ihep.cas.cn/kydw/{sec}/" if page == 0 else f"https://ihep.cas.cn/kydw/{sec}/index_{page}.html"
            t = fetch(url, cache_key=f"ihep_{sec}_{page}")
            if not t:
                break
            rows = re.findall(
                r'<tr>\s*<td[^>]*>\s*<a\s+href="([^"]+)"[^>]*>\s*([^<]+?)\s*</a>.*?</tr>',
                t, re.S)
            added = 0
            for href, name in rows:
                name = strip_tags(name)
                if not name or not re.search(r"[\u4e00-\u9fff]", name):
                    continue
                link = href if href.startswith("http") else ("http://ihep.cas.cn" + href if href.startswith("/") else href)
                recs.append({
                    "id": "ihep-" + slug(name) + "-" + slug(href)[-24:],
                    "name": name,
                    "school": "中国科学院高能物理研究所",
                    "department": "",
                    "title": label,
                    "profile_url": link,
                    "sources": [url],
                    "confidence": "coarse",
                    "verified": False,
                    "_detail_kind": "sourcedb",
                    "_detail_arg": {"url": link},
                })
                added += 1
            print(f"  IHEP {label} page {page}: +{added} (total {len(recs)})")
            if "index_{}.html".format(page + 1) in t or f"index_{page+1}.html" in t:
                page += 1
            else:
                break


# ---------------------------------------------------------------- ITP
def norm_itp_url(href):
    """Normalize ITP relative/absolute profile links to a working URL."""
    if href.startswith("http"):
        u = href.replace("http://www.itp.cas.cn", "https://itp.cas.cn").replace("http://itp.cas.cn", "https://itp.cas.cn")
        return u
    # strip ../ prefixes then map ./sourcedb or sourcedb to /sourcedb
    h = re.sub(r"^(\.\./)+", "", href)
    h = re.sub(r"^\./", "", h)
    if not h.startswith("/"):
        h = "/" + h
    if h.startswith("/rc/sourcedb"):
        h = h[len("/rc"):]
    return "https://itp.cas.cn" + h


def scrape_itp():
    for sec, label in [("yjtd", "研究人员"), ("ys", "院士"),
                       ("jcqn", "杰出青年"), ("rxry", "荣休研究员")]:
        page = 0
        while True:
            url = f"https://itp.cas.cn/rc/{sec}/" if page == 0 else f"https://itp.cas.cn/rc/{sec}/index_{page}.html"
            t = fetch(url, cache_key=f"itp_{sec}_{page}")
            if not t:
                break
            # 研究人员 4-col table: name | position | direction | homepage
            rows = re.findall(
                r'<tr>\s*<td>\s*<a\s+href="([^"]+)"[^>]*>\s*([^<]+?)\s*</a>\s*</td>\s*<td>([^<]*)</td>\s*<td>(.*?)</td>',
                t, re.S)
            seen_links = set()
            added = 0
            if rows:
                for href, name, pos, direction in rows:
                    name = strip_tags(name)
                    if not name or not re.search(r"[\u4e00-\u9fff]", name):
                        continue
                    seen_links.add(href)
                    link = norm_itp_url(href)
                    recs.append({
                        "id": "itp-" + slug(name) + "-" + slug(href)[-20:],
                        "name": name,
                        "school": "中国科学院理论物理研究所",
                        "department": "",
                        "title": strip_tags(pos) or label,
                        "research_directions": [strip_tags(direction)] if strip_tags(direction) else [],
                        "profile_url": link,
                        "sources": [url],
                        "confidence": "coarse",
                        "verified": False,
                        "_detail_kind": "sourcedb",
                        "_detail_arg": {"url": link},
                    })
                    added += 1
            else:
                # generic: any <a href=sourcedb...>Name</a>
                for m in re.finditer(r'<a\s+href="([^"]*sourcedb[^"]+)"[^>]*>\s*(?:<[^>]+>)*\s*([^<]+?)\s*(?:</[^>]+>)*\s*</a>', t, re.S):
                    href, name = m.group(1), strip_tags(m.group(2))
                    if not name or not re.search(r"[\u4e00-\u9fff]", name) or len(name) > 6:
                        continue
                    if href in seen_links:
                        continue
                    seen_links.add(href)
                    link = norm_itp_url(href)
                    recs.append({
                        "id": "itp-" + slug(name) + "-" + slug(href)[-20:],
                        "name": name,
                        "school": "中国科学院理论物理研究所",
                        "department": "",
                        "title": label,
                        "profile_url": link,
                        "sources": [url],
                        "confidence": "coarse",
                        "verified": False,
                        "_detail_kind": "sourcedb",
                        "_detail_arg": {"url": link},
                    })
                    added += 1
            print(f"  ITP {sec} page {page}: +{added} (total {len(recs)})")
            if f"index_{page+1}.html" in t:
                page += 1
            else:
                break


# ---------------------------------------------------------------- IMP
def scrape_imp():
    """IMP advisor hub embeds the whole roster in `var itemData = [...]`."""
    url = "https://imp.cas.cn/edu/zsyds/ds/dsyjzx/"
    t = fetch(url, cache_key="imp_hub")
    if not t:
        return
    m = re.search(r'var\s+itemData\s*=\s*(\[.*?\])\s*;', t, re.S)
    if not m:
        print("  IMP: itemData not found", file=sys.stderr)
        return
    raw = re.sub(r",\s*([\]}])", r"\1", m.group(1))
    try:
        arr = json.loads(raw)
    except Exception as e:
        print(f"  IMP parse error: {repr(e)[:120]}", file=sys.stderr)
        return
    # The flat list repeats a person once per (discipline) they advise in;
    # aggregate disciplines per (name, url).
    people = {}
    for item in arr:
        name = (item.get("name") or "").strip()
        hurl = (item.get("url") or "").strip()
        if not name:
            continue
        if hurl.startswith("//"):
            hurl = "https:" + hurl
        key = (name, hurl)
        rec = people.setdefault(key, {
            "centers": set(), "discs": set(), "tit": set(),
        })
        if (par := (item.get("channelParName") or "").strip()):
            rec["centers"].add(par)
        if (disc := (item.get("channelName") or "").strip()) and disc != par:
            rec["discs"].add(disc)
        if (st := (item.get("subTit") or "").strip()):
            rec["tit"].add(st)
    for (name, hurl), rec in people.items():
        recs.append({
            "id": "imp-" + slug(name) + "-" + slug(hurl)[-16:],
            "name": name,
            "school": "中国科学院近代物理研究所",
            "department": " / ".join(sorted(rec["centers"])),
            "title": " / ".join(sorted(rec["tit"])),
            "research_directions": sorted(rec["discs"]),
            "profile_url": hurl,
            "sources": [url],
            "confidence": "coarse",
            "verified": False,
            "_detail_kind": "ucas",
            "_detail_arg": {"url": hurl},
        })
    print(f"  IMP advisor hub: {len(arr)} entries -> {len(people)} people (total {len(recs)})")


# ---------------------------------------------------------------- SINAP
def scrape_sinap():
    t = fetch("http://www.sinap.cas.cn/rcdw/kjgg/", cache_key="sinap_kjgg")
    if t:
        # names are plain <td x:str="">名字</td> in the roster table
        for m in re.finditer(r'<td[^>]*x:str[^>]*>([^<]+)</td>', t):
            name = m.group(1).strip()
            if not re.search(r"[\u4e00-\u9fff]", name) or len(name) < 2 or len(name) > 8:
                continue
            recs.append({
                "id": "sinap-" + slug(name),
                "name": name,
                "school": "中国科学院上海应用物理研究所",
                "department": "",
                "title": "研究员/正高级",
                "profile_url": "http://www.sinap.cas.cn/rcdw/kjgg/",
                "sources": ["http://www.sinap.cas.cn/rcdw/kjgg/"],
                "confidence": "coarse",
                "verified": False,
                "_detail_kind": "none",
                "_detail_arg": {},
            })
        print(f"  SINAP roster: total {len(recs)}")


# ---------------------------------------------------------------- APM
def scrape_apm():
    for sec, label in [("zgj", "正高级"), ("fgj", "副高级")]:
        t = fetch(f"https://apm.cas.cn/rcdw/{sec}/", cache_key=f"apm_{sec}")
        if not t:
            continue
        # entries: ./<division>/YYYYMM/tYYYYMMDD_ID.html with <b>Name</b>
        for m in re.finditer(r'href="(\./' + sec + r'_[^"]+/t\d{8}_\d+\.html)"[^>]*>\s*<b>([^<]+)</b>', t):
            href, name = m.group(1), m.group(2).strip()
            div = re.match(r"\./(" + sec + r"_[^/]+)/", href)
            recs.append({
                "id": "apm-" + slug(name) + "-" + slug(href)[-20:],
                "name": name,
                "school": "中国科学院精密测量科学与技术创新研究院",
                "department": div.group(1) if div else "",
                "title": label,
                "profile_url": "https://apm.cas.cn/rcdw/" + sec + "/" + href.lstrip("./"),
                "sources": [f"https://apm.cas.cn/rcdw/{sec}/"],
                "confidence": "coarse",
                "verified": False,
                "_detail_kind": "sourcedb",
                "_detail_arg": {"url": "https://apm.cas.cn/rcdw/" + sec + "/" + href.lstrip("./")},
            })
        print(f"  APM {label}: total {len(recs)}")


def main():
    which = sys.argv[1:] or ["iphy", "ihep", "itp", "imp", "sinap", "apm"]
    fns = {
        "iphy": scrape_iphy, "ihep": scrape_ihep, "itp": scrape_itp,
        "imp": scrape_imp, "sinap": scrape_sinap, "apm": scrape_apm,
    }
    for w in which:
        print(f"[{w}]")
        try:
            fns[w]()
        except Exception as e:
            print(f"  ERROR {w}: {repr(e)[:200]}", file=sys.stderr)

    # de-dup by (school, name, profile_url)
    seen = set()
    out = []
    for r in recs:
        key = (r["school"], r["name"], r.get("profile_url", ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)

    (DATA / "roster_coarse.json").write_text(
        json.dumps({"professors": out}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    from collections import Counter
    print("\nBy school:")
    for s, c in Counter(r["school"] for r in out).most_common():
        print(f"  {c:4d}  {s}")
    print(f"\nTotal: {len(out)} -> data/roster_coarse.json")


if __name__ == "__main__":
    main()
