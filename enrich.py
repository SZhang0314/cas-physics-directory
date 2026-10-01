#!/usr/bin/env python3
"""Pass 2 (fine): enrich the coarse CAS physics roster.

For each record with a profile URL, fetch the detail page and extract:
subject, research_directions, focus_areas, summary, email, homepage,
publications. Promotes records to confidence=fine when enrichment succeeds.

Detail kinds:
  iphy     -> in.iphy.ac.cn JSON (bio, 主要研究方向, 代表性论文, email, homepage)
  sourcedb -> CAS 专家人才库 / APM sourcedb pages (研究方向, 简历, 代表论著, email)
  ucas     -> people.ucas.ac.cn personal homepages (招生方向, 电子邮件, 教育背景)
  none     -> no detail page (SINAP) - leave coarse

Resumable: caches detail text under data/raw/detail/.
"""
import html as htmllib
import json
import re
import ssl
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DETAIL = DATA / "raw" / "detail"
DETAIL.mkdir(parents=True, exist_ok=True)

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
HDR = {"User-Agent": "Mozilla/5.0 (faculty-directory research; contact: local)"}


def fetch(url, tries=3):
    key = re.sub(r"[^0-9A-Za-z]", "_", url)[-140:]
    cf = DETAIL / f"{key}.txt"
    if cf.exists() and cf.stat().st_size > 40:
        return cf.read_text(encoding="utf-8", errors="replace")
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=HDR)
            with urllib.request.urlopen(req, timeout=45, context=ctx) as r:
                b = r.read()
            m = re.search(rb"charset=[\"']?([\w-]+)", b[:3000], re.I)
            enc = m.group(1).decode() if m else "utf-8"
            if enc.lower() in ("gb2312", "gbk"):
                enc = "gb18030"
            text = b.decode(enc, "replace")
            cf.write_text(text, encoding="utf-8")
            time.sleep(0.35)
            return text
        except Exception as e:  # noqa
            last = e
            time.sleep(1.2 * (i + 1))
    print(f"  FAIL {url}: {repr(last)[:120]}", file=sys.stderr)
    return None


