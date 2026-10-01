#!/usr/bin/env python3
"""Clean department field: replace APM codes with Chinese names,
strip leftover English/code chars, drop empties.
"""
import json
import re
from pathlib import Path

DIV = {
    "yzfzgwlyjb": "原子分子光物理研究部",
    "yzplbzyjb": "原子频率标准研究部",
    "fzplbzyjb": "原子频率标准研究部",
    "jmclwlyjb": "精密测量物理研究部",
    "jmcqwlyjb": "精密测量物理研究部",
    "jmdqwlyjb": "精密地球物理研究部",
    "ddclyjb": "大地测量研究部",
    "ddclywgcyjz": "大地测量野外观测研究站",
    "cgzyxyjb": "磁共振影像研究部",
    "clhxcgzyjb": "磁力化学磁共振研究部",
    "clydhyjb": "磁性与半导体研究部",
    "hjyzhyjb": "核磁共振研究部",
    "swchzbpyjb": "生物磁共振波谱研究部",
    "swcgzbpyjb": "生物磁共振波谱研究部",
    "AIqyjcyjzx": "AI+前沿交叉研究中心",
    "cgzjszx": "磁共振技术中心",
    "cgzzx": "磁共振中心",
    "jcygdjszx": "交叉研究关键技术研究组",
}


def clean_dep(dep):
    if not dep:
        return ""
    parts = [p.strip() for p in re.split(r"[/·]", dep) if p.strip()]
    out = []
    for p in parts:
        # APM code form: (zgj|fgj)_<divcode>
        m = re.match(r"^(?:zgj|fgj)_(.+)$", p)
        if m:
            code = m.group(1)
            name = DIV.get(code, "")
            if name:
                out.append(name)
            continue
        out.append(p)
    # dedupe preserving order
    seen, res = set(), []
    for x in out:
        if x not in seen:
            seen.add(x)
            res.append(x)
    return " / ".join(res)


p = Path("data/faculty.json")
d = json.loads(p.read_text(encoding="utf-8"))
nchanged = 0
for rec in d["professors"]:
    old = rec.get("department", "")
    new = clean_dep(old)
    if new != old:
        nchanged += 1
    if new:
        rec["department"] = new
    else:
        rec.pop("department", None)

p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

# report
from collections import Counter
empties = sum(1 for r in d["professors"] if not r.get("department"))
print(f"changed {nchanged}; empty departments: {empties}/{len(d['professors'])}")
for s in sorted({r["school"] for r in d["professors"]}):
    deps = Counter(r.get("department", "") for r in d["professors"] if r["school"] == s)
    print(f"\n=== {s} ===")
    for dep, c in deps.most_common(20):
        print(f"  {c:4d}  {dep or '(空)'}")
