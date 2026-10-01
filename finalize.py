#!/usr/bin/env python3
"""Add subject field if missing and ensure consistent optional fields."""
import json
from pathlib import Path

p = Path("data/faculty.json")
d = json.loads(p.read_text(encoding="utf-8"))

subject_by_school = {
    "中国科学院物理研究所": "凝聚态物理 / 物理学",
    "中国科学院高能物理研究所": "粒子物理与原子核物理 / 高能物理",
    "中国科学院理论物理研究所": "理论物理",
    "中国科学院近代物理研究所": "核物理 / 加速器物理",
    "中国科学院上海应用物理研究所": "核技术应用 / 同步辐射 / 物理",
    "中国科学院精密测量科学与技术创新研究院": "原子分子光物理 / 精密测量物理",
}
n = 0
for rec in d["professors"]:
    if not rec.get("subject"):
        rec["subject"] = subject_by_school.get(rec["school"], "物理学")
        n += 1
    rec.setdefault("focus_areas", [])
    if rec.get("focus_areas") == []:
        rec.pop("focus_areas")

p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"set subject on {n} records; total {len(d['professors'])}")