def strip_tags(html):
    html = re.sub(r"(?is)<script.*?</script>", " ", html)
    html = re.sub(r"(?is)<style.*?</style>", " ", html)
    html = re.sub(r"(?s)<br\s*/?>", "\n", html)
    html = re.sub(r"(?s)</p>", "\n", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    html = htmllib.unescape(html)
    return re.sub(r"[ \t\r\f\v]+", " ", html)


def strip_tags_flat(html):
    return re.sub(r"\s+", " ", strip_tags(html)).strip()


EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def clean_email(em, name):
    if not em:
        return ""
    em = em.strip().strip(".,;")
    bad = ("example", "ihep@ihep", "cas.cn\"", "xxx")
    if any(b in em.lower() for b in bad):
        return ""
    return em


def section(text, start_kw, end_kws, after=None):
    """Extract text from start_kw to the nearest following end keyword.

    If `after` is given, only search at/after that offset (skips nav boilerplate).
    """
    i = text.find(start_kw, after or 0)
    if i < 0:
        return ""
    j = len(text)
    for ek in end_kws:
        k = text.find(ek, i + len(start_kw))
        if k >= 0:
            j = min(j, k)
    return text[i + len(start_kw):j].strip(" \n:：|")


def anchor(text, markers=("姓名", "简介", "个人简介")):
    """Return offset of the person content block (skips site nav)."""
    best = 0
    for mk in markers:
        idxs = [m.start() for m in re.finditer(mk, text)]
        if idxs:
            best = max(best, idxs[-1] if len(idxs) > 1 else idxs[0])
    return best


def split_dirs(text, limit=6):
    text = re.sub(r"\s+", " ", text).strip(" .;；")
    if not text:
        return []
    parts = re.split(r"[；;，,、]\s*", text)
    out = []
    for p in parts:
        p = p.strip(" 。.;；")
        if 1 < len(p) <= 40:
            out.append(p)
    return out[:limit]


# ------------------------------------------------------------------ IPhy
def enrich_iphy(rec, t):
    if not t:
        return
    try:
        content = json.loads(t).get("content", "")
    except Exception:
        content = t
    flat_ml = re.sub(r"[ \t]+", " ", strip_tags(content))
    flat = re.sub(r"\s+", " ", flat_ml)
    # person block starts at the name heading
    a = 0
    nm = re.search(r"([\u4e00-\u9fff]{2,4})\s*简介", flat)
    if nm:
        a = nm.start()
    rd = section(flat, "主要研究方向",
                 ["过去的主要工作", "目前的研究课题", "代表性论文", "培养研究生", "其他联系方式", "简历"], after=a)
    if not rd:
        rd = section(flat, "研究方向",
                     ["过去的主要工作", "目前的研究课题", "代表性论文", "培养研究生", "其他联系方式"], after=a)
    pi = flat_ml.rfind("代表性论文")
    pubs = ""
    if pi >= 0:
        rest = flat_ml[pi + len("代表性论文"):]
        for ek in ["目前的研究课题", "培养研究生", "其他联系方式", "简历", "主要研究方向"]:
            k = rest.find(ek)
            if k >= 0:
                rest = rest[:k]
        pubs = rest.strip(" \n:：|及专利")
    bios = section(flat, "简介",
                   ["主要研究方向", "过去的主要工作", "代表性论文", "目前的研究课题"], after=a)
    if not bios and nm:
        bios = flat[nm.end():nm.end() + 500]
    em = clean_email(EMAIL_RE.search(content).group(0) if EMAIL_RE.search(content) else "", rec["name"])
    hp = ""
    om = re.search(r"其他联系方式.{0,200}?href=\"(https?://[^\"]+)\"", content, re.S)
    if om and "iphy.ac.cn" not in om.group(1) and "javascript" not in om.group(1):
        hp = om.group(1)
    dirs = split_dirs(rd)
    if dirs:
        rec["research_directions"] = dirs
    if bios:
        rec["summary"] = re.sub(r"\s+", " ", bios).strip()[:400]
    if pubs:
        rec["publications"] = parse_pubs(pubs)[:5]
    if em:
        rec["email"] = em
    if hp:
        rec["homepage"] = hp
    rec["_enriched"] = bool(dirs or bios or em)


# ------------------------------------------------------------------ sourcedb
def enrich_sourcedb(rec, t):
    if not t:
        return
    flat_ml = re.sub(r"[ \t]+", " ", strip_tags(t))  # keeps newlines
    flat = re.sub(r"\s+", " ", flat_ml)
    # Content block: use the LAST occurrence of key markers to skip site nav.
    def last_pos(kw):
        idxs = [m.start() for m in re.finditer(kw, flat)]
        return idxs[-1] if idxs else -1
    # content starts at 姓名, else at the last 研究方向/简介
    a = max(last_pos("姓名"), 0)
    if a == 0:
        a = max(last_pos("研究方向"), last_pos("简介"), 0)
    END = ["代表论著", "承担科研项目", "社会任职", "获奖", "专利", "专利申请", "Email", "电子邮件",
           "通讯地址", "地址", "学历", "电话", "邮编", "个人简介", "简历"]
    rd = section(flat, "研究方向", END, after=max(a, 0))
    if not rd:
        rd = section(flat, "研究领域", END, after=max(a, 0))
    # bio: prefer 简历/个人简介; else prose between 简介 and 研究方向
    bios = section(flat, "简历", ["研究方向", "代表论著", "承担科研项目", "研究领域", "社会任职"], after=a)
    if not bios:
        bios = section(flat, "个人简介", ["研究方向", "代表论著", "承担科研项目", "研究领域"], after=a)
    if not bios:
        # IHEP style: 简介 <bio> 代表论著
        bios = section(flat, "简介", ["研究方向", "代表论著", "承担科研项目", "社会任职", "地址", "专利"], after=a)
    if not bios:
        # APM style: prose between the contact fields and 研究方向
        m = re.search(r"(?:通讯地址|所属部门|电子邮件|电话)[：:][^。]{0,120}?(?:。|)\s*(.{40,600}?)研究方向", flat)
        if m:
            bios = m.group(1)
    pi = flat_ml.rfind("代表论著")
    pubs = ""
    if pi >= 0:
        rest = flat_ml[pi + len("代表论著"):]
        for ek in ["承担科研项目", "社会任职", "获奖", "专利", "研究方向", "简历", "研究领域", "Email", "地址"]:
            k = rest.find(ek)
            if k >= 0:
                rest = rest[:k]
        pubs = rest.strip(" \n:：|")
    em = clean_email(EMAIL_RE.search(t).group(0) if EMAIL_RE.search(t) else "", rec["name"])
    # title: 职称/岗位 (avoid grabbing from nav)
    m = re.search(r"(?:职称|岗位)[:：]\s*([^\s\n，。]{2,20})", flat[a:] if a else flat)
    if m and not rec.get("title"):
        rec["title"] = m.group(1).strip()
    hp = ""
    for mm in re.finditer(r'href="(https?://[^"]+)"', t):
        u = mm.group(1)
        if any(s in u for s in ("cas.cn/", "javascript", "beian", "miit", ".css", ".js", "icon", "cas.cn\"")):
            continue
        if "people.ucas" in u or "homepage" in u or "group" in u:
            hp = u
            break
    dirs = split_dirs(rd)
    if dirs:
        rec["research_directions"] = dirs
    if bios:
        s = re.sub(r"\s+", " ", bios).strip()
        if len(s) > 20:
            rec["summary"] = s[:400]
    if pubs:
        rec["publications"] = parse_pubs(pubs)[:5]
    if em:
        rec["email"] = em
    if hp:
        rec["homepage"] = hp
    rec["_enriched"] = bool(dirs or rec.get("summary") or em)


# ------------------------------------------------------------------ UCAS
def enrich_ucas(rec, t):
    if not t:
        return
    flat = re.sub(r"[ \t]+", " ", strip_tags(t))
    a = anchor(flat, ("招生信息", "招生方向", "个人简介", "基本信息"))
    rd = section(flat, "招生方向",
                 ["教育背景", "工作经历", "个人简介", "研究领域", "教授课程", "指导学生", "基本信息"], after=a)
    if not rd:
        rd = section(flat, "研究领域",
                     ["教育背景", "工作经历", "个人简介", "招生方向", "教授课程"], after=a)
    bios = section(flat, "个人简介",
                   ["教育背景", "工作经历", "研究领域", "招生方向", "教授课程", "指导学生"], after=a)
    if not bios:
        bios = section(flat, "工作经历",
                       ["教育背景", "研究领域", "教授课程", "指导学生", "招生方向"], after=a)
    em = clean_email(EMAIL_RE.search(t).group(0) if EMAIL_RE.search(t) else "", rec["name"])
    dirs = split_dirs(rd)
    if dirs:
        rec["research_directions"] = dirs
    if bios:
        s = re.sub(r"\s+", " ", bios).strip()
        if len(s) > 20:
            rec["summary"] = s[:400]
    if em:
        rec["email"] = em
    rec["_enriched"] = bool(dirs or rec.get("summary") or em)


def parse_pubs(text):
    """Split a publications blob into entries.

    Only split on explicit list markers ([1], 1., (1), 1、) or hard line breaks;
    never on periods (they appear inside author initials / journal abbrevs).
    """
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text).strip()
    # If inline numbered markers exist ([1], (1), 1.), split on them first.
    if re.search(r"\[\d{1,3}\]", text):
        text = re.sub(r"\s*\[(\d{1,3})\]\s*", r"\n[\1] ", text)
    elif re.search(r"(?<![A-Za-z0-9])\(\d{1,3}\)", text):
        text = re.sub(r"\s*\((\d{1,3})\)\s*", r"\n(\1) ", text)
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    # If short lines look like list items, treat them as-is; else join.
    entries = []
    marker_re = re.compile(r"^\s*(?:\[|\(|\d{1,3}[.、)）])\s*\d*")
    buf = ""
    for ln in lines:
        if marker_re.match(ln) or len(ln) > 200:
            if buf:
                entries.append(buf)
                buf = ""
            # strip leading marker
            ln = re.sub(r"^\s*(?:\[\d+\]|\(\d+\)|\d{1,3}[.、)）])\s*", "", ln)
            entries.append(ln)
        else:
            buf = (buf + " " + ln).strip() if buf else ln
    if buf:
        entries.append(buf)
    if len(entries) <= 1:
        # no reliable structure: split only on explicit semicolons between years
        entries = re.split(r"(?<=[.)])\s+(?=[A-Z][a-z]+\s*[A-Z]?\.)", text)
    out = []
    for p in entries:
        p = p.strip(" .;")
        p = re.sub(r"^(及专利|发表的代表性论文如下)[:：]?\s*", "", p)
        if len(p) < 20:
            continue
        year = None
        ym = re.search(r"(?:19|20)\d{2}", p)
        if ym:
            year = int(ym.group(0))
        out.append({"title": p[:260], "year": year})
    return out


