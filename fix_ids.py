#!/usr/bin/env python3
"""Normalize record ids to ASCII slug form and de-duplicate."""
import hashlib
import json
import re
from pathlib import Path

p = Path("data/faculty.json")
d = json.loads(p.read_text(encoding="utf-8"))


def ascii_id(s):
    h = hashlib.md5(s.encode("utf-8")).hexdigest()[:8]
    base = re.sub(r"[^0-9a-z]+", "-", s.lower()).strip("-")
    return (base + "-" + h) if base else h


seen = set()
for rec in d["professors"]:
    old = rec["id"]
    new = ascii_id(old)
    while new in seen:
        new = new + "x"
    seen.add(new)
    rec["id"] = new

p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
bad = [r["id"] for r in d["professors"] if not re.match(r"^[a-z0-9][a-z0-9-]*$", r["id"])]
print("non-slug ids remaining:", len(bad))
print("total:", len(d["professors"]))
