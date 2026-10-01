#!/usr/bin/env python3
"""Ensure EVERY record has a `summary`.

Strategy (no fabrication):
1. Re-read the cached profile detail with a broader extractor; if real bio text
   exists ( 简历 / 简介 / 个人简介 / 教育背景+工作经历 ) use it.
2. Otherwise compose a factual one-line summary from verified fields
   (title / department / school / research_directions / subject).
For SINAP records (name + roster title only) compose from name + school + title.
"""
import html as H
import json
import re
from pathlib import Path

DATA = Path("data")
DETAIL = DATA / "raw" / "detail"


def cache_key(url):
    return re.sub(r"[^0-9A-Za-z]", "_", url)[-140:]


def strip_tags(h):
    h = re.sub(r"(?is)<script.*?</script>", " ", h)
    h = re.sub(r"(?is)<style.*?</style>", " ", h)
    h = re.sub(r"(?s)<br\s*/?>", "\n", h)
    h = re.sub(r"(?s)</p>", "\n", h)
    h = re.sub(r"(?s)<[^>]+>", " ", h)
    return H.unescape(h)


def clean(s):
    s = re.sub(r"\s+", " ", s).strip(" 。.;；,，")
    return s


CONTACT_RE = re.compile(r"^[\s0-9\-()（）:/]+$")
EMAIL_ONLY = re.compile(r"^(?:Email|电子邮件|邮箱)?\s*[:：]?\s*[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+")
CONTACT_PREFIX = re.compile(
    r"^(?:(?:电话|传真|电子邮件|邮箱|通讯地址|地址|邮编|Email|传真号|联系方式|其他联系方式)"
    r"\s*[:：]?\s*[^；;]*?[；;]?\s*)+")

NAV_KW = ["院领导", "现任领导", "历任领导", "历史沿革", "学术委员会", "学位委员会",
          "组织机构", "支撑平台", "友情链接", "版权所有", "违法违纪", "备案序号",
          "当前的位置", "您当前的位置", "人才队伍", "中国科学院青促会"]


def looks_like_contact(s):
    t = s.strip()
    if not t:
        return True
    if t.startswith(("其他联系方式", "联系方式", "通讯地址", "其他联系")):
        return True
    if len(t) < 25 and (EMAIL_ONLY.match(t) or CONTACT_RE.match(t)):
        return True
    # no CJK content and short -> junk
    if len(t) < 25 and not re.search(r"[\u4e00-\u9fff]", t):
        return True
    return False


def looks_like_nav(s):
    head = s[:80]
    return sum(1 for k in NAV_KW if k in head) >= 2


def looks_like_stub(s, name=""):
    t = re.sub(r"^(简介|简历|个人简介)\s*[:：]?\s*", "", s).strip()
    if len(t) <= max(10, len(name) + 4):
        return True
    # "Name / English name" only
    if len(t.split()) <= 2 and len(t) < 20:
        return True
    return False


def strip_contact_prefix(s):
    prev = None
    while prev != s:
        prev = s
        s = CONTACT_PREFIX.sub("", s).strip(" 。.;；,，")
    # drop a leading digit-heavy phone/fax blob
    s = re.sub(r"^(?:[0-9\-()（）\s]{6,})+(?:传真[:：][^；;]*)?[；;]?\s*", "", s).strip(" 。.;；,，")
    return s


END = ["代表论著", "承担科研项目", "社会任职", "获奖", "专利", "专利申请", "Email", "电子邮件",
       "通讯地址", "地址", "学历", "电话", "邮编", "研究方向", "研究领域", "招生方向",
       "教授课程", "指导学生", "工作经历", "教育背景", "学术兼职", "个人简介", "简历", "简介"]


def extract_bio(flat, name=""):
    """Return the best available biography string from a flattened profile."""
    # prefer explicit bio headings
    for start in ("个人简介", "简历介绍", "简介", "简历"):
        i = flat.rfind(start)
        if i >= 0:
            rest = flat[i + len(start):]
            j = len(rest)
            for ek in END:
                k = rest.find(ek)
                if k >= 0:
                    j = min(j, k)
            seg = clean(rest[:j])
            seg = strip_contact_prefix(seg)
            if (len(seg) >= 40 and not looks_like_contact(seg) and not looks_like_nav(seg)
                    and not looks_like_stub(seg, name)):
                return seg
    # UCAS style: 教育背景 + 工作经历
    for start in ("教育背景", "工作经历"):
        i = flat.rfind(start)
        if i >= 0:
            rest = flat[i + len(start):]
            j = len(rest)
            for ek in ("教授课程", "指导学生", "招生方向", "研究领域", "个人简介", "论文", "科研"):
                k = rest.find(ek)
                if k >= 0:
                    j = min(j, k)
            seg = clean(rest[:j])
            seg = strip_contact_prefix(seg)
            if (len(seg) >= 40 and not looks_like_contact(seg) and not looks_like_nav(seg)
                    and not looks_like_stub(seg, name)):
                return seg
    return ""


def compose(rec):
    name = rec.get("name", "")
    school = rec.get("school", "")
    dep = rec.get("department", "")
    title = rec.get("title", "")
    dirs = [d for d in (rec.get("research_directions") or []) if d]
    parts = [f"{name}"]
    affil = school + (f"（{dep}）" if dep and dep not in school else "")
    if affil:
        parts.append(f"就职于{affil}")
    if title:
        parts.append(f"，{title}")
    s = "".join(parts) + "。"
    if dirs:
        s += "研究方向：" + "、".join(dirs[:6]) + "。"
    return s


def main():
    p = DATA / "faculty.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    P = d["professors"]
    n_recovered = 0
    n_composed = 0
    n_fixed = 0
    for rec in P:
        cur = rec.get("summary", "")
        # re-process records with no summary OR junk summary (email-only / contact / nav blob)
        clean_cur = strip_contact_prefix(cur)
        if (cur and not looks_like_contact(cur) and not looks_like_nav(cur)
                and not looks_like_stub(cur, rec.get("name", ""))
                and not EMAIL_ONLY.match(cur) and clean_cur == cur.strip(" 。.;；,，")):
            continue
        # 1) try cached profile
        url = rec.get("profile_url", "")
        bio = ""
        if url:
            f = DETAIL / (cache_key(url) + ".txt")
            if f.exists():
                bio = extract_bio(strip_tags(f.read_text(encoding="utf-8", errors="replace")),
                                  rec.get("name", ""))
        if bio:
            rec["summary"] = bio[:400]
            n_recovered += 1
        else:
            rec["summary"] = compose(rec)[:400]
            n_composed += 1
        if cur:
            n_fixed += 1
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"recovered from profiles: {n_recovered}; composed fallback: {n_composed}; "
          f"re-fixed junk: {n_fixed}")
    print("records still missing summary:", sum(1 for r in P if not r.get("summary")))


if __name__ == "__main__":
    main()