def main():
    roster = json.loads((DATA / "roster_coarse.json").read_text(encoding="utf-8"))
    profs = roster["professors"]
    total = len(profs)
    print(f"Enriching {total} records ...")
    done = 0
    for idx, rec in enumerate(profs):
        kind = rec.pop("_detail_kind", "none")
        arg = rec.pop("_detail_arg", {}) or {}
        url = rec.get("profile_url", "")
        if kind == "iphy":
            t = arg.get("t")
            pid = arg.get("id")
            if t and pid:
                t2 = fetch(f"https://in.iphy.ac.cn/list_json.php?t={t}&id={pid}")
                enrich_iphy(rec, t2)
        elif kind == "sourcedb":
            u = arg.get("url") or url
            if u:
                enrich_sourcedb(rec, fetch(u))
        elif kind == "ucas":
            u = arg.get("url") or url
            if u:
                enrich_ucas(rec, fetch(u))
        # confidence
        if rec.get("_enriched"):
            rec["confidence"] = "fine"
            rec["verified"] = True
        rec.pop("_enriched", None)
        # clean empty fields
        for f in ("research_directions", "focus_areas", "publications"):
            if f in rec and not rec[f]:
                rec.pop(f, None)
        done += 1
        if done % 100 == 0:
            print(f"  {done}/{total} ...")

    (DATA / "faculty.json").write_text(
        json.dumps({
            "generated_at": "2026-10-01T00:00:00Z",
            "query": {
                "schools": sorted({p["school"] for p in profs}),
                "departments": [],
                "topics": ["物理学 / Physics"],
            },
            "professors": profs,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8")
    fine = sum(1 for p in profs if p.get("confidence") == "fine")
    print(f"\nDone: {fine} fine, {total - fine} coarse -> data/faculty.json")


if __name__ == "__main__":
    main()
